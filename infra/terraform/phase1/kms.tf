resource "aws_kms_key" "captures" {
  description             = "M6.7 restricted source captures"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_kms_alias" "captures" {
  name          = "alias/${var.name_prefix}-captures"
  target_key_id = aws_kms_key.captures.key_id
}

resource "aws_kms_key" "database" {
  description             = "M6.7 Phase 1 RDS"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_kms_alias" "database" {
  name          = "alias/${var.name_prefix}-database"
  target_key_id = aws_kms_key.database.key_id
}

resource "aws_kms_key" "logs" {
  description             = "M6.7 Phase 1 logs and audit evidence"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_kms_alias" "logs" {
  name          = "alias/${var.name_prefix}-logs"
  target_key_id = aws_kms_key.logs.key_id
}
