output "capture_bucket_name" {
  description = "Deterministic exact restricted-capture bucket name."
  value       = local.capture_bucket_name
}

output "capture_bucket_arn" {
  description = "Deterministic exact restricted-capture bucket ARN."
  value       = "arn:${var.partition}:s3:::${local.capture_bucket_name}"
}

output "audit_bucket_name" {
  description = "Deterministic exact audit bucket name."
  value       = local.audit_bucket_name
}

output "audit_bucket_arn" {
  description = "Deterministic exact audit bucket ARN."
  value       = "arn:${var.partition}:s3:::${local.audit_bucket_name}"
}
