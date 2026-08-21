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
