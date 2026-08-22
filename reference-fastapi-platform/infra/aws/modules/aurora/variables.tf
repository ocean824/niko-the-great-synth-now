variable "name" {
  type = string
}

variable "global_cluster_identifier" {
  type = string
}

variable "create_global_cluster" {
  type = bool
}

variable "is_primary" {
  type = bool
}

variable "engine_version" {
  type = string
}

variable "database_name" {
  type = string
}

variable "master_username" {
  type      = string
  sensitive = true
}

variable "instance_class" {
  type = string
}

variable "backup_retention_days" {
  type = number
}

variable "deletion_protection" {
  type = bool
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "availability_zones" {
  type = list(string)
}

variable "application_cidrs" {
  type = list(string)
}
