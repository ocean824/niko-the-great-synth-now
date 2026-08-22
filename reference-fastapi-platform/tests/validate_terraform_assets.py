from __future__ import annotations

from pathlib import Path

import hcl2

ROOT = Path(__file__).resolve().parents[1]
TERRAFORM_ROOT = ROOT / "infra" / "aws"


def parse_hcl(path: Path) -> dict:
    with path.open() as handle:
        return hcl2.load(handle)


def combined_text(paths: list[Path]) -> str:
    return "\n".join(path.read_text() for path in paths)


def main() -> None:
    tf_files = sorted(TERRAFORM_ROOT.rglob("*.tf"))
    assert tf_files, "Terraform package has no HCL files"
    for path in tf_files:
        parse_hcl(path)

    root_files = sorted(TERRAFORM_ROOT.glob("*.tf"))
    root_text = combined_text(root_files)
    assert 'provider "aws" {' in root_text
    assert 'alias  = "secondary"' in root_text
    assert 'module "eks_primary"' in root_text
    assert 'module "eks_secondary"' in root_text
    assert 'module "aurora_primary"' in root_text
    assert 'module "aurora_secondary"' in root_text
    assert 'aws_elasticache_global_replication_group' in root_text
    assert 'aws_s3_bucket_replication_configuration' in root_text
    assert 'aws_ecr_replication_configuration' in root_text
    assert 'aws_iam_openid_connect_provider' in combined_text(sorted((TERRAFORM_ROOT / "modules" / "eks").glob("*.tf")))

    network_text = combined_text(sorted((TERRAFORM_ROOT / "modules" / "network").glob("*.tf")))
    assert 'aws_nat_gateway' in network_text
    assert 'aws_vpc_endpoint' in network_text
    assert 'map_public_ip_on_launch = false' in network_text

    aurora_text = combined_text(sorted((TERRAFORM_ROOT / "modules" / "aurora").glob("*.tf")))
    assert 'aws_rds_global_cluster' in aurora_text
    assert 'storage_encrypted         = true' in aurora_text
    assert 'manage_master_user_password' in aurora_text
    assert 'deletion_protection' in aurora_text

    redis_text = combined_text(sorted((TERRAFORM_ROOT / "modules" / "redis").glob("*.tf")))
    assert 'transit_encryption_enabled' in redis_text
    assert 'at_rest_encryption_enabled' in redis_text
    assert 'automatic_failover_enabled' in redis_text

    s3_text = combined_text(sorted((TERRAFORM_ROOT / "modules" / "s3").glob("*.tf")))
    assert 'aws_s3_bucket_public_access_block' in s3_text
    assert 'aws_s3_bucket_versioning' in s3_text
    assert 'DenyInsecureTransport' in s3_text

    readme = (TERRAFORM_ROOT / "README.md").read_text()
    assert 'terraform init' in readme
    assert 'remote Terraform state backend' in readme
    assert (TERRAFORM_ROOT / "environments" / "production" / "terraform.tfvars.example").exists()
    assert (TERRAFORM_ROOT / "environments" / "production" / "backend.hcl.example").exists()
    print(f"Terraform HCL syntax and structural validation passed for {len(tf_files)} files")


if __name__ == "__main__":
    main()
