output "registry_evidence_inputs" {
  description = "Non-secret identifiers to observe after a separately authorized registry apply."
  value = {
    account_id         = data.aws_caller_identity.current.account_id
    region             = var.aws_region
    repository_name    = aws_ecr_repository.worker.name
    repository_url     = aws_ecr_repository.worker.repository_url
    repository_arn     = aws_ecr_repository.worker.arn
    kms_key_arn        = aws_kms_key.registry.arn
    kms_alias_arn      = aws_kms_alias.registry.arn
    publisher_role_arn = aws_iam_role.publisher.arn
  }
}
