# AWS and Security Research Notes

Amazon Aurora Global Database uses one writable primary region and read-only secondary regions. AWS documents cross-region global replication, managed switchover/failover, and version compatibility requirements between primary and secondary clusters. Provisioning must pin an Aurora PostgreSQL version available in both selected regions and validate global-database failover compatibility before deployment. Source: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-global-database.html

Aurora PostgreSQL supports the `pgvector` extension in supported engine versions. AWS documentation shows that an HNSW index requires pgvector 0.5.0 or later and that the extension version can be verified from `pg_extension`. Source: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html

OWASP API Security 2023 emphasizes object-level authorization for ID-based access, authentication integrity, property/function authorization, resource-consumption controls, business-flow protection, SSRF controls, security configuration, API inventory, and safe third-party API consumption. Source: https://owasp.org/API-Security/editions/2023/en/0x11-t10/

Terraform must not be given secrets through tracked variables or state without a controlled remote backend and access policies. This package therefore uses AWS Secrets Manager for application secrets and marks sensitive Terraform outputs. Secrets still require secure backend, IAM, KMS, and state access controls before use.
