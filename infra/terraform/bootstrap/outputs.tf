output "backend_configuration" {
  description = "Non-secret values for the Phase 1 partial backend file after bootstrap apply."
  value = {
    bucket         = aws_s3_bucket.state.id
    key            = local.state_key
    region         = var.aws_region
    kms_key_id     = aws_kms_key.state.arn
    use_lockfile   = true
    plan_role_arn  = aws_iam_role.state_plan.arn
    apply_role_arn = aws_iam_role.state_apply.arn
    state_account  = data.aws_caller_identity.current.account_id
    audit_bucket   = aws_s3_bucket.audit.id
    cloudtrail_arn = aws_cloudtrail.state.arn
  }
}
