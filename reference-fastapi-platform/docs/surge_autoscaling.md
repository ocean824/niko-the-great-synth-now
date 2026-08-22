# Niko The Great - SYNTH NOW — Surge Autoscaling

## Scaling boundary

The API and audio-worker deployments are horizontally scalable. PostgreSQL/pgvector and Redis are **not** safe targets for a generic HPA: they are stateful capacity services whose availability, connection limits, replication, storage IOPS, failover, and cross-region behavior require provider or operator controls. Kubernetes HPA adjusts scalable workload replicas based on resource, custom, or external metrics; external metrics require a compatible metrics API adapter.[1]

> **Scaling rule:** Never allow an application HPA to create more API or worker connections than PostgreSQL, Redis, object storage, or the audio-processing quota can sustain. A surge policy that scales the app while exhausting the database is an outage amplifier, not capacity management.

## 1. Included HPA policy

The deployment manifest at `deploy/kubernetes/03-edge-and-scaling.yaml` contains separate `autoscaling/v2` policies for the API and worker fleet.

| Workload | Minimum → maximum | Primary signals | Scale-up behavior | Scale-down behavior | Why |
|---|---:|---|---|---|---|
| API | 3 → 24 | CPU 65%, memory 75%, external requests/sec target of 20 per pod | Up to four pods or 100% per minute, whichever is larger | 25% per minute after a 5-minute stabilization window | Handles sudden query traffic while retaining enough capacity for connection reuse, OAuth, and cache warm-up. |
| Audio worker | 1 → 32 | External shared queue depth target of 10 jobs per worker, CPU 70% | Up to eight pods or 100% per minute | 20% per minute after a 10-minute stabilization window | Drains an ingestion/analysis surge without immediately terminating workers that have just reduced a backlog. |

HPA supports multiple metrics and configurable scaling policies/stabilization windows.[1] The included policy intentionally uses short scale-up and longer scale-down behavior to reduce flapping. Initial thresholds are **load-test hypotheses**, not permanent service-level objectives.

The audio queue metric is exposed by the worker on an internal metrics port and scraped through `synth-now-worker-metrics`. `deploy/kubernetes/04-monitoring-operator.yaml` normalizes its `service` label to `audio-worker`, while `deploy/kubernetes/prometheus-adapter-rules.yaml` maps the Prometheus series into the external metric names used by the HPA. Before enabling the HPA, inspect actual Prometheus labels and adapt the template to the installed metrics adapter.

## 2. Scaling choices

| Approach | Tradeoffs | Cost | Setup complexity |
|---|---|---:|---|
| **Included HPA plus Prometheus Adapter** | Keeps standard Kubernetes HPA semantics and reuses existing Prometheus metrics. Requires running and maintaining a metrics adapter and checking metric label/resource mappings. | Uses existing cluster/monitoring capacity. | Moderate. |
| **Event-driven queue scaler** | Can react directly to queue depth and scale workers closer to event arrival patterns. Adds another controller and requires careful drain/retry coordination. | Depends on controller and cluster footprint. | Moderate to high. |
| **Fixed worker pool with scheduled pre-warming** | Simplest operationally and predictable for known launches. It wastes capacity during quiet periods and cannot react safely to an unexpected spike. | Ongoing idle capacity. | Low. |

For the current reference architecture, use the included HPA policy after confirming the external metrics API. If music release campaigns or batch imports cause highly uneven queue bursts, evaluate an event-driven worker scaler. Keep the API deployment on HPA resource/request signals regardless.

## 3. PostgreSQL and Redis surge guardrails

Application scaling has upstream limits. Define an explicit global database connection budget, then derive per-pod connection-pool size so the HPA maximum cannot exceed it. Reserve capacity for migrations, monitoring, replication, and administrative access. Use a transaction-safe pooler where appropriate; do not let each new worker establish an unbounded direct connection pool.

| Layer | Surge control | Do not do |
|---|---|---|
| PostgreSQL/pgvector | Use managed/operator replication, provision CPU/IOPS/storage headroom, monitor connection saturation and vector query plans, and use read replicas only for read models proven replication-safe. | Do not HPA a primary database or send unbounded vector queries to a replica without index and replication validation. |
| Redis | Use a private, TLS-enabled managed Redis/cluster option for production; set client connection/command timeouts and bounded key TTLs. | Do not treat Redis as the canonical source for presets, claims, vector artifacts, or entitlement state. |
| API | Enforce request size/time limits, cache reviewed public read models, and rate-limit expensive audio submission paths. | Do not scale solely on CPU if p95 latency or upstream connection saturation is already critical. |
| Audio worker | Lease jobs atomically, use idempotent processing, cap per-pod concurrency, and apply ingress admission/rate limits. | Do not scale down workers without enough stabilization to finish/hand off leased work. |

## 4. Rollout and test sequence

1. Install/verify a resource metrics server and a Prometheus external-metrics adapter. Apply the adapter-rule template only after confirming target labels in Prometheus.
2. Confirm `synthnow_api_rps` and `synthnow_audio_job_queue_depth` are available through the Kubernetes external metrics API for the `synth-now` namespace.
3. Set deployment connection-pool and worker-concurrency limits before raising HPA maximums. Ensure queue leases/retries are idempotent.
4. Apply the manifests in staging. Generate controlled traffic and queued audio work; verify scale-up, queue drain, vector p95, database connections, Redis error rate, and scale-down stabilization together.
5. Exercise the included synthetic failure tests and the opt-in `tests/run_live_resilience_smoke.py` only against an approved non-production target. Its test alert carries `synthetic=true` and is discarded by Alertmanager, so it must not page PagerDuty.
6. Promote only after recording actual p50/p95/p99 load, queue service time, database connections, cache hit ratio, and object-storage error behavior. Revisit targets after each major model/index/retrieval change.

## TL;DR

1. Scale **API and workers**, not PostgreSQL or Redis, with HPA.
2. Use CPU/memory plus request rate for the API; use shared queue depth plus CPU for workers.
3. Scale up fast, scale down slowly, and cap replica counts by upstream database/cache/processing capacity.
4. Enable external metrics only after a Prometheus Adapter exposes the exact names/labels required by HPA.
5. Load-test the whole path: API p95, vector p95, worker queue, PostgreSQL connections, Redis fallback, and object storage must remain healthy together.

## References

[1]: https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/ "Kubernetes Horizontal Pod Autoscaling"
