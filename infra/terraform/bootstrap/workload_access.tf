locals {
  workload_name_prefix        = "m67-phase1"
  phase1_state_plan_role_arn  = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/m67-phase1-terraform-state-plan"
  phase1_state_apply_role_arn = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/m67-phase1-terraform-state-apply"
}

module "phase1_identifiers" {
  source = "../modules/phase1-identifiers"

  account_id  = data.aws_caller_identity.current.account_id
  aws_region  = var.aws_region
  name_prefix = local.workload_name_prefix
  partition   = data.aws_partition.current.partition
}

data "aws_iam_policy_document" "workload_plan_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = var.plan_principal_arns
    }
  }
}

data "aws_iam_policy_document" "workload_apply_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = var.apply_principal_arns
    }
  }
}

resource "aws_iam_role" "workload_plan" {
  name                 = "${local.workload_name_prefix}-terraform-workload-plan"
  description          = "Read-only Terraform refresh and plan identity for M6.7 Phase 1"
  assume_role_policy   = data.aws_iam_policy_document.workload_plan_assume.json
  max_session_duration = 14400
}

resource "aws_iam_role" "workload_apply" {
  name                 = "${local.workload_name_prefix}-terraform-workload-apply"
  description          = "Separately authorized Terraform apply identity for M6.7 Phase 1"
  assume_role_policy   = data.aws_iam_policy_document.workload_apply_assume.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "workload_read" {
  statement {
    sid       = "UseExactStateRole"
    actions   = ["sts:AssumeRole"]
    resources = [local.phase1_state_plan_role_arn]
  }

  statement {
    sid = "RefreshApprovedPhase1Services"
    actions = [
      "budgets:Describe*",
      "budgets:ViewBudget",
      "cloudtrail:DescribeTrails",
      "cloudtrail:GetTrail",
      "cloudtrail:GetTrailStatus",
      "cloudtrail:ListTags",
      "cloudtrail:ListTrails",
      "cloudwatch:DescribeAlarms",
      "cloudwatch:ListTagsForResource",
      "ec2:Describe*",
      "ecr:BatchGetImage",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:GetAuthorizationToken",
      "ecr:GetLifecyclePolicy",
      "ecr:GetRepositoryPolicy",
      "ecr:ListImages",
      "ecr:ListTagsForResource",
      "ecs:Describe*",
      "ecs:List*",
      "iam:Get*",
      "iam:List*",
      "kms:DescribeKey",
      "kms:GetKeyPolicy",
      "kms:GetKeyRotationStatus",
      "kms:ListAliases",
      "kms:ListResourceTags",
      "logs:DescribeLogGroups",
      "logs:ListTagsForResource",
      "rds:Describe*",
      "rds:ListTagsForResource",
      "servicediscovery:GetNamespace",
      "servicediscovery:GetOperation",
      "servicediscovery:GetService",
      "servicediscovery:ListNamespaces",
      "servicediscovery:ListOperations",
      "servicediscovery:ListServices",
      "servicediscovery:ListTagsForResource",
      "s3:GetBucket*",
      "s3:GetEncryptionConfiguration",
      "s3:GetLifecycleConfiguration",
      "s3:GetBucketPublicAccessBlock",
      "s3:ListAllMyBuckets",
      "s3:ListBucket",
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetResourcePolicy",
      "secretsmanager:ListSecretVersionIds",
      "secretsmanager:ListSecrets",
      "sns:GetTopicAttributes",
      "sns:ListTagsForResource",
      "sns:ListTopics",
      "ssm:DescribeParameters",
      "ssm:GetParameter",
      "ssm:ListTagsForResource",
      "sts:GetCallerIdentity",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "ReadExactPhase1BucketAcceleration"
    actions = ["s3:GetAccelerateConfiguration"]
    resources = [
      module.phase1_identifiers.capture_bucket_arn,
      module.phase1_identifiers.audit_bucket_arn,
    ]
  }

  statement {
    sid       = "ReadExactPhase1BudgetTags"
    actions   = ["budgets:ListTagsForResource"]
    resources = ["arn:${data.aws_partition.current.partition}:budgets::${data.aws_caller_identity.current.account_id}:budget/${local.workload_name_prefix}-monthly-hard-ceiling"]
  }
}

resource "aws_iam_role_policy" "workload_plan" {
  name   = "${local.workload_name_prefix}-terraform-workload-read"
  role   = aws_iam_role.workload_plan.id
  policy = data.aws_iam_policy_document.workload_read.json
}

resource "aws_iam_role_policy" "workload_apply_read" {
  name   = "${local.workload_name_prefix}-terraform-workload-read"
  role   = aws_iam_role.workload_apply.id
  policy = data.aws_iam_policy_document.workload_read.json
}

data "aws_iam_policy_document" "workload_apply_network_compute" {
  statement {
    sid       = "UseExactApplyStateRole"
    actions   = ["sts:AssumeRole"]
    resources = [local.phase1_state_apply_role_arn]
  }

  statement {
    sid = "Phase1Ec2NetworkLifecycle"
    actions = [
      "ec2:AllocateAddress",
      "ec2:AssociateRouteTable",
      "ec2:AttachInternetGateway",
      "ec2:AuthorizeSecurityGroupEgress",
      "ec2:AuthorizeSecurityGroupIngress",
      "ec2:CreateInternetGateway",
      "ec2:CreateNatGateway",
      "ec2:CreateRoute",
      "ec2:CreateRouteTable",
      "ec2:CreateSecurityGroup",
      "ec2:CreateSubnet",
      "ec2:CreateTags",
      "ec2:CreateVpc",
      "ec2:CreateVpcEndpoint",
      "ec2:DeleteInternetGateway",
      "ec2:DeleteNatGateway",
      "ec2:DeleteRoute",
      "ec2:DeleteRouteTable",
      "ec2:DeleteSecurityGroup",
      "ec2:DeleteSubnet",
      "ec2:DeleteTags",
      "ec2:DeleteVpc",
      "ec2:DeleteVpcEndpoints",
      "ec2:DetachInternetGateway",
      "ec2:DisassociateRouteTable",
      "ec2:ModifySubnetAttribute",
      "ec2:ModifyVpcAttribute",
      "ec2:ModifyVpcEndpoint",
      "ec2:ReleaseAddress",
      "ec2:RevokeSecurityGroupEgress",
      "ec2:RevokeSecurityGroupIngress",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "CreateExactPhase1PrivateHostedZone"
    actions   = ["route53:CreateHostedZone"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "route53:VPCs"
      values   = ["VPCId=${var.phase1_vpc_id},VPCRegion=${var.aws_region}"]
    }
  }

  statement {
    sid = "Phase1EcsLifecycle"
    actions = [
      "ecs:CreateCluster",
      "ecs:CreateService",
      "ecs:DeleteCluster",
      "ecs:DeleteService",
      "ecs:DeregisterTaskDefinition",
      "ecs:RegisterTaskDefinition",
      "ecs:TagResource",
      "ecs:UntagResource",
      "ecs:UpdateClusterSettings",
      "ecs:UpdateService",
    ]
    resources = ["*"]
  }

  statement {
    sid = "Phase1PrivateServiceDiscoveryLifecycle"
    actions = [
      "servicediscovery:CreatePrivateDnsNamespace",
      "servicediscovery:CreateService",
      "servicediscovery:DeleteNamespace",
      "servicediscovery:DeleteService",
      "servicediscovery:TagResource",
      "servicediscovery:UntagResource",
      "servicediscovery:UpdateService",
    ]
    resources = ["*"]
  }

  statement {
    sid = "ReadExactWorkerImage"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = ["arn:${data.aws_partition.current.partition}:ecr:${var.aws_region}:${data.aws_caller_identity.current.account_id}:repository/m67-phase1-worker"]
  }
}

resource "aws_iam_role_policy" "workload_apply_network_compute" {
  name   = "${local.workload_name_prefix}-terraform-network-compute"
  role   = aws_iam_role.workload_apply.id
  policy = data.aws_iam_policy_document.workload_apply_network_compute.json
}

data "aws_iam_policy_document" "workload_apply_data_observability" {
  statement {
    sid = "Phase1KmsLifecycle"
    actions = [
      "kms:CreateAlias",
      "kms:CreateKey",
      "kms:DeleteAlias",
      "kms:DisableKeyRotation",
      "kms:EnableKeyRotation",
      "kms:PutKeyPolicy",
      "kms:ScheduleKeyDeletion",
      "kms:TagResource",
      "kms:UntagResource",
      "kms:UpdateAlias",
      "kms:UpdateKeyDescription",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "CreateRdsGrantOnExactDatabaseKey"
    actions   = ["kms:CreateGrant"]
    resources = [var.phase1_database_kms_key_arn]

    condition {
      test     = "Bool"
      variable = "kms:GrantIsForAWSResource"
      values   = ["true"]
    }

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["rds.${var.aws_region}.amazonaws.com"]
    }
  }

  statement {
    sid = "Phase1S3Lifecycle"
    actions = [
      "s3:CreateBucket",
      "s3:DeleteBucket",
      "s3:DeleteBucketPolicy",
      "s3:PutLifecycleConfiguration",
      "s3:PutBucketOwnershipControls",
      "s3:PutBucketPolicy",
      "s3:PutBucketPublicAccessBlock",
      "s3:PutBucketTagging",
      "s3:PutBucketVersioning",
      "s3:PutEncryptionConfiguration",
    ]
    resources = [
      module.phase1_identifiers.capture_bucket_arn,
      module.phase1_identifiers.audit_bucket_arn,
    ]
  }

  statement {
    sid       = "TagExactPhase1Budget"
    actions   = ["budgets:TagResource"]
    resources = ["arn:${data.aws_partition.current.partition}:budgets::${data.aws_caller_identity.current.account_id}:budget/${local.workload_name_prefix}-monthly-hard-ceiling"]
  }

  statement {
    sid = "Phase1RdsLifecycle"
    actions = [
      "rds:AddTagsToResource",
      "rds:CreateDBInstance",
      "rds:CreateDBSubnetGroup",
      "rds:DeleteDBInstance",
      "rds:DeleteDBSubnetGroup",
      "rds:ModifyDBInstance",
      "rds:ModifyDBSubnetGroup",
      "rds:RemoveTagsFromResource",
    ]
    resources = ["*"]
  }

  statement {
    sid = "Phase1ObservabilityLifecycle"
    actions = [
      "budgets:ModifyBudget",
      "cloudtrail:AddTags",
      "cloudtrail:CreateTrail",
      "cloudtrail:DeleteTrail",
      "cloudtrail:RemoveTags",
      "cloudtrail:StartLogging",
      "cloudtrail:StopLogging",
      "cloudtrail:UpdateTrail",
      "cloudwatch:DeleteAlarms",
      "cloudwatch:PutMetricAlarm",
      "cloudwatch:TagResource",
      "cloudwatch:UntagResource",
      "logs:AssociateKmsKey",
      "logs:CreateLogGroup",
      "logs:DeleteLogGroup",
      "logs:DisassociateKmsKey",
      "logs:PutRetentionPolicy",
      "logs:TagResource",
      "logs:UntagResource",
      "sns:CreateTopic",
      "sns:DeleteTopic",
      "sns:SetTopicAttributes",
      "sns:TagResource",
      "sns:UntagResource",
      "ssm:AddTagsToResource",
      "ssm:DeleteParameter",
      "ssm:PutParameter",
      "ssm:RemoveTagsFromResource",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "workload_apply_data_observability" {
  name   = "${local.workload_name_prefix}-terraform-data-observability"
  role   = aws_iam_role.workload_apply.id
  policy = data.aws_iam_policy_document.workload_apply_data_observability.json
}

data "aws_iam_policy_document" "workload_apply_iam" {
  statement {
    sid = "Phase1NamedRolesOnly"
    actions = [
      "iam:AttachRolePolicy",
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:DeleteRolePolicy",
      "iam:DetachRolePolicy",
      "iam:PassRole",
      "iam:PutRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:UpdateRoleDescription",
    ]
    resources = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/m67-phase1-*"]
  }

  statement {
    sid = "CreateExactServiceLinkedRoles"
    actions = [
      "iam:CreateServiceLinkedRole",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/ecs.amazonaws.com/AWSServiceRoleForECS*",
      "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/rds.amazonaws.com/AWSServiceRoleForRDS*",
    ]
    condition {
      test     = "StringEquals"
      variable = "iam:AWSServiceName"
      values = [
        "ecs.amazonaws.com",
        "rds.amazonaws.com",
      ]
    }
  }

  statement {
    sid     = "TagExactServiceLinkedRoles"
    actions = ["iam:TagRole"]
    resources = [
      "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/ecs.amazonaws.com/AWSServiceRoleForECS",
      "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/rds.amazonaws.com/AWSServiceRoleForRDS",
    ]
  }

  statement {
    sid     = "DeleteExactServiceLinkedRoles"
    actions = ["iam:DeleteServiceLinkedRole"]
    resources = [
      "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/ecs.amazonaws.com/AWSServiceRoleForECS*",
      "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/rds.amazonaws.com/AWSServiceRoleForRDS*",
    ]
  }

  statement {
    sid       = "ObserveServiceLinkedRoleDeletion"
    actions   = ["iam:GetServiceLinkedRoleDeletionStatus"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "workload_apply_iam" {
  name   = "${local.workload_name_prefix}-terraform-iam"
  role   = aws_iam_role.workload_apply.id
  policy = data.aws_iam_policy_document.workload_apply_iam.json
}
