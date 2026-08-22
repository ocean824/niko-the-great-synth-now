# Synth Now AWS Terratest Suite

The Terratest suite is **staging-only**. It is intentionally inert unless an operator sets an explicit mode variable. It has three independent test modes:

| Mode | Environment flag | What it does | AWS mutation |
|---|---|---|---|
| Plan | `SYNTH_NOW_TERRATEST_PLAN=true` | Runs `terraform init` and `plan` against secure staging inputs. | None. |
| Existing stack verification | `SYNTH_NOW_TERRATEST_VERIFY_EXISTING=true` | Reads already-provisioned staging Terraform outputs and validates the approved account, distinct regional cluster names, and global cluster naming. | None. |
| Private bucket canary | `SYNTH_NOW_TERRATEST_CANARY=true` plus `SYNTH_NOW_TERRATEST_ALLOW_APPLY=YES-STAGING-ONLY` | Creates an isolated uniquely named private bucket, validates versioning/public-access protection with AWS APIs, and defers Terraform destroy. | Creates and destroys only the canary fixture. |

Terratest is a Go library intended to deploy real infrastructure, validate it, and undeploy it. That means the canary mode requires the strongest guardrail: isolated account, explicit confirmation, temporary credentials, monitoring, and post-test review.[1]

## Prerequisites

1. Create a dedicated AWS **staging** account, separate state prefix, bounded test execution role, short-lived credentials, and a secure `terraform.tfvars` file. Never point this test at a production account or production state key.
2. Install Go 1.24 or later, Terraform, and AWS credentials configured only for the approved staging account. The Terratest dependency currently requires Go 1.24; keep the local toolchain aligned with the staging workflow.
3. Use a role policy scoped to the fixture and permitted staging infrastructure. The plan/verify role should be read/plan only; the canary role needs only temporary S3/KMS/IAM permissions needed by the fixture. Do not use broad administrator credentials.
4. Set an AWS budget/CloudWatch alert and a test time window. Run one canary at a time.

## Plan-only example

```bash
cd infra/aws/test
export SYNTH_NOW_TERRATEST_ENVIRONMENT=staging
export SYNTH_NOW_TERRATEST_APPROVED_ACCOUNT_ID=123456789012
export SYNTH_NOW_TERRATEST_VAR_FILE=/secure/path/synth-now-staging.tfvars
export SYNTH_NOW_TERRATEST_PLAN=true
go test -v -run '^TestStagingPlan$' -timeout 30m
```

## Existing-stack verification example

```bash
cd infra/aws/test
export SYNTH_NOW_TERRATEST_ENVIRONMENT=staging
export SYNTH_NOW_TERRATEST_APPROVED_ACCOUNT_ID=123456789012
export SYNTH_NOW_TERRATEST_VAR_FILE=/secure/path/synth-now-staging.tfvars
export SYNTH_NOW_TERRATEST_VERIFY_EXISTING=true
export SYNTH_NOW_TERRATEST_STATE_BUCKET=private-staging-terraform-state
export SYNTH_NOW_TERRATEST_STATE_KEY=niko-synth-now/staging/terraform.tfstate
export SYNTH_NOW_TERRATEST_STATE_REGION=us-east-1
export SYNTH_NOW_TERRATEST_STATE_LOCK_TABLE=terraform-state-lock

go test -v -run '^TestExistingStagingOutputs$' -timeout 15m
```

## Canary example

```bash
cd infra/aws/test
export SYNTH_NOW_TERRATEST_ENVIRONMENT=staging
export SYNTH_NOW_TERRATEST_APPROVED_ACCOUNT_ID=123456789012
export SYNTH_NOW_TERRATEST_PRIMARY_REGION=us-east-1
export SYNTH_NOW_TERRATEST_CANARY=true
export SYNTH_NOW_TERRATEST_ALLOW_APPLY=YES-STAGING-ONLY

go test -v -run '^TestPrivateBucketCanary$' -timeout 30m
```

## Operational safeguards

The canary fixture intentionally tests only a private S3 bucket. It does not create EKS, Aurora, Redis, global replication, internet-facing endpoints, database records, production alerts, or application workloads. The test defers `terraform destroy`, but the test operator must still inspect the staging account, test logs, state lock, and cost dashboard if a test fails or is interrupted. Use a scheduled cleanup alarm/tag policy as an independent safety layer.

## References

[1]: https://terratest.gruntwork.io/ "Terratest"
