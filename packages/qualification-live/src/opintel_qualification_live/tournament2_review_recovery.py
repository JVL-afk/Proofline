"""Anthropic-only recovery of sealed Tournament II human-review renderings."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

from opintel_qualification.tournament2_corpus import CASES, project_case
from opintel_qualification.tournament2_domain import SemanticGraph, TournamentTask
from opintel_qualification.tournament2_freeze import FROZEN_MANIFEST, FrozenTaskBinding
from opintel_qualification.tournament2_machine_closure import (
    ORIGINAL_ARTIFACT_SHA256,
    ORIGINAL_MANIFEST_HASH,
    ORIGINAL_RUN_ID,
)
from opintel_qualification.tournament2_prefreeze import BINDINGS, price_for

from opintel_qualification_live.contracts import JsonTransport
from opintel_qualification_live.tournament2_certification import (
    TRANSIENT_HTTP_STATUSES,
    _cost_micros,
    _headers,
    _parse,
)
from opintel_qualification_live.tournament2_execution import (
    FINAL_MANIFEST_HASH,
    PlannedCall,
    _artifact,
    _call_definition,
    _hash,
    _payload,
    _policy,
    _reservation,
)

RECOVERY_VERSION = "m6.6b5r.human-review-recovery@1"
RENDERING_VERSION = "m6.6b5r.identical-plain-rendering@1"
RETENTION_POLICY_VERSION = "human_review_rendered_output.synthetic@1"
PRICING_VERSION = "anthropic-claude-sonnet-5-intro-2026-08-19"
RECOVERY_HARD_CAP_MICROS = 5_000_000
RECOVERY_PRIMARY_MAX_MICROS = 2_376_780
RECOVERY_TOTAL_MAX_MICROS = 4_753_560
MAX_ATTEMPTS = 2
REVIEW_DIMENSIONS = (
    "clarity",
    "naturalness",
    "concision",
    "usefulness",
    "relevance",
    "trustworthiness",
    "paired_preference",
    "material_defect_flag",
    "material_defect_note",
)
REVIEWER_SLOTS = (
    "PRIMARY_REVIEWER_SLOT_1",
    "PRIMARY_REVIEWER_SLOT_2",
    "PRIMARY_REVIEWER_SLOT_3",
    "CONDITIONAL_ADJUDICATOR_SLOT",
)
AUTHORIZED_TASKS = (
    TournamentTask.EVIDENCE_INTERPRETATION,
    TournamentTask.CONTRADICTION_ANALYSIS,
    TournamentTask.OPPORTUNITY_REASONING,
    TournamentTask.AUDIT_WORDING,
    TournamentTask.OUTREACH_WORDING,
)


class RecoveryState(StrEnum):
    COMPLETED = "completed"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class RecoveryAuthorization:
    version: str
    authorization_id: UUID
    original_run_id: str
    original_manifest_hash: str
    original_artifact_sha256: str
    deployment_key: str
    model_id: str
    endpoint: str
    task_bindings_hash: str
    case_set_hash: str
    retention_policy_version: str
    rendering_version: str
    pricing_version: str
    hard_cap_micros: int
    logical_calls: int
    maximum_transport_attempts: int
    actor: str
    authorized_at: datetime
    expires_at: datetime
    nonce_hash: str
    synthetic_only: bool
    new_model_samples: bool
    reviewer_release_allowed: bool
    route_activation_allowed: bool


@dataclass(frozen=True, slots=True)
class RecoveryCall:
    call: PlannedCall
    anonymous_case_id: str


@dataclass(frozen=True, slots=True)
class RecoveryReceipt:
    receipt_hash: str
    anonymous_case_id: str
    task: TournamentTask
    attempts: int
    safety_passed: bool
    hard_gate_codes: tuple[str, ...]
    failure_code: str | None
    output_hash: str | None
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    latency_ms: int
    actual_cost_micros: int
    pricing_version: str


@dataclass(frozen=True, slots=True)
class HumanReviewRenderedOutput:
    artifact_class: str
    anonymous_case_id: str
    task: TournamentTask
    deterministic_rendered_text: str
    candidate_rendered_text: str
    baseline_hash: str
    output_hash: str
    formatting_version: str
    semantic_safety_passed: bool
    receipt_hash: str
    sample_class: str = "NEW_MODEL_SAMPLES_FOR_HUMAN_USEFULNESS_EVALUATION"


@dataclass(frozen=True, slots=True)
class ReviewAssignment:
    anonymous_case_id: str
    task: TournamentTask
    reviewer_slot: str
    seed_hash: str
    candidate_side: str


@dataclass(frozen=True, slots=True)
class ReviewerFacingCase:
    anonymous_case_id: str
    task_id: str
    version_a: str
    version_b: str
    dimensions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SealedReviewerPackage:
    artifact_class: str
    package_id: UUID
    reviewer_slot: str
    task_id: str
    cases: tuple[ReviewerFacingCase, ...]
    sealed: bool
    released: bool
    package_hash: str


@dataclass(frozen=True, slots=True)
class RecoveryRunResult:
    version: str
    run_id: UUID
    authorization_hash: str
    original_run_id: str
    original_manifest_hash: str
    state: RecoveryState
    started_at: datetime
    completed_at: datetime
    calls_planned: int
    calls_attempted: int
    calls_completed: int
    transport_attempts: int
    actual_cost_micros: int
    hard_cap_micros: int
    receipts: tuple[RecoveryReceipt, ...]
    rendered_outputs: tuple[HumanReviewRenderedOutput, ...]
    assignments: tuple[ReviewAssignment, ...]
    packages: tuple[SealedReviewerPackage, ...]
    binding_failures: tuple[str, ...]
    stop_reason: str | None
    reviewer_release_allowed: bool = False
    route_activation_count: int = 0
    canonical_mutation_count: int = 0


def _bindings() -> tuple[FrozenTaskBinding, ...]:
    values = tuple(
        item
        for item in FROZEN_MANIFEST.manifest.bindings
        if item.deployment_key == "anthropic-claude-sonnet-5" and item.task in AUTHORIZED_TASKS
    )
    if len(values) != 5:
        raise AssertionError("recovery must bind exactly five frozen Sonnet tasks")
    return values


def _case_set_hash() -> str:
    return _hash(tuple((str(case.id), case.manifest_hash) for case in CASES))


def _bindings_hash() -> str:
    return _hash(tuple(asdict(item) for item in _bindings()))


def create_recovery_authorization(
    *, actor: str, now: datetime, expires_at: datetime, nonce: str
) -> RecoveryAuthorization:
    if FINAL_MANIFEST_HASH != ORIGINAL_MANIFEST_HASH:
        raise RuntimeError("original manifest lineage drifted")
    if not now < expires_at:
        raise ValueError("recovery authorization window must be future bounded")
    pricing = price_for("anthropic-claude-sonnet-5", now.date().isoformat())
    if pricing.version != PRICING_VERSION:
        raise ValueError("Anthropic pricing drift requires review")
    if RECOVERY_TOTAL_MAX_MICROS > RECOVERY_HARD_CAP_MICROS:
        raise ValueError("recovery conservative ceiling exceeds separate hard cap")
    return RecoveryAuthorization(
        RECOVERY_VERSION,
        uuid5(NAMESPACE_URL, f"{ORIGINAL_RUN_ID}:{nonce}"),
        ORIGINAL_RUN_ID,
        ORIGINAL_MANIFEST_HASH,
        ORIGINAL_ARTIFACT_SHA256,
        "anthropic-claude-sonnet-5",
        "claude-sonnet-5",
        "https://api.anthropic.com/v1/messages",
        _bindings_hash(),
        _case_set_hash(),
        RETENTION_POLICY_VERSION,
        RENDERING_VERSION,
        PRICING_VERSION,
        RECOVERY_HARD_CAP_MICROS,
        105,
        210,
        actor,
        now,
        expires_at,
        _hash(nonce),
        True,
        True,
        False,
        False,
    )


def recovery_plan() -> tuple[RecoveryCall, ...]:
    values: list[RecoveryCall] = []
    for binding in _bindings():
        if _hash(_policy(binding)) != binding.prompt_hash:
            raise RuntimeError("frozen recovery prompt policy hash drifted")
        family = next(
            item.schema_family
            for item in BINDINGS
            if item.deployment_key == binding.deployment_key and item.task is binding.task
        )
        for index, case in enumerate(CASES):
            values.append(
                RecoveryCall(
                    PlannedCall(
                        binding.deployment_key,
                        "anthropic",
                        "claude-sonnet-5",
                        binding,
                        family,
                        index,
                        1,
                        "human_review_recovery",
                        _reservation(binding),
                    ),
                    _hash((ORIGINAL_RUN_ID, str(case.id), binding.task.value))[:24],
                )
            )
    if len(values) != 105:
        raise AssertionError("recovery plan must contain 21 cases for each of five bindings")
    if sum(item.call.reserved_cost_micros for item in values) != RECOVERY_PRIMARY_MAX_MICROS:
        raise AssertionError("recovery primary budget projection drifted")
    return tuple(values)


def _lines(value: Sequence[str]) -> str:
    return ", ".join(value) if value else "None"


def _render_graph(graph: SemanticGraph) -> str:
    claims = graph.claims
    sections = []
    for claim in claims:
        sections.append(
            "\n".join(
                (
                    f"CLAIM {claim.claim_id}",
                    f"TYPE: {claim.semantic_label}",
                    f"TEXT: {claim.text}",
                    f"EVIDENCE: {_lines(claim.evidence_ids)}",
                    f"QUALIFIERS: {_lines(claim.qualifiers)}",
                    f"ECONOMIC BINDINGS: {_lines(claim.economic_binding_ids)}",
                )
            )
        )
    sections.append(f"PROTECTED UNKNOWNS: {_lines(graph.protected_unknown_ids)}")
    sections.append(f"CONTRADICTIONS: {_lines(graph.contradiction_ids)}")
    sections.append(f"CTA: {graph.cta_id or 'None'}")
    return "\n\n".join(sections)


def _render_output(call: PlannedCall, output: Mapping[str, object]) -> str:
    graph = _artifact(call, output, failure=None, tools=False).graph
    if graph is None:
        raise ValueError("validated output did not produce a semantic graph")
    return _render_graph(graph)


def _render_baseline(call: PlannedCall) -> str:
    return _render_graph(project_case(CASES[call.case_index], call.binding.task).baseline)


def _reviewer_packages(
    run_id: UUID, outputs: tuple[HumanReviewRenderedOutput, ...]
) -> tuple[tuple[ReviewAssignment, ...], tuple[SealedReviewerPackage, ...]]:
    assignments: list[ReviewAssignment] = []
    packages: list[SealedReviewerPackage] = []
    for slot in REVIEWER_SLOTS:
        for task in AUTHORIZED_TASKS:
            cases = []
            for output in (item for item in outputs if item.task is task):
                seed = _hash((str(run_id), slot, output.anonymous_case_id, task.value))
                candidate_side = "VERSION A" if int(seed[-1], 16) % 2 else "VERSION B"
                assignments.append(
                    ReviewAssignment(output.anonymous_case_id, task, slot, seed, candidate_side)
                )
                version_a, version_b = (
                    (output.candidate_rendered_text, output.deterministic_rendered_text)
                    if candidate_side == "VERSION A"
                    else (output.deterministic_rendered_text, output.candidate_rendered_text)
                )
                cases.append(
                    ReviewerFacingCase(
                        output.anonymous_case_id,
                        task.value,
                        version_a,
                        version_b,
                        REVIEW_DIMENSIONS,
                    )
                )
            package_id = uuid5(run_id, f"{slot}:{task.value}")
            if not cases:
                continue
            package_payload = {
                "artifact_class": "SEALED_BLINDED_REVIEW_PACKAGE",
                "package_id": str(package_id),
                "reviewer_slot": slot,
                "task_id": task.value,
                "cases": [asdict(item) for item in cases],
                "sealed": True,
                "released": False,
            }
            packages.append(
                SealedReviewerPackage(
                    "SEALED_BLINDED_REVIEW_PACKAGE",
                    package_id,
                    slot,
                    task.value,
                    tuple(cases),
                    True,
                    False,
                    _hash(package_payload),
                )
            )
    return tuple(assignments), tuple(packages)


class OneShotReviewRecoveryRunner:
    def __init__(
        self,
        authorization: RecoveryAuthorization,
        *,
        now: Callable[[], datetime],
        anthropic_credential: str,
        transport: JsonTransport,
        wait: Callable[[float], None] = time.sleep,
    ) -> None:
        if authorization.original_run_id != ORIGINAL_RUN_ID:
            raise ValueError("recovery must bind the original machine run")
        if authorization.deployment_key != "anthropic-claude-sonnet-5":
            raise ValueError("recovery is Anthropic Sonnet-only")
        if authorization.hard_cap_micros != RECOVERY_HARD_CAP_MICROS:
            raise ValueError("recovery hard cap must remain exactly USD 5")
        if authorization.reviewer_release_allowed or authorization.route_activation_allowed:
            raise ValueError("recovery cannot release packages or activate routes")
        self._authorization = authorization
        self._now = now
        self._credential = anthropic_credential
        self._transport = transport
        self._wait = wait
        self._consumed = False

    def run(self) -> RecoveryRunResult:
        if self._consumed:
            raise RuntimeError("one-shot human-review recovery authorization already consumed")
        self._consumed = True
        started = self._now()
        run_id = uuid5(NAMESPACE_URL, f"{RECOVERY_VERSION}:{self._authorization.nonce_hash}")
        receipts: list[RecoveryReceipt] = []
        rendered: list[HumanReviewRenderedOutput] = []
        failed_bindings: set[TournamentTask] = set()
        transport_attempts = 0
        actual_cost = 0
        stop_reason = None
        last_request_at: datetime | None = None

        for recovery_call in recovery_plan():
            call = recovery_call.call
            if call.binding.task in failed_bindings:
                continue
            if self._now() > self._authorization.expires_at:
                stop_reason = "authorization_window_closed"
                break
            if actual_cost + call.reserved_cost_micros > RECOVERY_HARD_CAP_MICROS:
                stop_reason = "recovery_budget_reservation_denied"
                break
            if last_request_at is not None:
                delay = 15 - (self._now() - last_request_at).total_seconds()
                if delay > 0:
                    self._wait(delay)

            definition = _call_definition(call)
            parsed = None
            failure = None
            attempts = 0
            latency = 0
            for attempt in range(1, MAX_ATTEMPTS + 1):
                attempts = attempt
                last_request_at = self._now()
                try:
                    response = self._transport.post(
                        definition.endpoint,
                        _headers(definition, self._credential),
                        _payload(call),
                        90,
                    )
                    transport_attempts += 1
                    latency += response.latency_ms
                    if response.status in TRANSIENT_HTTP_STATUSES:
                        failure = f"transient_http_{response.status}"
                        if attempt == 1:
                            retry_after = response.headers.get("retry-after")
                            self._wait(
                                float(retry_after) if retry_after and retry_after.isdigit() else 60
                            )
                            continue
                    elif not 200 <= response.status < 300:
                        stop_reason = f"provider_configuration_rejected_http_{response.status}"
                        failure = stop_reason
                    else:
                        parsed = _parse(definition, response)
                        if parsed.returned_model != "claude-sonnet-5":
                            stop_reason = "returned_model_identity_drift"
                            failure = stop_reason
                    break
                except TimeoutError:
                    transport_attempts += 1
                    failure = "timeout"
                    if attempt == 1:
                        continue
                except RuntimeError:
                    transport_attempts += 1
                    failure = "transport_failure"
                    if attempt == 1:
                        continue
                except (ValueError, json.JSONDecodeError):
                    failure = "structured_output_invalid"
                    break

            artifact = _artifact(
                call,
                parsed.output if parsed is not None else None,
                failure=failure,
                tools=parsed.tools_observed if parsed is not None else False,
            )
            from opintel_qualification.tournament2_evaluator import evaluate_artifact

            evaluation = evaluate_artifact(
                project_case(CASES[call.case_index], call.binding.task), artifact
            )
            pricing = price_for("anthropic-claude-sonnet-5", started.date().isoformat())
            call_cost = (
                _cost_micros(
                    pricing,
                    provider="anthropic",
                    input_tokens=parsed.input_tokens,
                    output_tokens=parsed.output_tokens,
                    reasoning_tokens=parsed.reasoning_tokens,
                    cached_tokens=parsed.cached_tokens,
                )
                if parsed is not None
                else 0
            )
            if call_cost > call.reserved_cost_micros or actual_cost + call_cost > 5_000_000:
                stop_reason = "actual_cost_exceeded_recovery_reservation"
                break
            actual_cost += call_cost
            output_hash = _hash(parsed.output) if parsed is not None else None
            receipt_payload = {
                "case": recovery_call.anonymous_case_id,
                "task": call.binding.task.value,
                "attempts": attempts,
                "output_hash": output_hash,
                "findings": [item.gate.value for item in evaluation.findings],
                "failure": failure,
            }
            receipt_hash = _hash(receipt_payload)
            receipts.append(
                RecoveryReceipt(
                    receipt_hash,
                    recovery_call.anonymous_case_id,
                    call.binding.task,
                    attempts,
                    evaluation.safety_passed,
                    tuple(item.gate.value for item in evaluation.findings),
                    failure,
                    output_hash,
                    parsed.input_tokens if parsed is not None else 0,
                    parsed.output_tokens if parsed is not None else 0,
                    parsed.reasoning_tokens if parsed is not None else 0,
                    latency,
                    call_cost,
                    pricing.version,
                )
            )
            if (
                evaluation.safety_passed
                and parsed is not None
                and isinstance(parsed.output, Mapping)
            ):
                baseline_text = _render_baseline(call)
                candidate_text = _render_output(call, parsed.output)
                rendered.append(
                    HumanReviewRenderedOutput(
                        "HUMAN_REVIEW_RENDERED_OUTPUT",
                        recovery_call.anonymous_case_id,
                        call.binding.task,
                        baseline_text,
                        candidate_text,
                        _hash(baseline_text),
                        output_hash or "",
                        RENDERING_VERSION,
                        True,
                        receipt_hash,
                    )
                )
            else:
                failed_bindings.add(call.binding.task)
            if stop_reason is not None:
                break

        assignments, packages = _reviewer_packages(run_id, tuple(rendered))
        completed = self._now()
        return RecoveryRunResult(
            RECOVERY_VERSION,
            run_id,
            _hash(asdict(self._authorization)),
            ORIGINAL_RUN_ID,
            ORIGINAL_MANIFEST_HASH,
            RecoveryState.COMPLETED if stop_reason is None else RecoveryState.STOPPED,
            started,
            completed,
            105,
            len(receipts),
            sum(1 for item in receipts if item.output_hash is not None),
            transport_attempts,
            actual_cost,
            RECOVERY_HARD_CAP_MICROS,
            tuple(receipts),
            tuple(rendered),
            assignments,
            packages,
            tuple(task.value for task in AUTHORIZED_TASKS if task in failed_bindings),
            stop_reason,
        )


def safe_result_dict(result: RecoveryRunResult) -> dict[str, object]:
    return {
        "version": result.version,
        "run_id": str(result.run_id),
        "authorization_hash": result.authorization_hash,
        "original_run_id": result.original_run_id,
        "original_manifest_hash": result.original_manifest_hash,
        "state": result.state.value,
        "started_at": str(result.started_at),
        "completed_at": str(result.completed_at),
        "calls_planned": result.calls_planned,
        "calls_attempted": result.calls_attempted,
        "calls_completed": result.calls_completed,
        "transport_attempts": result.transport_attempts,
        "actual_cost_micros": result.actual_cost_micros,
        "hard_cap_micros": result.hard_cap_micros,
        "receipts": [asdict(item) for item in result.receipts],
        "rendered_output_count": len(result.rendered_outputs),
        "rendered_output_hashes": tuple(_hash(asdict(item)) for item in result.rendered_outputs),
        "assignment_manifest_hash": _hash(tuple(asdict(item) for item in result.assignments)),
        "sealed_package_count": len(result.packages),
        "sealed_package_hashes": tuple(item.package_hash for item in result.packages),
        "binding_failures": result.binding_failures,
        "reviewer_release_allowed": result.reviewer_release_allowed,
        "route_activation_count": result.route_activation_count,
        "canonical_mutation_count": result.canonical_mutation_count,
        "stop_reason": result.stop_reason,
    }
