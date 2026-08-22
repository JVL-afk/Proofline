resource "aws_cloudwatch_log_group" "worker" {
  name              = "/opintel/${var.name_prefix}/worker"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.logs.arn
}

resource "aws_ecs_cluster" "phase1" {
  name = "${var.name_prefix}-research"
  setting {
    name  = "containerInsights"
    value = "enhanced"
  }
}

resource "aws_iam_service_linked_role" "ecs" {
  aws_service_name = "ecs.amazonaws.com"
}

resource "aws_iam_service_linked_role" "rds" {
  aws_service_name = "rds.amazonaws.com"
}

resource "aws_iam_service_linked_role" "service_discovery" {
  aws_service_name = "servicediscovery.amazonaws.com"
}

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secret" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_db_instance.phase1.master_user_secret[0].secret_arn]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.database.arn]
  }
}

resource "aws_iam_role_policy" "execution_secret" {
  name   = "${var.name_prefix}-database-secret"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secret.json
}

resource "aws_iam_role" "worker" {
  name               = "${var.name_prefix}-research-worker"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_ssm_parameter" "kill_switch" {
  name  = "/${var.name_prefix}/kill-switch"
  type  = "String"
  value = "TRIPPED"

  lifecycle {
    ignore_changes = [value]
  }
}

data "aws_iam_policy_document" "worker" {
  statement {
    sid       = "RestrictedCaptureObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.captures.arn}/*"]
  }
  statement {
    sid       = "RestrictedCaptureBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.captures.arn]
  }
  statement {
    sid       = "CaptureKey"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.captures.arn]
  }
  statement {
    sid       = "DatabaseIam"
    actions   = ["rds-db:connect"]
    resources = ["arn:${data.aws_partition.current.partition}:rds-db:${var.aws_region}:${data.aws_caller_identity.current.account_id}:dbuser:${aws_db_instance.phase1.resource_id}/${var.database_master_username}"]
  }
  statement {
    sid       = "ReadKillSwitch"
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.kill_switch.arn]
  }
}

resource "aws_iam_role_policy" "worker" {
  name   = "${var.name_prefix}-research-worker"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker.json
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name_prefix}-research-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.worker.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = "research-worker"
      image     = var.worker_image_uri
      essential = true
      environment = [
        { name = "OPINTEL_APP_ENV", value = "phase1" },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "OPINTEL_KILL_SWITCH_PARAMETER", value = aws_ssm_parameter.kill_switch.name },
        { name = "OPINTEL_AWS_REGION", value = var.aws_region },
        { name = "CAPTURE_BUCKET", value = aws_s3_bucket.captures.id },
        { name = "OPINTEL_DATABASE_HOST", value = aws_db_instance.phase1.address },
        { name = "OPINTEL_DATABASE_NAME", value = var.database_name },
        { name = "OPINTEL_DATABASE_USERNAME", value = var.database_master_username },
        { name = "OPINTEL_CONTROLLED_EGRESS_URL", value = "http://egress.m67.internal:8080" },
        { name = "OPINTEL_EGRESS_POLICY_REVISION", value = "NOT_AUTHORIZED" },
        { name = "OPINTEL_RESEARCH_LIVE_ENABLED", value = "false" },
        { name = "OPINTEL_RESEARCH_BROWSER_ENABLED", value = "false" }
      ]
      secrets = [
        {
          name      = "OPINTEL_DATABASE_PASSWORD"
          valueFrom = "${aws_db_instance.phase1.master_user_secret[0].secret_arn}:password::"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
      readonlyRootFilesystem = true
      user                   = "65532"
    }
  ])
}

resource "aws_ecs_service" "worker" {
  name                               = "${var.name_prefix}-research-worker"
  cluster                            = aws_ecs_cluster.phase1.id
  task_definition                    = aws_ecs_task_definition.worker.arn
  desired_count                      = var.worker_desired_count
  launch_type                        = "FARGATE"
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
  enable_execute_command             = false

  network_configuration {
    assign_public_ip = false
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.worker.id]
  }

  depends_on = [aws_iam_service_linked_role.ecs]
}

resource "aws_service_discovery_private_dns_namespace" "phase1" {
  name = "m67.internal"
  vpc  = aws_vpc.phase1.id

  depends_on = [aws_iam_service_linked_role.service_discovery]
}

resource "aws_service_discovery_service" "egress" {
  name = "egress"
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.phase1.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }
  health_check_custom_config {}
}

resource "aws_ecs_task_definition" "egress" {
  family                   = "${var.name_prefix}-controlled-egress"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name                   = "controlled-egress"
    image                  = var.worker_image_uri
    essential              = true
    entryPoint             = ["python", "-m", "opintel_research_worker.egress_main"]
    readonlyRootFilesystem = true
    user                   = "65532"
    portMappings           = [{ containerPort = 8080, hostPort = 8080, protocol = "tcp" }]
    environment = [
      { name = "OPINTEL_EGRESS_ALLOWED_HOSTS", value = "" },
      { name = "OPINTEL_EGRESS_POLICY_REVISION", value = "NOT_AUTHORIZED" }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.worker.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "controlled-egress"
      }
    }
  }])
}

resource "aws_ecs_service" "egress" {
  name            = "${var.name_prefix}-controlled-egress"
  cluster         = aws_ecs_cluster.phase1.id
  task_definition = aws_ecs_task_definition.egress.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = false
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.controlled_egress.id]
  }
  service_registries {
    registry_arn = aws_service_discovery_service.egress.arn
  }

  depends_on = [aws_iam_service_linked_role.ecs]
}
