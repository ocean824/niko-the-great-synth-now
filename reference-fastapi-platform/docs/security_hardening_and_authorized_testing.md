# Niko The Great - SYNTH NOW — Security Hardening and Authorized Testing Guide

## 1. Purpose, authority, and scope

This guide protects the Synth Now production design without authorizing intrusive testing by default. It applies to the FastAPI service, OAuth2/OIDC/JWT resource server, Python SDK, WebSockets, audio uploads, official-source ingestion, PostgreSQL/pgvector, Redis, containers, EKS, AWS infrastructure, and CI/CD workflow.

> **Authorization gate:** Perform active scanning, fuzzing, load testing, account-flow tests, token-negative tests, or any request designed to trigger a control only against systems you own or are explicitly authorized to test. Obtain written scope, named targets, permitted accounts, test window, rate/concurrency caps, data-handling rules, an emergency stop contact, and rollback expectations. Use staging by default. Production tests must be low-risk, approved, observable, reversible, and coordinated with on-call staff.

OWASP identifies broken object authorization, broken authentication, broken property/function authorization, unrestricted resource consumption, sensitive business-flow abuse, SSRF, misconfiguration, inventory gaps, and unsafe third-party API use as core API risks.[1] This guide turns those risks into preventive controls and authorized test expectations.

## 2. Priority security baseline

| Priority | Control | Acceptance evidence | Owner |
|---|---|---|---|
| P0 | Production never accepts the development `X-User-Id` path. | Deployment configuration and an integration test show `SYNTH_NOW_AUTH_MODE=oauth_jwt`; forged development headers do not authenticate. | Application owner |
| P0 | Every ID-based object read/write performs subject, role, scope, ownership, and lifecycle-state authorization. | Role/ownership matrix tests cover claim, source, preset, audio-job, feedback, and moderation objects. | Application owner |
| P0 | JWT verification pins trusted issuer, audience, allowed asymmetric algorithms, JWKS source, and time claims. | Negative test fixtures for expired, future, wrong issuer/audience, unexpected algorithm, unknown key ID, and modified-token rejection. | Identity owner |
| P0 | Aurora, Redis, EKS API, uploads, monitoring, and control endpoints are private or restricted. | AWS/VPC/EKS configuration evidence and external exposure inventory. | Platform owner |
| P0 | Secrets never enter Git, Terraform variables/state intentionally, URLs, client logs, exception text, or metrics labels. | Secret scan, CI gate, state access review, and log sample. | Security owner |
| P1 | TLS, strict CORS/host policy, secure headers, request limits, rate controls, and safe error handling are enforced at edge and application. | Staging HTTP security/behavior checks. | Application/platform |
| P1 | Containers run as non-root with read-only filesystem, dropped capabilities, restricted Pod Security, resource limits, and digest-pinned signed/scanned images. | Kubernetes manifest/admission evidence and CI artifact attestation. | Platform owner |
| P1 | Ingestion follows approved sources, robots/terms policy, redirect/DNS controls, archive safeguards, static parsing, quarantine, and review-only publication. | Automated source-worker negative tests and review queue audit sample. | Data/ingestion owner |
| P2 | Security telemetry detects auth failures, permission denials, SSRF blocks, quarantine failures, anomalous use, cache fallback, and privileged actions without logging secrets/audio. | Dashboards, alerts, retention controls, and tabletop drill evidence. | Security/operations |

## 3. FastAPI and endpoint hardening

### 3.1 Authentication and authorization

The API must perform local authorization for each protected endpoint. Centralize authentication at the identity provider, but do not assume that valid authentication implies permission for a particular claim, source observation, preset artifact, audio job, feedback object, or moderator decision. Object-level checks must run whenever an identifier selects a record; this directly addresses OWASP’s API1 authorization risk.[1]

Use an explicit endpoint policy map. Record the required OAuth scope, allowed Synth Now roles, object relationship, and allowed state transition for every endpoint. Enforce it through dependencies/services, not frontend visibility. Separate `contributor`, `moderator`, `editor`, `operator`, and `service-worker` privileges. A service worker must not inherit human moderator capabilities. Prevent self-review, require evidence for publish, and preserve immutable decision snapshots.

Protect WebSocket connections like any other API request: validate the access token at connect time, bind the connection to one user/query, stop or revalidate when the token expires, authorize every requested job/event channel, cap subscriptions and message size/rate, and never accept an identity in a user-controlled WebSocket message after connection.

### 3.2 Request, response, and workflow controls

Use strict Pydantic request models with unknown fields forbidden on privilege-sensitive/mutable endpoints. Allowlist fields; never bind arbitrary JSON directly to ORM objects. Validate content type, lengths, pagination bounds, cursor format, enum values, IDs, audio duration/size, and filter complexity. Enforce request-size limits at the ALB/ingress and application level. Return bounded pagination and a stable rate-limited error model; do not expose raw database, internal host, stack trace, JWT, source credential, artifact path, or queue details.

Use server-side workflow state checks for claim moderation, source fetch/review, audio jobs, feedback, preset publication, and data ingestion. OWASP notes that individual endpoints can be authenticated but still be abused when the server does not enforce the intended sequence.[2] The database conditional claim/job updates already present in Synth Now are the correct pattern; extend the same principle to every publish/review/replace transition.

Keep `/metrics`, OpenAPI administrator surfaces, debug routes, database/admin tools, worker routes, object-store keys, and internal health detail off public ingress. Expose only a minimally informative public health endpoint. Maintain an endpoint/version inventory and remove deprecated routes rather than leaving them as undocumented compatibility paths.

### 3.3 Edge and transport controls

Terminate TLS with modern approved policy at the AWS edge and re-encrypt to the private workload where the organizational policy requires it. Redirect or reject plaintext HTTP. Set an explicit trusted-host allowlist and a strict CORS allowlist of exact frontend origins; never combine credentialed CORS with a wildcard origin. For browser-consumed API responses, use the applicable protections described by OWASP, including HSTS, `X-Content-Type-Options: nosniff`, conservative framing policy, and `Cache-Control: no-store` where sensitive responses must not be cached.[2]

Apply rate/concurrency limits separately to authentication, audio upload, recognition query, moderation, ingestion, vector search, and source-fetch paths. Limit request body size, upload count, queue occupancy per actor, vector query dimensions/filter cost, cursor page size, and total WebSocket messages. The limiter must fail safe for privileged actions; a Redis disruption may fall back for reviewed public preset reads only if the PostgreSQL and upstream capacity controls remain safe.

## 4. OAuth2, OIDC, JWT, and session hardening

Use authorization-code flow with PKCE for user-facing clients and client credentials only for narrowly scoped machine identities. Keep signing keys in the identity provider/HSM-managed control plane; use asymmetric signing and pin the expected allowed algorithms in resource-server configuration. Do not choose verification behavior from an untrusted token header.

The FastAPI verifier must validate signature, issuer, audience, expiration, not-before, and any required authorized-party/client claim before mapping roles/scopes. It must use a trusted configured JWKS URL, cache keys with bounded refresh, reject unknown key IDs/algorithm changes, and fail closed if a required key cannot be verified. OWASP advises verifying JWT integrity and standardized claims such as issuer, audience, expiration, and not-before, and warns against unsecured/algorithm-confusion patterns.[2] [3]

| JWT/session control | Required implementation | Authorized test expectation |
|---|---|---|
| Algorithm policy | Permit only the identity provider’s expected asymmetric algorithm(s); reject unsigned, symmetric, unexpected, or case-variant algorithm choices. | Controlled invalid-token fixtures receive `401`; no role or user context is created. |
| Issuer/audience | Exact allowlist match, not prefix/substring. | Wrong issuer/audience fixture is rejected. |
| Time validity | Enforce `exp`, `nbf`, max acceptable clock skew, short access-token lifetime. | Expired/future fixture is rejected; valid near-boundary fixture behaves according to documented skew. |
| Key selection | Resolve `kid` only in the pinned JWKS set; never use token-supplied URL/file/SQL path. | Unknown key ID is rejected without network/file access outside the configured JWKS client. |
| Roles/scopes | Map only documented claims, default deny unknown role/scope combinations, and re-check object relationship per endpoint. | Matrix shows no contributor/moderator/editor escalation. |
| Revocation/logout | Use short-lived access tokens; where immediate invalidation is required, retain bounded `jti` denylist/identity-status check outside cache-only state. | Disabled user/logout fixture loses access within documented revocation period. |
| Redis session projection | Cache only minimal already-verified metadata, bounded by token expiration; validate JWT every request. | Redis flush/outage causes safe re-projection or controlled denial, never privilege persistence. |
| Logging | Redact `Authorization`, cookies, refresh tokens, codes, and raw JWTs from logs/errors/traces. | Log inspection after negative tests contains correlation IDs but not credentials. |

## 5. Audio upload, source ingestion, and model safety

Keep audio upload and VST preset ingestion as high-risk boundaries. Stream uploads into private quarantine. Verify server-observed size, signature/type, hash, quota, tenant/actor, archive traversal/bomb conditions, and malware scan outcome before parsing. Never execute plug-ins, installers, scripts, DAW projects, archive hooks, or untrusted media metadata. Store only approved content in private object storage; create short-lived server-generated download URLs only after authorization.

Maintain a default-deny official-source registry for web ingestion. It must constrain permitted scheme/domain/port/path/action, request rate, redirect count, maximum bytes, DNS/IP range, robots/terms decision, HTTP content type, and parser mode. Resolve and validate every redirect again. Block link-local, loopback, private, metadata-service, and unexpected address ranges; prohibit user-controlled URLs from reaching arbitrary network destinations. This is the operational control for OWASP SSRF and unsafe-consumption risks.[1]

Audio/vector results are inferences, not historical production facts. Keep artifact warnings, source-bleed state, feature/model version, confidence dimensions, and `historical_claim_allowed=false` on all inference paths. Only source-backed moderated claims become published production facts.

## 6. Container and Kubernetes runtime hardening

The existing manifests already use non-root user/group, dropped Linux capabilities, read-only root filesystem, disabled automatic service-account token mounts, resource limits, and private upload storage. Harden the surrounding cluster with the following controls.

| Area | Required control | Verification |
|---|---|---|
| Image build | Minimal pinned base images, non-root `USER`, no package manager/debug shell in runtime stage, SBOM, vulnerability scan, provenance/signature, immutable ECR tags. | CI policy blocks unscanned/unsigned critical images; deployment uses SHA-256 digest. |
| Pod security | Namespace Pod Security Admission `restricted` in audit/warn before enforce; `allowPrivilegeEscalation: false`, `runAsNonRoot`, capabilities drop all, `RuntimeDefault` seccomp, AppArmor/SELinux where supported. | Admission test rejects privileged/host namespace/root/capability-add manifest. |
| RBAC/IRSA | No `system:masters`; least-privilege namespace roles; IRSA service account per workload; no broad node role access; no static AWS keys. | `kubectl auth can-i` matrix and IAM policy simulation show expected deny by default. |
| Network | Default-deny ingress/egress policies, explicit API↔Aurora/Redis/S3/DNS/identity paths, metadata endpoint restrictions, private EKS API, no public database/cache. | Network-policy test verifies disallowed cross-namespace/external route fails. |
| Secrets | External Secrets/CSI preferred, KMS encryption, bound service tokens, no ConfigMap secrets, no secret in env where file mount is feasible. | Repository/state/log/manifest secret scan and in-cluster mount review. |
| Runtime observability | Audit logs, runtime/container events, image inventory, admission denials, abnormal restarts, privilege changes, and egress anomalies collected with retention/access controls. | Incident drill proves an alert links to a usable sanitized trace/audit record. |
| Capacity | ResourceQuota/LimitRange, image pull constraints, PodDisruptionBudget, HPA caps, queue limits. | Load test shows reject/backpressure before database/cache exhaustion. |

Kubernetes’ security checklist recommends restricting public Kubernetes/kubelet exposure, applying default-deny network policies, enforcing pod security, limiting resource consumption, using nonprivileged/digest-pinned scanned images, and keeping secrets out of ConfigMaps.[4]

## 7. AWS and Terraform hardening

Use AWS Organizations/service-control policies, CloudTrail/CloudWatch audit, AWS Config/Security Hub/GuardDuty or organizational equivalents, IAM Access Analyzer, KMS key policies, VPC flow logs, private endpoints, and restricted egress aligned to the organization baseline. Enforce MFA/SSO and short-lived assumed roles for administrators. Separate development, staging, and production accounts. Apply a break-glass policy that is time-bound, logged, reviewed, and never used for routine deployment.

Terraform remote state is sensitive infrastructure data. Keep it in a separate encrypted, versioned, access-logged bucket with locking and no public exposure. Limit state readers/writers, forbid `terraform apply` from unapproved local environments, scan plans and source for secrets, and use saved reviewed plans. Do not accept a generated plan from an untrusted pull request. Require a second approver for production plans that change identity, network, database, KMS, backup/deletion protection, public exposure, or data-replication resources.

Configure Aurora/Redis only in private subnets/security groups; require encryption in transit and at rest; use an application DB user rather than master credentials; and verify backups, global replication, object replication, and restore exercise evidence. The Terraform package’s multi-region architecture is a foundation, not a substitute for tested failover.

## 8. CI/CD and supply-chain controls

Use GitHub Actions OIDC with repository, branch/tag, workflow, and protected-environment conditions. Prefer pinned action commits or verified organization-approved action versions. Split build/publish and deploy credentials. The deployment credential must not be a Terraform-admin credential. Protect workflows from untrusted pull request write paths, do not expose secrets to forks, and require branch protection plus environment approval.

CI must run unit/integration, authorization regression, JWT negative, deployment-asset, Terraform HCL, dependency/license, secret, IaC, container-image, and SBOM/provenance checks. Fail builds on unresolved severity thresholds defined by the security owner. Production promotion deploys an immutable image digest after staging evidence, migration compatibility, monitoring, and rollback validation.

## 9. Authorized testing plan

### 9.1 Engagement checklist

| Item | Required before activity |
|---|---|
| Written authorization | System owner, dates, target URLs/accounts/regions, and permitted test class documented. |
| Environment | Staging/sandbox preferred; production only for approved low-impact confirmation. |
| Data | Synthetic accounts/audio/preset references; no unapproved customer media or credentials. |
| Rate and safety | RPS/concurrency limits, no destructive payloads, no broad account enumeration, no persistence, no production availability stress. |
| Monitoring | On-call staff, dashboards, logging, incident channel, and emergency stop contact active. |
| Boundaries | Explicitly exclude cloud control plane, unrelated AWS accounts, identity provider administration, social engineering, physical testing, and third parties unless separately approved. |
| Reporting | Reproducible evidence, severity rationale, affected asset, safe remediation, retest evidence, and disclosure handling. |

### 9.2 Staged test matrix

| Test class | Safe method | Expected secure behavior | Evidence |
|---|---|---|---|
| Object authorization | Use two synthetic users/roles and their own recorded IDs; attempt only approved cross-account access in staging. | API returns deny/not-found according to policy and never leaks object metadata. | Automated role/ownership tests plus sanitized request IDs. |
| Function authorization | Call moderation/editor/admin routes using each documented synthetic role. | Only intended roles/scopes reach the operation; self-review/state violations fail. | Endpoint policy matrix. |
| JWT verification | Use test-issuer fixtures for expired, future, wrong issuer/audience, changed body, unapproved algorithm, and unknown key ID. | No token fixture yields an authenticated principal except the valid intended case. | `401`/safe deny and no sensitive log output. |
| OAuth flow | Test redirect URI, PKCE, state/nonce, client binding, consent/session/logout behavior in the identity-provider staging tenant. | No open redirect, code replay, token leakage, or cross-client acceptance. | Identity-provider audit and automated flow test. |
| Input/HTTP | Contract/fuzz tests constrained to staging limits: malformed body, oversized body, unexpected field/type, pagination/filter extremes, unsupported content/method. | Valid 4xx/429/413 response, no stack trace, bounded CPU/queue/db use. | Error/log/metric sample. |
| Upload/archive | Synthetic benign malformed/oversized/wrong-type/archive-edge samples. | Quarantine/reject; no execution; no public artifact; review record retained. | Quarantine audit and object lifecycle evidence. |
| Ingestion/SSRF | Controlled source-registry tests using non-routable/test endpoints and allowed official fixture domain. | Unapproved destinations/redirects/private ranges fail before request; approved fixture becomes review-only observation. | Source-worker decision/audit log. |
| Cache/session | Redis flush/outage simulation and token-expiry/logout test. | JWT still revalidated; privileged action never uses stale session; reviewed reads fall back only within capacity protection. | Integration test/dashboard. |
| Container/Kubernetes | Manifest policy/admission and isolated runtime tests, not node-escape experimentation on shared infrastructure. | Privileged/root/host/network/unsafe image manifests denied; least-privilege workload succeeds. | Admission/audit result. |
| AWS/configuration | IaC scan, IAM policy simulation, security-group exposure audit, encrypted storage/backup/CloudTrail checks. | No public DB/cache/cluster admin path; only intended roles/resources reachable. | Policy and configuration report. |
| Resilience | Approved synthetic alerts, queue/Redis fallback, DB replica/backup restore drills. | No real PagerDuty page from test routes; data controls remain correct through degradation. | Runbook timeline and RPO/RTO evidence. |

Do not attempt credential cracking, privilege escalation beyond documented synthetic accounts, evasion of rate limits, denial-of-service, mass enumeration, malware execution, or attacks against AWS control plane/identity providers in this program. If a controlled test reveals suspected compromise, stop active testing, preserve evidence, notify the incident contact, and follow the incident-response plan.

## 10. Remediation and release gates

1. Triage findings by exploitability, impact on audio/privacy/evidence integrity, blast radius, compensating controls, and recoverability.
2. Fix P0 before release. For authorization, token, secret, public-exposure, arbitrary-fetch, code-execution, or data-integrity findings, block affected production promotion until fix and retest are accepted.
3. Add a regression test for every confirmed defect. Update threat model, endpoint policy map, runbook, alert, and owner if the finding changes operational risk.
4. Rotate any exposed token/key/secret, invalidate affected sessions/artifacts, audit relevant actions, and decide disclosure obligations with legal/security leadership.
5. Re-run the exact approved test case and record evidence. Do not mark fixed based only on code review.

## TL;DR

1. Default deny: exact endpoint roles/scopes plus per-object ownership/state checks.
2. Validate JWT signature and pinned issuer/audience/algorithm/time claims on every request; cache only already-verified minimal metadata.
3. Keep all control, database, Redis, object, and metrics surfaces private; route only the public API through hardened TLS edge controls.
4. Keep uploads and source fetches in quarantine/default-deny pipelines; never execute untrusted plug-ins, archives, scripts, or remote destinations.
5. Use rootless digest-pinned scanned containers, restricted pods, IRSA, default-deny network, and no secrets in Git/state/logs.
6. Test only with explicit authorization, staging synthetic data, bounded traffic, monitoring, emergency stop, and a documented retest/remediation loop.

## References

[1]: https://owasp.org/API-Security/editions/2023/en/0x11-t10/ "OWASP API Security Top 10 — 2023"
[2]: https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html "OWASP REST Security Cheat Sheet"
[3]: https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/06-Session_Management_Testing/10-Testing_JSON_Web_Tokens "OWASP Testing JSON Web Tokens"
[4]: https://kubernetes.io/docs/concepts/security/security-checklist/ "Kubernetes Security Checklist"
