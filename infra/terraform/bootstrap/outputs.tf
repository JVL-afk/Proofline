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

output "workload_identity_configuration" {
  description = "Separate provider identities for authenticated Phase 1 plan and approved apply."
  value = {
    workload_plan_role_arn  = aws_iam_role.workload_plan.arn
    workload_apply_role_arn = aws_iam_role.workload_apply.arn
    plan_state_role_arn     = local.phase1_state_plan_role_arn
    apply_state_role_arn    = local.phase1_state_apply_role_arn
  }
}
