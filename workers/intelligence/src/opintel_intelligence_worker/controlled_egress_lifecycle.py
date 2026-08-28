"""Bounded M1-only controlled-egress lease and readiness lifecycle."""

from __future__ import annotations

from typing import Protocol

from opintel_research.domain import ResearchRun
from opintel_research_local import ControlledEgressTransport
from opintel_research_worker.egress_lease import (
    EGRESS_LEASE_LOCK_SENTINEL,
    CanonicalNotAuthorizedEgressLease,
    ControlledEgressLease,
    EgressLeaseStore,
    build_egress_lease,
    parse_stored_egress_lease,
)
from opintel_shadow import LiveResearchPermissionRelease


class CurrentAuthority(Protocol):
    def current_release(self) -> LiveResearchPermissionRelease: ...


class StopSignal(Protocol):
    def is_active(self) -> bool: ...


class BoundedControlledEgressLifecycle:
    """Issue one exact lease, prove readiness, and remove it at the M1 boundary."""

    def __init__(
        self,
        *,
        store: EgressLeaseStore,
        authority: CurrentAuthority,
        stop_signal: StopSignal,
        transport: ControlledEgressTransport,
        readiness_timeout_seconds: float = 45.0,
    ) -> None:
        if readiness_timeout_seconds <= 0 or readiness_timeout_seconds > 60:
            raise ValueError("controlled-egress readiness timeout must be in (0, 60]")
        self._store = store
        self._authority = authority
        self._stop = stop_signal
        self._transport = transport
        self._readiness_timeout = readiness_timeout_seconds

    def activate_and_await_ready(
        self, release: LiveResearchPermissionRelease, run: ResearchRun
    ) -> tuple[ControlledEgressLease, bool]:
        self._require_authority(release)
        expected = build_egress_lease(release, run)
        stored = parse_stored_egress_lease(self._store.read())
        created = False
        if isinstance(stored, CanonicalNotAuthorizedEgressLease):
            self._store.write(expected.model_dump_json())
            created = True
        elif stored != expected:
            raise ValueError("a different controlled-egress lease already exists")
        if parse_stored_egress_lease(self._store.read()) != expected:
            raise ValueError("controlled-egress lease did not persist exactly")
        try:
            self._require_authority(release)
            self._transport.await_ready(timeout_seconds=self._readiness_timeout)
            self._require_authority(release)
        except Exception:
            self.deactivate(expected)
            raise
        return expected, created

    def deactivate(self, lease: ControlledEgressLease) -> bool:
        stored = parse_stored_egress_lease(self._store.read())
        if isinstance(stored, CanonicalNotAuthorizedEgressLease):
            return False
        if stored != lease:
            raise ValueError("controlled-egress lease changed before cleanup")
        self._store.write(EGRESS_LEASE_LOCK_SENTINEL)
        locked = parse_stored_egress_lease(self._store.read())
        if not isinstance(locked, CanonicalNotAuthorizedEgressLease):
            raise ValueError("controlled-egress authority did not return to NOT_AUTHORIZED")
        return True

    def _require_authority(self, release: LiveResearchPermissionRelease) -> None:
        if self._stop.is_active():
            raise ValueError("kill switch blocks controlled-egress activation")
        current = self._authority.current_release()
        if current.id != release.id or current.configuration_hash != release.configuration_hash:
            raise ValueError("release changed before controlled-egress boundary")


__all__ = ["BoundedControlledEgressLifecycle"]
