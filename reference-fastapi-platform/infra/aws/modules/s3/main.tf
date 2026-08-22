data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_iam_policy_document" "kms" {
  statement {
    sid    = "AllowAccountAdministration"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }

  dynamic "statement" {
    for_each = var.replication_role_arn == null ? [] : [var.replication_role_arn]
    content {
      sid    = "AllowS3ReplicationRole"
      effect = "Allow"

      principals {
        type        = "AWS"
        identifiers = [statement.value]
      }

      actions = var.replication_key_role == "source" ? [
        "kms:Decrypt",
        "kms:DescribeKey",
      ] : [
        "kms:Encrypt",
        "kms:ReEncrypt*",
        "kms:GenerateDataKey*",
        "kms:DescribeKey",
      ]
      resources = ["*"]
    }
  }
}

resource "aws_kms_key" "bucket" {
  description             = "${var.name} S3 encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.kms.json

  tags = {
    Name = "${var.name}-s3"
  }
}

resource "aws_kms_alias" "bucket" {
  name          = "alias/${var.name}-s3"
  target_key_id = aws_kms_key.bucket.key_id
}

resource "aws_s3_bucket" "this" {
  bucket              = var.bucket_name
  force_destroy       = false
  object_lock_enabled = var.object_lock_enabled

  tags = {
    Name = var.bucket_name
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.bucket.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "noncurrent-version-retention"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_retention_days
    }
  }
}

data "aws_iam_policy_document" "tls_only" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.this.arn,
      "${aws_s3_bucket.this.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "tls_only" {
  bucket = aws_s3_bucket.this.id
  policy = data.aws_iam_policy_document.tls_only.json
}
