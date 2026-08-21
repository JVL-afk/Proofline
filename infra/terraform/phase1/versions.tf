terraform {
  required_version = ">= 1.15.9, < 1.16.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.53.0"
    }
  }
}
