provider "aws" {
  region = var.primary_region

  default_tags {
    tags = merge(var.tags, {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    })
  }
}

provider "aws" {
  alias  = "secondary"
  region = var.secondary_region

  default_tags {
    tags = merge(var.tags, {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      RegionRole  = "secondary"
    })
  }
}

data "aws_caller_identity" "current" {}
