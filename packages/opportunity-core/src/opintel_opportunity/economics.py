"""Deterministic, versioned Commercial HVAC lead-response economics."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from opintel_opportunity.domain import (
    AssumptionRevision,
    EconomicRun,
    EconomicStatus,
    OpportunityValidationError,
    ValueState,
)

FORMULA_VERSION = "commercial_hvac.lead_response.potential_incremental_revenue@1"
REQUIRED_KEYS = (
    "monthly_inbound_leads",
    "affected_share",
    "conversion_lift",
    "average_customer_value",
)


def checksum(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def calculate_economics(
    run_id: UUID,
    hypothesis_id: UUID,
    assumptions: tuple[AssumptionRevision, ...],
    now: datetime,
) -> EconomicRun:
    values = {item.key: item for item in assumptions}
    if set(values) != set(REQUIRED_KEYS):
        raise OpportunityValidationError("exactly four formula inputs are required")
    unknown = [item for item in assumptions if item.value_state == ValueState.UNKNOWN]
    manifest = [
        {
            "id": str(item.id),
            "key": item.key,
            "revision": item.revision,
            "state": item.value_state,
            "value": item.decimal_value,
            "unit": item.unit,
            "currency": item.currency,
            "time_basis": item.time_basis,
            "source_kind": item.source_kind,
        }
        for item in assumptions
    ]
    digest = checksum({"formula": FORMULA_VERSION, "inputs": manifest})
    if unknown:
        return EconomicRun(
            id=run_id,
            hypothesis_id=hypothesis_id,
            formula_version=FORMULA_VERSION,
            status=EconomicStatus.INSUFFICIENT_DATA,
            assumption_revision_ids=tuple(item.id for item in assumptions),
            monthly_potential_incremental_revenue=None,
            annualized_potential_incremental_revenue=None,
            currency="USD",
            result_label="insufficient data — required business inputs are unknown",
            manifest_checksum=digest,
            created_at=now,
        )
    expected_metadata = {
        "monthly_inbound_leads": ("leads", None, "month"),
        "affected_share": ("ratio", None, "dimensionless"),
        "conversion_lift": ("ratio", None, "dimensionless"),
        "average_customer_value": ("currency_per_win", "USD", "per_win"),
    }
    decimals: dict[str, Decimal] = {}
    try:
        for key, item in values.items():
            if item.decimal_value is None:
                raise OpportunityValidationError(f"{key} has no decimal value")
            if (item.unit, item.currency, item.time_basis) != expected_metadata[key]:
                raise OpportunityValidationError(f"{key} metadata does not match formula version")
            value = Decimal(item.decimal_value)
            if not value.is_finite() or value < 0:
                raise OpportunityValidationError(f"{key} must be finite and non-negative")
            if key in {"affected_share", "conversion_lift"} and value > 1:
                raise OpportunityValidationError(f"{key} must be between zero and one")
            decimals[key] = value
    except InvalidOperation as error:
        raise OpportunityValidationError("formula input is not a valid decimal") from error
    monthly = (
        decimals["monthly_inbound_leads"]
        * decimals["affected_share"]
        * decimals["conversion_lift"]
        * decimals["average_customer_value"]
    ).quantize(Decimal("0.01"))
    annual = (monthly * Decimal(12)).quantize(Decimal("0.01"))
    hypothetical = any(item.value_state == ValueState.PROPOSED for item in assumptions)
    return EconomicRun(
        id=run_id,
        hypothesis_id=hypothesis_id,
        formula_version=FORMULA_VERSION,
        status=EconomicStatus.HYPOTHETICAL if hypothetical else EconomicStatus.COMPLETE,
        assumption_revision_ids=tuple(item.id for item in assumptions),
        monthly_potential_incremental_revenue=str(monthly),
        annualized_potential_incremental_revenue=str(annual),
        currency="USD",
        result_label=(
            "hypothetical potential incremental revenue — not actual loss or realized gain"
            if hypothetical
            else "potential incremental revenue from verified business-specific inputs"
        ),
        manifest_checksum=digest,
        created_at=now,
    )
