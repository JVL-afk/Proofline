"""Durable local M2 analysis runner."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from opintel_m0.ports import Clock, IdentifierFactory

from opintel_opportunity.domain import AnalysisStatus, OpportunityBundle
from opintel_opportunity.economics import calculate_economics
from opintel_opportunity.ports import EvidenceCatalog, MockReasoner, OpportunityRepository
from opintel_opportunity.rules import detect, score_snapshot


class OpportunityWorkflowRunner:
    def __init__(
        self,
        repository: OpportunityRepository,
        evidence: EvidenceCatalog,
        reasoner: MockReasoner,
        clock: Clock,
        identifiers: IdentifierFactory,
        lease: timedelta = timedelta(seconds=30),
    ) -> None:
        self._repository = repository
        self._evidence = evidence
        self._reasoner = reasoner
        self._clock = clock
        self._identifiers = identifiers
        self._lease = lease

    def run_once(self) -> bool:
        run = self._repository.claim_run(self._clock.now(), self._lease)
        if run is None:
            return False
        try:
            evidence = self._evidence.list_evidence(
                run.workspace_id, run.business_id, run.research_run_id
            )
            allowed = self._reasoner.validate(tuple(item.id for item in evidence))
            if set(allowed) != {item.id for item in evidence}:
                raise ValueError("mock reasoner returned IDs outside the supplied evidence set")
            observations, inference, hypothesis, gaps, assumptions = detect(
                run.id,
                run.workspace_id,
                run.business_id,
                evidence,
                self._identifiers,
                self._clock.now(),
            )
            if hypothesis is None:
                completed = replace(
                    run,
                    status=AnalysisStatus.INSUFFICIENT_DATA,
                    updated_at=self._clock.now(),
                    lease_expires_at=None,
                )
                self._repository.save_bundle(
                    OpportunityBundle(completed, observations, inference, None, (), (), None, None)
                )
                return True
            economic = calculate_economics(
                self._identifiers.new(), hypothesis.logical_id, assumptions, self._clock.now()
            )
            score = score_snapshot(
                self._identifiers.new(),
                hypothesis,
                economic.status,
                any(item.predicate == "inbound_path.structured_fields" for item in observations),
                self._clock.now(),
            )
            hypothesis = replace(
                hypothesis,
                economic_run_id=economic.id,
                score_snapshot_id=score.id,
            )
            completed = replace(
                run,
                status=AnalysisStatus.SUCCEEDED,
                updated_at=self._clock.now(),
                lease_expires_at=None,
                hypothesis_id=hypothesis.logical_id,
                current_hypothesis_revision_id=hypothesis.id,
            )
            self._repository.save_bundle(
                OpportunityBundle(
                    completed,
                    observations,
                    inference,
                    hypothesis,
                    gaps,
                    assumptions,
                    economic,
                    score,
                )
            )
            return True
        except Exception:
            self._repository.fail_run(run.id, "analysis_failed", self._clock.now())
            return True
