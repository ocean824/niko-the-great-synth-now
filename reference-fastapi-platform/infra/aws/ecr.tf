resource "aws_ecr_repository" "api_primary" {
  name                 = "${var.project_name}/synth-now-api"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
  }
}

resource "aws_ecr_repository" "api_secondary" {
  provider             = aws.secondary
  name                 = "${var.project_name}/synth-now-api"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
  }
}

resource "aws_ecr_replication_configuration" "this" {
  replication_configuration {
    rule {
      destination {
        region      = var.secondary_region
        registry_id = data.aws_caller_identity.current.account_id
      }
    }
  }
}

output "primary_ecr_repository_url" {
  value = aws_ecr_repository.api_primary.repository_url
}

output "secondary_ecr_repository_url" {
  value = aws_ecr_repository.api_secondary.repository_url
}
