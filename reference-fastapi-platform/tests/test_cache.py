import time

from app.cache import SynthNowCache


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}

    def _expired(self, key):
        return key in self.expirations and self.expirations[key] <= time.time()

    def get(self, key):
        if self._expired(key):
            self.values.pop(key, None)
            return None
        return self.values.get(key)

    def set(self, key, value, ex=None, nx=False):
        if nx and self.get(key) is not None:
            return False
        self.values[key] = value
        if ex is not None:
            self.expirations[key] = time.time() + ex
        return True

    def delete(self, key):
        self.values.pop(key, None)
        self.expirations.pop(key, None)
        return 1

    def incr(self, key):
        value = int(self.get(key) or 0) + 1
        self.values[key] = str(value)
        return value


def test_preset_detail_cache_aside_and_revision_invalidation():
    cache = SynthNowCache(client=FakeRedis())
    calls = []

    def loader():
        calls.append("loaded")
        return {"id": "preset-1", "canonical_name": "Warm Chorus Pad"}

    first = cache.get_or_load_preset_detail(preset_id="preset-1", reviewed_revision="review-1", loader=loader)
    second = cache.get_or_load_preset_detail(preset_id="preset-1", reviewed_revision="review-1", loader=loader)
    assert first.hit is False
    assert second.hit is True
    assert calls == ["loaded"]

    before = cache.catalog_revision()
    cache.invalidate_preset_after_commit("preset-1", prior_revision="review-1")
    assert cache.catalog_revision() == before + 1
    after = cache.get_json(cache.preset_detail_key("preset-1", "review-1"))
    assert after.hit is False


def test_session_state_is_bounded_and_revocable():
    cache = SynthNowCache(client=FakeRedis())
    cache.store_session(
        session_id="session-1",
        subject="oidc-user-1",
        roles=["member"],
        organization_id="org-1",
        expires_at_epoch=int(time.time()) + 300,
        token_id="token-1",
        local_user_id="local-user-1",
        email="user@example.com",
        display_name="User",
    )
    cached = cache.get_session("session-1")
    assert cached.hit is True
    assert cached.value["local_user_id"] == "local-user-1"
    cache.revoke_session("session-1")
    assert cache.get_session("session-1").hit is False
