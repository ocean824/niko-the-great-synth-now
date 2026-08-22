variable "project_name" {
  description = "DNS-safe project prefix used in AWS resource names."
  type        = string
  default     = "niko-synth-now"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.project_name))
    error_message = "project_name must be 3-31 lowercase letters, digits, and hyphens and start with a letter."
  }
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "production"
}

variable "primary_region" {
  description = "AWS region that owns canonical database writes."
  type        = string
  default     = "us-east-1"
}

variable "secondary_region" {
  description = "AWS recovery region. Must differ from primary_region."
  type        = string
  default     = "us-west-2"

  validation {
    condition     = var.secondary_region != var.primary_region
    error_message = "secondary_region must differ from primary_region."
  }
}

variable "primary_vpc_cidr" {
  description = "Primary-region VPC CIDR."
  type        = string
  default     = "10.20.0.0/16"
}

variable "secondary_vpc_cidr" {
  description = "Secondary-region VPC CIDR."
  type        = string
  default     = "10.30.0.0/16"
}

variable "availability_zones_per_region" {
  description = "Number of available AZs used by each VPC. Three is recommended for production."
  type        = number
  default     = 3

  validation {
    condition     = var.availability_zones_per_region >= 2 && var.availability_zones_per_region <= 3
    error_message = "availability_zones_per_region must be 2 or 3."
  }
}

variable "eks_version" {
  description = "Supported EKS Kubernetes version approved for both regions."
  type        = string
  default     = "1.31"
}

variable "eks_node_instance_types" {
  description = "Instance classes for the managed EKS application node group."
  type        = list(string)
  default     = ["m6i.large"]
}

variable "eks_node_min_size" {
  description = "Minimum managed-node count per regional EKS cluster."
  type        = number
  default     = 2
}

variable "eks_node_desired_size" {
  description = "Initial managed-node count per regional EKS cluster."
  type        = number
  default     = 3
}

variable "eks_node_max_size" {
  description = "Maximum managed-node count per regional EKS cluster."
  type        = number
  default     = 8
}

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL engine version available and compatible in both chosen regions."
  type        = string
  default     = "16.4"
}

variable "aurora_instance_class" {
  description = "Primary and secondary Aurora writer/reader instance class."
  type        = string
  default     = "db.r6g.large"
}

variable "aurora_database_name" {
  description = "Initial application database name."
  type        = string
  default     = "synthnow"
}

variable "aurora_master_username" {
  description = "Aurora master login name. Password is managed by RDS in Secrets Manager."
  type        = string
  default     = "synthnow_admin"
  sensitive   = true
}

variable "backup_retention_days" {
  description = "Aurora automated backup retention period."
  type        = number
  default     = 35

  validation {
    condition     = var.backup_retention_days >= 7 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be between 7 and 35."
  }
}

variable "redis_node_type" {
  description = "ElastiCache replication-group node type."
  type        = string
  default     = "cache.r7g.large"
}

variable "redis_num_cache_clusters" {
  description = "Number of Redis nodes in the primary-region replication group."
  type        = number
  default     = 2

  validation {
    condition     = var.redis_num_cache_clusters >= 2
    error_message = "Use at least two Redis cache nodes for production failover."
  }
}

variable "artifact_bucket_name" {
  description = "Globally unique private S3 bucket name for authorized reference assets and private uploads."
  type        = string
}

variable "logs_bucket_name" {
  description = "Globally unique private S3 bucket name for audit/flow logs."
  type        = string
}

variable "route53_zone_id" {
  description = "Optional public Route53 hosted-zone ID. Leave null when DNS is managed elsewhere."
  type        = string
  default     = null
  nullable    = true
}

variable "api_domain_name" {
  description = "Optional API DNS name used for Route53 health-aware records."
  type        = string
  default     = null
  nullable    = true
}

variable "alert_email" {
  description = "Email endpoint subscribed to CloudWatch operational alarms. Replace or extend with PagerDuty/EventBridge integration after bootstrap."
  type        = string
  default     = null
  nullable    = true
}

variable "enable_deletion_protection" {
  description = "Prevents accidental Aurora deletion. Keep true in production."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional resource tags."
  type        = map(string)
  default     = {}
}

variable "redis_auth_token" {
  description = "Redis AUTH token supplied through a secure environment variable or encrypted variable set; never commit it to tfvars."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.redis_auth_token) >= 16
    error_message = "redis_auth_token must be at least 16 characters."
  }
}
