"""Deterministic fake provider machinery; no live transport exists in M6.6A."""

from __future__ import annotations

from dataclasses import dataclass, replace

from opintel_qualification.tournament2_domain import (
    ModelArtifact,
    ProviderOutcome,
    SemanticGraph,
    TaskProjection,
)


@dataclass(frozen=True, slots=True)
class FakeProviderReceipt:
    artifact: ModelArtifact
    input_tokens: int
    output_tokens: int
    latency_ms: int
    actual_cost_micros: int
    pricing_version: str


class DeterministicTournamentProvider:
    is_fixture_provider = True

    def __init__(
        self,
        behavior: ProviderOutcome,
        *,
        pricing_version: str = "fixture-pricing@1",
        contaminated_graph: SemanticGraph | None = None,
    ) -> None:
        self.behavior = behavior
        self.pricing_version = pricing_version
        self.contaminated_graph = contaminated_graph
        self.invocations = 0

    def invoke(self, projection: TaskProjection) -> FakeProviderReceipt:
        self.invocations += 1
        graph: SemanticGraph | None = projection.baseline
        schema_valid = True
        failure: str | None = None
        unsupported: tuple[str, ...] = ()
        injection_followed = False
        if self.behavior is ProviderOutcome.MALFORMED_SCHEMA:
            schema_valid = False
            graph = None
        elif self.behavior is ProviderOutcome.TIMEOUT:
            failure = "timeout"
            graph = None
        elif self.behavior is ProviderOutcome.TRANSIENT_FAILURE and self.invocations == 1:
            failure = "transient_failure"
            graph = None
        elif self.behavior is ProviderOutcome.REFUSAL:
            failure = "provider_refusal"
            graph = None
        elif self.behavior is ProviderOutcome.SAFETY_FILTERED:
            failure = "provider_safety_filtered"
            graph = None
        elif self.behavior is ProviderOutcome.UNSUPPORTED_FIELD:
            unsupported = ("unexpected_provider_field",)
        elif self.behavior is ProviderOutcome.HARD_GATE_VIOLATION:
            assert graph is not None
            graph = replace(graph, protected_unknown_ids=())
        elif self.behavior is ProviderOutcome.CROSS_CASE_CONTAMINATION:
            if self.contaminated_graph is None:
                raise ValueError("contamination behavior requires a hostile graph")
            graph = self.contaminated_graph
        elif self.behavior is ProviderOutcome.PROMPT_INJECTION_COMPLIANCE:
            injection_followed = True
        artifact = ModelArtifact(
            case_id=projection.case_id,
            task=projection.task,
            graph=graph,
            schema_valid=schema_valid,
            injection_followed=injection_followed,
            attempted_capabilities=(),
            provider_failure=failure,
            unsupported_fields=unsupported,
        )
        return FakeProviderReceipt(
            artifact=artifact,
            input_tokens=120,
            output_tokens=60,
            latency_ms=5,
            actual_cost_micros=2,
            pricing_version=self.pricing_version,
        )
