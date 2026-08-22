# Niko The Great - SYNTH NOW — Multi-Region Disaster Recovery and Backup Strategy

## 1. Recovery principle

PostgreSQL/pgvector is the **authoritative system of record** for canonical presets, claims, evidence, moderation decisions, reference-asset metadata, Chromaprint artifacts, and versioned Essentia/embedding vectors. Redis is only a cache and a bounded local session projection. A regional Redis loss must cause misses and user/session re-projection; it must not cause loss of verified gear facts, vectors, raw fingerprints, or audit history.

> **Recovery rule:** Restore PostgreSQL and the private object store first. Rebuild Redis from live traffic and canonical reads. Never promote a cache snapshot as a source of truth.

PostgreSQL continuous archiving combines a base backup with archived WAL. With a continuous WAL sequence extending back to the base backup, the database can be restored to a chosen point in time; a secondary system replaying the same archive can act as a warm standby.[1] This is the recovery mechanism for the canonical database. A logical dump is an additional portability/verification artifact, not a replacement for WAL-based recovery.[1]

## 2. Data classification and protection

| Data class | Canonical store | Regional recovery treatment | Backup / replication requirement | Recovery validation |
|---|---|---|---|---|
| Claims, sources, moderation, users, preset metadata | PostgreSQL | Promote/restore with transaction consistency | Physical base backup + continuous WAL archive; asynchronous warm standby in DR region | Row counts, foreign-key checks, latest moderation revision and source-observation samples. |
| Essentia vectors, pgvector indexes, fingerprints | PostgreSQL | Restore with schema and extension versions; verify retrieval afterward | Same physical backup/WAL stream; independent logical export for portability/rehearsal | Confirm extension/version, vector dimensions/model registry, sampled nearest-neighbor retrieval, and index validity. |
| Private reference audio, approved preset archives, upload artifacts | Versioned private object storage | Cross-region replicated or recoverable from immutable backup copy | Versioning, immutability/retention controls, cross-region replication, encrypted backups | Manifest count, object hash sample, object-to-database metadata reconciliation. |
| Redis preset cache | Redis | Discard and warm from PostgreSQL | No DR restore required for correctness; optional local snapshot only for performance diagnostics | Cache hit ratio returns after warm-up; canonical reads remain correct. |
| Redis session projection | Redis plus OAuth/JWT identity provider | Discard; re-project from newly verified access token | Do not treat as a durable session database; retain identity-provider revocation/audit controls | JWT validation remains successful; new session projection is created without role elevation. |
| Alert silences/configuration | Git, secret manager, Alertmanager state | Recreate from version-controlled config and secret manager | Back up state only if operationally required; retain change history in approved system | Synthetic Alertmanager route test and PagerDuty secret mount validation. |

## 3. Recommended regional topology

Use **single-writer, warm-standby** PostgreSQL as the default topology. The primary region accepts canonical writes. A private, asynchronous physical standby in the recovery region replays the WAL stream. Base backups and WAL archives are encrypted, copied to independent storage in both regions, and protected in a separate administrative boundary from the production database account. Application traffic is routed to the recovery region only after a fenced, declared failover.

Do not run active-active canonical writes for claims, moderation, vectors, or source evidence until the product has an explicit conflict-resolution model, globally ordered audit events, replicated identity semantics, and proven multi-writer PostgreSQL technology. The trust model is more valuable than a superficially lower failover time.

| Approach | Tradeoffs | Cost | Setup complexity |
|---|---|---:|---|
| **Single writer with cross-region warm standby and WAL archive** | Strongest balance for Synth Now’s evidence and vector integrity. Accepts a bounded asynchronous replication lag and requires controlled failover/fencing. **Recommended.** | Two regional database footprints plus backup/object storage. | Moderate to high. |
| **Single primary with backups only** | Simplest and lower steady-state cost, but recovery waits for restore and WAL replay; stale period depends on archive cadence. | Lower steady-state infrastructure. | Moderate. |
| **Multi-writer regional database** | Potentially lower geographic write latency, but greatly increases conflict, audit-order, operational, and testing complexity. Not appropriate before a deliberate data-conflict design. | Higher platform and engineering cost. | High. |

## 4. Recovery objectives and retention proposal

The following are **initial targets for approval**, not promises. Final values must follow legal, customer, provider, and observed restore-test requirements.

| Objective | Initial target | How it is achieved | Alert / test |
|---|---:|---|---|
| Canonical database RPO | ≤ 5 minutes | Frequent WAL archiving and monitored replica/archive lag | Page if archive/replica lag exceeds target; inspect `pg_stat_archiver`/replication health. |
| Regional canonical DB RTO | ≤ 60 minutes | Warm standby, tested promotion runbook, pre-provisioned application manifests and secrets | Quarterly controlled regional failover rehearsal. |
| Single-record recovery | ≤ 4 hours | PITR clone to an isolated environment; export/reconcile only approved records | Monthly PITR restoration drill. |
| Redis recovery | ≤ 15 minutes for cache warm-up | Redis starts empty; cache-aside repopulates reviewed reads/session projection | Measure cache-hit recovery and PostgreSQL connection headroom. |
| Logical portability restore | ≤ 24 hours | Periodic `pg_dump`-style logical artifact plus extension/schema verification | Monthly isolated logical restore. |

Take physical base backups at a cadence that permits the RTO target; continuously archive WAL between base backups. PostgreSQL notes that a successful continuous-archive recovery needs an uninterrupted WAL sequence going back at least to the start of the base backup.[1] Retain a second independent logical backup series for selective audit/portability validation, but do not rely on it for point-in-time recovery.

## 5. Backup design

### PostgreSQL and pgvector

1. Use a PostgreSQL service/operator that supports continuous physical backup, WAL archiving, point-in-time restore, and cross-region replica recovery. Confirm the exact PostgreSQL and pgvector extension versions in both regions before enabling a replica.
2. Encrypt base backups and WAL archives in transit and at rest. Use isolated backup credentials that can write new objects but cannot delete retained backups. Enable immutable retention where the provider/compliance program permits it.
3. Copy backup metadata and data to a second region and a distinct account/project. A backup under the same compromised administrative boundary is not an independent recovery copy.
4. Include schema migrations, pgvector extension state, model registry, vector dimensions, index parameters, and reference-asset manifests in restore validation. If ANN indexes require rebuild or `REINDEX` after recovery, treat that time as part of the tested RTO rather than an undocumented afterthought.
5. Record backup completion, archive age, restore duration, restore error count, replica lag, and sampled vector-query correctness in Prometheus/Grafana. Page on a sustained missed backup or archive lag that breaches the approved RPO.

### Redis

Redis session/cache loss is intentionally recoverable from PostgreSQL plus an OAuth/JWT identity provider. In production, use private TLS Redis with replication/failover appropriate to its provider. Do not enable cross-region session replication as a replacement for token validation, user disablement, or identity-provider revocation. If the product later needs globally durable session/revocation state, create an explicit canonical session/revocation service and model—not an undocumented Redis persistence dependency.

Optional Redis snapshots can help diagnose cache warm-up behavior, but they are not required for correctness and must be encrypted, retained briefly, and excluded from any canonical recovery chain. Never store bearer tokens, refresh tokens, raw audio, raw vectors, or source credentials in Redis.

### Private object storage

Use encrypted, versioned object storage for authorized reference audio, preset files, and upload artifacts. Enable cross-region replication or independent immutable backup copies. Store only private object keys and integrity metadata in PostgreSQL; issue short-lived server-generated download URLs. During recovery, reconcile the object manifest with the restored database before re-enabling ingestion or vector-reference jobs.

## 6. Failover runbook

1. **Declare and assess.** Confirm primary-region failure, record the incident start, pause destructive automation, and identify the last known good WAL/archive point.
2. **Fence the old primary.** Remove write routing and ensure the old primary cannot resume writes after recovery-region promotion. This prevents split-brain evidence and audit history.
3. **Promote or restore.** Promote the tested warm standby, or restore the latest base backup and replay WAL to the approved recovery target. Verify PostgreSQL and pgvector versions before opening traffic.
4. **Validate data.** Run schema/extension checks, row-count and foreign-key checks, source/claim revision samples, reference-object reconciliation, and sampled vector nearest-neighbor queries. Do not infer historical claims from a failed/missing cache.
5. **Repoint applications.** Update the protected database endpoint/secret, deploy API and worker services in the recovery region, preserve OAuth issuer/audience configuration, and enable restricted health traffic first.
6. **Rebuild cache.** Start Redis empty or from a local safe snapshot, restore only configuration, and let cache-aside/session re-projection repopulate. Monitor cache-miss pressure and PostgreSQL connections.
7. **Restore monitoring.** Apply Alertmanager/PagerDuty secrets/configuration, validate the synthetic discard route, and then re-enable alerting. Do not submit an unmarked test alert to the production PagerDuty integration.
8. **Return traffic gradually.** Shift traffic after health, vector retrieval, queue leasing, object access, and latency checks meet the approved gates. Document the actual RPO/RTO result.
9. **Re-establish resilience.** Build a new standby in the repaired region, resume WAL/backups, conduct root-cause analysis, and revise the recovery runbook based on measured gaps.

## 7. Recovery drills and evidence

| Frequency | Drill | Success evidence |
|---|---|---|
| Daily | Backup/WAL/archive completion check | Fresh base-backup and WAL-age status with no missed retention task. |
| Weekly | Standby/replication health check | Replica lag within target and a valid recovery point visible in DR. |
| Monthly | Isolated PITR and logical restore | Restored cluster passes extension/schema, claim/audit, manifest, and vector-query sample checks. |
| Quarterly | Controlled regional failover rehearsal | Fenced primary, promoted recovery database, validated app/cache/alerts, recorded actual RPO/RTO. |
| After schema/model/index change | Restore compatibility drill | New migrations, vector dimensions, model registry, and ANN behavior survive restore. |

## TL;DR

1. PostgreSQL/pgvector and private object storage are the recovery priority; Redis is disposable acceleration.
2. Use a **single writer, cross-region warm standby, physical base backups, and continuous WAL archive** as the default design.
3. Keep independent, encrypted backup copies across regions and administrative boundaries; test restores regularly.
4. Treat vector indexes/model metadata and object manifests as first-class restore-validation data.
5. Use fenced, declared failover. Do not activate two canonical write regions without a tested conflict/audit model.
6. Rebuild Redis from verified JWTs and PostgreSQL after failover; never use a cache snapshot as canonical data.

## References

[1]: https://www.postgresql.org/docs/current/continuous-archiving.html "PostgreSQL continuous archiving and point-in-time recovery"
[2]: https://www.postgresql.org/docs/current/backup.html "PostgreSQL backup and restore"
[3]: https://redis.io/docs/latest/develop/use-cases/cache-aside/ "Redis cache-aside"
