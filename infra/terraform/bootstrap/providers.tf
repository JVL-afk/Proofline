provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.expected_state_account_id]

  default_tags {
    tags = {
      ManagedBy     = "terraform-bootstrap"
      Milestone     = "M6.7-Phase1"
      DataClass     = "terraform-state"
      LiveAuthority = "none"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
