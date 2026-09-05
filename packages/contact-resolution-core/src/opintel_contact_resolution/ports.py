"""M6.10 provider adapter interfaces (section 21).

These are interfaces and a fail-closed null implementation only. No adapter
in this codebase performs a live third-party network call - see
``NullSourceProvider`` and ``adapters.py`` for the only implementations that
exist right now. A real provider (RocketReach, ZoomInfo, a professional
directory, an email-verification service, ...) is a future, separately
authorized addition behind these same Protocols; adding one must never
require changing eligibility/authority semantics elsewhere in this package.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from opintel_contact_resolution.domain import (
    AuthorityDomain,
    Channel,
    SourceCategory,
)


class ProviderQueryResult:
    """What a provider adapter returns for one query - deliberately thin;
    callers must run this through minimization/verification, never trust it
    directly as an eligible endpoint."""

    __slots__ = (
        "observed_at",
        "provider_name",
        "raw_fields",
        "source_category",
        "source_url",
    )

    def __init__(
        self,
        *,
        raw_fields: dict[str, str],
        source_url: str | None,
        observed_at: datetime,
        provider_name: str,
        source_category: SourceCategory,
    ) -> None:
        self.raw_fields = raw_fields
        self.source_url = source_url
        self.observed_at = observed_at
        self.provider_name = provider_name
        self.source_category = source_category


class SourceProviderPort(Protocol):
    """One adapter per external source. ``required_authority`` names the
    :class:`domain.AuthorityDomain` the caller must confirm is not
    NOT_AUTHORIZED before ``query`` may be invoked at all - enforced by
    ``application.py``, not by the adapter itself (defense in depth: even a
    buggy adapter cannot self-authorize)."""

    provider_name: str
    source_category: SourceCategory
    required_authority: AuthorityDomain
    supported_channels: frozenset[Channel]

    def query(
        self, *, company_name: str, person_name: str, role_hint: str
    ) -> tuple[ProviderQueryResult, ...]: ...


class NullSourceProvider:
    """Fail-closed default: never queried in this task (section 26 hard
    boundary). Exists so the pipeline has something concrete to wire against
    without importing a real provider SDK."""

    def __init__(
        self,
        provider_name: str,
        source_category: SourceCategory,
        required_authority: AuthorityDomain,
        supported_channels: frozenset[Channel],
    ) -> None:
        self.provider_name = provider_name
        self.source_category = source_category
        self.required_authority = required_authority
        self.supported_channels = supported_channels

    def query(
        self, *, company_name: str, person_name: str, role_hint: str
    ) -> tuple[ProviderQueryResult, ...]:
        del company_name, person_name, role_hint
        return ()
