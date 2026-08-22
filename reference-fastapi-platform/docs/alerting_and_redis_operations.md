# Niko The Great - SYNTH NOW — Alert Routing and Redis Operations

## Purpose and operating boundary

This package adds two **non-authoritative** operational layers to Synth Now. Alertmanager decides who is notified when service health crosses a sustained threshold. Redis accelerates repeat reads and short-lived session projections. Neither layer may publish a production claim, alter moderation state, store raw audio/vector artifacts, or replace PostgreSQL as the source of truth.

> **Reliability rule:** A Redis outage must degrade to a slower PostgreSQL-backed request, not an incorrect result. A PagerDuty integration outage must preserve the alert in Alertmanager and Prometheus, not silently erase the incident signal.

## 1. Alert routing: Prometheus → Alertmanager → PagerDuty

Alertmanager uses a routing tree to group related alerts, choose receivers, schedule repeat notifications, and apply inhibition rules.[1] The provided configuration groups by alert, service, environment, model code, and reference role. It sends a critical issue to a dedicated high-urgency PagerDuty service after 15 seconds, while warning alerts are grouped for five minutes and routed to a separate low-urgency PagerDuty service. PagerDuty’s Events API v2 uses a routing key attached to a PagerDuty service; use different services or integrations to preserve the distinction between actionable pages and reviewable warnings.[2] [3]

| Alert condition | Initial threshold and duration | Severity | Alertmanager behavior | PagerDuty destination | First responder focus |
|---|---:|---|---|---|---|
| Vector p95 latency high | >500 ms for 10 min | Warning | Group for 5 min; repeat every 8 hr | Low-urgency integration | Check pgvector query plan, index health, candidate filtering, and database saturation. |
| Vector p95 latency critical | >1.5 s for 5 min | Critical | Send after 15 sec; repeat hourly | Critical on-call integration | Stabilize retrieval path, rollback regression if necessary, and protect response latency. |
| Audio queue backlog | >100 jobs for 10 min | Warning | Group for 5 min | Low-urgency integration | Compare arrivals versus worker throughput; inspect lease/worker health. |
| Audio queue critical | >500 jobs for 10 min | Critical | Send after 15 sec; repeat hourly | Critical on-call integration | Add/recover worker capacity and investigate stuck jobs or storage failure. |
| Audio-worker failure rate critical | >0.05 failed jobs/sec for 10 min | Critical | Send after 15 sec | Critical on-call integration | Halt unsafe retry loops and investigate decoder, upload, dependency, or deployment errors. |
| API unavailable | Prometheus cannot scrape API for 3 min | Critical | Send after 15 sec | Critical on-call integration | Check pods, endpoints, network policy, and metrics authentication. |

The alert rules live in `deploy/monitoring/alerts.yml`. The routing policy, PagerDuty receiver configuration, grouping, and critical-over-warning inhibition live in `deploy/monitoring/alertmanager/alertmanager.yml`. When a critical and warning alert are active for the same service/environment, the critical alert inhibits the warning alert to prevent duplicate notification fatigue.

### PagerDuty setup

Create two PagerDuty Events API v2 integrations. Associate the **critical** integration with the service and escalation policy that should page the on-call owner. Associate the **warning** integration with a low-urgency service or policy that records actionable work without waking the on-call responder. Store each routing key in the secret manager and mount it as a file named `pagerduty-critical-routing-key` or `pagerduty-warning-routing-key`; never place either key in a Git repository, Docker image, ConfigMap, Grafana variable, log line, or browser response.

The Kubernetes reference uses a secret named `synth-now-pagerduty-routing-keys`. The tracked foundation manifest supplies only an `-example` contract. In local Compose, create the ignored secret files under `deploy/monitoring/alertmanager/secrets/` before starting Alertmanager. Run `amtool check-config` against the mounted configuration before replacing a live policy. Test a new PagerDuty service only in an approved maintenance window, because a synthetic critical event can create or escalate an incident.

## 2. Redis cache-aside and session state

Redis cache-aside reads Redis first, loads PostgreSQL only on a miss, then writes a TTL-bounded response. A canonical database update is committed first and then invalidates affected cache state.[4] The implementation in `app/cache.py` follows that model and treats Redis as optional. It uses a versioned `synthnow:v1` prefix and structured cache keys, which makes a future key-schema change safe without flushing another environment’s data.

| Key family | Cached content | TTL | Invalidation | Must not contain |
|---|---|---:|---|---|
| `preset:detail:{preset_id}:{reviewed_revision}` | Safe canonical preset response for a reviewed revision | 5 min | Delete known prior revision after PostgreSQL commit | Preset files, private artifacts, unreviewed observations, raw vectors, source credentials. |
| `preset:search:{public_scope}:{catalog_revision}:{filter_hash}` | Paginated public preset-search read model | 60 sec | Atomically increment `catalog:revision` after canonical publication/update; old keys expire naturally | User-specific result sets, moderator queues, hidden claims. |
| `session:{session_hash}` | Local audit-user projection and minimal session metadata | At most 15 min and never beyond JWT expiry | Explicit logout/revocation delete, token expiry, user/role disable | Bearer token, refresh token, OAuth client secret, raw claim evidence. |
| `*:lock` | Short best-effort cache-fill lock token | 10 sec | TTL only | Business data or authorization state. |

The global catalog revision prevents unsafe wildcard deletes or `SCAN` calls on the write path. A reviewed preset change first commits PostgreSQL, then deletes the known revision-specific detail key and increments a compact Redis counter. New search queries include the new counter value; old search responses remain unreachable and expire normally. This preserves correctness without a distributed cache sweep.

### Session safety

The API validates the OAuth/JWT signature, issuer, audience, expiry, and current token roles **before** it consults Redis. The session cache only avoids repeated PostgreSQL reads needed to project the stable local audit user. The cache key is a SHA-256-derived identifier from the subject and token ID (or token expiry fallback), not the bearer token itself. Its TTL is capped by the access-token expiration. Token roles are always taken from the newly verified JWT, so an old cached role cannot elevate a caller.

For immediate access revocation beyond normal short-lived token expiry, add a logout/admin revoke path that calls `cache.revoke_session(session_id)` and maintain token revocation at the identity-provider layer. Cache session state should never be the sole authorization system. `SYNTH_NOW_AUTH_MODE=oauth_jwt` remains the production control that disables the development identity header.

### Cache failure and stampede behavior

A missing or failed Redis connection produces an `unavailable`/`error` Prometheus outcome and falls back to PostgreSQL. The cache adapter also uses a short, best-effort Redis lock for simultaneous search misses. It does not block a user while waiting for a lock, because availability and canonical correctness matter more than avoiding every duplicate database read. Redis documents both TTL-bounded cache-aside invalidation and Lua/atomic primitives that can be used for more advanced stampede controls if measured load justifies it.[4]

## 3. Metrics and dashboard additions

The cache layer publishes low-cardinality metrics only. No metric label includes a user ID, token/session ID, preset ID, source URL, raw query, or error text.

| Metric | Meaning | Suggested observation |
|---|---|---|
| `synthnow_cache_requests_total{key_family,outcome}` | Cache hit, miss, unavailable, or error counts | Hit ratio = hits / (hits + misses); treat a rising `unavailable` count as a capacity/reachability issue. |
| `synthnow_cache_operation_duration_seconds{operation,outcome}` | Redis GET/SET latency | Compare cache p95 with API latency; a slow cache may be worse than a local database read. |
| `synthnow_vector_search_duration_seconds` | Existing vector retrieval p95 | Page only after sustained critical latency; use the warning to review trend/regression. |
| `synthnow_audio_job_queue_depth` | Current queued work | Compare backlog with worker failures and job processing p95 before adding capacity. |

Add cache-hit ratio and cache-error panels to the existing Grafana dashboard once preset API routes are mounted. The supplied Alertmanager policy does not page on a standalone Redis error because the system intentionally falls back to PostgreSQL; page only when the business-facing vector/API/queue symptom becomes sustained.

## 4. Deployment choices

| Approach | Tradeoffs | Cost | Setup complexity |
|---|---|---:|---|
| **Managed Redis and managed/cluster observability** | Provides TLS, failover, backups, monitoring, and operational ownership outside the app team. It is the recommended production path for multi-replica API/worker usage. | Varies by provider and capacity. | Moderate; configure private networking, secrets, and service integrations. |
| **Included Kubernetes Redis and Alertmanager references** | Useful for development/staging and controlled low-scale environments. The included Redis reference is a single replica and does not provide production HA. The Alertmanager reference stores silences locally. | Uses existing cluster capacity. | Higher; the team owns upgrades, backups, failover, and security posture. |
| **Local Docker Compose** | Fastest way to validate the API, worker, PostgreSQL/pgvector, Redis, Prometheus, Grafana, and Alertmanager together. It uses development-only credentials and does not model production availability. | Local machine resources. | Low. |

For production, prefer the managed path and use the application manifests only for API/worker configuration, secrets, and monitoring integration. Use the in-cluster references only when the team explicitly accepts the database/cache/alerting operational burden.

## 5. Required configuration and rollout

1. Set `SYNTH_NOW_REDIS_URL` to a private Redis endpoint, preferably `rediss://` with provider CA validation. Keep it server-side and use a least-privilege ACL user limited to the selected database/key prefix.
2. Set `SYNTH_NOW_CACHE_ENABLED=true`; retain a tested PostgreSQL fallback. Start with the documented TTLs and adjust only after measuring cache hit ratio, stale-read tolerance, and write frequency.
3. Create the PagerDuty routing-key secret from the provider’s Events API v2 integrations. Mount key files read-only in Alertmanager.
4. Validate Prometheus rules and Alertmanager configuration in CI. Deploy alert rules before routing changes, then configure critical paging and validate it during an approved test window.
5. Tune initial thresholds with rights-cleared production-like traffic. The thresholds in this package are operating hypotheses, not permanent SLOs.
6. Add a Redis connectivity/runbook panel and verify that a Redis outage causes a bounded cache fallback rather than authentication or claim-publication failure.

## TL;DR

1. Use Alertmanager to route **critical vector latency, critical audio backlog/failures, and API unavailability** to a high-urgency PagerDuty integration; keep warning alerts separate and inhibited when a matching critical alert is active.
2. Keep PagerDuty routing keys as mounted secret files, never in YAML, code, logs, or browser data.
3. Use Redis cache-aside only for **reviewed public preset read models** and minimal short-lived session projection data.
4. Commit PostgreSQL first, then delete revision-specific detail keys and increment the catalog revision. Do not wildcard-scan Redis on publication.
5. Verify JWTs on every request. Cap session-cache TTL at token expiry and never cache bearer tokens or authorization decisions.
6. Treat Redis as an accelerator: record cache hits/misses/errors, fall back safely to PostgreSQL, and page only on sustained user-impacting symptoms.

## References

[1]: https://prometheus.io/docs/alerting/latest/configuration/ "Prometheus Alertmanager configuration"
[2]: https://www.pagerduty.com/docs/guides/prometheus-integration-guide/ "PagerDuty Prometheus integration guide"
[3]: https://developer.pagerduty.com/docs/events-api-v2-overview "PagerDuty Events API v2 overview"
[4]: https://redis.io/docs/latest/develop/use-cases/cache-aside/ "Redis cache-aside"
[5]: https://redis.io/docs/latest/develop/clients/redis-py/async/ "redis-py asyncio client"
