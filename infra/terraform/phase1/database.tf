resource "aws_db_subnet_group" "phase1" {
  name       = "${var.name_prefix}-database"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "phase1" {
  identifier                          = "${var.name_prefix}-postgres"
  engine                              = "postgres"
  engine_version                      = "18.3"
  instance_class                      = "db.t4g.micro"
  allocated_storage                   = 20
  max_allocated_storage               = 50
  storage_type                        = "gp3"
  storage_encrypted                   = true
  kms_key_id                          = aws_kms_key.database.arn
  db_name                             = var.database_name
  username                            = var.database_master_username
  manage_master_user_password         = true
  master_user_secret_kms_key_id       = aws_kms_key.database.arn
  iam_database_authentication_enabled = true
  publicly_accessible                 = false
  db_subnet_group_name                = aws_db_subnet_group.phase1.name
  vpc_security_group_ids              = [aws_security_group.database.id]
  backup_retention_period             = var.backup_retention_days
  delete_automated_backups            = true
  copy_tags_to_snapshot               = true
  deletion_protection                 = true
  skip_final_snapshot                 = true
  auto_minor_version_upgrade          = false
  apply_immediately                   = false

  depends_on = [aws_iam_service_linked_role.rds]
}
