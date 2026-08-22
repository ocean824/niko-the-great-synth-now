locals {
  name = "${var.project_name}-${var.environment}"
}

module "network_primary" {
  source = "./modules/network"

  name               = "${local.name}-primary"
  vpc_cidr           = var.primary_vpc_cidr
  availability_zones = var.availability_zones_per_region
  cluster_tag        = "${local.name}-primary"
}

module "network_secondary" {
  source = "./modules/network"
  providers = {
    aws = aws.secondary
  }

  name               = "${local.name}-secondary"
  vpc_cidr           = var.secondary_vpc_cidr
  availability_zones = var.availability_zones_per_region
  cluster_tag        = "${local.name}-secondary"
}

module "observability_primary" {
  source = "./modules/observability"

  name        = "${local.name}-primary"
  alert_email = var.alert_email
}

module "observability_secondary" {
  source = "./modules/observability"
  providers = {
    aws = aws.secondary
  }

  name        = "${local.name}-secondary"
  alert_email = var.alert_email
}

module "eks_primary" {
  source = "./modules/eks"

  name                = "${local.name}-primary"
  kubernetes_version  = var.eks_version
  private_subnet_ids  = module.network_primary.private_subnet_ids
  node_instance_types = var.eks_node_instance_types
  node_min_size       = var.eks_node_min_size
  node_desired_size   = var.eks_node_desired_size
  node_max_size       = var.eks_node_max_size
}

module "eks_secondary" {
  source = "./modules/eks"
  providers = {
    aws = aws.secondary
  }

  name                = "${local.name}-secondary"
  kubernetes_version  = var.eks_version
  private_subnet_ids  = module.network_secondary.private_subnet_ids
  node_instance_types = var.eks_node_instance_types
  node_min_size       = var.eks_node_min_size
  node_desired_size   = var.eks_node_desired_size
  node_max_size       = var.eks_node_max_size
}

module "aurora_primary" {
  source = "./modules/aurora"

  name                      = "${local.name}-primary"
  global_cluster_identifier = "${local.name}-global"
  create_global_cluster     = true
  is_primary                = true
  engine_version            = var.aurora_engine_version
  database_name             = var.aurora_database_name
  master_username           = var.aurora_master_username
  instance_class            = var.aurora_instance_class
  backup_retention_days     = var.backup_retention_days
  deletion_protection       = var.enable_deletion_protection
  vpc_id                    = module.network_primary.vpc_id
  private_subnet_ids        = module.network_primary.private_subnet_ids
  availability_zones        = module.network_primary.availability_zones
  application_cidrs         = [var.primary_vpc_cidr]
}

module "aurora_secondary" {
  source = "./modules/aurora"
  providers = {
    aws = aws.secondary
  }

  name                      = "${local.name}-secondary"
  global_cluster_identifier = module.aurora_primary.global_cluster_id
  create_global_cluster     = false
  is_primary                = false
  engine_version            = var.aurora_engine_version
  database_name             = var.aurora_database_name
  master_username           = var.aurora_master_username
  instance_class            = var.aurora_instance_class
  backup_retention_days     = var.backup_retention_days
  deletion_protection       = var.enable_deletion_protection
  vpc_id                    = module.network_secondary.vpc_id
  private_subnet_ids        = module.network_secondary.private_subnet_ids
  availability_zones        = module.network_secondary.availability_zones
  application_cidrs         = [var.secondary_vpc_cidr]
}

module "redis_primary" {
  source = "./modules/redis"

  name                      = "${local.name}-primary"
  vpc_id                    = module.network_primary.vpc_id
  private_subnet_ids        = module.network_primary.private_subnet_ids
  application_cidrs         = [var.primary_vpc_cidr]
  node_type                 = var.redis_node_type
  num_cache_clusters        = var.redis_num_cache_clusters
  auth_token                = var.redis_auth_token
  cloudwatch_log_group_name = module.observability_primary.redis_log_group_name
  is_primary                = true
}

resource "aws_elasticache_global_replication_group" "redis" {
  global_replication_group_id_suffix = "${var.project_name}-${var.environment}"
  primary_replication_group_id        = module.redis_primary.replication_group_id
  global_replication_group_description = "${local.name} Redis cache and bounded session projection"
}

module "redis_secondary" {
  source = "./modules/redis"
  providers = {
    aws = aws.secondary
  }

  name                        = "${local.name}-secondary"
  vpc_id                      = module.network_secondary.vpc_id
  private_subnet_ids          = module.network_secondary.private_subnet_ids
  application_cidrs           = [var.secondary_vpc_cidr]
  node_type                   = var.redis_node_type
  num_cache_clusters          = var.redis_num_cache_clusters
  auth_token                  = var.redis_auth_token
  cloudwatch_log_group_name   = module.observability_secondary.redis_log_group_name
  is_primary                  = false
  global_replication_group_id = aws_elasticache_global_replication_group.redis.global_replication_group_id
}

resource "aws_iam_role" "artifact_replication" {
  name = "${local.name}-artifact-replication"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

module "artifacts_secondary" {
  source = "./modules/s3"
  providers = {
    aws = aws.secondary
  }

  name                 = "${local.name}-artifacts-secondary"
  bucket_name          = "${var.artifact_bucket_name}-${var.secondary_region}"
  replication_role_arn = aws_iam_role.artifact_replication.arn
  replication_key_role = "destination"
}

module "artifacts_primary" {
  source = "./modules/s3"

  name                 = "${local.name}-artifacts-primary"
  bucket_name          = var.artifact_bucket_name
  replication_role_arn = aws_iam_role.artifact_replication.arn
  replication_key_role = "source"
}

module "logs_secondary" {
  source = "./modules/s3"
  providers = {
    aws = aws.secondary
  }

  name                 = "${local.name}-logs-secondary"
  bucket_name          = "${var.logs_bucket_name}-${var.secondary_region}"
  replication_role_arn = aws_iam_role.artifact_replication.arn
  replication_key_role = "destination"
}

module "logs_primary" {
  source = "./modules/s3"

  name                 = "${local.name}-logs-primary"
  bucket_name          = var.logs_bucket_name
  replication_role_arn = aws_iam_role.artifact_replication.arn
  replication_key_role = "source"
}

data "aws_iam_policy_document" "artifact_replication" {
  statement {
    effect = "Allow"
    actions = [
      "s3:GetReplicationConfiguration",
      "s3:ListBucket",
    ]
    resources = [
      module.artifacts_primary.bucket_arn,
      module.logs_primary.bucket_arn,
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:GetObjectVersionForReplication",
      "s3:GetObjectVersionAcl",
      "s3:GetObjectVersionTagging",
    ]
    resources = [
      "${module.artifacts_primary.bucket_arn}/*",
      "${module.logs_primary.bucket_arn}/*",
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:ReplicateObject",
      "s3:ReplicateDelete",
      "s3:ReplicateTags",
    ]
    resources = [
      "${module.artifacts_secondary.bucket_arn}/*",
      "${module.logs_secondary.bucket_arn}/*",
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
    ]
    resources = [
      module.artifacts_primary.kms_key_arn,
      module.logs_primary.kms_key_arn,
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "kms:Encrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]
    resources = [
      module.artifacts_secondary.kms_key_arn,
      module.logs_secondary.kms_key_arn,
    ]
  }
}

resource "aws_iam_role_policy" "artifact_replication" {
  name   = "${local.name}-artifact-replication"
  role   = aws_iam_role.artifact_replication.id
  policy = data.aws_iam_policy_document.artifact_replication.json
}

resource "aws_s3_bucket_replication_configuration" "artifacts" {
  bucket = module.artifacts_primary.bucket_id
  role   = aws_iam_role.artifact_replication.arn

  rule {
    id     = "replicate-approved-artifacts"
    status = "Enabled"

    filter {}

    delete_marker_replication {
      status = "Enabled"
    }

    destination {
      bucket        = module.artifacts_secondary.bucket_arn
      storage_class = "STANDARD"

      encryption_configuration {
        replica_kms_key_id = module.artifacts_secondary.kms_key_arn
      }
    }
  }

  depends_on = [aws_iam_role_policy.artifact_replication]
}

resource "aws_s3_bucket_replication_configuration" "logs" {
  bucket = module.logs_primary.bucket_id
  role   = aws_iam_role.artifact_replication.arn

  rule {
    id     = "replicate-logs"
    status = "Enabled"

    filter {}

    delete_marker_replication {
      status = "Enabled"
    }

    destination {
      bucket        = module.logs_secondary.bucket_arn
      storage_class = "STANDARD"

      encryption_configuration {
        replica_kms_key_id = module.logs_secondary.kms_key_arn
      }
    }
  }

  depends_on = [aws_iam_role_policy.artifact_replication]
}
