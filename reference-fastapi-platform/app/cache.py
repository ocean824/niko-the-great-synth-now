"""Redis cache-aside and short-lived session-state primitives for Synth Now.

PostgreSQL remains the authority for canonical presets, evidence, moderation, and audit records.
Redis is an optional acceleration layer: cache failure must not change canonical data, authorization,
or publication behavior. The adapter stores only reviewed public read models and minimal session state;
it never stores raw audio, raw vectors, fingerprints, artifacts, bearer tokens, or source credentials.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from redis import Redis
from redis.exceptions import RedisError

from app.metrics import CACHE_OPERATION_DURATION, CACHE_REQUESTS

log = logging.getLogger("synthnow.cache")

REDIS_URL = os.getenv("SYNTH_NOW_REDIS_URL")
CACHE_ENABLED = os.getenv("SYNTH_NOW_CACHE_ENABLED", "true").lower() == "true"
CACHE_KEY_PREFIX = os.getenv("SYNTH_NOW_CACHE_KEY_PREFIX", "synthnow")
PRESET_DETAIL_TTL_SECONDS = int(os.getenv("SYNTH_NOW_PRESET_DETAIL_CACHE_TTL_SECONDS", "300"))
PRESET_SEARCH_TTL_SECONDS = int(os.getenv("SYNTH_NOW_PRESET_SEARCH_CACHE_TTL_SECONDS", "60"))
SESSION_TTL_SECONDS = int(os.getenv("SYNTH_NOW_SESSION_CACHE_TTL_SECONDS", "900"))
LOCK_TTL_SECONDS = int(os.getenv("SYNTH_NOW_CACHE_LOCK_TTL_SECONDS", "10"))

T = TypeVar("T")


@dataclass(frozen=True)
class CacheResult:
    value: dict[str, Any] | None
    hit: bool


class SynthNowCache:
    """Small synchronous Redis adapter suitable for FastAPI sync routes and worker processes."""

    def __init__(self, client: Redis | None = None) -> None:
        self.client = client
        if self.client is None and CACHE_ENABLED and REDIS_URL:
            self.client = Redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True, socket_connect_timeout=0.25, socket_timeout=0.25, health_check_interval=30)

    @property
    def available(self) -> bool:
        return self.client is not None

    def _key(self, *parts: str) -> str:
        return ":".join((CACHE_KEY_PREFIX, "v1", *parts))

    @staticmethod
    def _stable_hash(value: Any) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:32]

    @staticmethod
    def _family(key: str) -> str:
        parts = key.split(":")
        return parts[2] if len(parts) > 2 else "other"

    def get_json(self, key: str) -> CacheResult:
        family = self._family(key)
        started = time.perf_counter()
        if not self.client:
            CACHE_REQUESTS.labels(key_family=family, outcome="unavailable").inc()
            CACHE_OPERATION_DURATION.labels(operation="get", outcome="unavailable").observe(time.perf_counter() - started)
            return CacheResult(value=None, hit=False)
        try:
            raw = self.client.get(key)
            outcome = "hit" if raw is not None else "miss"
            CACHE_REQUESTS.labels(key_family=family, outcome=outcome).inc()
            CACHE_OPERATION_DURATION.labels(operation="get", outcome=outcome).observe(time.perf_counter() - started)
            return CacheResult(value=json.loads(raw) if raw else None, hit=raw is not None)
        except (RedisError, ValueError, TypeError):
            CACHE_REQUESTS.labels(key_family=family, outcome="error").inc()
            CACHE_OPERATION_DURATION.labels(operation="get", outcome="error").observe(time.perf_counter() - started)
            log.warning("Redis cache read failed", extra={"cache_key_family": family})
            return CacheResult(value=None, hit=False)

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> bool:
        family = self._family(key)
        started = time.perf_counter()
        if not self.client:
            CACHE_OPERATION_DURATION.labels(operation="set", outcome="unavailable").observe(time.perf_counter() - started)
            return False
        try:
            self.client.set(key, json.dumps(value, separators=(",", ":"), ensure_ascii=False), ex=max(1, ttl_seconds))
            CACHE_OPERATION_DURATION.labels(operation="set", outcome="success").observe(time.perf_counter() - started)
            return True
        except (RedisError, TypeError, ValueError):
            CACHE_OPERATION_DURATION.labels(operation="set", outcome="error").observe(time.perf_counter() - started)
            log.warning("Redis cache write failed", extra={"cache_key_family": family})
            return False

    def delete(self, key: str) -> None:
        if not self.client:
            return
        try:
            self.client.delete(key)
        except RedisError:
            log.warning("Redis cache delete failed", extra={"cache_key_family": key.split(":")[2] if ":" in key else "unknown"})

    def increment_catalog_revision(self) -> int | None:
        """Bumps a global reviewed-catalog version after a committed canonical change.

        Search keys include this revision, so update invalidation does not require unsafe wildcard
        scans. Old keys expire normally by TTL.
        """
        if not self.client:
            return None
        try:
            key = self._key("catalog", "revision")
            return int(self.client.incr(key))
        except RedisError:
            log.warning("Redis catalog revision increment failed")
            return None

    def catalog_revision(self) -> int:
        if not self.client:
            return 0
        try:
            value = self.client.get(self._key("catalog", "revision"))
            return int(value or 0)
        except (RedisError, ValueError):
            return 0

    def preset_detail_key(self, preset_id: str, reviewed_revision: str) -> str:
        return self._key("preset", "detail", preset_id, reviewed_revision)

    def preset_search_key(self, *, public_scope: str, filters: dict[str, Any], catalog_revision: int | None = None) -> str:
        revision = self.catalog_revision() if catalog_revision is None else catalog_revision
        return self._key("preset", "search", public_scope, str(revision), self._stable_hash(filters))

    def get_or_load_preset_detail(self, *, preset_id: str, reviewed_revision: str, loader: Callable[[], dict[str, Any] | None]) -> CacheResult:
        key = self.preset_detail_key(preset_id, reviewed_revision)
        cached = self.get_json(key)
        if cached.hit:
            return cached
        value = loader()
        if value is not None:
            self.set_json(key, value, PRESET_DETAIL_TTL_SECONDS)
        return CacheResult(value=value, hit=False)

    def get_or_load_preset_search(self, *, public_scope: str, filters: dict[str, Any], loader: Callable[[], dict[str, Any]]) -> CacheResult:
        key = self.preset_search_key(public_scope=public_scope, filters=filters)
        cached = self.get_json(key)
        if cached.hit:
            return cached
        # A short, best-effort lock limits synchronized cold-miss bursts. Losing the lock never
        # blocks a user request; PostgreSQL remains the fallback authority.
        lock_key = f"{key}:lock"
        lock_token = secrets.token_urlsafe(16)
        lock_acquired = False
        if self.client:
            try:
                lock_acquired = bool(self.client.set(lock_key, lock_token, nx=True, ex=max(1, LOCK_TTL_SECONDS)))
            except RedisError:
                lock_acquired = False
        try:
            value = loader()
            self.set_json(key, value, PRESET_SEARCH_TTL_SECONDS)
            return CacheResult(value=value, hit=False)
        finally:
            if lock_acquired and self.client:
                try:
                    # Delete only the lock owned by this request; never remove a replacement lock.
                    if self.client.get(lock_key) == lock_token:
                        self.client.delete(lock_key)
                except RedisError:
                    pass

    def invalidate_preset_after_commit(self, preset_id: str, prior_revision: str | None = None) -> None:
        """Invalidates a known detail revision and version-bumps catalog searches after DB commit."""
        if prior_revision:
            self.delete(self.preset_detail_key(preset_id, prior_revision))
        self.increment_catalog_revision()

    def session_key(self, session_id: str) -> str:
        return self._key("session", session_id)

    def store_session(self, *, session_id: str, subject: str, roles: list[str], organization_id: str | None, expires_at_epoch: int, token_id: str | None, local_user_id: str, email: str, display_name: str) -> bool:
        remaining = min(SESSION_TTL_SECONDS, max(1, expires_at_epoch - int(time.time())))
        payload = {
            "subject": subject,
            "roles": sorted(set(roles)),
            "organization_id": organization_id,
            "token_id": token_id,
            "local_user_id": local_user_id,
            "email": email,
            "display_name": display_name,
            "expires_at": expires_at_epoch,
        }
        return self.set_json(self.session_key(session_id), payload, remaining)

    def get_session(self, session_id: str) -> CacheResult:
        result = self.get_json(self.session_key(session_id))
        if result.value and int(result.value.get("expires_at", 0)) <= int(time.time()):
            self.delete(self.session_key(session_id))
            return CacheResult(value=None, hit=False)
        return result

    def revoke_session(self, session_id: str) -> None:
        self.delete(self.session_key(session_id))


cache = SynthNowCache()
