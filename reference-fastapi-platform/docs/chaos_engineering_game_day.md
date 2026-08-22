# Niko The Great - SYNTH NOW — Chaos Engineering Game Day

## 1. Objective and scope

This game day verifies that the multi-region Synth Now architecture behaves safely when the primary application region is unavailable to users or when database-path latency rises sharply. The objective is not to “break production.” The objective is to test stated hypotheses, validate observability and operating procedures, measure recovery behavior, and identify resilience gaps using **synthetic staging data** in an isolated AWS staging account.

> **Non-negotiable boundary:** No experiment may target production, real customer audio, production PagerDuty integration keys, production Aurora/Redis clusters, or an unapproved AWS account. A production experiment requires a separate written scope, change approval, customer-impact assessment, and an updated abort plan.

Gremlin scenarios recommend health checks to establish baseline health, halt unsafe experiments automatically, and verify recovery between steps.[1] LitmusChaos probes can execute before, during, and after an experiment and contribute to the experiment verdict.[2] This plan adopts those controls regardless of the chosen platform.

## 2. Experiment platform choice

| Approach | What it provides | Tradeoffs | Cost | Setup complexity |
|---|---|---|---|---|
| **Gremlin-managed game day** | Managed scenarios, health checks, scheduling, controlled target selection, reports, and a facilitation workflow. | Commercial tooling and agent/service integration must be reviewed; limit AWS/Kubernetes permissions tightly. | Vendor subscription may apply. | Moderate. |
| **LitmusChaos in the staging EKS cluster** | Kubernetes-native experiments, declarative CRDs, HTTP/Kubernetes/Prometheus probes, Git-controlled templates. | The team operates the control plane, RBAC, upgrades, experiment images, and reports. | Open-source software, plus staging infrastructure cost. | Higher. |
| **Lighter-weight controlled drill** | Route traffic only to the already healthy secondary environment or temporarily inject application-level delay through a pre-approved failure flag. | Covers fewer infrastructure failure modes and does not validate chaos-platform controls. | Lowest incremental cost. | Lowest. |

Do not select a platform only because it is familiar. Gremlin is a practical option when facilitation/reporting and centralized guardrails are the priority. LitmusChaos is suitable when experiment definitions must stay in the Kubernetes/Git workflow. The lighter drill is an appropriate first rehearsal while the team establishes baselines, runbooks, and recovery ownership.

## 3. Required readiness gates

The incident commander (IC), platform lead, data lead, security lead, primary on-call engineer, and scribe must be assigned before execution. The staging account, Terraform state prefix, Kubernetes context, database endpoint, and PagerDuty/Alertmanager synthetic route must be verified. Notify stakeholders that the exercise is staging-only and record the scheduled window.

| Gate | Required evidence | Abort before start when |
|---|---|---|
| Scope | Written experiment ID, target namespace/account/region, owner, duration, and synthetic-data confirmation. | A target could resolve to production or customer data. |
| Baseline | API health, authenticated synthetic query, private audio-job lifecycle, queue depth, vector-search latency, Aurora/Redis health, replication state, dashboards, and alert routing are healthy. | Any baseline check is degraded or unobservable. |
| Observability | Dashboards and log/audit access are working; the `synthetic=true` alert route discards test alerts rather than contacting PagerDuty. | Metrics/logs cannot prove impact or recovery. |
| Reversibility | Clear stop control, rollback steps, emergency contacts, and recovery owner are recorded. | The team cannot halt/reverse within the approved window. |
| Data | Backup/replication status is acceptable for staging and only seeded synthetic data is present. | Backup/restore or replica status is unknown. |

## 4. Common probes, abort conditions, and evidence

Use platform-native health checks or probes for the following controls. Prometheus thresholds must be configured from approved staging baselines; do not hard-code production SLOs into an experiment template without review.

| Control | When evaluated | Pass criterion | Abort condition | Evidence |
|---|---|---|---|---|
| Synthetic API health and authorized preset query | Before, continuously, after | Expected success from the intended healthy region. | Health unavailable, authorization regression, or unexpected cross-environment result. | Request IDs, region headers, dashboard link. |
| Audio-job lifecycle | Before, continuously, after | Synthetic job enters/finishes expected safe state without duplicate processing. | Job loss, double-processing, uncontrolled retry, or historical-claim boundary violation. | Job IDs, worker logs, queue metrics. |
| Vector-search service | Before, continuously, after | Candidate retrieval succeeds within approved staging baseline/tolerance. | Sustained errors, database overload, or result/evidence contamination. | p95/p99, error rate, sample IDs. |
| Aurora/pgvector health | Before, continuously, after | Writer/reader role and replication remain expected for scenario. | Data-integrity concern, unexpected writer promotion, schema/index error, or replication health deterioration. | Cluster events, connection/lag/health metrics. |
| Redis/cache behavior | Before, continuously, after | Cache may degrade to PostgreSQL fallback only within configured database headroom. | JWT/authorization state inconsistency or database saturation. | Cache hit/failure/fallback metrics. |
| Alerting | Before and during | Synthetic alerts follow discard route; real alerts retain normal policy. | A real PagerDuty incident is triggered or alert path is not observable. | Alertmanager status and event IDs. |

**Immediate stop procedure:** Stop the active scenario/ChaosEngine, remove or reverse the fault, pause traffic shifts, preserve logs/metrics/audit state, notify IC, classify the event under the incident runbook, and do not start the next experiment until recovery controls pass. A failed probe is a useful result; never override it merely to complete the agenda.

## 5. Game-day agenda

| Stage | Activity | Owner | Output |
|---|---|---|---|
| T-14 days | Confirm scope, approach, staging account, team, synthetic data, access/RBAC, platform version, rollback, and approval. | IC and platform lead. | Approved exercise charter. |
| T-7 days | Dry-run probes/alerts, rehearse stop control, review regional recovery runbook, and seed/validate synthetic queries/jobs. | Platform/data/security leads. | Baseline packet and corrected gaps. |
| T-0 | Baseline gate, communications, clocks, dashboards, experiment target labels, and evidence folder. | IC and scribe. | Go/no-go decision. |
| Exercise | Run one experiment at a time; observe, halt/recover, and re-baseline between experiments. | Experiment owner. | Experiment timeline and verdict. |
| T+1 day | Review measured behavior, defects, alert/runbook gaps, capacity impact, and approved follow-up work. | IC. | Blameless report and action register. |

## 6. Experiment matrix

### GD-0: Baseline and stop-control rehearsal

**Hypothesis.** Before failure injection, the team can prove the staged service is healthy, alerts are isolated, and the fault can be stopped quickly.

**Method.** Run all common probes with no fault. Trigger one synthetic Alertmanager event with `synthetic=true`; it must resolve to the discard route. Demonstrate the Gremlin halt control or Litmus ChaosEngine stop procedure without injecting fault.

**Success.** All baseline controls pass; the team can halt and document the stop control; no external page is generated.

**Abort.** Any missing dashboard, ambiguous account/region, alert misroute, or inaccessible rollback control.

### GD-1: Primary-region application isolation simulation

**Hypothesis.** When primary-region application endpoints are deliberately unavailable, traffic can be controlled toward the ready secondary EKS environment without bypassing identity, evidence, or data-role protections.

**Method.** Use an application/load-balancer/traffic-steering **staging-only** control to remove only the selected primary synthetic endpoint from service, or inject network blackhole into a labeled canary API workload. Verify the secondary EKS environment is already healthy before altering route weight. If using Gremlin, target only a pre-labeled staging service/namespace with health checks. If using Litmus, use a namespace-scoped network experiment with Prometheus/HTTP probes.

**Do not** simulate a real AWS regional outage by changing broad AWS account controls, deleting infrastructure, stopping Aurora global replication, or forcing unapproved Aurora promotion. The current Terraform foundation does not yet create a global public traffic manager; that is a prerequisite before a fully automated regional traffic-shift experiment can be considered.

**Success.** Synthetic requests show controlled secondary-route behavior; JWT validation, authorization, source/evidence boundaries, job handling, and observability remain correct. The data layer remains in its expected role; no uncontrolled writer change occurs.

**Abort.** Secondary readiness is not proven; any traffic reaches production; an unexpected database role change occurs; metrics/alerting are unavailable; or the experiment exceeds its approved impact envelope.

**Recovery.** Restore normal staging routing/network policy, wait for common probes to pass, validate no pending duplicate audio jobs, and document actual recovery time.

### GD-2: Database-path latency injection

**Hypothesis.** A bounded latency increase between a labeled staging API canary and Aurora/pgvector triggers detection, graceful application behavior, queue/backpressure controls, and safe recovery without incorrect matches or claim publication.

**Method.** Apply delay to a small, labeled canary traffic slice only. With Gremlin, use a scoped network latency fault against the canary database path and automatic health checks. With Litmus, use a namespace/pod/target-scoped network-delay experiment and continuous HTTP plus Prometheus probes. Keep the fault duration and percentage within the change-approved staging envelope; avoid packet loss and high blast radius in the first run.

**Success.** Dashboards show vector-search latency and database-path effect; application timeouts/retries remain bounded; safe limited/no-result behavior occurs where expected; the audio queue does not silently lose/duplicate work; Alertmanager raises the appropriate **synthetic** alert only; and recovery restores baseline.

**Abort.** Database saturation, error propagation outside canary scope, queue loss/duplication, cache/session authorization inconsistency, data writes/claims outside expected behavior, or inability to remove fault.

**Recovery.** Stop delay, observe database/queue/cache normalization, reconcile job state, review sample result provenance, and retain latency/error/capacity evidence.

### GD-3: Secondary-region readiness and recovery validation

**Hypothesis.** The secondary region is actually deployable/observable and can serve approved synthetic read-only/recovery-path checks after a primary application isolation drill.

**Method.** Validate secondary EKS workload identity, image digest, secrets injection, S3 replicated synthetic artifact availability, Aurora reader/role, Redis global datastore role, metrics, Alertmanager/Grafana access, and readiness endpoints. This is **not** a database failover. A writer promotion is a separate data-recovery exercise requiring the existing fenced Aurora Global Database runbook and explicit executive/data approval.

**Success.** Secondary readiness controls pass and all mismatches are documented. No primary writer or production traffic is affected.

**Abort.** Replica/data role ambiguity, missing encrypted asset, outdated image/secret, or missing observability.

## 7. Platform-specific implementation notes

For Gremlin, create a project/team restricted to the staging account and labeled staging Kubernetes targets. Use health checks tied to synthetic API endpoints and Prometheus dashboards, restrict testing windows, and do not grant broad AWS or cluster permissions. Gremlin’s scenario/health-check capabilities should enforce baseline, continuous, and post-recovery controls.[1]

For LitmusChaos, create a dedicated `chaos-staging` namespace, least-privilege service accounts, namespace selectors that exclude system and production namespaces, image pinning, network policies, and admission policy that rejects experiments without required labels. Use `SOT`/`Edge`/`Continuous`/`EOT` probe modes for baseline, ongoing, and recovery validation, and configure probe failure to stop rather than continue for critical checks.[2]

## 8. Metrics and decision record

The scribe records start/stop, intended target, actual affected scope, baseline and experiment metrics, region behavior, detection time, intervention time, recovery time, alert behavior, probe verdict, fault removal proof, data validation, and action items. Compare measurements to approved staging baselines rather than treating any illustrative number as an SLO. Document whether results validate the hypothesis, falsify it, or are inconclusive due to instrumentation/scope limitations.

## TL;DR

1. Start in an isolated staging account with synthetic data; no production targets or real customer media.
2. Pick Gremlin, LitmusChaos, or a lighter traffic/failure-flag drill after choosing the desired operational tradeoff.
3. Run baseline, continuous, and recovery probes. A failed critical probe stops the experiment.
4. First test primary application isolation and scoped database-path latency—do not force regional database failover in the first game day.
5. The current Terraform needs a reviewed global traffic-steering component before automated regional traffic-shift tests.
6. Re-baseline after every experiment; preserve evidence and create owned corrective work.

## References

[1]: https://www.gremlin.com/docs/fault-injection-scenarios "Gremlin Fault Injection Scenarios and Health Checks"
[2]: https://litmuschaos.github.io/litmus/experiments/concepts/chaos-resources/probes/litmus-probes/ "LitmusChaos Probes"
[3]: https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html "AWS Disaster Recovery Options in the Cloud"
