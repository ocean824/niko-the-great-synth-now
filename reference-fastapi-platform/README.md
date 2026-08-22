# Synth Now Evidence API

A runnable FastAPI backend reference for **evidence-first music-production knowledge**. It implements crowd-submitted gear/VST/preset claims, moderator verification, immutable revisions, approved-source observations, private audio-feature jobs, and real-time status streaming.

The API’s central protection is structural:

> **Audio analysis can create a private observation. Source ingestion can create a review candidate. Only source-backed human moderation can publish a production claim.**

## What is included

| Component | Implementation |
|---|---|
| Crowd contributions | Authenticated members submit version-scoped claims with canonical targets or unresolved source text, scopes, and evidence. |
| Moderation | Reviewer/editor queue, self-review prevention, independent-domain corroboration gate, verified-source gate, decision notes, revisions, and contributor reputation updates. |
| Evidence ledger | Claims, scopes, evidence, reviews, and snapshots use SQLAlchemy relational models with an SQLite development database. |
| Audio jobs | Private multipart upload, consent version, size control, background DSP feature extraction, job status endpoint, and WebSocket status stream. |
| Source ingestion | Editor-approved source registry, default-deny URL policy, `robots.txt` check, public HTML/JSON-LD extraction, review-only source observation. |
| Tests | An end-to-end test creates users/entities, submits a source-backed claim, publishes a verified claim, creates a source configuration, uploads audio, and confirms that the audio result does not assert gear/preset provenance. |

## Quick start

```bash
cd synth_now_fastapi
sudo pip3 install -r requirements.txt
PYTHONPATH=. pytest -q
PYTHONPATH=. uvicorn app.main:app --reload
```

Open the generated OpenAPI interface at `http://127.0.0.1:8000/docs`.

The development service uses SQLite at `./synth_now.db` and local private-path uploads at `./private_uploads`. Override the database location with `DATABASE_URL` and the private upload path with `SYNTH_NOW_UPLOAD_DIR`.

## Development authentication

The reference service accepts a development `X-User-Id` header. Create a user with `POST /v1/users`, then use that user ID in subsequent requests:

```bash
curl -X POST http://127.0.0.1:8000/v1/users \
  -H 'Content-Type: application/json' \
  -d '{"email":"editor@example.com","display_name":"Editor","role":"editor"}'

curl http://127.0.0.1:8000/v1/moderation/claims \
  -H 'X-User-Id: <editor-user-id>'
```

Replace this development header with verified OAuth/JWT authentication, role authorization, short-lived session/WebSocket credentials, request rate limits, and audit logging before any deployment.

## Endpoint map

| Route | Role | Purpose |
|---|---|---|
| `POST /v1/users` | Development bootstrap | Create a local user with a role. |
| `POST /v1/entities` | Editor/admin | Create canonical recording-version, gear, VST, preset, artist, or person entities. |
| `POST /v1/claims` | Authenticated contributor | Submit a source-backed production claim with scopes. |
| `GET /v1/claims/{claim_id}` | Authenticated user | Retrieve the evidence ledger, scopes, and review history. |
| `GET /v1/moderation/claims` | Reviewer/editor/admin | View a filtered moderation queue. |
| `POST /v1/moderation/claims/{id}/decisions` | Reviewer/editor/admin | Request changes, reject, publish community corroboration, or publish verified claim. |
| `POST /v1/moderation/source-configs` | Editor/admin | Register an official source domain and narrow path policy. |
| `POST /v1/moderation/source-configs/{id}/fetch` | Editor/admin | Queue one approved source URL for review-only metadata extraction. |
| `GET /v1/moderation/source-observations` | Reviewer/editor/admin | Inspect structured source observations. |
| `POST /v1/moderation/source-observations/{id}/decisions` | Editor/admin | Approve/reject an observation; optionally attach it as evidence to an existing claim. |
| `POST /v1/audio/jobs` | Authenticated user | Upload private authorized audio and enqueue deterministic feature extraction. |
| `GET /v1/audio/jobs/{id}` | Owner or moderator | Retrieve job status and private feature result. |
| `POST /v1/audio/jobs/{id}/feedback` | Owner | Submit feedback without converting model output into a historical claim. |
| `WS /ws/v1/audio/jobs/{id}` | Owner or moderator | Development status stream for queued/running/completed audio jobs. |

## Crowd-moderation rules

The full policy is in [`docs/contribution_moderation_governance.md`](docs/contribution_moderation_governance.md). In summary, the API enforces the following gates.

| Outcome | Required condition |
|---|---|
| **Submitted lead** | Recording version, target or source-quoted target, scope, and at least one source. |
| **Community corroborated** | Reviewer decision plus source URLs from at least two independent publisher domains. |
| **Verified** | Editor decision plus one quality-4/5 official, official-archive, credits, creator-confirmation, or producer-interview source. |
| **Audio observation** | Private feature job; never publishes a claim. |
| **Official-source observation** | Approved source config and permitted fetch; never publishes a claim. |

The code forbids moderators from reviewing their own claims and writes an audit snapshot at submission and every review decision. Production should add two-editor approval for high-impact verified publication, retirement, or target/version changes.

## Source-ingestion safety

The source worker only fetches URLs from an editor-approved registry. It validates HTTPS, verified domain, narrow path prefix, enabled state, worker mode, successfully retrieved `robots.txt` rules, response type, response size, and redirect domain. It extracts a limited citation/JSON-LD observation and records it for editorial review.

RFC 9309 requires a crawler that successfully obtains `robots.txt` to follow its parseable rules. [1] Schema.org Product markup is useful as a discovery input for product name, brand, category, and variant data, but does not by itself prove a recording-level use or historical event. [2]

## Audio-analysis boundary

The current worker produces deterministic duration, level/clipping, spectral, MFCC, and chroma feature summaries from private uploaded audio. It intentionally returns a notice that it has not established instrument, gear, VST, or preset attribution. Extend it with separately versioned model workers and a rights-cleared reference-render retrieval system; do not give model workers database permission to write `production_claims` or published usage edges.

## Development-to-production migration

| Development reference | Production replacement |
|---|---|
| SQLite | PostgreSQL with the core schema, typed enums, `pgvector`, partitioned analysis tables, migrations, and row-level access controls. |
| Local `private_uploads/` path | Private object storage with signed URLs, content scanning, strict retention deletion, and encryption. |
| FastAPI `BackgroundTasks` | Durable queue workers with idempotent jobs, retries, a dead-letter path, monitoring, and progress event broker. |
| `X-User-Id` header | OAuth/JWT authentication, role/organization authorization, short-lived WebSocket tokens, abuse/rate limits. |
| Source observation JSON | Source-document/fetch/diff tables with fetch provenance, publisher verification, source health, review tasks, and change alerts. |
| One-editor decision | Two-editor review for sensitive publication/retirement paths, appeal workflow, duplicate/conflict resolution. |

## Deployment choices

| Approach | Tradeoffs | Cost | Setup complexity |
|---|---|---:|---|
| **Managed application service with a database and worker queue** | Lowest operations burden and a good fit for the API, moderation UI, scheduled approved-source checks, and normal background jobs. Heavy audio separation/inference must run outside the request path and may exceed the service’s compute envelope. | Starts low; varies with database, storage, queue, and worker usage. | Moderate. |
| **Self-managed Python service with dedicated worker hosts** | Supports custom audio packages, GPU-capable inference workers, strict network controls, and large batch processing. Requires patching, secrets, backups, monitoring, and incident ownership. | Infrastructure and operations costs vary with host/GPU/storage choices. | High. |

For an initial moderation/ingestion API, use the managed path and keep heavyweight separation/model inference in a separate queued worker. Choose self-managed infrastructure only when measured model-resource or OS/runtime requirements make it necessary.

## Client SDK and deployment assets

The installable synchronous Python SDK lives in [`sdk/`](sdk/). Install it locally with `pip install -e sdk` and use `SynthNowClient` for health checks, evidence claims, audio-job polling, and contract-first preset/recognition API calls. The SDK does not expose worker-only routes, raw vectors, raw fingerprints, or private artifact storage locations.

Deployment assets are included for local Compose and Kubernetes under [`docker-compose.yml`](docker-compose.yml) and [`deploy/kubernetes/`](deploy/kubernetes/). The full rollout guide is [`docs/deployment.md`](docs/deployment.md). It documents the separate API/worker topology, PostgreSQL pgvector bootstrap, private upload/object-storage migration, secrets, image publishing, rollout/health checks, and production hardening.

## Production RBAC, monitoring, and CI/CD

The OAuth2/JWT resource-server layer is implemented in [`app/auth.py`](app/auth.py). Set `SYNTH_NOW_AUTH_MODE=oauth_jwt` with a trusted issuer, audience, JWKS URL, and asymmetric algorithm allow-list before internet exposure. In that mode, the API validates bearer tokens and maps controlled role/scope claims to Synth Now roles; the development `X-User-Id` mechanism is not used.

Prometheus metrics are available at `/metrics` and are token-protected outside development mode. Local Compose now starts Redis, Prometheus, Alertmanager, and Grafana, while `deploy/monitoring/` contains alert rules, PagerDuty routing templates, and provisioned dashboards for vector latency, candidate count, audio queue depth, job p95, API errors, cache hit ratio, cache fallbacks, and critical alert state. Redis is strictly cache-aside/session acceleration: PostgreSQL remains canonical, Redis failure falls back safely, and JWTs are still validated on every request. GitHub Actions workflows under [`.github/workflows/`](.github/workflows/) run CI, publish provenance-enabled container releases, and require a protected, dry-run-first Kubernetes deployment. The full operational guides are [`docs/production_operations.md`](docs/production_operations.md) and [`docs/alerting_and_redis_operations.md`](docs/alerting_and_redis_operations.md).

## Resilience, surge autoscaling, and disaster recovery

The reference stack now includes deterministic Redis-fallback and Alertmanager-routing tests, plus an opt-in live smoke runner that sends only a `synthetic=true` alert to the discard receiver. It must be run only against an approved non-production target. API and worker deployments use separate surge-aware HPAs: the API scales on CPU, memory, and request rate; workers scale on CPU and a shared audio-queue external metric. PostgreSQL/pgvector and Redis are stateful capacity services, so they are not HPA targets. The worker exposes internal queue metrics for Prometheus, and [`deploy/kubernetes/prometheus-adapter-rules.yaml`](deploy/kubernetes/prometheus-adapter-rules.yaml) documents the adapter mapping required before external metric scaling is enabled.

The multi-region recovery plan treats PostgreSQL/pgvector and private object storage as canonical recovery priorities, with Redis rebuilt as disposable acceleration after recovery. The recommended topology is a single write region, cross-region warm standby, physical base backups, continuous WAL archiving, independent logical restore validation, cross-region object replication, and fenced failover drills. Read [`docs/surge_autoscaling.md`](docs/surge_autoscaling.md) and [`docs/disaster_recovery_multi_region.md`](docs/disaster_recovery_multi_region.md) before production rollout.

## AWS infrastructure and security hardening

The repository now contains a multi-region AWS Terraform foundation under [`infra/aws/`](infra/aws/). It provisions private primary/secondary VPC and EKS topology, Aurora PostgreSQL-compatible global database resources, Redis global replication members, encrypted replicated S3 buckets, immutable ECR repositories, CloudWatch/SNS foundations, and EKS OIDC workload roles. It is intentionally plan-first: bootstrap a separate encrypted/locked remote state backend, provide inputs only through a secure environment, validate engine/region compatibility, review a saved plan, and apply only through an approved production change path. Read [`infra/aws/README.md`](infra/aws/README.md) and [`docs/aws_terraform_deployment_runbook.md`](docs/aws_terraform_deployment_runbook.md) before using it.

The authorized security program is documented in [`docs/security_hardening_and_authorized_testing.md`](docs/security_hardening_and_authorized_testing.md). It covers FastAPI object/function authorization, OAuth/OIDC/JWT verification, WebSockets, uploads, SSRF-safe ingestion, PostgreSQL/Redis boundaries, container/Kubernetes hardening, AWS/Terraform security, supply chain, and a staged penetration-testing plan that requires written scope and favors synthetic staging data.

## Staging infrastructure tests, compliance gates, and incident response

The AWS foundation now includes a guarded Go/Terratest suite in [`infra/aws/test/`](infra/aws/test/). It supports plan-only validation, read-only existing-stack output checks, and one opt-in canary that creates/destroys only a uniquely named private S3 fixture. All modes require an isolated staging account, explicit environment/account guards, and short-lived credentials; the canary additionally requires the exact `YES-STAGING-ONLY` confirmation. Read [`infra/aws/test/README.md`](infra/aws/test/README.md) and [`docs/terratest_and_ci_compliance.md`](docs/terratest_and_ci_compliance.md) before enabling it.

New GitHub Actions workflows add Terraform format/validation, Checkov, Trivy, Gitleaks, Python dependency audit, workflow linting, and a manual protected-environment OIDC Terratest workflow. See [`.github/workflows/infrastructure-security.yml`](.github/workflows/infrastructure-security.yml) and [`.github/workflows/staging-terratest.yml`](.github/workflows/staging-terratest.yml). The production response model—including severity definitions, incident roles, alert-specific steps, regional-recovery escalation, evidence handling, handoffs, and drills—is in [`docs/incident_response_and_on_call.md`](docs/incident_response_and_on_call.md).

## Chaos Engineering game day and topology map

[`docs/chaos_engineering_game_day.md`](docs/chaos_engineering_game_day.md) defines a controlled staging-only resilience exercise with Gremlin, LitmusChaos, and lighter-weight drill options. Its first experiments validate baseline/abort controls, primary application isolation, bounded database-path latency, and secondary readiness without touching production, customer media, or unapproved data failover. The interactive map at [`docs/interactive_multi_region_topology.html`](docs/interactive_multi_region_topology.html) lets operators click components, filter region/replication paths, and distinguish Terraform-provisioned resources from the still-required global traffic-steering layer. The version-controlled Mermaid source and static PNG are available at [`docs/multi_region_topology.mmd`](docs/multi_region_topology.mmd) and [`docs/multi_region_topology.png`](docs/multi_region_topology.png).

## Validation

The test suite now runs the original API workflow, SDK integration, JWT role/scope validation, Prometheus metric exposure, Redis-fallback and Alertmanager-routing simulations, and deployment/monitoring/CI asset checks:

```bash
PYTHONPATH=.:sdk pytest -q
python3 tests/validate_deploy_assets.py
python3 tests/validate_terraform_assets.py
python3 tests/validate_terratest_compliance_operations.py
python3 tests/validate_chaos_topology_assets.py
```

## References

[1]: https://datatracker.ietf.org/doc/html/rfc9309 "RFC 9309: Robots Exclusion Protocol"
[2]: https://schema.org/Product "Schema.org: Product"

## TL;DR

1. Install dependencies and run `PYTHONPATH=.:sdk pytest -q` plus `python3 tests/validate_deploy_assets.py`.
2. Create the two local PagerDuty routing-key files described in `deploy/monitoring/alertmanager/secrets/README.md`, then start API, PostgreSQL/pgvector, Redis, worker, Prometheus, Alertmanager, and Grafana with `docker compose up --build`.
3. Use the SDK for supported public/user-level requests; do not call internal worker APIs or expose raw vectors/fingerprints.
4. Create editor/contributor/recording/gear entities, submit evidence-scoped claims, and keep moderation separate from audio inference.
5. Register only carefully approved official sources; fetches create review observations, never public facts.
6. Configure OAuth2/JWT with trusted issuer/audience/JWKS, role/scope claims, and short-lived tokens; remove development identity headers before internet exposure.
7. Keep private uploads in object storage and move polling to a durable queue before production scale; protect `/metrics`, use private TLS Redis with bounded cache TTLs, and tune dashboard alerts from measured workload baselines.
8. Install/verify the external metrics adapter before enabling HPA request-rate and audio-queue scaling; load-test API, worker, PostgreSQL connection, Redis fallback, and object-storage limits together.
9. Implement the multi-region warm-standby/WAL/archive/object-replication recovery plan and complete restore/failover drills before asserting production RPO/RTO.
10. Require GitHub CI on pull requests, release immutable/provenance-enabled container images, and deploy only an image digest through protected staging/production environments with dry-run and rollout checks.
11. Follow [`docs/deployment.md`](docs/deployment.md), [`docs/production_operations.md`](docs/production_operations.md), [`docs/alerting_and_redis_operations.md`](docs/alerting_and_redis_operations.md), [`docs/surge_autoscaling.md`](docs/surge_autoscaling.md), [`docs/disaster_recovery_multi_region.md`](docs/disaster_recovery_multi_region.md), [`infra/aws/README.md`](infra/aws/README.md), [`docs/aws_terraform_deployment_runbook.md`](docs/aws_terraform_deployment_runbook.md), [`docs/security_hardening_and_authorized_testing.md`](docs/security_hardening_and_authorized_testing.md), [`infra/aws/test/README.md`](infra/aws/test/README.md), [`docs/terratest_and_ci_compliance.md`](docs/terratest_and_ci_compliance.md), and [`docs/incident_response_and_on_call.md`](docs/incident_response_and_on_call.md) for migrations, cloud infrastructure, cache invalidation, PagerDuty routing, backups, monitoring, incident response, on-call operations, security validation, staging infrastructure tests, compliance gates, recovery hardening, controlled Chaos Engineering experiments, and topology validation.
