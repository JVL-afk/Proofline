"""Hierarchical, fail-closed Tournament II fixture budgeting."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from opintel_qualification.tournament2_domain import TournamentTask, UsageLedgerEntry

TKey = TypeVar("TKey", str, TournamentTask)


@dataclass(frozen=True, slots=True)
class FixturePricing:
    version: str
    input_micros_per_million_tokens: int
    output_micros_per_million_tokens: int


@dataclass(frozen=True, slots=True)
class TournamentBudgetCaps:
    total_micros: int
    emergency_reserve_micros: int
    provider_caps: dict[str, int]
    deployment_caps: dict[str, int]
    task_caps: dict[TournamentTask, int]
    stage_caps: dict[str, int]


@dataclass(frozen=True, slots=True)
class Reservation:
    id: str
    provider_key: str
    deployment_key: str
    task: TournamentTask
    stage: str
    amount_micros: int


def conservative_preflight_cost(
    pricing: FixturePricing | None, max_input_tokens: int, max_output_tokens: int
) -> int:
    if pricing is None:
        raise ValueError("unknown pricing fails closed")
    if max_input_tokens < 0 or max_output_tokens < 0:
        raise ValueError("token bounds must be non-negative")
    numerator = (
        max_input_tokens * pricing.input_micros_per_million_tokens
        + max_output_tokens * pricing.output_micros_per_million_tokens
    )
    return (numerator + 999_999) // 1_000_000


class TournamentBudgetLedger:
    def __init__(self, caps: TournamentBudgetCaps) -> None:
        if caps.emergency_reserve_micros >= caps.total_micros:
            raise ValueError("emergency reserve must be smaller than total cap")
        self._caps = caps
        self._reservations: dict[str, Reservation] = {}
        self._actual_total = 0
        self._actual_by_provider: dict[str, int] = {}
        self._actual_by_deployment: dict[str, int] = {}
        self._actual_by_task: dict[TournamentTask, int] = {}
        self._actual_by_stage: dict[str, int] = {}
        self._entries: list[UsageLedgerEntry] = []

    @property
    def entries(self) -> tuple[UsageLedgerEntry, ...]:
        return tuple(self._entries)

    @property
    def actual_total_micros(self) -> int:
        return self._actual_total

    def reserve(self, reservation: Reservation) -> None:
        if reservation.id in self._reservations:
            raise ValueError("reservation id already exists")
        pending = (*tuple(self._reservations.values()), reservation)
        usable_total = self._caps.total_micros - self._caps.emergency_reserve_micros
        if self._actual_total + sum(item.amount_micros for item in pending) > usable_total:
            raise ValueError("tournament budget exhausted")
        self._check_dimension(
            reservation.provider_key,
            self._actual_by_provider,
            self._caps.provider_caps,
            pending,
            lambda item: item.provider_key,
            "provider",
        )
        self._check_dimension(
            reservation.deployment_key,
            self._actual_by_deployment,
            self._caps.deployment_caps,
            pending,
            lambda item: item.deployment_key,
            "deployment",
        )
        self._check_dimension(
            reservation.task,
            self._actual_by_task,
            self._caps.task_caps,
            pending,
            lambda item: item.task,
            "task",
        )
        self._check_dimension(
            reservation.stage,
            self._actual_by_stage,
            self._caps.stage_caps,
            pending,
            lambda item: item.stage,
            "stage",
        )
        self._reservations[reservation.id] = reservation

    def reconcile(self, reservation_id: str, entry: UsageLedgerEntry) -> None:
        reservation = self._reservations.pop(reservation_id, None)
        if reservation is None:
            raise ValueError("reservation not found")
        if entry.actual_cost_micros > reservation.amount_micros:
            raise ValueError("actual cost exceeds conservative reservation")
        if (
            entry.task != reservation.task
            or entry.stage != reservation.stage
            or entry.reserved_cost_micros != reservation.amount_micros
        ):
            raise ValueError("usage entry does not match reservation")
        self._actual_total += entry.actual_cost_micros
        self._actual_by_provider[reservation.provider_key] = (
            self._actual_by_provider.get(reservation.provider_key, 0) + entry.actual_cost_micros
        )
        self._actual_by_deployment[reservation.deployment_key] = (
            self._actual_by_deployment.get(reservation.deployment_key, 0) + entry.actual_cost_micros
        )
        self._actual_by_task[reservation.task] = (
            self._actual_by_task.get(reservation.task, 0) + entry.actual_cost_micros
        )
        self._actual_by_stage[reservation.stage] = (
            self._actual_by_stage.get(reservation.stage, 0) + entry.actual_cost_micros
        )
        self._entries.append(entry)

    @staticmethod
    def _check_dimension(
        key: TKey,
        actual: dict[TKey, int],
        caps: dict[TKey, int],
        pending: tuple[Reservation, ...],
        selector: Callable[[Reservation], TKey],
        label: str,
    ) -> None:
        cap = caps.get(key)
        if cap is None:
            raise ValueError(f"{label} budget is not configured")
        pending_value = sum(item.amount_micros for item in pending if selector(item) == key)
        if actual.get(key, 0) + pending_value > cap:
            raise ValueError(f"{label} budget exhausted")
