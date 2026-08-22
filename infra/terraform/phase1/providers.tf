provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.expected_aws_account_id]

  default_tags {
    tags = {
      ManagedBy          = "terraform"
      Milestone          = "M6.7-Phase1"
      DataClassification = "confidential"
      LiveAuthority      = "none"
    }
  }
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

module "phase1_identifiers" {
  source = "../modules/phase1-identifiers"

  account_id  = data.aws_caller_identity.current.account_id
  aws_region  = var.aws_region
  name_prefix = var.name_prefix
  partition   = data.aws_partition.current.partition
}
