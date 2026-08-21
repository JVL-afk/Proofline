variable "expected_account_id" {
  description = "Exact approved AWS account for the Phase 1 worker registry."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.expected_account_id))
    error_message = "expected_account_id must contain exactly 12 digits."
  }
}

variable "aws_region" {
  description = "Approved Phase 1 AWS region."
  type        = string
  default     = "us-east-2"

  validation {
    condition     = var.aws_region == "us-east-2"
    error_message = "The Phase 1 worker registry is restricted to us-east-2."
  }
}

variable "publisher_principal_arns" {
  description = "Approved short-lived principals allowed to assume the worker image publisher role."
  type        = set(string)

  validation {
    condition     = length(var.publisher_principal_arns) > 0
    error_message = "At least one approved short-lived publisher principal is required."
  }
}
