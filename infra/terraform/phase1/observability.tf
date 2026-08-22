resource "aws_sns_topic" "operations" {
  name              = "${var.name_prefix}-operations"
  kms_master_key_id = aws_kms_key.logs.arn
}

data "aws_iam_policy_document" "operations_topic" {
  statement {
    sid     = "AccountOwnerAdministration"
    actions = ["SNS:GetTopicAttributes", "SNS:SetTopicAttributes", "SNS:Subscribe"]
    principals {
      type        = "AWS"
      identifiers = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    resources = [aws_sns_topic.operations.arn]
  }

  statement {
    sid     = "AwsServicePublish"
    actions = ["SNS:Publish"]
    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com", "cloudwatch.amazonaws.com"]
    }
    resources = [aws_sns_topic.operations.arn]
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_sns_topic_policy" "operations" {
  arn    = aws_sns_topic.operations.arn
  policy = data.aws_iam_policy_document.operations_topic.json
}

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

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "FORECASTED"
    subscriber_sns_topic_arns = [aws_sns_topic.operations.arn]
  }
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
  alarm_actions       = [aws_sns_topic.operations.arn]
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
  alarm_actions       = [aws_sns_topic.operations.arn]
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
  max_session_duration = 14400
}

data "aws_iam_policy_document" "environment_validation" {
  statement {
    sid       = "RunExactSyntheticValidationTask"
    actions   = ["ecs:RunTask"]
    resources = ["arn:${data.aws_partition.current.partition}:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:task-definition/${var.name_prefix}-research-worker:*"]

    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.phase1.arn]
    }
  }

  statement {
    sid       = "ObserveOrStopExactSyntheticValidationTask"
    actions   = ["ecs:DescribeTasks", "ecs:StopTask"]
    resources = ["arn:${data.aws_partition.current.partition}:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:task/${var.name_prefix}-research/*"]
  }

  statement {
    sid     = "PassExactSyntheticValidationRoles"
    actions = ["iam:PassRole"]
    resources = [
      aws_iam_role.execution.arn,
      aws_iam_role.worker.arn,
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }

  statement {
    sid     = "RestoreExactSyntheticValidationDatabase"
    actions = ["rds:RestoreDBInstanceToPointInTime"]
    resources = [
      aws_db_instance.phase1.arn,
      "arn:${data.aws_partition.current.partition}:rds:${var.aws_region}:${data.aws_caller_identity.current.account_id}:db:${var.name_prefix}-restore-validation-*",
    ]
  }

  statement {
    sid     = "TagOrDeleteExactSyntheticValidationDatabase"
    actions = ["rds:AddTagsToResource", "rds:DeleteDBInstance"]
    resources = [
      "arn:${data.aws_partition.current.partition}:rds:${var.aws_region}:${data.aws_caller_identity.current.account_id}:db:${var.name_prefix}-restore-validation-*"
    ]
  }

  statement {
    sid       = "ObservePhase1DatabaseValidation"
    actions   = ["rds:DescribeDBInstances", "rds:ListTagsForResource"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "environment_validation" {
  name   = "${var.name_prefix}-environment-validation"
  role   = aws_iam_role.operator.id
  policy = data.aws_iam_policy_document.environment_validation.json
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
  max_session_duration = 14400
}

data "aws_iam_policy_document" "kill_operator" {
  statement {
    actions   = ["ssm:GetParameter", "ssm:PutParameter"]
    resources = [aws_ssm_parameter.kill_switch.arn]
  }
  statement {
    actions = ["ecs:UpdateService", "ecs:DescribeServices"]
    # Keep the policy stable across task-definition revisions. The service ARN
    # is deterministic and does not depend on the service's pending update.
    resources = [
      "arn:${data.aws_partition.current.partition}:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:service/${var.name_prefix}-research/${var.name_prefix}-research-worker"
    ]
  }
}

resource "aws_iam_role_policy" "kill_operator" {
  name   = "${var.name_prefix}-kill-switch"
  role   = aws_iam_role.kill_operator.id
  policy = data.aws_iam_policy_document.kill_operator.json
}
