resource "aws_s3_bucket" "captures" {
  bucket_prefix = "${var.name_prefix}-restricted-captures-"
}

resource "aws_s3_bucket_public_access_block" "captures" {
  bucket                  = aws_s3_bucket.captures.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "captures" {
  bucket = aws_s3_bucket.captures.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_versioning" "captures" {
  bucket = aws_s3_bucket.captures.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "captures" {
  bucket = aws_s3_bucket.captures.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.captures.arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "captures" {
  bucket = aws_s3_bucket.captures.id
  rule {
    id     = "approved-restricted-capture-retention"
    status = "Enabled"
    filter {}
    expiration { days = var.capture_retention_days }
    noncurrent_version_expiration {
      noncurrent_days = var.capture_retention_days
    }
  }

  depends_on = [aws_s3_bucket_versioning.captures]
}

resource "aws_s3_bucket" "audit" {
  bucket_prefix = "${var.name_prefix}-audit-"
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "audit" {
  bucket = aws_s3_bucket.audit.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.logs.arn
    }
  }
}

data "aws_iam_policy_document" "audit_bucket" {
  statement {
    sid    = "CloudTrailAclCheck"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions   = ["s3:GetBucketAcl"]
    resources = [aws_s3_bucket.audit.arn]
  }

  statement {
    sid    = "CloudTrailWrite"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.audit.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"]
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
  }

  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.audit.arn, "${aws_s3_bucket.audit.arn}/*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "audit" {
  bucket = aws_s3_bucket.audit.id
  policy = data.aws_iam_policy_document.audit_bucket.json
}
