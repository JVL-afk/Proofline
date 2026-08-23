# Owner checklist: PRIMARY_A independent authentication

The PRIMARY_A designation is already approved. Do not re-enter a name, email, or subject ID.

1. **Request the authentication-only invitation/assignment.** Send the following text to the
   approved AWS IAM Identity Center/upstream-IdP administrator through the normal protected access
   request channel. This is an **invitation/access request** and must happen **before PRIMARY_A
   authenticates**:

   > Please provision or identify one existing least-privilege authentication-only AWS IAM Identity
   > Center/upstream-IdP assignment for PRIMARY_A_ACTOR in AWS account 785072247535 for the M6.7
   > Phase 1 environment in us-east-2. It must permit independent MFA-backed authentication and
   > auditable challenge reconciliation only; it must not grant administrator, operator, workload,
   > kill-switch, discovery, research, data, or delivery authority. Return through the protected
   > system interface—not chat or Git—the IdP issuer/instance reference, authentication audience or
   > permission-set reference, secure invitation status, MFA policy reference, assignment identifier,
   > and expiry/review metadata. Do not return the human name, email, raw subject, tokens, cookies,
   > MFA secrets, recovery codes, or credentials.

   Expected result: a system-captured `IDP_ASSIGNMENT_EVIDENCE_SHA256`. If the IdP administrator
   cannot provide an authentication-only path, stop; do not assign an administrator/operator role.

2. **Approve one challenge after Codex fills every binding.** Paste the following into this Codex
   task only after the state is `READY_FOR_PRIMARY_A_CHALLENGE_ISSUANCE_AUTHORIZATION`. This is an
   **approval**, completed **before PRIMARY_A authenticates**:

   > I approve APPROVE_PRIMARY_A_CHALLENGE_ISSUANCE for AWS account 785072247535 in us-east-2,
   > binding PRIMARY_A authentication package SHA-256 `<AUTHENTICATION_PACKAGE_SHA256>`, approved
   > IdP issuer reference `<IDP_ISSUER_REF>`, authentication-only audience `<AUDIENCE_REF>`,
   > assignment evidence SHA-256 `<IDP_ASSIGNMENT_EVIDENCE_SHA256>`, and challenge mechanism SHA-256
   > `<CHALLENGE_MECHANISM_SHA256>`. This authorizes issuance of exactly one fresh, expiring,
   > single-use challenge to PRIMARY_A_ACTOR through the approved independent IdP session and secure
   > invitation path. It authorizes no owner-session substitution, AWS administration, discovery,
   > research, person/contact processing, Slot 1, communication, or M6.7 permission change.

   Do not fill the placeholders yourself. Codex derives them from observed IdP and frozen package
   evidence and emits the completed statement. Expected result: a challenge record/hash in state
   `PRIMARY_A_CHALLENGE_ISSUED`; the raw nonce stays outside Git.

3. **Accept or reject the reconciled identity evidence.** After PRIMARY_A authenticates and Codex
   reports `PRIMARY_A_RECONCILED_PENDING_OWNER_ACCEPTANCE`, paste the exact completed statement Codex
   emits from this template. This is a **reconciliation approval**, completed **after PRIMARY_A
   authentication**:

   > I approve ACCEPT_PRIMARY_A_INDEPENDENT_AUTHENTICATION for AWS account 785072247535 and the M6.7
   > Phase 1 environment in us-east-2, binding PRIMARY_A authentication evidence SHA-256
   > `<PRIMARY_A_AUTHENTICATION_EVIDENCE_SHA256>`, challenge ID `<CHALLENGE_ID>`, authenticated event
   > reference `<AUTH_EVENT_REF>`, opaque subject digest `<OPAQUE_SUBJECT_DIGEST>`, approved IdP issuer
   > reference `<IDP_ISSUER_REF>`, authentication-only audience `<AUDIENCE_REF>`, and reconciliation
   > evidence SHA-256 `<RECONCILIATION_EVIDENCE_SHA256>`. I accept that the independently authenticated
   > subject reconciles to PRIMARY_A_ACTOR and remains distinct from OWNER_ACTOR for the
   > INDEPENDENT_SECOND_REVIEWER role. This acceptance satisfies only the identity prerequisite and
   > authorizes no discovery, research, person/contact processing, Slot 1, communication, AWS
   > administration, or other M6.7 permission.

   Again, do not fill placeholders yourself. Expected result: an immutable accepted evidence hash
   and state `PRIMARY_A_INDEPENDENT_AUTHENTICATION_ACCEPTED`.

4. **Later acknowledge the binding in the exact discovery release.** This happens only after all
   source-policy blockers close and a specific discovery release exists. It is a **separate later
   acknowledgement/approval**, not part of authentication:

   > I acknowledge that PRIMARY_A independent authentication evidence SHA-256
   > `<ACCEPTED_PRIMARY_A_EVIDENCE_SHA256>` satisfies only the independent-reviewer identity
   > prerequisite for discovery release `<EXACT_DISCOVERY_RELEASE_ID_AND_SHA256>`. I understand
   > authentication is not independent opportunity review or approval, and no state advances unless
   > I separately sign the exact REAL_BUSINESS_DISCOVERY release after all remaining source and policy
   > prerequisites pass.

   Codex fills both placeholders only when the state is
   `READY_FOR_REAL_BUSINESS_DISCOVERY_OWNER_SIGNATURE`.
