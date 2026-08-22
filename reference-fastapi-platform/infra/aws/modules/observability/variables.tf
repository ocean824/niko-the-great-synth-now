variable "name" {
  type = string
}

variable "log_retention_days" {
  type    = number
  default = 90
}

variable "alert_email" {
  type     = string
  default  = null
  nullable = true
}
