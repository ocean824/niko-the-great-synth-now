locals {
  primary_oidc_host   = trimprefix(module.eks_primary.oidc_issuer, "https://")
  secondary_oidc_host = trimprefix(module.eks_secondary.oidc_issuer, "https://")
}

resource "aws_kms_key" "application_secrets_primary" {
  description             = "${local.name} primary application configuration secret"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_key" "application_secrets_secondary" {
  provider                = aws.secondary
  description             = "${local.name} secondary application configuration secret"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_secretsmanager_secret" "application_primary" {
  name                    = "/${var.project_name}/${var.environment}/application"
  description             = "Populate after Terraform with Synth Now application configuration; do not commit a secret value."
  kms_key_id              = aws_kms_key.application_secrets_primary.arn
  recovery_window_in_days = 30
}

resource "aws_secretsmanager_secret" "application_secondary" {
  provider                = aws.secondary
  name                    = "/${var.project_name}/${var.environment}/application"
  description             = "Populate only through approved regional failover/bootstrap procedure."
  kms_key_id              = aws_kms_key.application_secrets_secondary.arn
  recovery_window_in_days = 30
}

data "aws_iam_policy_document" "api_primary_assume" {
  statement {
    effect = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [module.eks_primary.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.primary_oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.primary_oidc_host}:sub"
      values   = ["system:serviceaccount:synth-now:synth-now-api", "system:serviceaccount:synth-now:synth-now-worker"]
    }
  }
}

resource "aws_iam_role" "api_primary" {
  name               = "${local.name}-synth-now-workload"
  assume_role_policy = data.aws_iam_policy_document.api_primary_assume.json
}

data "aws_iam_policy_document" "api_primary_permissions" {
  statement {
    effect = "Allow"
    actions = ["s3:ListBucket"]
    resources = [module.artifacts_primary.bucket_arn]
  }

  statement {
    effect = "Allow"
    actions = ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload"]
    resources = ["${module.artifacts_primary.bucket_arn}/*"]
  }

  statement {
    effect = "Allow"
    actions = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [module.artifacts_primary.kms_key_arn, aws_kms_key.application_secrets_primary.arn]
  }

  statement {
    effect = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.application_primary.arn,
      module.aurora_primary.master_user_secret_arn,
    ]
  }
}

resource "aws_iam_role_policy" "api_primary" {
  name   = "${local.name}-synth-now-workload"
  role   = aws_iam_role.api_primary.id
  policy = data.aws_iam_policy_document.api_primary_permissions.json
}

data "aws_iam_policy_document" "api_secondary_assume" {
  statement {
    effect = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [module.eks_secondary.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.secondary_oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.secondary_oidc_host}:sub"
      values   = ["system:serviceaccount:synth-now:synth-now-api", "system:serviceaccount:synth-now:synth-now-worker"]
    }
  }
}

resource "aws_iam_role" "api_secondary" {
  provider           = aws.secondary
  name               = "${local.name}-synth-now-workload"
  assume_role_policy = data.aws_iam_policy_document.api_secondary_assume.json
}

data "aws_iam_policy_document" "api_secondary_permissions" {
  statement {
    effect = "Allow"
    actions = ["s3:ListBucket"]
    resources = [module.artifacts_secondary.bucket_arn]
  }

  statement {
    effect = "Allow"
    actions = ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload"]
    resources = ["${module.artifacts_secondary.bucket_arn}/*"]
  }

  statement {
    effect = "Allow"
    actions = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [module.artifacts_secondary.kms_key_arn, aws_kms_key.application_secrets_secondary.arn]
  }

  statement {
    effect = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.application_secondary.arn]
  }
}

resource "aws_iam_role_policy" "api_secondary" {
  provider = aws.secondary
  name     = "${local.name}-synth-now-workload"
  role     = aws_iam_role.api_secondary.id
  policy   = data.aws_iam_policy_document.api_secondary_permissions.json
}

output "primary_workload_role_arn" {
  value = aws_iam_role.api_primary.arn
}

output "secondary_workload_role_arn" {
  value = aws_iam_role.api_secondary.arn
}

output "primary_application_secret_arn" {
  value     = aws_secretsmanager_secret.application_primary.arn
  sensitive = true
}

output "secondary_application_secret_arn" {
  value     = aws_secretsmanager_secret.application_secondary.arn
  sensitive = true
}
