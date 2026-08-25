"""SSM-backed exact-scope Phase 1 research authorization."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import boto3
from opintel_research.domain import Business, FetchError, ResearchRun
from opintel_shadow import LiveResearchPermissionRelease, PermissionActivity, PermissionState


class AwsSsmResearchAuthorization:
    """Fail closed unless one current immutable release binds the exact business and host."""

    def __init__(self, parameter_name: str, region: str, runtime_revision: str) -> None:
        if not parameter_name or not runtime_revision:
            raise ValueError("release parameter and runtime revision are required")
        self._parameter_name = parameter_name
        self._client = boto3.client("ssm", region_name=region)
        self._runtime_revision = runtime_revision

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
        if (
            release.business_identity != business.name
            or release.exact_hostname != business.permitted_host
            or release.allowed_source_scope != (run.permitted_host,)
            or run.business_id != business.id
        ):
            raise FetchError("research_scope_mismatch", "research run is outside exact authority")

    def current_revision(self) -> str:
        return self.current_release().configuration_hash

    def current_gateway_policy(self) -> tuple[frozenset[str], str]:
        release = self.current_release()
        return frozenset(release.allowed_source_scope), release.configuration_hash


class SyntheticResearchAuthorization:
    """Explicit non-network authorization used only by synthetic/local validation."""

    def authorize(self, run: ResearchRun, business: Business) -> None:
        if run.business_id != business.id or run.permitted_host != business.permitted_host:
            raise FetchError("synthetic_scope_mismatch", "synthetic run scope mismatch")
