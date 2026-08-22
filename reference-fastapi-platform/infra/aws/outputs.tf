output "primary_eks_cluster_name" {
  value = module.eks_primary.cluster_name
}

output "secondary_eks_cluster_name" {
  value = module.eks_secondary.cluster_name
}

output "primary_eks_endpoint" {
  value     = module.eks_primary.cluster_endpoint
  sensitive = true
}

output "secondary_eks_endpoint" {
  value     = module.eks_secondary.cluster_endpoint
  sensitive = true
}

output "aurora_global_cluster_id" {
  value = module.aurora_primary.global_cluster_id
}

output "aurora_primary_writer_endpoint" {
  value     = module.aurora_primary.cluster_endpoint
  sensitive = true
}

output "aurora_secondary_reader_endpoint" {
  value     = module.aurora_secondary.reader_endpoint
  sensitive = true
}

output "aurora_primary_master_secret_arn" {
  value     = module.aurora_primary.master_user_secret_arn
  sensitive = true
}

output "redis_primary_endpoint" {
  value     = module.redis_primary.primary_endpoint_address
  sensitive = true
}

output "artifacts_primary_bucket" {
  value = module.artifacts_primary.bucket_id
}

output "artifacts_secondary_bucket" {
  value = module.artifacts_secondary.bucket_id
}

output "logs_primary_bucket" {
  value = module.logs_primary.bucket_id
}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}
