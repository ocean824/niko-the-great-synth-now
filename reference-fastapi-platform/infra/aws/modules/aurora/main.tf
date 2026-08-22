resource "aws_kms_key" "database" {
  description             = "${var.name} Aurora PostgreSQL encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${var.name}-aurora"
  }
}

resource "aws_kms_alias" "database" {
  name          = "alias/${var.name}-aurora"
  target_key_id = aws_kms_key.database.key_id
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-aurora"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${var.name}-aurora"
  }
}

resource "aws_security_group" "database" {
  name_prefix = "${var.name}-aurora-"
  description = "Aurora PostgreSQL access only from approved private CIDRs."
  vpc_id      = var.vpc_id

  ingress {
    description = "PostgreSQL from approved workload CIDRs"
    from_port   = 5432
    to_port     = 5432
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

  tags = {
    Name = "${var.name}-aurora"
  }
}

resource "aws_rds_global_cluster" "this" {
  count = var.create_global_cluster ? 1 : 0

  global_cluster_identifier = var.global_cluster_identifier
  engine                    = "aurora-postgresql"
  engine_version            = var.engine_version
  storage_encrypted         = true
  deletion_protection       = var.deletion_protection
}

resource "aws_rds_cluster" "this" {
  cluster_identifier        = var.name
  global_cluster_identifier = var.create_global_cluster ? aws_rds_global_cluster.this[0].id : var.global_cluster_identifier
  engine                    = "aurora-postgresql"
  engine_version            = var.engine_version
  engine_mode               = "provisioned"

  database_name                 = var.is_primary ? var.database_name : null
  master_username               = var.is_primary ? var.master_username : null
  manage_master_user_password   = var.is_primary ? true : null
  master_user_secret_kms_key_id = var.is_primary ? aws_kms_key.database.arn : null

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.database.id]
  availability_zones     = var.availability_zones

  storage_encrypted            = true
  kms_key_id                   = aws_kms_key.database.arn
  backup_retention_period      = var.backup_retention_days
  preferred_backup_window      = "03:00-04:00"
  preferred_maintenance_window = "sun:04:00-sun:05:00"
  deletion_protection          = var.deletion_protection
  skip_final_snapshot          = true
  copy_tags_to_snapshot        = true
  enabled_cloudwatch_logs_exports = ["postgresql"]

  # Aurora creates and rotates the master secret in Secrets Manager for the primary cluster.
  # Application credentials should be separate least-privilege users provisioned by a migration job.
}

resource "aws_rds_cluster_instance" "writer_or_reader" {
  identifier         = "${var.name}-instance-1"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class     = var.instance_class
  engine             = aws_rds_cluster.this.engine
  engine_version     = aws_rds_cluster.this.engine_version
  publicly_accessible = false
  auto_minor_version_upgrade = false
  performance_insights_enabled = true
  performance_insights_kms_key_id = aws_kms_key.database.arn

  monitoring_interval = 60

  tags = {
    Name = "${var.name}-instance-1"
  }
}
