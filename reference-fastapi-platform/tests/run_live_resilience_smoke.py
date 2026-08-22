"""Opt-in smoke test for a running local/staging Synth Now stack.

Run only against an approved non-production target:
  SYNTH_NOW_SMOKE_API_URL=http://localhost:8000 \
  SYNTH_NOW_SMOKE_ALERTMANAGER_URL=http://localhost:9093 \
  python tests/run_live_resilience_smoke.py

The Alertmanager payload carries synthetic=true, so the supplied route sends it to the discard
receiver. It must never page PagerDuty.
"""

from __future__ import annotations

import concurrent.futures
import os
import sys
import time
from datetime import UTC, datetime, timedelta

import requests

API_URL = os.getenv("SYNTH_NOW_SMOKE_API_URL", "http://localhost:8000").rstrip("/")
ALERTMANAGER_URL = os.getenv("SYNTH_NOW_SMOKE_ALERTMANAGER_URL", "http://localhost:9093").rstrip("/")
REQUESTS = int(os.getenv("SYNTH_NOW_SMOKE_REQUESTS", "50"))
CONCURRENCY = int(os.getenv("SYNTH_NOW_SMOKE_CONCURRENCY", "10"))


def health_request(_: int) -> int:
    return requests.get(f"{API_URL}/health", timeout=5).status_code


def main() -> None:
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        statuses = list(pool.map(health_request, range(REQUESTS)))
    failures = sum(status != 200 for status in statuses)
    elapsed = time.perf_counter() - started
    if failures:
        raise SystemExit(f"API smoke failed: {failures}/{REQUESTS} health requests were not HTTP 200")
    print(f"API concurrent health smoke passed: {REQUESTS} requests in {elapsed:.2f}s")

    now = datetime.now(UTC)
    alert = {
        "labels": {
            "alertname": "SynthNowSyntheticRoutingTest",
            "severity": "critical",
            "service": "vector-search",
            "environment": "smoke",
            "synthetic": "true",
        },
        "annotations": {
            "summary": "Synthetic routing smoke test",
            "description": "This event must be discarded by the synthetic Alertmanager route and must not notify PagerDuty.",
        },
        "startsAt": now.isoformat().replace("+00:00", "Z"),
        "endsAt": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
    }
    response = requests.post(f"{ALERTMANAGER_URL}/api/v2/alerts", json=[alert], timeout=5)
    response.raise_for_status()
    listed = requests.get(f"{ALERTMANAGER_URL}/api/v2/alerts", timeout=5)
    listed.raise_for_status()
    names = {item["labels"].get("alertname") for item in listed.json()}
    if "SynthNowSyntheticRoutingTest" not in names:
        raise SystemExit("Alertmanager accepted no visible synthetic test alert")
    print("Alertmanager synthetic routing smoke passed: PagerDuty-discard route accepted the test event")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"Live smoke target unavailable: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
