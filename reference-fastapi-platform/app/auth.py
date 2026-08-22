"""OAuth2/JWT authentication and role-based authorization for Synth Now.

Production mode validates access tokens issued by an external OAuth2/OIDC provider. The API is a
resource server: it validates issuer, audience, signature, expiration, and required claims; it
does not implement password grants or mint user passwords. Development mode preserves the existing
X-User-Id test harness and must never be enabled in internet-facing deployments.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jwt import InvalidTokenError, PyJWKClient

AUTH_MODE = os.getenv("SYNTH_NOW_AUTH_MODE", "development").lower()
JWT_ISSUER = os.getenv("SYNTH_NOW_JWT_ISSUER")
JWT_AUDIENCE = os.getenv("SYNTH_NOW_JWT_AUDIENCE")
JWT_JWKS_URL = os.getenv("SYNTH_NOW_JWT_JWKS_URL")
JWT_PUBLIC_KEY = os.getenv("SYNTH_NOW_JWT_PUBLIC_KEY")
JWT_SHARED_SECRET = os.getenv("SYNTH_NOW_JWT_SHARED_SECRET")
JWT_ALGORITHMS = tuple(item.strip() for item in os.getenv("SYNTH_NOW_JWT_ALGORITHMS", "RS256").split(",") if item.strip())
ROLE_CLAIM = os.getenv("SYNTH_NOW_JWT_ROLE_CLAIM", "roles")
SCOPE_CLAIM = os.getenv("SYNTH_NOW_JWT_SCOPE_CLAIM", "scope")
OAUTH_AUTHORIZATION_URL = os.getenv("SYNTH_NOW_OAUTH_AUTHORIZATION_URL", "https://issuer.example/authorize")
OAUTH_TOKEN_URL = os.getenv("SYNTH_NOW_OAUTH_TOKEN_URL", "https://issuer.example/oauth/token")

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=OAUTH_AUTHORIZATION_URL,
    tokenUrl=OAUTH_TOKEN_URL,
    scopes={
        "profile:read": "Read the current Synth Now profile",
        "claims:read": "Read own and public evidence claims",
        "claims:write": "Submit evidence claims",
        "audio:query": "Create private audio-recognition queries",
        "presets:read": "Search public canonical preset data",
        "moderation:read": "Read moderation queues",
        "moderation:write": "Approve or reject moderation items",
        "sources:write": "Manage approved official sources",
        "jobs:lease": "Lease internal worker jobs",
        "jobs:write": "Write internal worker job results",
        "references:write": "Write approved reference assets",
        "vectors:write": "Write derived vector artifacts",
    },
    auto_error=False,
)

ROLE_SCOPE_MAP: dict[str, set[str]] = {
    "member": {"profile:read", "claims:write", "claims:read", "audio:query", "presets:read"},
    "reviewer": {"profile:read", "claims:write", "claims:read", "audio:query", "presets:read", "moderation:read"},
    "editor": {"profile:read", "claims:write", "claims:read", "audio:query", "presets:read", "moderation:read", "moderation:write", "sources:write"},
    "admin": {"*"},
    "worker": {"jobs:lease", "jobs:write", "references:write", "vectors:write"},
}


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    subject: str
    roles: frozenset[str]
    scopes: frozenset[str]
    email: str | None = None
    organization_id: str | None = None
    token_id: str | None = None
    expires_at_epoch: int = 0

    @property
    def primary_role(self) -> str:
        ordered = ("admin", "editor", "reviewer", "member", "worker")
        return next((role for role in ordered if role in self.roles), "member")


def is_development_auth() -> bool:
    return AUTH_MODE == "development"


def _unauthorized(message: str = "Invalid or missing access token") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    if not JWT_JWKS_URL:
        raise RuntimeError("SYNTH_NOW_JWT_JWKS_URL is required for JWKS token validation")
    return PyJWKClient(JWT_JWKS_URL, cache_keys=True, lifespan=300)


def _coerce_string_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {part for part in value.replace(",", " ").split() if part}
    if isinstance(value, list):
        return {str(part) for part in value if isinstance(part, (str, int))}
    return set()


def _decode_access_token(token: str) -> dict[str, Any]:
    if not JWT_ISSUER or not JWT_AUDIENCE:
        raise RuntimeError("SYNTH_NOW_JWT_ISSUER and SYNTH_NOW_JWT_AUDIENCE are required in oauth_jwt mode")
    options = {"require": ["exp", "iat", "sub", "iss", "aud"]}
    if JWT_JWKS_URL:
        signing_key = _jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(token, signing_key, algorithms=list(JWT_ALGORITHMS), audience=JWT_AUDIENCE, issuer=JWT_ISSUER, options=options)
    if JWT_PUBLIC_KEY:
        return jwt.decode(token, JWT_PUBLIC_KEY, algorithms=list(JWT_ALGORITHMS), audience=JWT_AUDIENCE, issuer=JWT_ISSUER, options=options)
    if JWT_SHARED_SECRET and set(JWT_ALGORITHMS).issubset({"HS256", "HS384", "HS512"}):
        return jwt.decode(token, JWT_SHARED_SECRET, algorithms=list(JWT_ALGORITHMS), audience=JWT_AUDIENCE, issuer=JWT_ISSUER, options=options)
    raise RuntimeError("Configure JWKS URL or public key; HS algorithms are test-only and require an explicit shared secret")


def principal_from_bearer_token(token: str) -> AuthenticatedPrincipal:
    try:
        claims = _decode_access_token(token)
    except InvalidTokenError as exc:
        raise _unauthorized("Access token validation failed") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication validation is not configured") from exc
    roles = _coerce_string_set(claims.get(ROLE_CLAIM))
    if not roles and claims.get("role"):
        roles = _coerce_string_set(claims["role"])
    normalized_roles = {role.lower().removeprefix("synthnow:") for role in roles}
    allowed_roles = set(ROLE_SCOPE_MAP)
    normalized_roles &= allowed_roles
    if not normalized_roles:
        normalized_roles = {"member"}
    token_scopes = _coerce_string_set(claims.get(SCOPE_CLAIM))
    inherited_scopes = set().union(*(ROLE_SCOPE_MAP[role] for role in normalized_roles))
    return AuthenticatedPrincipal(
        subject=str(claims["sub"]),
        roles=frozenset(normalized_roles),
        scopes=frozenset(token_scopes | inherited_scopes),
        email=claims.get("email"),
        organization_id=claims.get("org_id") or claims.get("organization_id"),
        token_id=claims.get("jti"),
        expires_at_epoch=int(claims["exp"]),
    )


def authorize(principal: AuthenticatedPrincipal, *, roles: set[str] | None = None, scopes: set[str] | None = None) -> None:
    if roles and not (principal.roles & roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The access token does not have a permitted role")
    if scopes and "*" not in principal.scopes and not scopes.issubset(principal.scopes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The access token does not have the required scope")
