variable "expected_aws_account_id" {
  description = "Exact pre-approved dedicated Phase 1 workload account ID."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_aws_account_id))
    error_message = "expected_aws_account_id must contain exactly 12 digits."
  }
}

variable "aws_region" {
  description = "Owner-approved Phase 1 AWS region."
  type        = string
  default     = "us-east-2"

  validation {
    condition     = var.aws_region == "us-east-2"
    error_message = "Phase 1 is restricted to us-east-2."
  }
}

variable "name_prefix" {
  description = "Stable resource-name prefix."
  type        = string
  default     = "m67-phase1"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.name_prefix))
    error_message = "name_prefix must be a short lowercase DNS-style label."
  }
}

variable "vpc_cidr" {
  description = "Dedicated Phase 1 VPC CIDR."
  type        = string
  default     = "10.67.0.0/16"
}

variable "public_egress_subnet_cidr" {
  description = "Public subnet used only by the dedicated NAT egress identity."
  type        = string
  default     = "10.67.0.0/24"
}

variable "private_subnet_cidrs" {
  description = "Exactly two private workload/data subnet CIDRs."
  type        = tuple([string, string])
  default     = ["10.67.10.0/24", "10.67.11.0/24"]
}

variable "availability_zones" {
  description = "Two explicit us-east-2 availability zones."
  type        = tuple([string, string])
  default     = ["us-east-2a", "us-east-2b"]

  validation {
    condition = alltrue([
      for zone in var.availability_zones : startswith(zone, "us-east-2")
    ])
    error_message = "Every availability zone must be in us-east-2."
  }
}

variable "worker_image_uri" {
  description = "Immutable ECR image URI for the research worker, including a sha256 digest."
  type        = string

  validation {
    condition     = can(regex("^[^[:space:]]+@sha256:[0-9a-f]{64}$", var.worker_image_uri))
    error_message = "worker_image_uri must use an immutable sha256 digest."
  }
}

variable "controlled_egress_image_uri" {
  description = "Separately frozen immutable ECR image URI for the controlled-egress runtime."
  type        = string

  validation {
    condition     = can(regex("^[^[:space:]]+@sha256:[0-9a-f]{64}$", var.controlled_egress_image_uri))
    error_message = "controlled_egress_image_uri must use an immutable sha256 digest."
  }
}

variable "worker_desired_count" {
  description = "Worker activation count; zero until separately authorized."
  type        = number
  default     = 0

  validation {
    condition     = contains([0, 1], var.worker_desired_count)
    error_message = "Phase 1 permits zero or one worker only."
  }
}

variable "intelligence_worker_desired_count" {
  description = "Deterministic M2-M5 worker count; zero until a separately authorized run."
  type        = number
  default     = 0

  validation {
    condition     = contains([0, 1], var.intelligence_worker_desired_count)
    error_message = "Phase 1 permits zero or one deterministic intelligence worker only."
  }
}

variable "research_runtime_revision" {
  description = "Immutable successor runtime revision bound by future research releases."
  type        = string

  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.research_runtime_revision))
    error_message = "research_runtime_revision must be an immutable sha256 digest."
  }
}

variable "capture_retention_days" {
  description = "Exact A-08 successful minimized-capture retention."
  type        = number
  default     = 90

  validation {
    condition     = var.capture_retention_days == 90
    error_message = "Phase 1 minimized captures have an exact 90-day primary retention."
  }
}

variable "backup_retention_days" {
  description = "Exact approved RDS backup retention, capped at the approved 30-day overhang."
  type        = number
  default     = 30

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 30
    error_message = "Backup retention must be between 1 and 30 days."
  }
}

variable "database_name" {
  description = "Phase 1 PostgreSQL database name."
  type        = string
  default     = "opintel_phase1"
}

variable "database_master_username" {
  description = "Non-secret master username; AWS manages the password."
  type        = string
  default     = "phase1_admin"
}

variable "operator_principal_arns" {
  description = "Approved short-lived IAM Identity Center/OIDC operator principal ARNs."
  type        = set(string)

  validation {
    condition     = length(var.operator_principal_arns) > 0
    error_message = "At least one approved operator principal ARN is required."
  }
}

variable "kill_switch_operator_principal_arn" {
  description = "Exact independently assigned kill-switch operator principal ARN."
  type        = string

  validation {
    condition     = startswith(var.kill_switch_operator_principal_arn, "arn:aws:iam::")
    error_message = "A valid IAM principal ARN is required."
  }
}

variable "monthly_budget_limit_usd" {
  description = "Owner-approved maximum Phase 1 AWS budget ceiling."
  type        = number
  default     = 250

  validation {
    condition     = var.monthly_budget_limit_usd == 250
    error_message = "Phase 1 AWS budget is fixed at USD 250."
  }
}
