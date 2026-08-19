from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from opintel_qualification.tournament2_final_readiness import FINAL_READINESS_MANIFEST
from opintel_qualification_live.tournament2_execution import (
    FINAL_MANIFEST_HASH,
    HARD_BUDGET_MICROS,
    OneShotTournamentRunner,
    create_authorization,
    execution_plan,
)

NOW = datetime(2026, 8, 19, 13, 0, tzinfo=UTC)


def test_exact_manifest_builds_frozen_384_call_plan() -> None:
    assert FINAL_READINESS_MANIFEST.manifest_hash == FINAL_MANIFEST_HASH
    plan = execution_plan()
    assert len(plan) == 384
    assert len({(item.deployment_key, item.binding.task) for item in plan}) == 12
    assert sum(item.reserved_cost_micros for item in plan) < HARD_BUDGET_MICROS
    assert {item.stage for item in plan} == {
        "safety_gauntlet",
        "hidden_qualification",
        "required_repetitions",
    }


def test_authorization_fails_closed_for_hash_window_and_budget_drift() -> None:
    with pytest.raises(ValueError, match="exact final"):
        create_authorization(actor="owner", now=NOW, nonce="n", manifest_hash="0" * 64)
    with pytest.raises(ValueError, match="window"):
        create_authorization(
            actor="owner",
            now=datetime(2026, 8, 20, 1, tzinfo=UTC),
            nonce="n",
            manifest_hash=FINAL_MANIFEST_HASH,
        )
    auth = create_authorization(
        actor="owner", now=NOW, nonce="n", manifest_hash=FINAL_MANIFEST_HASH
    )
    with pytest.raises(ValueError, match="USD 25"):
        OneShotTournamentRunner(
            replace(auth, budget_micros=25_000_001),
            now=lambda: NOW,
            secret_for_provider=lambda _: "fixture",
            transport_for_provider=lambda _: None,  # type: ignore[arg-type,return-value]
            wait=lambda _: None,
        )


def test_authorization_cannot_activate_routes_or_release_reviews() -> None:
    auth = create_authorization(
        actor="owner", now=NOW, nonce="n", manifest_hash=FINAL_MANIFEST_HASH
    )
    assert not auth.route_activation_allowed
    assert not auth.review_package_release_allowed
    assert auth.synthetic_only and auth.hidden_access
