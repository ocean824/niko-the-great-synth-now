variable "name" {
  type = string
}

variable "bucket_name" {
  type = string
}

variable "object_lock_enabled" {
  type    = bool
  default = false
}

variable "noncurrent_version_retention_days" {
  type    = number
  default = 90
}

variable "replication_role_arn" {
  type     = string
  default  = null
  nullable = true
}

variable "replication_key_role" {
  description = "Use source for decrypt access and destination for encrypt access. Ignored without replication_role_arn."
  type        = string
  default     = "source"

  validation {
    condition     = contains(["source", "destination"], var.replication_key_role)
    error_message = "replication_key_role must be source or destination."
  }
}
