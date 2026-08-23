locals {
  primary_a_identity_center_instance_arn = "arn:aws:sso:::instance/ssoins-668449c46cda2b4b"
}

variable "primary_a_identity_store_user_id" {
  description = "Observed Identity Store user ID for PRIMARY_A_ACTOR. Supply only through a protected process environment; never commit it."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.primary_a_identity_store_user_id) >= 10
    error_message = "The system-observed PRIMARY_A Identity Store user ID is required."
  }
}

resource "aws_ssoadmin_permission_set" "primary_a_authentication_only" {
  name             = "m67-primary-a-auth-only"
  description      = "Authentication-only Phase 1 identity proof for PRIMARY_A_ACTOR; no service permissions attached."
  instance_arn     = local.primary_a_identity_center_instance_arn
  session_duration = "PT1H"

  tags = {
    DataClass = "identity-control"
    Purpose   = "primary-a-independent-authentication-only"
  }
}

# Deliberately attach no inline, AWS-managed, customer-managed, permissions-boundary, or
# application policy. The assignment exists only so PRIMARY_A can obtain an independently
# auditable SSO role session and call STS GetCallerIdentity, which AWS permits without an IAM allow.
resource "aws_ssoadmin_account_assignment" "primary_a_authentication_only" {
  instance_arn       = local.primary_a_identity_center_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.primary_a_authentication_only.arn
  principal_id       = var.primary_a_identity_store_user_id
  principal_type     = "USER"
  target_id          = data.aws_caller_identity.current.account_id
  target_type        = "AWS_ACCOUNT"
}
