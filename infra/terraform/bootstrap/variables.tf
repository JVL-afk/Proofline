variable "expected_state_account_id" {
  description = "Exact approved AWS account that owns the protected Terraform backend."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_state_account_id))
    error_message = "expected_state_account_id must contain exactly 12 digits."
  }
}

variable "aws_region" {
  description = "Owner-confirmed backend region."
  type        = string
  default     = "us-east-2"

  validation {
    condition     = var.aws_region == "us-east-2"
    error_message = "The Phase 1 backend is restricted to us-east-2."
  }
}

variable "plan_principal_arns" {
  description = "Approved short-lived principals permitted to assume the state plan role."
  type        = set(string)

  validation {
    condition     = length(var.plan_principal_arns) > 0
    error_message = "At least one approved plan principal is required."
  }
}

variable "apply_principal_arns" {
  description = "Approved short-lived principals permitted to assume the separately gated apply role."
  type        = set(string)

  validation {
    condition     = length(var.apply_principal_arns) > 0
    error_message = "At least one approved apply principal is required."
  }
}

variable "phase1_vpc_id" {
  description = "Observed Phase 1 VPC used to constrain private Route 53 hosted-zone creation."
  type        = string

  validation {
    condition     = can(regex("^vpc-[0-9a-f]+$", var.phase1_vpc_id))
    error_message = "phase1_vpc_id must be an observed AWS VPC identifier."
  }
}

variable "phase1_database_kms_key_arn" {
  description = "Observed exact Phase 1 database KMS key authorized for RDS service grants."
  type        = string

  validation {
    condition = can(regex(
      "^arn:aws:kms:us-east-2:[0-9]{12}:key/[0-9a-f-]+$",
      var.phase1_database_kms_key_arn,
    ))
    error_message = "phase1_database_kms_key_arn must identify an observed us-east-2 KMS key."
  }
}
