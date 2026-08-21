resource "aws_cloudtrail" "phase1" {
  name                          = "${var.name_prefix}-audit"
  s3_bucket_name                = aws_s3_bucket.audit.id
  kms_key_id                    = aws_kms_key.logs.arn
  include_global_service_events = true
  is_multi_region_trail         = false
  enable_log_file_validation    = true

  event_selector {
    read_write_type           = "All"
    include_management_events = true
    data_resource {
      type   = "AWS::S3::Object"
      values = ["${aws_s3_bucket.captures.arn}/"]
    }
  }

  depends_on = [aws_s3_bucket_policy.audit]
}

resource "aws_budgets_budget" "phase1" {
  name         = "${var.name_prefix}-monthly-hard-ceiling"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
}

resource "aws_cloudwatch_metric_alarm" "database_cpu" {
  alarm_name          = "${var.name_prefix}-database-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Phase 1 RDS CPU exceeds 80 percent"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.phase1.identifier }
}

resource "aws_cloudwatch_metric_alarm" "database_storage" {
  alarm_name          = "${var.name_prefix}-database-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Minimum"
  threshold           = 2147483648
  alarm_description   = "Phase 1 RDS free storage below 2 GiB"
  dimensions          = { DBInstanceIdentifier = aws_db_instance.phase1.identifier }
}

data "aws_iam_policy_document" "operator_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = var.operator_principal_arns
    }
  }
}

resource "aws_iam_role" "operator" {
  name                 = "${var.name_prefix}-operator"
  assume_role_policy   = data.aws_iam_policy_document.operator_assume.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "kill_operator_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.kill_switch_operator_principal_arn]
    }
  }
}

resource "aws_iam_role" "kill_operator" {
  name                 = "${var.name_prefix}-kill-switch-operator"
  assume_role_policy   = data.aws_iam_policy_document.kill_operator_assume.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "kill_operator" {
  statement {
    actions   = ["ssm:GetParameter", "ssm:PutParameter"]
    resources = [aws_ssm_parameter.kill_switch.arn]
  }
  statement {
    actions   = ["ecs:UpdateService", "ecs:DescribeServices"]
    resources = [aws_ecs_service.worker.id]
  }
}

resource "aws_iam_role_policy" "kill_operator" {
  name   = "${var.name_prefix}-kill-switch"
  role   = aws_iam_role.kill_operator.id
  policy = data.aws_iam_policy_document.kill_operator.json
}
