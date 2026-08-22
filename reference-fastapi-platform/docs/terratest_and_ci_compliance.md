# Niko The Great - SYNTH NOW — Terratest and CI Compliance Operations

## 1. Testing strategy

Infrastructure testing must combine fast static checks with a tightly controlled real-cloud validation. The package uses three layers: Terraform format/validation and HCL structure checks on every change; policy/secret/dependency/workflow/container configuration scans on relevant pull requests; and Terratest against an isolated staging AWS account only after approval. Terratest is intentionally capable of real infrastructure deployment and teardown, so its canary remains narrow, uniquely named, and explicitly opt-in.[1]

| Layer | Trigger | AWS mutation | Purpose | Gate |
|---|---|---:|---|---|
| Static Terraform validation | Pull request/push | None | Format, provider/config validation, repository HCL invariants. | Required PR check. |
| Compliance/vulnerability scans | Pull request/push | None | Checkov Terraform policy, Trivy IaC/secret/container-config scan, Gitleaks, Python dependency audit, workflow lint. | Required PR check; no soft fail for high/critical policy/secret findings. |
| Terratest plan | Manually approved staging workflow | None | Verify provider/module compatibility with isolated staging inputs. | Protected staging environment. |
| Existing staging verification | Manually approved staging workflow | None | Verify approved account and core Terraform outputs. | Protected staging environment. |
| S3 private-bucket canary | Manually approved staging workflow + explicit confirmation | Only an ephemeral test fixture that is deferred for destroy | Confirm real AWS versioning/public-access controls work. | Protected staging environment, staging-only role, budget/monitoring. |

## 2. GitHub Actions workflows

`infrastructure-security.yml` runs on relevant pull requests and main-branch changes. It receives no AWS credentials. It validates Terraform with remote state disabled, scans Terraform with Checkov, scans configuration/secrets with Trivy, audits Python dependencies, scans repository history with Gitleaks, and lints workflows with Zizmor. Uploading security SARIF is the only reason that selected jobs receive `security-events: write`.

`staging-terratest.yml` is manual-only and uses the protected GitHub `staging` environment. It requests `id-token: write` only because it exchanges a GitHub OIDC token for short-lived AWS staging credentials. GitHub documents that OIDC removes the need to store long-lived cloud credentials in Actions and lets the cloud trust policy constrain which workflow identity can obtain the temporary role.[2]

| GitHub setting | Required value/control |
|---|---|
| Repository visibility | Keep the infrastructure repository private unless a deliberate security review approves otherwise. |
| Branch protection | Require passing API, Terraform, security, and review checks; restrict direct push to main. |
| `staging` environment | Require reviewers, restrict deployment branches/tags, and store staging credentials/configuration only here. |
| OIDC AWS trust | Restrict issuer, audience, repository identity, environment, and workflow/branch as supported by the current GitHub OIDC subject/claim format. Test with a nonproduction role. |
| `AWS_STAGING_TERRATEST_ROLE_ARN` | Environment secret pointing to a role limited to the isolated staging account. |
| `STAGING_TERRAFORM_TFVARS_B64` | Environment secret containing the base64-encoded staging variable file; never echo it. |
| `AWS_STAGING_*` values | Environment variables for account, regions, and remote-state identifiers. They must refer only to staging. |
| Action dependencies | Pin/review third-party actions according to organization policy; update deliberately after security review. |

## 3. Staging-only Terratest guardrails

The test suite refuses to run active modes unless `SYNTH_NOW_TERRATEST_ENVIRONMENT=staging`, the expected staging account ID is supplied, and the test mode is explicitly enabled. Canary mode is activated only with `SYNTH_NOW_TERRATEST_CANARY=true` and additionally requires the exact `SYNTH_NOW_TERRATEST_ALLOW_APPLY=YES-STAGING-ONLY` confirmation. The canary fixture contains only a unique private S3 bucket with versioning and public-access-block verification. It does not create or modify EKS, Aurora, Redis, global replication, DNS, production alerts, or application records.

Use distinct AWS roles for plan/verify/canary actions. Plan and existing-stack verification are read/plan roles. The canary role has a narrowly scoped temporary fixture policy, a short session, a budget alert, required tags, and cleanup monitoring. Do not reuse the Terraform deployment role or production account. If a canary fails/interruption occurs, stop concurrent tests, inspect the cloud account/state lock/cost dashboard, and complete cleanup through the documented incident/change path.

## 4. Scan policy and triage

| Scanner/control | Blocking condition | Normal remediation | Exception rule |
|---|---|---|---|
| Terraform format/validate | Syntax/format/provider validation failure | Fix source or version constraints; do not bypass. | None. |
| Checkov | Any organization-defined failing policy check. | Harden resource/exception with documented risk acceptance. | Time-bound exception approved by security/platform with tracked owner. |
| Trivy IaC/secret/config | High/critical configuration or secret finding. | Remove secret, restrict exposure, encrypt/resource-policy fix, or use approved suppression with rationale. | No suppression for exposed secret or public data path without security approval. |
| Gitleaks | Potential committed credential/secret. | Revoke/rotate first, remove history/exposure through security process, add test. | No simple allowlist for active credential material. |
| Dependency audit | Known vulnerable dependency under approved severity policy. | Upgrade/replace/patch or isolate with compensating control. | Documented, expiring risk acceptance. |
| Workflow lint | Dangerous token/action/workflow pattern. | Reduce permissions, pin/review action, isolate secret path. | Security/platform review required. |
| Terratest | Staging assertion/cleanup failure. | Investigate staging state/infrastructure and test logic. | Never rerun repeatedly against a possibly wrong account. |

A scan failure is triaged as either a real finding, false positive, environmental issue, or policy exception. Record tool, version, rule/CVE, affected asset, exploitability/context, owner, remediation, due date, and retest. Do not suppress a failure only to unblock a release; use a time-bound approved exception where needed and add a tracked follow-up.

## 5. Recommended rollout order

1. Merge static security workflow only after it passes in a non-production branch and scan thresholds are agreed.
2. Create protected GitHub `staging` environment and OIDC trust/role in the isolated AWS staging account.
3. Run Terratest plan mode; fix provider/module/state configuration issues.
4. Run existing-stack output verification mode against an approved pre-created staging foundation.
5. Conduct one monitored private-bucket canary with a platform engineer observing state, AWS tags, cost, and cleanup.
6. Make static checks required; keep Terratest manual until reliability and cost profile are understood.
7. Add a scheduled or release-gated staging verification only when test duration, account guardrails, and cleanup monitoring are proven.

## TL;DR

1. Static checks run automatically and never receive AWS credentials.
2. Real AWS tests are manual, staging-only, short-lived, guarded by account/mode confirmation, and limited to a private S3 canary.
3. GitHub OIDC provides short-lived staging credentials; restrict trust to the protected environment and exact repository/workflow identity.
4. Treat security scan failures as findings until triaged, time-bound, approved, and retested.
5. Never aim Terratest, plan/apply, or canary cleanup at production.

## References

[1]: https://terratest.gruntwork.io/ "Terratest"
[2]: https://docs.github.com/en/actions/concepts/security/openid-connect "GitHub Actions OpenID Connect"
