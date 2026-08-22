locals {
  capture_bucket_suffix = substr(
    sha256("${var.account_id}:${var.aws_region}:${var.name_prefix}:restricted-captures"),
    0,
    26,
  )
  audit_bucket_suffix = substr(
    sha256("${var.account_id}:${var.aws_region}:${var.name_prefix}:audit"),
    0,
    26,
  )

  capture_bucket_name = "${var.name_prefix}-restricted-captures-${local.capture_bucket_suffix}"
  audit_bucket_name   = "${var.name_prefix}-audit-${local.audit_bucket_suffix}"
}
