terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {}

module "private_bucket" {
  source = "../../../modules/s3"

  name        = var.name
  bucket_name = var.bucket_name
}
