resource "aws_kms_key" "logs" {
  description             = "${var.name} CloudWatch Logs encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${var.name}-logs"
  }
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/synth-now/${var.name}/application"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.logs.arn
}

resource "aws_cloudwatch_log_group" "redis" {
  name              = "/synth-now/${var.name}/redis"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.logs.arn
}

resource "aws_sns_topic" "alerts" {
  name              = "${var.name}-operations"
  kms_master_key_id = aws_kms_key.logs.arn
}

resource "aws_sns_topic_subscription" "email" {
  count = var.alert_email == null ? 0 : 1

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
