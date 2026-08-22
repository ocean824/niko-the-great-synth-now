resource "aws_kms_key" "redis" {
  description             = "${var.name} ElastiCache Redis encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${var.name}-redis"
  }
}

resource "aws_kms_alias" "redis" {
  name          = "alias/${var.name}-redis"
  target_key_id = aws_kms_key.redis.key_id
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name}-redis"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "redis" {
  name_prefix = "${var.name}-redis-"
  description = "Redis TLS access only from approved private workload CIDRs."
  vpc_id      = var.vpc_id

  ingress {
    description = "Redis TLS from approved workload CIDRs"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = var.application_cidrs
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id       = var.name
  description                = "${var.name} Redis cache and bounded session projection"
  global_replication_group_id = var.global_replication_group_id
  engine                     = var.is_primary ? "redis" : null
  engine_version             = var.is_primary ? var.engine_version : null
  node_type                  = var.is_primary ? var.node_type : null
  port                       = 6379
  num_cache_clusters         = var.is_primary ? var.num_cache_clusters : null
  parameter_group_name       = var.is_primary ? "default.redis7" : null
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  security_group_ids         = [aws_security_group.redis.id]
  automatic_failover_enabled = var.is_primary ? true : null
  multi_az_enabled           = var.is_primary ? true : null

  at_rest_encryption_enabled = var.is_primary ? true : null
  transit_encryption_enabled = var.is_primary ? true : null
  auth_token                 = var.is_primary ? var.auth_token : null
  kms_key_id                 = var.is_primary ? aws_kms_key.redis.arn : null

  snapshot_retention_limit = var.is_primary ? 7 : null
  snapshot_window          = var.is_primary ? "04:00-05:00" : null
  maintenance_window       = "sun:05:00-sun:06:00"
  apply_immediately        = false

  dynamic "log_delivery_configuration" {
    for_each = var.is_primary ? [1] : []
    content {
      destination      = var.cloudwatch_log_group_name
      destination_type = "cloudwatch-logs"
      log_format       = "json"
      log_type         = "engine-log"
    }
  }

  lifecycle {
    ignore_changes = [auth_token]
  }

  tags = {
    Name = var.name
  }
}
