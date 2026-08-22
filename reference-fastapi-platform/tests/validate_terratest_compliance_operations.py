from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(relative: str) -> str:
    return (ROOT / relative).read_text()


def assert_contains(content: str, values: list[str], name: str) -> None:
    missing = [value for value in values if value not in content]
    assert not missing, f"{name} missing: {', '.join(missing)}"


def main() -> None:
    go_mod = text("infra/aws/test/go.mod")
    assert_contains(go_mod, ["github.com/gruntwork-io/terratest", "go 1.24.0"], "Terratest go.mod")

    terratest = text("infra/aws/test/staging_infrastructure_test.go")
    assert_contains(
        terratest,
        [
            "TestStagingPlan",
            "TestExistingStagingOutputs",
            "TestPrivateBucketCanary",
            "SYNTH_NOW_TERRATEST_ENVIRONMENT",
            "YES-STAGING-ONLY",
            "defer terraform.Destroy",
            "SYNTH_NOW_TERRATEST_APPROVED_ACCOUNT_ID",
        ],
        "Terratest suite",
    )
    assert "InitAndApply" in terratest and "TestPrivateBucketCanary" in terratest

    fixture = text("infra/aws/test/fixtures/private_bucket/main.tf")
    assert_contains(fixture, ["modules/s3", "provider \"aws\""], "Terratest fixture")

    security = text(".github/workflows/infrastructure-security.yml")
    assert_contains(
        security,
        [
            "terraform fmt -check -recursive",
            "terraform init -backend=false",
            "bridgecrewio/checkov-action",
            "aquasecurity/trivy-action",
            "gitleaks/gitleaks-action",
            "pip-audit",
            "zizmor",
            "permissions:",
        ],
        "Infrastructure security workflow",
    )

    staging = text(".github/workflows/staging-terratest.yml")
    assert_contains(
        staging,
        [
            "workflow_dispatch:",
            "environment: staging",
            "id-token: write",
            "aws-actions/configure-aws-credentials",
            "SYNTH_NOW_TERRATEST_ALLOW_APPLY",
            "YES-STAGING-ONLY",
            "concurrency:",
        ],
        "Staging Terratest workflow",
    )
    assert "pull_request:" not in staging, "Real AWS Terratest must not run from pull requests"

    incident = text("docs/incident_response_and_on_call.md")
    assert_contains(
        incident,
        [
            "SEV1 Critical",
            "Incident commander",
            "Suspected JWT, authorization, credential, or secret compromise",
            "Aurora/pgvector availability",
            "On-call rotation",
            "Post-incident review",
        ],
        "Incident/on-call runbook",
    )

    operations = text("docs/terratest_and_ci_compliance.md")
    assert_contains(
        operations,
        [
            "Static Terraform validation",
            "Terratest plan",
            "GitHub OIDC",
            "SYNTH_NOW_TERRATEST_CANARY",
        ],
        "Terratest/CI operations guide",
    )
    print("Terratest, compliance, and incident-operations asset validation passed")


if __name__ == "__main__":
    main()
