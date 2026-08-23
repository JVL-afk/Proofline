# Required Offline Roster and Attestation

This is documentation only. It contains no real candidate and is not an executable input artifact.

## Exact input paths

```text
local-data/m6.7/seed-source-acquisition/input/offline-business-roster.json
local-data/m6.7/seed-source-acquisition/input/offline-business-roster-attestation.json
```

The roster is a UTF-8 JSON array with 24-100 items and must validate against
`phase1-seed-construction-input-v1.schema.json`. The exact-instance attestation must contain every
field in `offline-seed-source-instance-attestation.template.json`, with no null decision value.

## Synthetic one-record shape example

This single record intentionally fails the 24-record minimum and cannot be supplied as the roster.
Replicate the structure—not these values—for the complete predeclared frame.

```json
[
  {
    "public_business_name": "Synthetic Commercial HVAC Fixture 001",
    "public_business_aliases": ["Synthetic HVAC Fixture 001"],
    "texas_city_or_service_area": "Synthetic City, TX",
    "first_party_host_candidate": "fixture-001.example.test",
    "organization_group_hint": "synthetic-organization-001",
    "franchise_or_shared_brand_hint": null,
    "lead_flow_unit_hint": "synthetic-lead-flow-001",
    "distinct_lead_flow_observations": ["Synthetic business-level lead-flow evidence"],
    "identity_ambiguous": false,
    "eligibility_observations": {
      "identity": ["Synthetic business identity evidence"],
      "texas": ["Synthetic Texas operation evidence"],
      "commercial_hvac": ["Synthetic commercial HVAC evidence"],
      "b2b": ["Synthetic B2B evidence"],
      "operational": ["Synthetic public operating-status evidence"],
      "first_party_host": ["Synthetic first-party-host evidence"]
    },
    "provenance": [
      {
        "source_id": "SYNTHETIC_OFFLINE_SOURCE_001",
        "source_artifact_ref": "synthetic-artifact-001",
        "source_artifact_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        "locator": "synthetic:row:1",
        "observed_at": "2026-08-23T00:00:00Z"
      }
    ]
  }
]
```

The all-zero artifact digest and `.example.test` host are placeholders and must never appear in a
real input.

## Completed exact-instance attestation shape

```json
{
  "record_type": "M67_OFFLINE_SEED_SOURCE_INSTANCE_ATTESTATION",
  "version": "1.0.0",
  "state": "ATTESTED_READY_FOR_ACQUISITION",
  "source_class": "OWNER_CONTROLLED_FIELD_LIMITED_OFFLINE_BUSINESS_ROSTER_V1",
  "source_kind": "DISCOVERY_SOURCE_SUBSTAGE",
  "artifact_ref": "OWNER_ASSIGNED_OPAQUE_ARTIFACT_REF",
  "artifact_sha256_before_parse": "ACTUAL_64_CHARACTER_LOWERCASE_SHA256",
  "artifact_bytes": "ACTUAL_INTEGER_NOT_GREATER_THAN_5000000",
  "record_count": "ACTUAL_INTEGER_FROM_24_TO_100",
  "complete_predeclared_frame": true,
  "origin_and_construction_method": "FACTUAL_DESCRIPTION_OF_THE_OFFLINE_ROSTER_ORIGIN",
  "row_level_provenance_present": true,
  "permitted_use_and_reuse_basis": "FACTUAL_OWNER_ATTESTATION_OR_APPROVED_SOURCE_REVIEW_REFERENCE",
  "terms_access_review": "APPROVED_EXACT_INSTANCE_OR_NOT_APPLICABLE_OWNER_CREATED",
  "robots_review": "NOT_APPLICABLE_NO_NETWORK",
  "third_party_restrictions": "NONE_OR_EXACT_RESTRICTIONS_AND_APPROVAL_REFERENCE",
  "business_only_field_limited_export": true,
  "prohibited_field_scan_result": "OWNER_ATTESTED_ABSENT_PENDING_SYSTEM_VERIFICATION",
  "opportunity_or_outcome_selection_absent": true,
  "accountable_owner_actor_ref": "OWNER_ACTOR",
  "privacy_source_reviewer_actor_ref": "OWNER_ACTOR",
  "qualified_source_review_state": "NOT_REQUIRED_OWNER_CREATED_AND_RIGHTS_ATTESTED_OR_COMPLETED_APPROVAL_REF",
  "effective_at": "ACTUAL_EFFECTIVE_TIMESTAMP",
  "expires_at": "ACTUAL_EXPIRY_TIMESTAMP_NOT_AFTER_AUTHORIZATION_EXPIRY",
  "configuration_hash": "CANONICAL_SHA256_WITH_CONFIGURATION_HASH_OMITTED"
}
```

If third-party rights or reuse are uncertain, `qualified_source_review_state` must instead remain
pending and the source is `SOURCE_BLOCKED`. OWNER_ACTOR cannot manufacture a legal conclusion.
