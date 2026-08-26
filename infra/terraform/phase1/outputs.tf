output "evidence_manifest_inputs" {
  description = "Non-secret observed identifiers; verify again through AWS before approval."
  value = {
    account_id                                 = data.aws_caller_identity.current.account_id
    region                                     = var.aws_region
    vpc_id                                     = aws_vpc.phase1.id
    private_subnet_ids                         = aws_subnet.private[*].id
    route_table_ids                            = [aws_route_table.private.id, aws_route_table.public_egress.id]
    egress_eip                                 = aws_eip.research_egress.public_ip
    worker_security_group_id                   = aws_security_group.worker.id
    database_security_group_id                 = aws_security_group.database.id
    ecs_cluster_arn                            = aws_ecs_cluster.phase1.arn
    ecs_service_id                             = aws_ecs_service.worker.id
    ecs_task_definition_arn                    = aws_ecs_task_definition.worker.arn
    sampled_slot_activator_task_definition_arn = aws_ecs_task_definition.sampled_slot_activator.arn
    intelligence_service_id                    = aws_ecs_service.intelligence.id
    intelligence_task_definition_arn           = aws_ecs_task_definition.intelligence.arn
    worker_image_digest                        = var.worker_image_uri
    rds_instance_arn                           = aws_db_instance.phase1.arn
    rds_resource_id                            = aws_db_instance.phase1.resource_id
    capture_bucket_arn                         = aws_s3_bucket.captures.arn
    audit_bucket_arn                           = aws_s3_bucket.audit.arn
    kms_key_arns = [
      aws_kms_key.captures.arn,
      aws_kms_key.database.arn,
      aws_kms_key.logs.arn
    ]
    workload_role_arn                         = aws_iam_role.worker.arn
    operator_role_arn                         = aws_iam_role.operator.arn
    kill_operator_role_arn                    = aws_iam_role.kill_operator.arn
    cloudtrail_arn                            = aws_cloudtrail.phase1.arn
    operations_topic_arn                      = aws_sns_topic.operations.arn
    kill_switch_parameter                     = aws_ssm_parameter.kill_switch.arn
    research_release_parameter                = aws_ssm_parameter.research_release.arn
    sampled_slot_execution_approval_parameter = aws_ssm_parameter.sampled_slot_execution_approval.arn
    worker_desired_count                      = var.worker_desired_count
    intelligence_worker_desired_count         = var.intelligence_worker_desired_count
  }
}
