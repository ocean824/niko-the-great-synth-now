# Niko The Great - SYNTH NOW — AWS Terraform Deployment Runbook

## Scope and deployment boundary

The Terraform package at [`infra/aws/`](../infra/aws/) provisions the AWS platform foundation. The existing FastAPI source, Kubernetes manifests, Alertmanager configuration, Grafana dashboards, PostgreSQL schema migration, and operational documents remain separate layers. This separation is deliberate: changing an EKS cluster, modifying a database schema, rotating a secret, and deploying an application image require different approvals and rollback strategies.

The target design has a writable **primary** AWS Region and a prepared **secondary** recovery Region. Both contain private EKS clusters. The Aurora Global Database primary accepts canonical writes, while the secondary is read-only until an intentional recovery operation. Redis remains acceleration state. Its loss must not affect canonical records, claims, vectors, or access-control decisions.

| Layer | Terraform action | Post-provision application action | Approval gate |
|---|---|---|---|
| Network/EKS | Creates private VPCs, NAT egress, private endpoints, EKS, node groups, OIDC providers. | Reach cluster from a controlled private management path; install ingress/controller/add-ons. | Platform and security review. |
| Aurora/pgvector | Creates encrypted regional clusters and global topology. | Create least-privilege DB users, enable `vector`, apply versioned schema/migrations, validate indexes. | Database owner review. |
| Redis | Creates encrypted TLS regional members/global datastore. | Set `REDIS_URL` with TLS, use secret reference, validate cache fallback. | Platform and application review. |
| S3/ECR | Creates encrypted replicated buckets and immutable scan-on-push image repositories. | Push signed/approved image digest, grant only IRSA workload access, wire artifact prefix controls. | Delivery and security review. |
| Secrets/OIDC | Creates empty secret containers and OIDC workload roles. | Insert approved secret versions and annotate service accounts with regional role ARN. | Security owner review. |

## 1. Bootstrap an isolated Terraform backend

Create the state S3 bucket, state KMS key, DynamoDB lock table, least-privilege Terraform execution role, log/audit trail, and recovery policy in a dedicated platform bootstrap stack. The state bucket must be encrypted, versioned, private, and accessed only by named deployment roles. It must not share an administration boundary with the application buckets.

Copy `infra/aws/environments/production/backend.hcl.example` to an approved secure local path and set the account-specific values. Copy `terraform.tfvars.example` to an approved secure local path. Never commit either populated file.

```bash
cd infra/aws
export TF_VAR_redis_auth_token="$(secure-secret-read --name synth-now/production/redis-auth-token)"
export TF_VAR_aurora_master_username="synthnow_admin"
terraform init -backend-config=/secure/path/backend.hcl
terraform fmt -recursive
terraform validate
terraform plan -var-file=/secure/path/production.tfvars -out=production.tfplan
```

Review the plan manually. Check every region, CIDR, bucket, KMS key, endpoint exposure setting, engine version, instance class, node size, and deletion-protection setting. Apply only the reviewed saved plan from an approved deployment environment. The `aws` provider credentials used for plan/apply should be short-lived, logged, and tied to an explicit change request.

## 2. Verify the AWS foundation

After apply, verify the following before any workload is deployed:

1. The EKS API endpoints are private and accessible only through the approved management network. Do not enable public endpoint access just to make a hosted CI runner work.
2. Each regional VPC has private application subnets, the expected NAT/VPC endpoint design, flow logs if enabled by the organization baseline, and no public database/cache endpoint.
3. Aurora Global Database contains the intended primary and secondary regional clusters. Confirm engine/patch compatibility in both regions; AWS notes that managed global switchovers/failovers can have compatibility requirements.[1]
4. Confirm the selected Aurora PostgreSQL engine supports the required `pgvector` extension version. Run the extension query only through a controlled migration connection.[2]
5. Confirm ElastiCache transit and at-rest encryption, AUTH token behavior, multi-AZ/failover, and global replication health.
6. Confirm artifact/log buckets have public access blocks, KMS encryption, versioning, TLS-only policy, and completed cross-region replication.
7. Confirm ECR tag immutability, scan-on-push, image replication, and the preferred digested image reference.
8. Confirm Terraform state is encrypted, versioned, locked, access logged, and unavailable to general application users.

## 3. Regional application configuration

Use **External Secrets** or an equivalent in-cluster controller to read the appropriate regional `application` secret. The secret version should include only the connection/configuration fields required by the application, such as the private Aurora endpoint, an application-specific database user/password (not master), Redis TLS endpoint/AUTH token, S3 bucket/prefix, OAuth issuer/audience/JWKS URL, metrics token, and PagerDuty routing key reference.

Create separate least-privilege application database roles through a migration/bootstrap job. The master secret created by Aurora is for administration and recovery, not regular FastAPI or worker use. The application secret should be rotated independently, and all rotation must be tested against connection pools and worker leases.

Annotate the regional Kubernetes service accounts:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: synth-now-api
  namespace: synth-now
  annotations:
    eks.amazonaws.com/role-arn: REPLACE_WITH_PRIMARY_OR_SECONDARY_WORKLOAD_ROLE_ARN
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: synth-now-worker
  namespace: synth-now
  annotations:
    eks.amazonaws.com/role-arn: REPLACE_WITH_PRIMARY_OR_SECONDARY_WORKLOAD_ROLE_ARN
```

Use the Terraform workload-role output from the **active** region. Configure the FastAPI and worker pods to use the private endpoints, certificate validation, least-privilege S3 prefix restrictions, and an image **digest**, not a mutable tag.

## 4. Add-on and deployment order

Install the following in each cluster through independently version-pinned Helm/Kustomize releases. Do not treat the Terraform module as a substitute for in-cluster policy configuration.

1. EKS operational add-ons required by the approved cluster baseline, including storage and networking components.
2. AWS Load Balancer Controller or the organization-approved ingress implementation; keep internal monitoring endpoints outside public ingress.
3. External Secrets or an equivalent secret-injection controller with least-privilege IRSA access.
4. Metrics Server, Prometheus Operator/Prometheus, Prometheus Adapter, Grafana, and Alertmanager. Confirm the external metric adapter exposes `synthnow_api_rps` and `synthnow_audio_job_queue_depth` before applying the HPA.
5. Policy enforcement: Pod Security Admission labels, NetworkPolicies, image verification policy, admission controls, and namespace resource quotas.
6. Synth Now database migration Job, followed by the API, worker, Redis/Alertmanager/monitoring manifests as applicable to the managed AWS services.

The included self-hosted PostgreSQL/Redis Kubernetes StatefulSets are **development/reference** assets. In AWS production, point the app to Aurora and ElastiCache; do not deploy a second canonical in-cluster PostgreSQL or Redis cluster.

## 5. CI/CD integration

Use GitHub Actions only with short-lived AWS OIDC credentials bound to a specific repository, branch/tag, and protected environment. The private EKS endpoint requires a self-hosted runner in the management network or another reviewed private connectivity method. The deployment role should be split: one narrowly scoped role for image publishing and a separate environment-protected role for cluster deployment. Do not grant a public hosted runner general EKS or Terraform-admin access.

The promotion sequence is: run tests and static validation; build and scan; create an immutable image digest and provenance/SBOM; deploy to staging; execute synthetic Alertmanager/Redis fallback and health checks; approve production; apply the reviewed infra plan only when necessary; deploy the exact digest; verify rollout and external metrics; retain a rollback reference. Database migrations require their own forward/backward compatibility gate.

## 6. Regional failover integration

During a regional failover, freeze canonical writes, follow the Aurora Global Database failover runbook, and verify the promoted region’s database, extension/version, app secret, object-store replication, Redis behavior, service-account role, and ECR image availability before routing traffic. Only then change the global traffic record/load-balancer policy under the incident commander’s approval.

After recovery, rebuild Redis cache/session projections from PostgreSQL and verified JWTs. Do not restore a cache snapshot as canonical data. Re-establish the old region as a recovery region only after the incident record, data reconciliation, replication health, and new recovery posture are complete.

## References

[1]: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html "Using Amazon Aurora Global Database"
[2]: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html "Using Aurora PostgreSQL as a Knowledge Base"
