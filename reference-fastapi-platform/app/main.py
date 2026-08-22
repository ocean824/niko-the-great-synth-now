"""Synth Now FastAPI reference backend.

This runnable backend uses SQLite and background tasks for local development. It implements the
core safety property of Synth Now: contributors can submit claims, moderators can review them
with evidence and auditable decisions, but audio features and source observations never become
published historical facts without human review.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Query, Security, UploadFile, WebSocket, WebSocketDisconnect, status
from prometheus_client import make_asgi_app
from starlette.requests import Request
from starlette.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audio_worker import process_audio_job
from app.auth import is_development_auth, oauth2_scheme, principal_from_bearer_token
from app.cache import cache
from app.db import (
    AudioAnalysisJob,
    Base,
    ClaimEvidence,
    ClaimReview,
    ClaimRevision,
    ClaimScope,
    Entity,
    ProductionClaim,
    SessionLocal,
    SourceConfig,
    SourceObservation,
    User,
    create_all,
    engine,
)
from app.ingestion_worker import IngestionPolicyError, ingest_source_url
from app.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS, route_label

UPLOAD_DIR = Path(os.getenv("SYNTH_NOW_UPLOAD_DIR", "./private_uploads"))
MAX_UPLOAD_BYTES = 25_000_000
METRICS_TOKEN = os.getenv("SYNTH_NOW_METRICS_TOKEN")
MODERATOR_ROLES = {"reviewer", "editor", "admin"}
EDITOR_ROLES = {"editor", "admin"}
VERIFIED_SOURCE_TYPES = {"official", "official_archive", "credits", "creator_confirmation", "producer_interview"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    create_all()
    yield


app = FastAPI(
    title="Synth Now Evidence API",
    version="0.3.0",
    description="Contributor, moderator, audio-analysis, approved-source ingestion, OAuth2/JWT RBAC, and observability backend.",
    lifespan=lifespan,
)
# Keep this endpoint cluster-internal with ingress/network policy. Do not expose it publicly.
app.mount("/metrics", make_asgi_app())


@app.middleware("http")
async def observe_http_metrics(request: Request, call_next):
    if request.url.path.startswith("/metrics") and not is_development_auth():
        expected = METRICS_TOKEN
        actual = request.headers.get("Authorization", "")
        valid = expected and hmac.compare_digest(actual, f"Bearer {expected}")
        if not valid:
            return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": "Metrics access is restricted"})
    started = time.perf_counter()
    response = await call_next(request)
    route = route_label(request.scope)
    labels = {"method": request.method, "route": route, "status_code": str(response.status_code)}
    HTTP_REQUESTS.labels(**labels).inc()
    HTTP_REQUEST_DURATION.labels(**labels).observe(time.perf_counter() - started)
    return response


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


Db = Annotated[Session, Depends(get_db)]


def current_user(
    db: Db,
    bearer_token: Annotated[str | None, Security(oauth2_scheme)] = None,
    x_user_id: Annotated[str | None, Header()] = None,
) -> User:
    """Returns a development user or an OAuth2/JWT-authenticated local user projection.

    In `oauth_jwt` mode, a bearer token is mandatory and the X-User-Id development header is
    ignored. Token subjects map deterministically to a local UUID so existing contribution and
    audit foreign keys remain stable while current token roles are re-evaluated on every request.
    """
    if is_development_auth():
        if not x_user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-User-Id is required in development auth mode")
        user = db.get(User, x_user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
        return user

    if not bearer_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer access token is required", headers={"WWW-Authenticate": "Bearer"})
    principal = principal_from_bearer_token(bearer_token)
    # JWT validation always happens before the cache is consulted. The session cache only avoids
    # repeated local-user lookups; it cannot extend token lifetime or grant a role absent in token.
    session_id = hashlib.sha256(f"{principal.subject}:{principal.token_id or principal.expires_at_epoch}".encode("utf-8")).hexdigest()[:48]
    cached = cache.get_session(session_id)
    if cached.value and cached.value.get("subject") == principal.subject and cached.value.get("local_user_id"):
        return User(
            id=str(cached.value["local_user_id"]),
            email=str(cached.value.get("email") or f"{cached.value['local_user_id']}@token.invalid")[:320],
            display_name=str(cached.value.get("display_name") or principal.subject)[:120],
            role=principal.primary_role,
        )

    user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"synthnow:oidc:{principal.subject}"))
    user = db.get(User, user_id)
    if user is None:
        email = principal.email or f"{user_id}@token.invalid"
        user = User(id=user_id, email=email[:320], display_name=(principal.email or principal.subject)[:120], role=principal.primary_role)
        db.add(user)
    else:
        # Token roles are the current authority; this prevents stale database role elevation.
        user.role = principal.primary_role
        if principal.email:
            user.email = principal.email[:320]
    db.commit()
    cache.store_session(
        session_id=session_id,
        subject=principal.subject,
        roles=list(principal.roles),
        organization_id=principal.organization_id,
        expires_at_epoch=principal.expires_at_epoch,
        token_id=principal.token_id,
        local_user_id=user.id,
        email=user.email,
        display_name=user.display_name,
    )
    return user


def require_role(user: User, allowed: set[str]) -> None:
    if user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action requires a moderator/editor role")


def require_entity(db: Session, entity_id: str, expected_types: set[str] | None = None) -> Entity:
    entity = db.get(Entity, entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown entity: {entity_id}")
    if expected_types and entity.entity_type not in expected_types:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Entity {entity_id} has incompatible type")
    return entity


def claim_snapshot(claim: ProductionClaim) -> dict:
    return {
        "target_entity_id": claim.target_entity_id,
        "target_text": claim.target_text,
        "claim_type": claim.claim_type,
        "role_label": claim.role_label,
        "evidence_status": claim.evidence_status,
        "review_state": claim.review_state,
        "evidence": [
            {
                "source_type": item.source_type,
                "source_url": item.source_url,
                "support_summary": item.support_summary,
                "source_quality": item.source_quality,
            }
            for item in claim.evidence
        ],
        "scopes": [
            {
                "scope_kind": item.scope_kind,
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
                "song_section": item.song_section,
            }
            for item in claim.scopes
        ],
    }


def serialize_claim(claim: ProductionClaim) -> dict:
    return {
        "id": claim.id,
        "recording_version_entity_id": claim.recording_version_entity_id,
        "target_entity_id": claim.target_entity_id,
        "target_text": claim.target_text,
        "claim_type": claim.claim_type,
        "role_label": claim.role_label,
        "evidence_status": claim.evidence_status,
        "review_state": claim.review_state,
        "submitted_by_user_id": claim.submitted_by_user_id,
        "published_at": claim.published_at.isoformat() if claim.published_at else None,
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
        "evidence": [
            {
                "id": item.id,
                "source_type": item.source_type,
                "source_url": item.source_url,
                "publisher_or_owner": item.publisher_or_owner,
                "published_on": item.published_on,
                "support_summary": item.support_summary,
                "source_location": item.source_location,
                "source_quality": item.source_quality,
            }
            for item in claim.evidence
        ],
        "scopes": [
            {
                "id": item.id,
                "scope_kind": item.scope_kind,
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
                "song_section": item.song_section,
                "scope_note": item.scope_note,
            }
            for item in claim.scopes
        ],
        "reviews": [
            {
                "id": item.id,
                "reviewer_user_id": item.reviewer_user_id,
                "decision": item.decision,
                "decision_note": item.decision_note,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in claim.reviews
        ],
    }


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=120)
    role: Literal["member", "reviewer", "editor", "admin"] = "member"


class EntityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: Literal["recording_version", "gear_product", "product_variant", "software_product", "software_version", "preset_bank", "preset", "artist", "person"]
    canonical_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,218}$")
    display_name: str = Field(min_length=1, max_length=300)


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: Literal["official", "official_archive", "credits", "creator_confirmation", "producer_interview", "community_source", "other"]
    source_url: HttpUrl
    publisher_or_owner: str | None = Field(default=None, max_length=300)
    published_on: str | None = Field(default=None, max_length=32)
    support_summary: str = Field(min_length=20, max_length=3000)
    source_location: str | None = Field(default=None, max_length=300)
    source_quality: int = Field(default=3, ge=1, le=5)


class ScopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope_kind: Literal["recording_version", "song_section", "session", "album", "tour", "studio_ownership", "general_context"]
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    song_section: str | None = Field(default=None, max_length=120)
    scope_note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_ms is not None and self.start_ms is not None and self.end_ms < self.start_ms:
            raise ValueError("end_ms must not be earlier than start_ms")
        if self.scope_kind == "song_section" and self.start_ms is None and not self.song_section:
            raise ValueError("song_section claims require a time range or named song section")
        return self


class ClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recording_version_entity_id: str
    claim_type: Literal["instrument_use", "gear_use", "software_use", "preset_use", "sample_use", "personnel_credit", "production_technique", "mix_technique", "studio_context"]
    target_entity_id: str | None = None
    target_text: str | None = Field(default=None, max_length=300)
    role_label: str | None = Field(default=None, max_length=160)
    scopes: list[ScopeInput] = Field(min_length=1, max_length=8)
    evidence: list[EvidenceInput] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def require_target(self):
        if not self.target_entity_id and not self.target_text:
            raise ValueError("Provide a canonical target entity or a source-quoted unresolved target")
        return self


class ReviewDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["needs_changes", "reject", "publish_community", "publish_verified"]
    decision_note: str | None = Field(default=None, max_length=2000)


class SourceConfigCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_name: str = Field(min_length=1, max_length=300)
    verified_domain: str = Field(pattern=r"^[a-z0-9.-]+$")
    base_url: HttpUrl
    allowed_path_prefixes: list[str] = Field(min_length=1, max_length=50)
    min_interval_seconds: int = Field(default=10, ge=5, le=86_400)
    enabled: bool = False
    user_agent: str = Field(default="SynthNowSourceBot/0.1 (+https://synthnow.example/source-policy)", min_length=8, max_length=300)
    terms_reviewed_at: str | None = Field(default=None, max_length=32)
    review_owner_user_id: str | None = None


class SourceFetchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: HttpUrl


class SourceReviewDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    claim_id: str | None = None
    support_summary: str | None = Field(default=None, max_length=3000)
    source_quality: int = Field(default=4, ge=1, le=5)

    @model_validator(mode="after")
    def require_attachment_details(self):
        if self.decision == "approve" and self.claim_id and not self.support_summary:
            raise ValueError("support_summary is required when attaching an approved observation to a claim")
        return self


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feedback_type: Literal["agree", "disagree", "correction", "not_sure"]
    note: str | None = Field(default=None, max_length=1000)
    consent_for_model_evaluation: bool = False


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "synth-now-evidence-api", "version": app.version}


@app.post("/v1/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Db) -> dict:
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    user = User(id=new_id(), **payload.model_dump())
    db.add(user)
    db.commit()
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role}


@app.post("/v1/entities", status_code=status.HTTP_201_CREATED)
def create_entity(payload: EntityCreate, db: Db, user: User = Depends(current_user)) -> dict:
    require_role(user, EDITOR_ROLES)
    if db.scalar(select(Entity).where(Entity.entity_type == payload.entity_type, Entity.canonical_slug == payload.canonical_slug)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Entity slug already exists for this type")
    entity = Entity(
        id=new_id(),
        entity_type=payload.entity_type,
        canonical_slug=payload.canonical_slug,
        display_name=payload.display_name,
        normalized_name=payload.display_name.casefold(),
    )
    db.add(entity)
    db.commit()
    return {"id": entity.id, "entity_type": entity.entity_type, "display_name": entity.display_name}


@app.post("/v1/claims", status_code=status.HTTP_201_CREATED)
def submit_claim(payload: ClaimCreate, db: Db, user: User = Depends(current_user)) -> dict:
    require_entity(db, payload.recording_version_entity_id, {"recording_version"})
    if payload.target_entity_id:
        require_entity(db, payload.target_entity_id)
    claim = ProductionClaim(
        id=new_id(),
        recording_version_entity_id=payload.recording_version_entity_id,
        target_entity_id=payload.target_entity_id,
        target_text=payload.target_text,
        claim_type=payload.claim_type,
        role_label=payload.role_label,
        evidence_status="unverified_lead",
        review_state="submitted",
        submitted_by_user_id=user.id,
    )
    db.add(claim)
    for item in payload.scopes:
        db.add(ClaimScope(id=new_id(), claim=claim, **item.model_dump()))
    for item in payload.evidence:
        db.add(ClaimEvidence(id=new_id(), claim=claim, source_url=str(item.source_url), **item.model_dump(exclude={"source_url"})))
    db.flush()
    db.add(ClaimRevision(id=new_id(), claim=claim, changed_by_user_id=user.id, change_reason="Contributor submitted a new claim", snapshot=claim_snapshot(claim)))
    db.commit()
    db.refresh(claim)
    return serialize_claim(claim)


@app.get("/v1/claims/{claim_id}")
def get_claim(claim_id: str, db: Db, _: User = Depends(current_user)) -> dict:
    claim = db.get(ProductionClaim, claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return serialize_claim(claim)


@app.get("/v1/moderation/claims")
def list_claim_queue(
    db: Db,
    user: User = Depends(current_user),
    review_state: str = Query(default="submitted"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    require_role(user, MODERATOR_ROLES)
    claims = db.scalars(select(ProductionClaim).where(ProductionClaim.review_state == review_state).order_by(ProductionClaim.created_at.asc()).limit(limit)).all()
    return {"items": [serialize_claim(item) for item in claims], "count": len(claims)}


@app.post("/v1/moderation/claims/{claim_id}/decisions")
def review_claim(claim_id: str, payload: ReviewDecisionInput, db: Db, user: User = Depends(current_user)) -> dict:
    claim = db.get(ProductionClaim, claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    if claim.submitted_by_user_id == user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Moderators cannot review their own claims")
    if payload.decision == "publish_verified":
        require_role(user, EDITOR_ROLES)
        qualifying = [item for item in claim.evidence if item.source_type in VERIFIED_SOURCE_TYPES and item.source_quality >= 4]
        if not qualifying:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Verified publication needs at least one high-quality primary/official/credit source")
        claim.review_state = "published"
        claim.evidence_status = "verified"
        claim.published_at = utc_now()
    elif payload.decision == "publish_community":
        require_role(user, MODERATOR_ROLES)
        distinct_publishers = {urlparse(item.source_url).hostname for item in claim.evidence if urlparse(item.source_url).hostname}
        if len(distinct_publishers) < 2:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Community publication needs evidence from two independent publisher domains")
        claim.review_state = "published"
        claim.evidence_status = "community_corroborated"
        claim.published_at = utc_now()
    elif payload.decision == "needs_changes":
        require_role(user, MODERATOR_ROLES)
        claim.review_state = "needs_changes"
    else:
        require_role(user, MODERATOR_ROLES)
        claim.review_state = "rejected"
    db.add(ClaimReview(id=new_id(), claim=claim, reviewer_user_id=user.id, decision=payload.decision, decision_note=payload.decision_note))
    db.flush()
    db.add(ClaimRevision(id=new_id(), claim=claim, changed_by_user_id=user.id, change_reason=f"Moderator decision: {payload.decision}", snapshot=claim_snapshot(claim)))
    if claim.review_state == "published":
        contributor = db.get(User, claim.submitted_by_user_id)
        if contributor:
            contributor.reputation += 2 if claim.evidence_status == "verified" else 1
    db.commit()
    db.refresh(claim)
    return serialize_claim(claim)


@app.post("/v1/moderation/source-configs", status_code=status.HTTP_201_CREATED)
def create_source_config(payload: SourceConfigCreate, db: Db, user: User = Depends(current_user)) -> dict:
    require_role(user, EDITOR_ROLES)
    if payload.review_owner_user_id:
        if not db.get(User, payload.review_owner_user_id):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Review owner user not found")
    config = SourceConfig(
        id=new_id(),
        owner_name=payload.owner_name,
        verified_domain=payload.verified_domain.lower(),
        base_url=str(payload.base_url),
        allowed_path_prefixes=payload.allowed_path_prefixes,
        mode="robots_jsonld",
        min_interval_seconds=payload.min_interval_seconds,
        enabled=payload.enabled,
        user_agent=payload.user_agent,
        terms_reviewed_at=payload.terms_reviewed_at,
        review_owner_user_id=payload.review_owner_user_id or user.id,
    )
    db.add(config)
    db.commit()
    return {"id": config.id, "verified_domain": config.verified_domain, "enabled": config.enabled, "mode": config.mode}


@app.get("/v1/moderation/source-configs")
def list_source_configs(db: Db, user: User = Depends(current_user)) -> dict:
    require_role(user, EDITOR_ROLES)
    rows = db.scalars(select(SourceConfig).order_by(SourceConfig.created_at.desc())).all()
    return {"items": [{"id": row.id, "owner_name": row.owner_name, "verified_domain": row.verified_domain, "allowed_path_prefixes": row.allowed_path_prefixes, "enabled": row.enabled} for row in rows]}


@app.post("/v1/moderation/source-configs/{source_config_id}/fetch", status_code=status.HTTP_202_ACCEPTED)
def request_source_fetch(source_config_id: str, payload: SourceFetchRequest, background_tasks: BackgroundTasks, db: Db, user: User = Depends(current_user)) -> dict:
    require_role(user, EDITOR_ROLES)
    if not db.get(SourceConfig, source_config_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source configuration not found")
    # The worker applies default-deny policy and records only a review candidate.
    background_tasks.add_task(ingest_source_url, source_config_id, str(payload.url))
    return {"accepted": True, "source_config_id": source_config_id, "url": str(payload.url), "notice": "A pending source observation may be created; no public claim is changed."}


@app.get("/v1/moderation/source-observations")
def list_source_observations(db: Db, user: User = Depends(current_user), review_state: str = Query(default="submitted")) -> dict:
    require_role(user, MODERATOR_ROLES)
    observations = db.scalars(select(SourceObservation).where(SourceObservation.review_state == review_state).order_by(SourceObservation.created_at.asc())).all()
    return {"items": [{"id": row.id, "source_config_id": row.source_config_id, "requested_url": row.requested_url, "content_sha256": row.content_sha256, "extracted": row.extracted_json, "review_state": row.review_state} for row in observations]}


@app.post("/v1/moderation/source-observations/{observation_id}/decisions")
def review_source_observation(observation_id: str, payload: SourceReviewDecisionInput, db: Db, user: User = Depends(current_user)) -> dict:
    require_role(user, EDITOR_ROLES)
    observation = db.get(SourceObservation, observation_id)
    if not observation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source observation not found")
    if payload.decision == "reject":
        observation.review_state = "rejected"
        db.commit()
        return {"id": observation.id, "review_state": observation.review_state}
    observation.review_state = "approved"
    attached_evidence_id = None
    if payload.claim_id:
        claim = db.get(ProductionClaim, payload.claim_id)
        if not claim:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Claim not found")
        evidence = ClaimEvidence(
            id=new_id(),
            claim=claim,
            source_type="official",
            source_url=observation.requested_url,
            publisher_or_owner="Approved official source",
            support_summary=payload.support_summary or "Approved source observation",
            source_location="Automated structured-data observation",
            source_quality=payload.source_quality,
        )
        db.add(evidence)
        attached_evidence_id = evidence.id
    db.commit()
    return {"id": observation.id, "review_state": observation.review_state, "attached_evidence_id": attached_evidence_id, "notice": "Approval can add evidence but cannot publish the linked claim automatically."}


@app.post("/v1/audio/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_audio_job(
    background_tasks: BackgroundTasks,
    db: Db,
    user: User = Depends(current_user),
    consent_version: str = Form(..., min_length=3, max_length=80),
    file: UploadFile = File(...),
) -> dict:
    if not (file.content_type or "").startswith("audio/"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only audio uploads are accepted")
    job_id = new_id()
    suffix = Path(file.filename or "upload.bin").suffix or ".bin"
    safe_path = UPLOAD_DIR / f"{job_id}{suffix.lower()}"
    digest = hashlib.sha256()
    total = 0
    with safe_path.open("wb") as out:
        while chunk := await file.read(65_536):
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                out.close()
                safe_path.unlink(missing_ok=True)
                raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Audio upload exceeds development limit")
            digest.update(chunk)
            out.write(chunk)
    job = AudioAnalysisJob(
        id=job_id,
        owner_user_id=user.id,
        filename=file.filename or "upload",
        storage_uri=str(safe_path),
        content_sha256=digest.hexdigest(),
        consent_version=consent_version,
        status="queued",
        retention_expires_at=utc_now() + timedelta(hours=1),
    )
    db.add(job)
    db.commit()
    background_tasks.add_task(process_audio_job, job_id)
    return {"id": job.id, "status": job.status, "retention_expires_at": job.retention_expires_at.isoformat(), "notice": "Analysis generates private feature observations only; it does not create gear/preset claims."}


@app.get("/v1/audio/jobs/{job_id}")
def get_audio_job(job_id: str, db: Db, user: User = Depends(current_user)) -> dict:
    job = db.get(AudioAnalysisJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio job not found")
    if job.owner_user_id != user.id and user.role not in MODERATOR_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Audio job does not belong to the current user")
    return {"id": job.id, "status": job.status, "filename": job.filename, "result": job.result_json, "retention_expires_at": job.retention_expires_at.isoformat(), "error": job.error_message}


@app.post("/v1/audio/jobs/{job_id}/feedback", status_code=status.HTTP_201_CREATED)
def submit_audio_feedback(job_id: str, payload: FeedbackInput, db: Db, user: User = Depends(current_user)) -> dict:
    job = db.get(AudioAnalysisJob, job_id)
    if not job or job.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio job not found")
    # Production schema persists feedback to a dedicated table. This reference returns an auditable payload contract.
    return {"accepted": True, "job_id": job_id, "submitted_by_user_id": user.id, "feedback_type": payload.feedback_type, "consent_for_model_evaluation": payload.consent_for_model_evaluation}


@app.websocket("/ws/v1/audio/jobs/{job_id}")
async def audio_job_status_stream(websocket: WebSocket, job_id: str, user_id: str = Query(...)) -> None:
    """Development status stream; production should use signed short-lived socket tokens and an event broker."""
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        job = db.get(AudioAnalysisJob, job_id)
        if not user or not job or (job.owner_user_id != user.id and user.role not in MODERATOR_ROLES):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        await websocket.accept()
        last_status = None
        while True:
            db.expire_all()
            job = db.get(AudioAnalysisJob, job_id)
            if not job:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            if job.status != last_status:
                await websocket.send_json({"type": "audio.job.status", "job_id": job.id, "status": job.status, "result": job.result_json if job.status == "completed" else None})
                last_status = job.status
            if job.status in {"completed", "failed", "cancelled", "expired"}:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                return
            await asyncio.sleep(0.25)
    except WebSocketDisconnect:
        return
    finally:
        db.close()
