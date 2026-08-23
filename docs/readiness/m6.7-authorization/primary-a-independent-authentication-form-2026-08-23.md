# PRIMARY_A independent-authentication form

## What this is

You are acting only as the independent second reviewer/control for the M6.7 Phase 1 pilot. You are
not becoming the project owner, legal reviewer, AWS administrator, operator, or delivery user. This
authentication proves that a second human—not OWNER_ACTOR—controls the already-approved
`PRIMARY_A_ACTOR` role binding. It grants no discovery, research, contact, communication, or Slot 1
permission.

## Before you begin

Use only the secure invitation supplied by the approved identity administrator. It must identify:

- AWS account `785072247535`;
- Phase 1/M6.7 environment in `us-east-2`;
- an authentication-only audience or assignment that is not the owner's administrator/operator
  session;
- one fresh challenge ID and its expiry.

If any item differs, is missing, or the challenge is expired, stop. Do not use somebody else's
session and do not ask the owner for their credentials.

## What you do

1. Open the approved AWS IAM Identity Center/upstream-IdP link from the secure invitation. Do not
   copy the link into Git, repository files, or chat.
2. Sign in using your own independently controlled identity and complete MFA.
3. In the approved challenge prompt, enter the one-time challenge value supplied through the same
   secure channel. Do not send that value to the owner in chat or email.
4. Read and affirm the following text, substituting only the displayed challenge ID:

> I, the human independently authenticating as PRIMARY_A_ACTOR, affirm that I am acting independently
> from OWNER_ACTOR for the INDEPENDENT_SECOND_REVIEWER role; I authenticated through the approved
> identity provider using MFA for AWS account 785072247535 and the M6.7 Phase 1 environment in
> us-east-2; I am responding to one-time challenge `<CHALLENGE_ID>`; I consent to the system recording
> only an opaque or pseudonymous binding and authentication evidence; and I understand this role does
> not authorize unrelated project, AWS, discovery, research, contact, communication, or delivery
> actions.

5. Select/sign **Affirm** once. Do not retry an expired, rejected, or already-used challenge. Ask the
   owner to request a newly approved challenge instead.

## What you do not fill in

The system—not you—records the IdP issuer, opaque subject digest, authentication event ID and time,
audience/environment, MFA assurance, challenge commitment, evidence hashes, and reconciliation
result. Do not manually send your name, email, telephone number, raw IdP subject, password, access
or refresh token, session cookie, MFA secret, recovery code, SSO cache, or credential to the owner,
Codex, chat, or the repository.

Authentication completion satisfies only the independent identity prerequisite. It does not mean
that you approved business discovery or completed a later independent opportunity review. Those
remain separate events.
