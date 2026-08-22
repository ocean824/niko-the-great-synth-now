output "cluster_arn" {
  value = aws_rds_cluster.this.arn
}

output "cluster_endpoint" {
  value = aws_rds_cluster.this.endpoint
}

output "reader_endpoint" {
  value = aws_rds_cluster.this.reader_endpoint
}

output "security_group_id" {
  value = aws_security_group.database.id
}

output "global_cluster_id" {
  value = var.create_global_cluster ? aws_rds_global_cluster.this[0].id : var.global_cluster_identifier
}

output "master_user_secret_arn" {
  value     = var.is_primary ? aws_rds_cluster.this.master_user_secret[0].secret_arn : null
  sensitive = true
}
