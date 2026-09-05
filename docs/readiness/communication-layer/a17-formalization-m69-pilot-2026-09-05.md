# A-17 formalization — M6.9 bounded A-Plus pilot (2026-09-05)

Owner authorization 2026-09-05 "NARROW LIVE-GEOGRAPHY VALIDATOR FIX + A-17
FORMALIZATION + REVALIDATE REAL A-PLUS PACKAGE", §3. Formalizes the written
Texas/federal legal guidance PROJECT_OWNER already supplied for this exact
pilot into the project's A-17 record. **No new legal conclusion is added by
this task** — every substantive control and the counsel operational
instruction below are transcribed exactly as supplied.

## Record

`docs/readiness/communication-layer/a17-attorney-result-m69-pilot-2026-09-05.json`,
following the same `A17_ATTORNEY_PROVIDED_RESULT` schema already used for the
Phase 1 research-scope review (`docs/readiness/m6.7-authorization/a17-attorney-result-2026-08-21.json`)
and the pending-signature template
(`docs/readiness/m6.7-authorization/a17-qualified-review.template.json`).

**`state: APPROVE_WITH_CONTROLS`** — scope: US-TX and federal CAN-SPAM, the
one bounded A-Plus first-contact email pilot (ADR-0078 Path B / ADR-0079).

## Controls recorded (verbatim from PROJECT_OWNER's supplied guidance)

CAN-SPAM compliance; valid sender identity (Andrew, Proofline); valid
physical postal address (Proofline, Str. Lucian Blaga, nr. 8, Ciugud, Alba
517240, Romania); clear reply-based opt-out; monitored mailbox
(andrew@proofline.business); opt-out honored within 3 days maximum; no
tracking; no deceptive subject/header/body; no implication of affiliation;
professional/business contact data only; source provenance retained;
suppression enforcement before send; exact message/header/recipient logging.

Every one of these is already implemented and tested, not merely
recorded as a policy statement:

| control | where it is enforced |
|---|---|
| Sender identity / postal / opt-out copy | `opintel_suppression.PROOFLINE_SENDER_IDENTITY` / `resolve_known_disclosure_slots` |
| Opt-out honored within 3 days | `opintel_suppression.OPT_OUT_SUPPRESSION_MAX_SLA = timedelta(days=3)`, tested in `test_opt_out_sla_timestamp_calculation_is_auditable` |
| Suppression enforcement before send, no override | `opintel_suppression.enforce_pre_send_suppression_gate` (Stage A, `37ad4bb`) |
| Source provenance retained | Stage B real-run evidence table (exact URL + sha256 per fact) |
| No deceptive subject (DO_NOT_PREPEND_ADV) | see below |

## Counsel operational instruction: `DO_NOT_PREPEND_ADV`

Recorded as a **counsel-directed operational instruction for this exact
Texas pilot**, not an internally derived legal conclusion — this task does
not assert a general subject-line policy beyond this pilot's scope. Verified:
the real Stage B candidate's subject (`"A quick comparison idea for A-Plus
AC's intake"`) carries no `ADV:` prefix (`subject_has_adv_prefix: false`),
and `test_subject_does_not_receive_adv_prefix` (Stage A suite) regression-
tests that no code path in this repository ever adds one.

## Literal counsel signature — still required

Per ADR-0035 ("A signed, scoped A-17 legal/privacy policy release remains
mandatory before any live adapter") and the project's own precedent record
(`a17-attorney-result-2026-08-21.json`, whose `attestation.reviewer_subject_ref`
and `reviewer_credential_record_ref` were also left `null` pending a verified
identity binding), this task does **not** pretend a literal, credentialed
counsel signature exists. The JSON record's
`attestation.reviewer_subject_ref` / `reviewer_credential_record_ref` are
`null`, and `reviewer_identity_binding_state` is explicitly
`NOT_YET_BOUND_A17_SIGNATURE_REQUIRED`.

**`A17_SIGNATURE_REQUIRED`** — the substantive controls are formally
recorded as `APPROVE_WITH_CONTROLS` from the owner-supplied guidance; what
remains outstanding is binding that guidance to a verified, credentialed
counsel identity/signature, exactly the same outstanding step the project's
own M6.7 precedent left open.

## What this does and does not change

- Does **not** modify or weaken Stage A (suppression registry, opt-out
  workflow, 3-day SLA, pre-send gate, sender/postal configuration).
- Does **not** change M6.9 Path B or M6.8-3's `NOT_CERTIFIED` status.
- Does **not** authorize contact resolution, send, or demo deployment.
- Does resolve the "A-17 never signed" item from
  `m6.9-pilot-package-a-plus-2026-09-04.md` §7 and `m6.9-stage-b-real-run-report-2026-09-05.md`
  from "no policy exists at all" to "APPROVE_WITH_CONTROLS recorded; literal
  signature binding still required" — a narrower, more accurate remaining
  gap than before.
