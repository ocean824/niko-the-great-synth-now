from __future__ import annotations

import json
from pathlib import Path

import yaml
from redis.exceptions import RedisError

from app.cache import SynthNowCache

ROOT = Path(__file__).resolve().parents[1]


class FailingRedis:
    """Deterministic Redis transport failure for fallback tests."""

    def get(self, *_args, **_kwargs):
        raise RedisError("simulated redis transport outage")

    def set(self, *_args, **_kwargs):
        raise RedisError("simulated redis transport outage")

    def delete(self, *_args, **_kwargs):
        raise RedisError("simulated redis transport outage")

    def incr(self, *_args, **_kwargs):
        raise RedisError("simulated redis transport outage")


class MemoryRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def delete(self, key):
        self.values.pop(key, None)
        return 1

    def incr(self, key):
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value


def _matches(matchers: list[str], labels: dict[str, str]) -> bool:
    for matcher in matchers:
        key, expected = matcher.split("=", 1)
        if labels.get(key) != expected.strip('"'):
            return False
    return True


def _receiver_for(config: dict, labels: dict[str, str]) -> str:
    """Mirrors the first-match part of the checked Alertmanager route tree for contract tests."""
    for route in config["route"]["routes"]:
        if _matches(route.get("matchers", []), labels):
            return route["receiver"]
    return config["route"]["receiver"]


def _is_inhibited(config: dict, source: dict[str, str], target: dict[str, str]) -> bool:
    for rule in config["inhibit_rules"]:
        if not _matches(rule["source_matchers"], source) or not _matches(rule["target_matchers"], target):
            continue
        if all(source.get(label) == target.get(label) for label in rule.get("equal", [])):
            return True
    return False


def test_redis_outage_falls_back_under_repeated_preset_read_load():
    cache = SynthNowCache(client=FailingRedis())
    calls = 0

    def loader():
        nonlocal calls
        calls += 1
        return {"id": "preset-1", "canonical_name": "Warm Chorus Pad", "reviewed": True}

    # This is intentionally a burst: every cache operation fails, but every request still receives
    # the PostgreSQL-equivalent loader result and no invalid cached state is returned.
    results = [cache.get_or_load_preset_detail(preset_id="preset-1", reviewed_revision="r1", loader=loader) for _ in range(200)]
    assert calls == 200
    assert all(result.value and result.value["reviewed"] is True for result in results)
    assert all(result.hit is False for result in results)
    # Invalidation remains non-fatal when Redis is down because the database write already committed.
    cache.invalidate_preset_after_commit("preset-1", prior_revision="r1")


def test_catalog_revision_invalidates_search_without_wildcard_scan():
    cache = SynthNowCache(client=MemoryRedis())
    filters = {"plugin_id": "plugin-1", "query": "pad", "limit": 20}
    first_key = cache.preset_search_key(public_scope="public", filters=filters)
    cache.set_json(first_key, {"items": ["preset-1"]}, 60)
    assert cache.get_json(first_key).hit is True
    cache.invalidate_preset_after_commit("preset-1", prior_revision="r1")
    second_key = cache.preset_search_key(public_scope="public", filters=filters)
    assert first_key != second_key
    assert cache.get_json(second_key).hit is False


def test_alertmanager_routes_critical_and_warning_and_discards_synthetic_alerts():
    config_path = ROOT / "deploy" / "monitoring" / "alertmanager" / "alertmanager.yml"
    config = yaml.safe_load(config_path.read_text())
    assert _receiver_for(config, {"severity": "critical", "service": "vector-search"}) == "pagerduty-critical"
    assert _receiver_for(config, {"severity": "warning", "service": "audio-worker"}) == "pagerduty-warning"
    assert _receiver_for(config, {"severity": "critical", "service": "vector-search", "synthetic": "true"}) == "discard"


def test_alertmanager_inhibits_duplicate_warning_when_matching_critical_exists():
    config_path = ROOT / "deploy" / "monitoring" / "alertmanager" / "alertmanager.yml"
    config = yaml.safe_load(config_path.read_text())
    critical = {"severity": "critical", "service": "audio-worker", "environment": "production"}
    warning = {"severity": "warning", "service": "audio-worker", "environment": "production"}
    unrelated_warning = {"severity": "warning", "service": "vector-search", "environment": "production"}
    assert _is_inhibited(config, critical, warning) is True
    assert _is_inhibited(config, critical, unrelated_warning) is False


def test_alerting_dashboard_declares_cache_and_critical_signal_panels():
    dashboard_path = ROOT / "deploy" / "monitoring" / "grafana" / "dashboards" / "synth-now-cache-alerting.json"
    dashboard = json.loads(dashboard_path.read_text())
    titles = {panel["title"] for panel in dashboard["panels"]}
    assert "Preset/Session Cache Hit Ratio (5m)" in titles
    assert "Firing Critical Alerts" in titles
