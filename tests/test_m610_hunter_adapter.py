"""M6.10 Hunter adapter - fail-closed gating.

Owner authorization "ACTIVATE HUNTER AND RESUME REAL M6.10 A-PLUS
RESOLUTION" (2026-09-06). No live Hunter API call is made anywhere in this
file - these prove the adapter refuses to construct (and therefore can
never make a network call) unless the counsel-controlled preconditions are
all met. The live-call path is exercised only by the run script, and only
after the vendor-activation gate passes.
"""

from __future__ import annotations

import pytest
from opintel_contact_resolution import (
    AuthorityDomain,
    AuthorityLevel,
    ResolutionAuthorityError,
    SourceAuthorityMatrix,
    VendorComplianceChecklist,
    counsel_controlled_authority_matrix,
)
from opintel_contact_resolution_local import HunterAdapter

_FULLY_SATISFIED = VendorComplianceChecklist(
    lawful_sourcing_warranty=True,
    per_record_provenance=True,
    no_sensitive_categories=True,
    no_minors=True,
    no_scraped_credentials=True,
    deletion_on_request=True,
    vendor_contractual_controls_or_indemnity=True,
    texas_data_broker_registry_screened=True,
)


def test_adapter_refuses_without_contact_enrichment_authority() -> None:
    with pytest.raises(ResolutionAuthorityError, match="CONTACT_ENRICHMENT_AUTHORITY"):
        HunterAdapter(
            matrix=SourceAuthorityMatrix(),  # everything NOT_AUTHORIZED
            vendor_checklist=_FULLY_SATISFIED,
        )


def test_adapter_refuses_when_vendor_checklist_not_satisfied() -> None:
    incomplete = VendorComplianceChecklist(
        lawful_sourcing_warranty=True,
        per_record_provenance=True,
        no_sensitive_categories=True,
        no_minors=True,
        no_scraped_credentials=True,
        deletion_on_request=True,
        vendor_contractual_controls_or_indemnity=True,
        # texas_data_broker_registry_screened missing -> not satisfied
    )
    with pytest.raises(ResolutionAuthorityError, match="texas_data_broker_registry_screened"):
        HunterAdapter(
            matrix=counsel_controlled_authority_matrix(),
            vendor_checklist=incomplete,
        )


def test_adapter_constructs_only_when_both_gates_pass() -> None:
    # This constructs the adapter object (no network call happens in
    # __init__) - it proves the gate logic, not a live query.
    adapter = HunterAdapter(
        matrix=counsel_controlled_authority_matrix(),
        vendor_checklist=_FULLY_SATISFIED,
    )
    assert adapter.provider_name == "Hunter (hunter.io)"
    assert adapter.required_authority is AuthorityDomain.CONTACT_ENRICHMENT_AUTHORITY


def test_verifier_refuses_without_email_verification_authority() -> None:
    # Enrichment authorized, email verification NOT.
    matrix = SourceAuthorityMatrix(
        levels={
            **SourceAuthorityMatrix().levels,
            AuthorityDomain.CONTACT_ENRICHMENT_AUTHORITY: AuthorityLevel.AUTHORIZED_WITH_CONTROLS,
        }
    )
    adapter = HunterAdapter(matrix=matrix, vendor_checklist=_FULLY_SATISFIED)
    with pytest.raises(ResolutionAuthorityError, match="EMAIL_VERIFICATION_AUTHORITY"):
        adapter.verify_email("greg@aplusac.com")


def test_verifier_rejects_syntactically_invalid_email_before_any_call() -> None:
    adapter = HunterAdapter(
        matrix=counsel_controlled_authority_matrix(),
        vendor_checklist=_FULLY_SATISFIED,
    )
    with pytest.raises(ResolutionAuthorityError, match="syntactically valid"):
        adapter.verify_email("not-an-email")
