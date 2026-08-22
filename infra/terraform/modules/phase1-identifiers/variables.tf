variable "account_id" {
  description = "Exact AWS account that owns the Phase 1 resources."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "account_id must contain exactly 12 digits."
  }
}

variable "aws_region" {
  description = "Exact Phase 1 AWS region."
  type        = string

  validation {
    condition     = var.aws_region == "us-east-2"
    error_message = "Phase 1 identifiers are restricted to us-east-2."
  }
}

variable "name_prefix" {
  description = "Approved Phase 1 resource prefix."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.name_prefix))
    error_message = "name_prefix must be a short lowercase DNS-style label."
  }
}

variable "partition" {
  description = "AWS partition used to construct exact ARNs."
  type        = string
  default     = "aws"
}
