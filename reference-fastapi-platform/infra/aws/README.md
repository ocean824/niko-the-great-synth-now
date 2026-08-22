# Niko The Great - SYNTH NOW — AWS Terraform Foundation

This Terraform package provisions an AWS production foundation for the existing Niko The Great - SYNTH NOW application package. It creates two private regional VPCs, two private-endpoint EKS clusters, an Aurora PostgreSQL-compatible global database topology, a Redis Global Datastore topology, immutable/scanned ECR repositories, encrypted private S3 artifact/log buckets with cross-region replication, CloudWatch/SNS foundations, and EKS OIDC workload roles.

> **Intent:** This is an infrastructure foundation, not an instruction to run `apply` immediately. AWS engine availability, regional quotas, instance classes, Terraform provider behavior, naming, cost, DNS, identity provider, and security approvals must be verified in a dedicated staging account first.

## Architecture

| Component | Primary region | Secondary region | Recovery role |
|---|---|---|---|
| VPC and EKS | Private application cluster with private API endpoint | Equivalent recovery application cluster | Promote traffic only through an approved regional failover procedure. |
| Aurora PostgreSQL / pgvector | Single writable Aurora global-database cluster | Read-only Aurora global secondary cluster | Managed switchover/failover after compatibility and runbook checks. |
| Redis | Encrypted, TLS primary replication group | ElastiCache Global Datastore secondary member | Cache/session acceleration only; never canonical recovery data. |
| S3 artifacts/logs | Versioned, KMS-encrypted, public access blocked | KMS-encrypted replica bucket | Private authorized asset and audit-log recovery. |
| ECR | Immutable, scan-on-push repository | Regional replicated repository | Same approved image digest deployable in recovery region. |
| Workload access | EKS OIDC role permits scoped S3 and secret reads | Equivalent regional OIDC role | Prevents node-wide credentials and static cloud keys in pods. |

Aurora Global Database uses one writable primary region and read-only secondary regions. It supports controlled switchover/failover but has region, engine-version, and compatibility requirements; validate the exact version in both selected regions before deployment.[1] Aurora PostgreSQL can support `pgvector`; confirm the extension version and index behavior required by the Synth Now schema before migration.[2]

## What Terraform intentionally does **not** do

Terraform does not insert application secrets, Redis tokens, OAuth client secrets, PagerDuty keys, database application-user passwords, or TLS private keys. It creates empty regional application secret containers, manages Aurora’s primary master secret, and outputs references. Populate application secrets from an approved secret-management workflow after apply. Do not add secret values to `tfvars`, GitHub Actions YAML, or Terraform state.

Terraform also leaves the following as controlled post-provisioning operations: database schema migration, `CREATE EXTENSION vector`, least-privilege application database-user creation, external-secrets deployment, ALB/NLB controller installation, Prometheus Adapter installation, Alertmanager/PagerDuty secret mount, DNS cutover, and Aurora global failover. These operations must be versioned, gated, and rehearsed independently.

## Secure bootstrap

A remote Terraform state backend must be created **before** this stack. Use a separate protected platform account/project or bootstrap stack with an encrypted versioned S3 state bucket, DynamoDB lock table, KMS key, least-privilege IAM, access logging, and a restricted break-glass policy. Copy `environments/production/backend.hcl.example` into a secure location and replace placeholders outside source control.

Prepare inputs without writing secrets to files:

```bash
cd infra/aws
export TF_VAR_redis_auth_token='REPLACE_FROM_APPROVED_SECRET_STORE'
export TF_VAR_aurora_master_username='REPLACE_APPROVED_ADMIN_LOGIN'
terraform init -backend-config=/secure/path/backend.hcl
terraform fmt -recursive
terraform validate
terraform plan -var-file=/secure/path/production.tfvars -out=production.tfplan
```

Review the saved plan with infrastructure, database, security, and cost owners. Run `terraform apply production.tfplan` only from an approved protected environment. Ensure the execution identity cannot read arbitrary application secrets and that state access is tightly limited.

## Required post-apply checks

1. Confirm EKS public endpoint access is disabled and use a private runner/VPN/approved management path for cluster administration.
2. Confirm Aurora engine version exists in both regions and is approved for the needed pgvector extension. Run `SELECT extversion FROM pg_extension WHERE extname='vector';` after the controlled migration.[2]
3. Create least-privilege application DB roles, not application use of the Aurora master user. Place application connection configuration in the regional application secret.
4. Configure Kubernetes service accounts `synth-now-api` and `synth-now-worker` with the region’s `eks.amazonaws.com/role-arn` annotation from the Terraform output. Do not attach broad AWS permissions to the node role.
5. Deploy the existing Kubernetes manifests with regional image repository URL/digest, regional Aurora endpoint/secret reference, Redis TLS endpoint/secret reference, S3 bucket, and the OIDC role annotation.
6. Install the AWS Load Balancer Controller, External Secrets solution, Prometheus Adapter, ingress/TLS integration, Alertmanager/PagerDuty secret, and network policies through separately reviewed manifests or Helm releases.
7. Verify S3 versioning/replication, Aurora global replication health, Redis global replication health, ECR replication, backup schedules, CloudWatch logs, and synthetic failover/test procedures.

## Important limitations and decisions

The VPC module creates one NAT gateway per availability zone to avoid a single-AZ egress dependency. This provides stronger availability but increases cost. A lower-cost staging mode may consolidate NAT egress after a separate review; do not silently copy that compromise to production.

The EKS endpoint is private. Managed GitHub-hosted runners cannot directly reach it without a controlled private connectivity pattern. Use a self-hosted runner in the VPC, a private management network, or a separately approved secure deployment path. Do not enable broad public EKS endpoint access merely to simplify CI/CD.

The Aurora global secondary remains read-only until an intentional recovery procedure. Redis is replicated for locality and faster cache recovery, but the product must remain correct if it is completely empty. These boundaries preserve the source-backed evidence model.

## References

[1]: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html "Using Amazon Aurora Global Database"
[2]: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html "Using Aurora PostgreSQL as a Knowledge Base"
