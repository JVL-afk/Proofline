"""SSM-backed exact-scope Phase 1 research authorization."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import boto3  # type: ignore[import-untyped]
from opintel_research.domain import Business, FetchError, ResearchRun
from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState

from opintel_research_worker.activation import (
    A09_MARKER_PREFIX,
    V2_CRAWL_PROTOCOL,
    SampledSlotActivator,
    release_execution_ceilings_sha256,
)
from opintel_research_worker.egress_lease import (
    ControlledEgressLease,
    SsmControlledEgressLeaseStore,
    build_egress_lease,
    parse_stored_egress_lease,
)
from opintel_research_worker.sample_registry import FrozenPhaseOneSampleRegistry


def _run_is_v2(run: ResearchRun) -> bool:
    return getattr(run, "crawl_protocol_version", None) == V2_CRAWL_PROTOCOL


class AwsSsmResearchAuthorization:
    """Fail closed unless one current immutable release binds the exact business and host."""

    def __init__(
        self,
        parameter_name: str,
        region: str,
        runtime_revision: str,
        slot_registry_path: str,
        egress_lease_parameter: str | None = None,
        egress_lease_store: SsmControlledEgressLeaseStore | None = None,
        require_egress_lease: bool = False,
    ) -> None:
        if not parameter_name or not runtime_revision or not slot_registry_path:
            raise ValueError("release parameter, runtime revision, and slot registry are required")
        self._parameter_name = parameter_name
        self._client = boto3.client("ssm", region_name=region)
        self._runtime_revision = runtime_revision
        self._slot_registry = FrozenPhaseOneSampleRegistry(slot_registry_path)
        self._egress_lease_store = egress_lease_store
        if self._egress_lease_store is None and egress_lease_parameter:
            self._egress_lease_store = SsmControlledEgressLeaseStore(egress_lease_parameter, region)
        self._require_egress_lease = require_egress_lease

    def current_release(self) -> LiveResearchPermissionRelease:
        try:
            raw = self._client.get_parameter(Name=self._parameter_name, WithDecryption=False)[
                "Parameter"
            ]["Value"]
            release = LiveResearchPermissionRelease.model_validate(json.loads(raw))
        except Exception as error:
            raise FetchError(
                "research_release_invalid", "research authorization is unavailable"
            ) from error
        now = datetime.now(UTC)
        if (
            release.activity is not PermissionActivity.REAL_PUBLIC_RESEARCH
            or release.state is not PermissionState.AUTHORIZED
            or not release.starts_at <= now < release.expires_at
            or release.research_runtime_revision != self._runtime_revision
            or release.terminal_rollback_state != "NOT_AUTHORIZED"
        ):
            raise FetchError("research_not_authorized", "research authorization is not effective")
        return release

    def authorize(self, run: ResearchRun, business: Business) -> None:
        release = self.current_release()
        identity = run.sampled_slot_identity
        activation = run.sampled_slot_activation
        try:
            if identity is None or activation is None:
                raise ValueError("sampled slot activation or identity is missing")
            self._slot_registry.verify_identity(identity, run.id)
            self._slot_registry.verify_release(release)
        except ValueError as error:
            raise FetchError(
                "research_sample_identity_mismatch", "research work item is outside exact authority"
            ) from error
        if (
            release.ordered_package_sha256 != identity.ordered_package_semantic_sha256
            or release.slot_number != identity.slot_number
            or release.business_identity != identity.business_identity
            or release.exact_hostname != identity.exact_hostname
            or activation.sampled_slot_identity != identity
            or activation.authorization_release_id != release.id
            or activation.authorization_configuration_hash != release.configuration_hash
            or activation.research_runtime_revision != self._runtime_revision
            or activation.execution_ceilings_sha256 != release_execution_ceilings_sha256(release)
            or f"{A09_MARKER_PREFIX}{activation.a09_decision_sha256}" not in release.approval_ids
            or activation.activation_sha256 != activation.computed_sha256()
            or release.business_identity != business.name
            or release.exact_hostname != business.permitted_host
            or release.allowed_source_scope != (run.permitted_host,)
            or run.business_id != business.id
            or run.permitted_host != identity.exact_hostname
            or run.policy != SampledSlotActivator._policy(release)
            or _run_is_v2(run) != (release.crawl_protocol_version == V2_CRAWL_PROTOCOL)
        ):
            raise FetchError("research_scope_mismatch", "research run is outside exact authority")
        if self._require_egress_lease:
            lease = self.current_egress_lease()
            if lease != build_egress_lease(release, run):
                raise FetchError(
                    "controlled_egress_lease_mismatch",
                    "research run has no exact controlled-egress capability",
                )

    def current_revision(self) -> str:
        return self.current_release().configuration_hash

    def current_gateway_policy(self) -> tuple[frozenset[str], str]:
        release = self.current_release()
        try:
            self._slot_registry.verify_release(release)
        except ValueError as error:
            raise FetchError(
                "research_sample_identity_mismatch", "research release is outside frozen sample"
            ) from error
        return frozenset(release.allowed_source_scope), release.configuration_hash

    def current_egress_lease(self) -> ControlledEgressLease:
        if self._egress_lease_store is None:
            raise FetchError(
                "controlled_egress_lease_unavailable",
                "controlled-egress authority is unavailable",
            )
        try:
            lease = parse_stored_egress_lease(self._egress_lease_store.read())
        except Exception as error:
            raise FetchError(
                "controlled_egress_lease_invalid",
                "controlled-egress authority is invalid",
            ) from error
        if not isinstance(lease, ControlledEgressLease):
            raise FetchError(
                "controlled_egress_not_authorized",
                "controlled-egress authority is not active",
            )
        release = self.current_release()
        now = datetime.now(UTC)
        if (
            lease.authorization_release_id != release.id
            or lease.authorization_configuration_hash != release.configuration_hash
            or lease.slot_number != release.slot_number
            or lease.business_identity != release.business_identity
            or lease.exact_hostname != release.exact_hostname
            or lease.ordered_package_semantic_sha256 != release.ordered_package_sha256
            or not lease.starts_at <= now < lease.expires_at
        ):
            raise FetchError(
                "controlled_egress_lease_mismatch",
                "controlled-egress lease is outside exact current authority",
            )
        return lease

    def current_gateway_capability(self) -> dict[str, object]:
        return self.current_egress_lease().capability_payload()


class SyntheticResearchAuthorization:
    """Explicit non-network authorization used only by synthetic/local validation."""

    def authorize(self, run: ResearchRun, business: Business) -> None:
        if run.business_id != business.id or run.permitted_host != business.permitted_host:
            raise FetchError("synthetic_scope_mismatch", "synthetic run scope mismatch")
