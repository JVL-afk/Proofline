# AWS CLI v2 and short-lived SSO setup

The only owner-supplied AWS facts are the approved dedicated account/organization (if it already
exists) and the IAM Identity Center/SSO entry point. Never paste access keys, secret keys, session
tokens, passwords, or SSO refresh tokens into chat or Git.

1. Install AWS CLI v2 from the signed AWS installer and verify its version and publisher.
2. Run `aws configure sso --profile m67-phase1-owner` locally.
3. Supply the organization's SSO start URL or issuer, SSO region, approved account, and approved
   permission set through the interactive CLI prompt.
4. Run `aws sso login --profile m67-phase1-owner` locally.
5. The system calls `aws sts get-caller-identity` and IAM/Organizations read APIs to record the
   account, organization if visible, partition, authenticated role, and session evidence.
6. The system derives stable IAM role principals, deterministic resource names, backend values, and
   Terraform variables. It never commits the SSO cache or generated credentials.

If AWS CLI v2 is absent, installation requires a separate local-software installation approval. No
AWS resource is created by installation, configuration, login, or caller-identity verification.
