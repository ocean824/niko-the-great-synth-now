"""Low-cardinality Prometheus metrics for Synth Now.

Never use user IDs, query IDs, preset IDs, source URLs, raw model input, or error text as metric labels.
Metrics explain system behavior; logs/traces carry request-correlated diagnostic detail under privacy rules.
"""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "synthnow_http_requests_total",
    "Completed HTTP requests",
    labelnames=("method", "route", "status_code"),
)
HTTP_REQUEST_DURATION = Histogram(
    "synthnow_http_request_duration_seconds",
    "FastAPI request duration",
    labelnames=("method", "route", "status_code"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
VECTOR_SEARCH_DURATION = Histogram(
    "synthnow_vector_search_duration_seconds",
    "Vector search duration from query vector to candidate shortlist",
    labelnames=("model_code", "reference_role", "outcome"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
VECTOR_SEARCH_CANDIDATES = Histogram(
    "synthnow_vector_search_candidates",
    "Candidate count returned before reranking",
    labelnames=("model_code", "reference_role"),
    buckets=(0, 1, 5, 10, 25, 50, 100, 250, 500),
)
AUDIO_JOBS_TOTAL = Counter(
    "synthnow_audio_jobs_total",
    "Audio analysis job state transitions",
    labelnames=("state",),
)
AUDIO_JOB_PROCESSING_DURATION = Histogram(
    "synthnow_audio_job_processing_seconds",
    "Audio analysis job processing duration",
    labelnames=("outcome",),
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0),
)
AUDIO_JOB_QUEUE_DEPTH = Gauge(
    "synthnow_audio_job_queue_depth",
    "Current queued audio analysis jobs",
)
INGESTION_FETCHES_TOTAL = Counter(
    "synthnow_ingestion_fetches_total",
    "Official source ingestion fetch state transitions",
    labelnames=("state",),
)
CACHE_REQUESTS = Counter(
    "synthnow_cache_requests_total",
    "Redis cache operations by bounded key family and outcome",
    labelnames=("key_family", "outcome"),
)
CACHE_OPERATION_DURATION = Histogram(
    "synthnow_cache_operation_duration_seconds",
    "Redis cache operation latency",
    labelnames=("operation", "outcome"),
    buckets=(0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5),
)


@contextmanager
def observe_vector_search(model_code: str, reference_role: str):
    """Observes one bounded vector-search operation.

    `model_code` and `reference_role` must come from a small configured registry, never a user
    request. Call `result.set_candidate_count(n)` before leaving the context.
    """
    started = perf_counter()
    outcome = "success"
    candidate_count = 0

    class Result:
        def set_candidate_count(self, value: int) -> None:
            nonlocal candidate_count
            candidate_count = max(0, value)

    result = Result()
    try:
        yield result
    except Exception:
        outcome = "error"
        raise
    finally:
        VECTOR_SEARCH_DURATION.labels(model_code=model_code, reference_role=reference_role, outcome=outcome).observe(perf_counter() - started)
        VECTOR_SEARCH_CANDIDATES.labels(model_code=model_code, reference_role=reference_role).observe(candidate_count)


def route_label(scope: dict) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path or "unmatched"
