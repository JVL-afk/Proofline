"""Authorized M2 commands and queries."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from opintel_m0.domain import Principal
from opintel_m0.ports import Clock, IdentifierFactory

from opintel_opportunity.domain import (
    AnalysisStatus,
    AssumptionRevision,
    HypothesisStatus,
    OpportunityAnalysisRun,
    OpportunityAuthorizationError,
    OpportunityBundle,
    OpportunityNotFoundError,
    OpportunityValidationError,
    ReviewDecision,
    ReviewDecisionType,
    RevisionStatus,
    ValueState,
)
from opintel_opportunity.economics import calculate_economics, checksum
from opintel_opportunity.ports import OpportunityRepository
from opintel_opportunity.rules import DEFINITION_VERSION, score_snapshot


class OpportunityApplicationService:
    def __init__(
        self,
        repository: OpportunityRepository,
        clock: Clock,
        identifiers: IdentifierFactory,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._identifiers = identifiers

    def start_run(
        self,
        principal: Principal,
        business_id: UUID,
        research_run_id: UUID,
        idempotency_key: str,
    ) -> tuple[OpportunityAnalysisRun, bool]:
        if not principal.can_operate():
            raise OpportunityAuthorizationError()
        now = self._clock.now()
        run = OpportunityAnalysisRun(
            id=self._identifiers.new(),
            workspace_id=principal.workspace_id,
            business_id=business_id,
            research_run_id=research_run_id,
            operation_id=self._identifiers.new(),
            trace_id=self._identifiers.new(),
            definition_version=DEFINITION_VERSION,
            status=AnalysisStatus.PENDING,
            created_by=principal.subject,
            created_at=now,
            updated_at=now,
        )
        result, created = self._repository.create_or_get_run(run, idempotency_key)
        if created:
            self._repository.invalidate_reviews_for_new_evidence(
                principal.workspace_id,
                business_id,
                DEFINITION_VERSION,
                result.id,
                now,
            )
        return result, created

    def get_run(self, principal: Principal, run_id: UUID) -> OpportunityAnalysisRun:
        value = self._repository.get_run(principal.workspace_id, run_id)
        if value is None:
            raise OpportunityNotFoundError()
        return value

    def get_bundle_by_run(self, principal: Principal, run_id: UUID) -> OpportunityBundle:
        value = self._repository.get_bundle_by_run(principal.workspace_id, run_id)
        if value is None:
            raise OpportunityNotFoundError()
        return value

    def get_bundle_by_hypothesis(
        self, principal: Principal, hypothesis_id: UUID
    ) -> OpportunityBundle:
        value = self._repository.get_bundle_by_hypothesis(principal.workspace_id, hypothesis_id)
        if value is None:
            raise OpportunityNotFoundError()
        return value

    def recalculate(
        self,
        principal: Principal,
        hypothesis_id: UUID,
        expected_hypothesis_revision_id: UUID,
        inputs: tuple[dict[str, str | None], ...],
    ) -> OpportunityBundle:
        if not principal.can_operate():
            raise OpportunityAuthorizationError()
        previous = self.get_bundle_by_hypothesis(principal, hypothesis_id)
        old = previous.hypothesis
        if old is None or previous.inference is None:
            raise OpportunityValidationError("hypothesis is unavailable")
        if old.id != expected_hypothesis_revision_id:
            raise OpportunityValidationError("hypothesis revision precondition failed")
        by_key = {item.key: item for item in previous.assumptions}
        if {str(item["key"]) for item in inputs} != set(by_key):
            raise OpportunityValidationError("all four formula inputs must be supplied")
        now = self._clock.now()
        assumptions: list[AssumptionRevision] = []
        for value in inputs:
            key = str(value["key"])
            prior = by_key[key]
            try:
                state = ValueState(str(value["value_state"]))
            except ValueError as error:
                raise OpportunityValidationError("unsupported assumption value state") from error
            if state not in {ValueState.KNOWN, ValueState.PROPOSED, ValueState.UNKNOWN}:
                raise OpportunityValidationError("unsupported formula input state")
            source_kind = str(value.get("source_kind") or state.value.upper())
            provenance = value.get("provenance")
            decimal_value = value.get("decimal_value")
            if state == ValueState.KNOWN and (
                source_kind != "VERIFIED_BUSINESS_INPUT" or not provenance or decimal_value is None
            ):
                raise OpportunityValidationError(
                    "known inputs require verified business-specific provenance"
                )
            if state == ValueState.PROPOSED and (
                source_kind != "USER_PROPOSED" or not provenance or decimal_value is None
            ):
                raise OpportunityValidationError(
                    "proposed inputs require explicit user-proposed provenance"
                )
            if state == ValueState.UNKNOWN and (
                source_kind != "UNKNOWN" or decimal_value is not None
            ):
                raise OpportunityValidationError("unknown inputs cannot carry a value")
            assumptions.append(
                replace(
                    prior,
                    id=self._identifiers.new(),
                    revision=prior.revision + 1,
                    value_state=state,
                    decimal_value=decimal_value,
                    source_kind=source_kind,
                    provenance=provenance,
                    created_by=principal.subject,
                    created_at=now,
                )
            )
        assumption_tuple = tuple(assumptions)
        economic = calculate_economics(
            self._identifiers.new(), old.logical_id, assumption_tuple, now
        )
        hypothesis = replace(
            old,
            id=self._identifiers.new(),
            revision=old.revision + 1,
            status=(
                HypothesisStatus.NEEDS_INFORMATION
                if old.contradictory_evidence_ids
                else HypothesisStatus.READY_FOR_REVIEW
            ),
            assumption_revision_ids=tuple(item.id for item in assumption_tuple),
            economic_run_id=economic.id,
            score_snapshot_id=self._identifiers.new(),
            manifest_checksum=checksum(
                {
                    "prior": old.manifest_checksum,
                    "revision": old.revision + 1,
                    "assumptions": [str(item.id) for item in assumption_tuple],
                    "economic": economic.manifest_checksum,
                }
            ),
            created_by=principal.subject,
            created_at=now,
        )
        score = score_snapshot(
            hypothesis.score_snapshot_id,
            hypothesis,
            economic.status,
            any(
                item.predicate == "inbound_path.structured_fields" for item in previous.observations
            ),
            now,
        )
        return self._repository.save_recalculation(
            previous, hypothesis, assumption_tuple, economic, score
        )

    def review(
        self,
        principal: Principal,
        hypothesis_id: UUID,
        expected_hypothesis_revision_id: UUID,
        decision_type: ReviewDecisionType,
        reason: str,
    ) -> OpportunityBundle:
        if not principal.can_review():
            raise OpportunityAuthorizationError()
        previous = self.get_bundle_by_hypothesis(principal, hypothesis_id)
        hypothesis = previous.hypothesis
        if hypothesis is None or hypothesis.id != expected_hypothesis_revision_id:
            raise OpportunityValidationError("hypothesis revision precondition failed")
        if (
            previous.inference is None
            or previous.economic_run is None
            or previous.score_snapshot is None
        ):
            raise OpportunityValidationError("complete hypothesis lineage is required")
        if decision_type == ReviewDecisionType.ACCEPT:
            if hypothesis.status != HypothesisStatus.READY_FOR_REVIEW:
                raise OpportunityValidationError("hypothesis is not ready for acceptance")
            if hypothesis.contradictory_evidence_ids:
                raise OpportunityValidationError("hard contradiction gate cannot be overridden")
        decision = ReviewDecision(
            id=self._identifiers.new(),
            hypothesis_id=hypothesis.logical_id,
            hypothesis_revision_id=hypothesis.id,
            inference_revision_ids=hypothesis.inference_revision_ids,
            assumption_revision_ids=hypothesis.assumption_revision_ids,
            economic_run_id=hypothesis.economic_run_id,
            score_snapshot_id=hypothesis.score_snapshot_id,
            manifest_checksum=hypothesis.manifest_checksum,
            decision=decision_type,
            actor=principal.subject,
            actor_roles=tuple(sorted(role.value for role in principal.roles)),
            reason=reason.strip(),
            self_review=principal.subject == previous.run.created_by,
            created_at=self._clock.now(),
        )
        return self._repository.save_review(previous, decision)

    def reject_hypothesis_inference(
        self,
        principal: Principal,
        hypothesis_id: UUID,
        inference_id: UUID,
        expected_hypothesis_revision_id: UUID,
        reason: str,
    ) -> OpportunityBundle:
        if not principal.can_review():
            raise OpportunityAuthorizationError()
        previous = self.get_bundle_by_hypothesis(principal, hypothesis_id)
        inference = previous.inference
        hypothesis = previous.hypothesis
        if inference is None or hypothesis is None or inference.logical_id != inference_id:
            raise OpportunityNotFoundError()
        if hypothesis.id != expected_hypothesis_revision_id:
            raise OpportunityValidationError("hypothesis revision precondition failed")
        now = self._clock.now()
        rejected = replace(
            inference,
            id=self._identifiers.new(),
            revision=inference.revision + 1,
            status=RevisionStatus.REJECTED,
            statement=f"Rejected by human reviewer: {reason.strip()}",
            created_at=now,
        )
        revised = replace(
            hypothesis,
            id=self._identifiers.new(),
            revision=hypothesis.revision + 1,
            status=HypothesisStatus.NEEDS_INFORMATION,
            inference_revision_ids=(rejected.id,),
            manifest_checksum=checksum(
                {
                    "prior": hypothesis.manifest_checksum,
                    "rejected_inference": str(rejected.id),
                    "reason": reason.strip(),
                }
            ),
            created_by=principal.subject,
            created_at=now,
        )
        return self._repository.save_inference_rejection(previous, rejected, revised)
