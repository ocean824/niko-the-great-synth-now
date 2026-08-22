# Niko The Great - SYNTH NOW — Incident Response and On-Call Procedures

## 1. Purpose and operating model

This runbook coordinates the response to production security alerts, availability failures, data-integrity concerns, and regional infrastructure events across the Synth Now API, workers, Aurora/pgvector, Redis, private object storage, EKS, CI/CD, and identity provider. It is designed to be used with the existing Alertmanager/PagerDuty configuration, dashboards, AWS monitoring, and multi-region recovery strategy.

NIST SP 800-61 Rev. 3 recommends integrating incident response into cybersecurity risk management to improve preparation, detection, response, recovery, and continual improvement.[1] The procedures below use that model: prepare before an incident, triage and contain safely, recover with evidence, then improve controls and tests.

> **Safety rule:** Preserve people safety, data integrity, evidence integrity, and customer trust before restoring convenience. Do not perform destructive changes, regional failover, broad credential revocation, public disclosure, or database rollback without the designated incident authority and a recorded decision.

## 2. Roles and on-call coverage

Use role names in tickets and incident channels; assign people through the approved PagerDuty schedule and escalation policy. Do not put personal phone numbers, home addresses, or credential details in this document.

| Role | Primary responsibility | Authority | Backup |
|---|---|---|---|
| Primary on-call engineer | Acknowledge, assess, stabilize, gather initial evidence, open incident record. | Execute pre-authorized low-risk mitigations. | Secondary on-call engineer. |
| Incident commander (IC) | Owns severity, decisions, timeline, communication cadence, and handoffs. | Authorizes significant containment, recovery progression, and closure. | Named engineering/security leader. |
| Security lead | Directs suspected compromise, token/secret, ingestion/SSRF, malware, privacy, or abuse investigation. | Authorizes credential/token revocation and forensic preservation with IC. | Security delegate. |
| Platform lead | Directs EKS/AWS/network/CI/CD, observability, and regional failover execution. | Authorizes approved infrastructure changes under IC. | Platform delegate. |
| Data lead | Directs Aurora/pgvector, migration, backup, restore, and evidence-integrity validation. | Authorizes database recovery procedure under IC. | Database delegate. |
| Communications lead | Maintains stakeholder/customer/status updates approved by IC/legal. | Sends pre-approved operational updates. | Product/operations delegate. |
| Scribe | Maintains timestamped factual timeline, actions, decisions, owners, and evidence links. | No change authority. | Any non-primary responder. |

### On-call rotation

Maintain a **primary** and **secondary** engineer at all times for the production service. Use weekly rotations with a scheduled weekday handoff; adapt duration only after reviewing alert volume and burnout. The primary must acknowledge a page within the approved service target, normally five minutes for critical pages. If the primary has not acknowledged by the target, the schedule escalates to the secondary; if neither is available, route to the engineering/security manager according to the PagerDuty escalation policy.

Each handoff includes the current deployment/version, unresolved alerts, ongoing maintenance, risk acceptances, migration state, dependency changes, backup/replica status, on-call coverage gaps, known noisy alerts, and any temporary mitigations with expiry. The outgoing primary must not close the handoff until the incoming primary acknowledges it in the approved channel.

| Cadence | Action | Evidence |
|---|---|---|
| Every shift/handoff | Review open incidents, unresolved alerts, change calendar, dashboard health, current region, and escalation contacts. | Handoff entry. |
| Weekly | Review page volume, acknowledgment/mitigation times, false positives, and stale runbooks. | On-call operations review. |
| Monthly | Conduct a tabletop or controlled technical drill. | Drill timeline and action items. |
| Quarterly | Run a cross-functional security/infrastructure or regional recovery exercise. | Measured RPO/RTO, lessons, ownership. |
| After any SEV1/SEV2 | Complete post-incident review and regression work. | Approved review and tracked actions. |

## 3. Severity classification and service targets

Severity reflects observed or credible impact, not alert color alone. Upgrade immediately when evidence changes. Downgrade only with IC agreement and documented rationale.

| Severity | Example impact | Acknowledge target | Initial update cadence | Resolution target | Paging |
|---|---|---:|---:|---:|---|
| **SEV1 Critical** | Confirmed data exposure/credential compromise; active malware/SSRF escape; canonical data integrity threat; complete public API outage; unrecoverable queue/data loss; regional failure requiring promotion. | 5 minutes | Every 30 minutes | Incident-specific; recovery prioritized continuously | Primary, secondary, IC, security/platform/data leads as applicable. |
| **SEV2 High** | Sustained vector p95 breach, audio queue cannot drain, partial API unavailability, significant authorization defect without confirmed exposure, degraded primary database/replication, failed production deployment. | 15 minutes | Every 60 minutes | Same business day or approved mitigation | Primary and relevant lead; escalate if sustained. |
| **SEV3 Moderate** | Single service degradation with workaround, noncritical security misconfiguration, backup/scan failure with recovery margin remaining, noisy alert requiring tuning. | Business-hours/rotational target | Daily or ticket updates | Planned remediation | Create ticket; page only if sustained/upgrade criteria met. |
| **SEV4 Low** | Informational anomaly, documentation gap, low-risk dependency finding, test-only alert. | No page | Ticket only | Backlog | No page. |

## 4. Common first-five-minute procedure

1. **Acknowledge** the page, identify the service/region/alert labels, and open an incident record for SEV1/SEV2.
2. **Establish facts** from dashboards, logs, recent deploys, AWS health, GitHub Actions, database/Redis health, queue depth, and alerts. Record timestamps and query links; do not paste raw tokens, customer media, secrets, or personally identifying content.
3. **Assess scope**: availability, confidentiality, integrity, customer impact, regions, services, identities, source ingestion, and whether data may have been changed.
4. **Select severity and roles**. Invite the IC and the relevant security/platform/data lead early. Appoint a scribe for SEV1.
5. **Stabilize safely** using pre-authorized low-risk actions: pause a failing deployment, scale within approved HPA caps, disable a nonessential ingestion source, rate-limit an abusive path, put maintenance mode around a non-destructive operation, or fail closed on an unsafe external integration.
6. **Do not** delete evidence, restart every service blindly, rotate all secrets without a dependency plan, promote a recovery region casually, or disable logging/controls to reduce noise.

## 5. Alert and service runbooks

### 5.1 Vector search latency or error spike

**Signals:** `SynthNowVectorSearchLatencyCritical`, elevated API 5xx, database CPU/connections/IO, pgvector query changes, cache miss/fallback rise, new model/index/deployment.

1. Confirm primary vs secondary region, recent image/schema/index/model changes, p95/p99 latency, error rate, candidate count, cache behavior, database connection saturation, and query execution plan sample using non-sensitive staging-safe diagnostics.
2. Pause rollout or traffic shift if correlated. Enforce request/rate/filter limits and disable optional expensive recommendation/similarity paths before weakening evidence controls.
3. Scale API only within database/Redis/object-storage connection budget; HPA cannot repair a saturated database. Add temporary capacity only through approved platform procedure.
4. If a bad index/model/query plan is suspected, route the feature to a safe fallback/limited result state, preserve logs/query metadata, and involve data lead. Do not discard or mutate canonical vectors during triage.
5. Resolve after latency and error rate remain below target for an agreed observation window. Create regression/load test and update capacity model.

### 5.2 Audio job queue failure or backlog

**Signals:** `SynthNowAudioQueueCritical`, worker failures, queue depth rising, worker restarts, object-storage errors, corrupted/quarantined uploads, model dependency errors.

1. Confirm queue leasing, worker replicas, HPA external metric freshness, job age, retry/poison-job profile, object storage, CPU/memory, and recent code/model changes.
2. Apply admission control: rate-limit new noncritical jobs, preserve customer order, and do not silently drop jobs. Mark job status transparently with bounded retry state.
3. Scale workers within queue/database/object-storage capacity. If a specific source/model/input causes repeated failure, quarantine it and disable the affected worker path rather than retrying indefinitely.
4. Verify no job is double-processed or converted into historical gear/preset facts. Inference remains source-separated and auditable.
5. Drain under monitored controls, reconcile queue/job states, and add a test for the failed condition.

### 5.3 Suspected JWT, authorization, credential, or secret compromise

**Signals:** unusual auth failures/successes, impossible role transition, access from an unexpected workload, secret scan finding, leaked token report, anomaly in moderation/source actions, unexpected OIDC trust use.

1. Raise to SEV1 when unauthorized access or credible credential exposure is confirmed; involve security lead and IC.
2. Preserve logs, token metadata (redacted), request IDs, IAM/CloudTrail/OIDC records, affected object IDs, deployment versions, and source of report. Do not paste the secret/token in chat or ticket.
3. Contain narrowly: disable the specific identity/client/service account/OIDC role, revoke/rotate the affected key/secret, invalidate sessions/tokens according to identity policy, and block the suspicious route/source if needed. Keep unrelated authentication functioning where safe.
4. Validate every protected endpoint still enforces issuer/audience/algorithm/time claims and object/function authorization. Examine Redis projection only as cache; do not rely on it for forensics/canonical identity state.
5. Assess exposure, required notification, and evidence retention with legal/privacy leadership. Rebuild trust policy/role scope, deploy fix, and perform controlled retest before closure.

### 5.4 Unsafe source ingestion, SSRF, malicious file, or supply-chain alert

1. Disable the affected source configuration or artifact pipeline; preserve the quarantine object hash, source URL metadata, parser result, redirect/DNS decision, worker image digest, and audit record.
2. Confirm no file/plugin/script/installer executed and no internal/private/metadata endpoint was reached. Review egress and cloud metadata access logs with security/platform leads.
3. Revoke any affected source credentials; restrict source registry/path/redirect/DNS policy; scan related artifacts in isolation.
4. Publish no observation/claim based on the affected source until source integrity is verified. Notify owners if contractual/security process requires.
5. Add a regression test for the blocked condition and review all active source configurations for similar exposure.

### 5.5 Aurora/pgvector availability, integrity, or replication event

1. Engage data and platform lead. Check writer health, global replication lag, backups/WAL, connection pool, schema/migration status, extension/index state, and regional AWS health.
2. Stop destructive migration/maintenance and fence unsafe writers if integrity is in doubt. Preserve database/audit evidence; do not run ad hoc cleanup or mass update.
3. For local issue, restore service using approved database procedures. For regional failure, use the documented fenced Aurora Global Database failover plan; IC authorizes promotion and traffic movement.
4. Validate extension/version, schema, moderation/claim samples, reference asset manifest, vector dimension/model registry, sampled nearest-neighbor results, and application data path before allowing full traffic.
5. Record actual RPO/RTO, rebuild recovery posture, and schedule a corrective drill.

### 5.6 Redis/cache outage or session anomaly

1. Confirm TLS/endpoint, replication/failover, cache error rate, app fallback pressure, JWT validation, database connection headroom, and deployment/config changes.
2. Redis is non-authoritative: allow bounded cache-aside fallback only while PostgreSQL remains healthy. Enforce rate/backpressure before database exhaustion.
3. If session metadata is inconsistent, flush only the affected bounded projection namespace if approved; users must be revalidated by JWT/identity provider. Never use stale Redis projection to grant privileged access.
4. Recover Redis, monitor cache-hit recovery and database pressure, then review TTL/invalidation/connection settings.

### 5.7 EKS, network, or regional infrastructure failure

1. Confirm scope via AWS/EKS/ingress/DNS/CloudWatch, node/pod health, network policy, identity/IRSA, image registry, secrets, and deployment changes.
2. Roll back only the identified bad manifest/image digest using the approved deployment mechanism. Do not bypass private API/RBAC/network controls for speed.
3. For regional outage, follow the data failover runbook before shifting application traffic. Confirm the regional workload role, secrets, artifact replication, database role, Redis role, image digest, metrics, and alerts in the target region.
4. Restore monitoring/Alertmanager first enough to observe recovery; synthetic alerts must continue to use discard route.

## 6. Communication, evidence, and customer handling

Use one approved incident channel and one canonical incident document. The scribe records time, decision, actor, evidence link, command/change reference, customer impact, and next update. Separate technical speculation from confirmed facts. Preserve relevant immutable audit logs, CloudTrail, GitHub Actions metadata, Terraform plans, image digest/SBOM, database/ingestion records, and object hashes using access-controlled evidence storage.

The communications lead sends status updates only after IC approval. Do not state root cause, exposure scope, or recovery time as fact until supported by evidence. Customer/privacy/legal notifications follow contractual and legal requirements; technical responders should escalate that decision rather than improvising disclosure language.

## 7. Post-incident review and learning

Schedule a blameless review after every SEV1/SEV2 once service is stable and immediate evidence is preserved. Review detection, escalation, decision quality, impact, controls, communications, recovery, and customer experience. Identify what changed, contributing factors, what worked, what did not, and measurable prevention/mitigation items with owner/due date.

A finding is not closed until the remediation, alert/runbook/test update, and retest evidence are recorded. Security findings also require scope/exposure decision, secret/token handling, and threat-model update. Recurrent pages require alert tuning and capacity/workflow correction rather than normalizing fatigue.

## TL;DR

1. Page primary and secondary; establish an IC and scribe for every SEV1/SEV2.
2. Preserve evidence, assess scope, stabilize safely, and avoid destructive or broad changes without authorization.
3. Treat PostgreSQL/pgvector and private artifacts as canonical; Redis is rebuildable acceleration only.
4. Use fenced data failover before traffic failover. Validate data, vectors, claims, assets, roles, secrets, image, and monitoring in recovery region.
5. Keep incident communication factual, approved, and customer-safe.
6. Complete a blameless review, regression test, runbook/alert change, and retest before closure.

## References

[1]: https://csrc.nist.gov/pubs/sp/800/61/r3/final "NIST SP 800-61 Rev. 3: Incident Response Recommendations and Considerations"
