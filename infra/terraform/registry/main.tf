locals {
  repository_name = "m67-phase1-worker"
}

resource "aws_kms_key" "registry" {
  description             = "M6.7 Phase 1 immutable worker images"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "registry" {
  name          = "alias/m67-phase1-worker-registry"
  target_key_id = aws_kms_key.registry.key_id
}

resource "aws_ecr_repository" "worker" {
  name                 = local.repository_name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.registry.arn
  }

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "worker" {
  repository = aws_ecr_repository.worker.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire abandoned untagged build layers after seven days"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 7
      }
      action = { type = "expire" }
    }]
  })
}

data "aws_iam_policy_document" "publisher_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = var.publisher_principal_arns
    }
  }
}

resource "aws_iam_role" "publisher" {
  name                 = "m67-phase1-worker-image-publisher"
  assume_role_policy   = data.aws_iam_policy_document.publisher_assume.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "publisher" {
  statement {
    sid       = "AuthorizationToken"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "ExactRepositoryPushAndScan"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:DescribeImageScanFindings",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:StartImageScan",
      "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.worker.arn]
  }
}

resource "aws_iam_role_policy" "publisher" {
  name   = "m67-phase1-worker-image-publisher"
  role   = aws_iam_role.publisher.id
  policy = data.aws_iam_policy_document.publisher.json
}
