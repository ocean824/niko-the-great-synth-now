variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "application_cidrs" {
  type = list(string)
}

variable "node_type" {
  type = string
}

variable "num_cache_clusters" {
  type = number
}

variable "engine_version" {
  type    = string
  default = "7.1"
}

variable "auth_token" {
  type      = string
  sensitive = true
}

variable "cloudwatch_log_group_name" {
  type = string
}

variable "is_primary" {
  type    = bool
  default = true
}

variable "global_replication_group_id" {
  type     = string
  default  = null
  nullable = true
}
