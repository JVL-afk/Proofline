from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from opintel_qualification.tournament2_machine_closure import ORIGINAL_MANIFEST_HASH
from opintel_qualification_live.contracts import HttpResponse
from opintel_qualification_live.secrets import load_single_provider_secret
from opintel_qualification_live.tournament2_review_recovery import (
    RECOVERY_HARD_CAP_MICROS,
    RECOVERY_TOTAL_MAX_MICROS,
    REVIEW_DIMENSIONS,
    REVIEWER_SLOTS,
    OneShotReviewRecoveryRunner,
    RecoveryAuthorization,
    create_recovery_authorization,
    recovery_plan,
)

NOW = datetime(2026, 8, 19, 15, 0, tzinfo=UTC)


class BaselineTransport:
    def __init__(self) -> None:
        self.calls = 0

    def post(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> HttpResponse:
        assert url == "https://api.anthropic.com/v1/messages"
        assert "x-api-key" in headers
        assert payload["model"] == "claude-sonnet-5"
        prompt = json.loads(payload["messages"][0]["content"])  # type: ignore[index]
        baseline = prompt["task_data"]["baseline"]
        schema = payload["output_config"]["format"]["schema"]  # type: ignore[index]
        properties = schema["properties"]
        if "claims" in properties:
            output = {
                **baseline,
                "cta_id": baseline["cta_id"] or "",
                "reply_safety_label": baseline["reply_safety_label"] or "",
            }
        else:
            claim = baseline["claims"][0]
            output = {
                "rendered_text": claim["text"],
                "claim_ids": [claim["claim_id"]],
                "evidence_ids": claim["evidence_ids"],
                "qualifiers": claim["qualifiers"],
                "protected_unknown_ids": baseline["protected_unknown_ids"],
                "contradiction_ids": baseline["contradiction_ids"],
                "cta_id": baseline["cta_id"],
            }
        body = {
            "id": f"msg_recovery_{self.calls}",
            "model": "claude-sonnet-5",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": json.dumps(output)}],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }
        self.calls += 1
        return HttpResponse(200, {"request-id": f"req-{self.calls}"}, json.dumps(body).encode(), 1)


def _authorization() -> RecoveryAuthorization:
    return create_recovery_authorization(
        actor="project-owner",
        now=NOW,
        expires_at=NOW + timedelta(hours=2),
        nonce="test-nonce",
    )


def test_recovery_scope_and_separate_budget_are_exact() -> None:
    authorization = _authorization()
    plan = recovery_plan()
    assert authorization.original_manifest_hash == ORIGINAL_MANIFEST_HASH
    assert authorization.logical_calls == len(plan) == 105
    assert authorization.maximum_transport_attempts == 210
    assert RECOVERY_TOTAL_MAX_MICROS == 4_753_560 < RECOVERY_HARD_CAP_MICROS == 5_000_000
    assert {item.call.provider for item in plan} == {"anthropic"}
    assert {item.call.model for item in plan} == {"claude-sonnet-5"}
    assert len({item.anonymous_case_id for item in plan}) == 105


def test_recovery_loads_only_the_anthropic_credential(tmp_path: Path) -> None:
    path = tmp_path / "keys.txt"
    path.write_text("OPENAI: not-loaded\nANTHROPIC: exact-secret\nGEMINI: not-loaded\n")
    assert load_single_provider_secret(path, "anthropic") == "exact-secret"


def test_tracked_recovery_summary_preserves_sealed_no_route_result() -> None:
    path = Path("docs/evidence/m6.6b-5r/human-review-recovery-safe-summary.json")
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value["recovery_run_id"] == "551c3c0d-d68e-568c-b9b8-14d947eec22e"
    assert value["execution"] == {
        "calls_planned": 105,
        "calls_attempted": 105,
        "calls_completed": 105,
        "transport_attempts": 105,
        "retries": 0,
        "new_safety_failures": 0,
        "stop_reason": None,
    }
    assert value["artifacts"]["usable_rendered_output_count"] == 105
    assert value["artifacts"]["sealed_package_count"] == 20
    assert value["review"]["packages_sealed"]
    assert not value["review"]["packages_released"]
    assert value["authority"]["qualified_bindings"] == 0
    assert value["authority"]["route_activations"] == 0


def test_recovery_generates_usable_identity_free_sealed_packages() -> None:
    transport = BaselineTransport()
    result = OneShotReviewRecoveryRunner(
        _authorization(),
        now=lambda: NOW,
        anthropic_credential="test-secret",
        transport=transport,
        wait=lambda _: None,
    ).run()
    assert result.calls_attempted == result.calls_completed == transport.calls == 105
    assert len(result.rendered_outputs) == 105
    assert len(result.assignments) == 105 * len(REVIEWER_SLOTS)
    assert len(result.packages) == 5 * len(REVIEWER_SLOTS) == 20
    assert all(item.sealed and not item.released for item in result.packages)
    assert all(
        item.dimensions == REVIEW_DIMENSIONS for pkg in result.packages for item in pkg.cases
    )
    reviewer_json = json.dumps([asdict(item) for item in result.packages], default=str).casefold()
    for prohibited in (
        "anthropic",
        "claude",
        "sonnet",
        "provider",
        "model",
        "latency",
        "token",
        "cost",
    ):
        assert prohibited not in reviewer_json
    assert "controlled synthetic observation" in reviewer_json
    assert result.route_activation_count == result.canonical_mutation_count == 0
    assert not result.reviewer_release_allowed
