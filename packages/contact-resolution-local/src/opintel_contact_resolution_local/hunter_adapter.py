"""Hunter.io adapter for M6.10 professional-email resolution + verification.

Owner authorization "ACTIVATE HUNTER AND RESUME REAL M6.10 A-PLUS
RESOLUTION" (2026-09-06). Implemented behind the existing
``opintel_contact_resolution.SourceProviderPort`` - M6.10 is not redesigned.

Only two Hunter capabilities are wired: **Email Finder** and **Email
Verifier**. Bulk search, lead lists, campaigns, and outreach/sequences are
not implemented and cannot be reached through this adapter.

This adapter fails closed three ways before it will make any network call:

1. ``AuthorityDomain.CONTACT_ENRICHMENT_AUTHORITY`` (Finder) /
   ``EMAIL_VERIFICATION_AUTHORITY`` (Verifier) must not be NOT_AUTHORIZED;
2. a fully-``satisfied`` ``VendorComplianceChecklist`` for Hunter must be
   supplied (missing any field -> ``ResolutionAuthorityError``);
3. the API key must be present and non-empty in the local secret file.

The API key is read from ``apikeys.txt`` only, held in memory only, and is
never logged, printed, returned, hashed, or written to any artifact.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from opintel_contact_resolution.counsel_controls import VendorComplianceChecklist
from opintel_contact_resolution.domain import (
    AuthorityDomain,
    AuthorityLevel,
    Channel,
    ResolutionAuthorityError,
    SourceAuthorityMatrix,
    SourceCategory,
)

_HUNTER_API = "https://api.hunter.io/v2"
_DURABLE_HUNTER_FIELDS = frozenset(
    {"first_name", "last_name", "position", "email", "domain", "company", "score", "sources"}
)


def _load_hunter_key() -> str:
    """Colon-format (``KEY:value``) - the project's established
    ``apikeys.txt`` convention, matching every existing loader
    (``ANTHROPIC:`` / ``OPENAI:`` / ``GEMINI:``). The key is named
    ``HUNTER`` in the file. Never logged or returned to callers."""
    here = Path(__file__).resolve()
    for base in (here, *here.parents):
        candidate = base.parent / "apikeys.txt"
        if candidate.is_file():
            for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = line.strip()
                if s.upper().startswith("HUNTER:"):
                    value = s.split(":", 1)[1].strip()
                    if not value:
                        raise ResolutionAuthorityError("HUNTER key present but empty")
                    return value
        # also check the repo/worktree root explicitly
        root_candidate = base / "apikeys.txt"
        if root_candidate.is_file():
            for line in root_candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = line.strip()
                if s.upper().startswith("HUNTER:"):
                    value = s.split(":", 1)[1].strip()
                    if not value:
                        raise ResolutionAuthorityError("HUNTER key present but empty")
                    return value
    raise ResolutionAuthorityError("apikeys.txt not found / no HUNTER: line")


@dataclass(frozen=True)
class HunterFinderResult:
    email: str | None
    score: int | None
    corporate_domain: str | None
    provenance_kind: str  # "observed" | "generated_or_inferred" | "none"
    sources: tuple[str, ...]
    retrieved_at: datetime
    minimized_fields: dict[str, str]


@dataclass(frozen=True)
class HunterVerifierResult:
    email: str
    status: str  # hunter: valid | invalid | accept_all | webmail | disposable | unknown
    is_catch_all: bool
    mx_records: bool
    smtp_check: bool | None
    score: int | None
    verified_at: datetime


class HunterAdapter:
    """Behind ``SourceProviderPort``. ``supported_channels`` is EMAIL only."""

    provider_name = "Hunter (hunter.io)"
    source_category = SourceCategory.APPROVED_CONTACT_ENRICHMENT
    required_authority = AuthorityDomain.CONTACT_ENRICHMENT_AUTHORITY
    supported_channels = frozenset({Channel.EMAIL})

    def __init__(
        self,
        *,
        matrix: SourceAuthorityMatrix,
        vendor_checklist: VendorComplianceChecklist,
        timeout_seconds: float = 15.0,
    ) -> None:
        if matrix.level(AuthorityDomain.CONTACT_ENRICHMENT_AUTHORITY) is (
            AuthorityLevel.NOT_AUTHORIZED
        ):
            raise ResolutionAuthorityError("CONTACT_ENRICHMENT_AUTHORITY is NOT_AUTHORIZED")
        if not vendor_checklist.satisfied:
            raise ResolutionAuthorityError(
                "Hunter VendorComplianceChecklist not satisfied; missing: "
                + ", ".join(vendor_checklist.missing)
            )
        self._matrix = matrix
        self._timeout = timeout_seconds
        # key loaded lazily on first request only, never stored as an attr
        self._verify_matrix_for_verifier = matrix

    def _get(self, path: str, params: dict[str, str]) -> dict[str, object]:
        key = _load_hunter_key()
        query = urllib.parse.urlencode({**params, "api_key": key})
        url = f"{_HUNTER_API}/{path}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "opintel-m6.10/1.0"})
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        del key, query, url
        if not isinstance(payload, dict):
            raise ResolutionAuthorityError("Hunter returned a non-object payload")
        return payload

    def find_email(self, *, company_domain: str, full_name: str) -> HunterFinderResult:
        """Hunter Email Finder. ``full_name`` and ``company_domain`` are the
        only identifiers sent - Hunter does not originate or change the
        targeting decision (the caller already verified the person's role
        first-party)."""
        first, _, last = full_name.strip().partition(" ")
        raw = self._get(
            "email-finder",
            {"domain": company_domain.strip().lower(), "first_name": first, "last_name": last},
        )
        data = raw.get("data")
        data_dict = data if isinstance(data, dict) else {}
        minimized = {
            k: str(v)
            for k, v in data_dict.items()
            if k in _DURABLE_HUNTER_FIELDS and not isinstance(v, list | dict) and v is not None
        }
        sources_raw = data_dict.get("sources")
        sources = (
            tuple(str(s.get("uri", "")) for s in sources_raw if isinstance(s, dict))
            if isinstance(sources_raw, list)
            else ()
        )
        email = data_dict.get("email")
        email_str = str(email) if isinstance(email, str) and email else None
        score = data_dict.get("score")
        score_int = int(score) if isinstance(score, int | float) else None
        # Hunter marks whether the address was seen on a page ("sources"
        # present) vs generated from an org pattern.
        provenance_kind = "none"
        if email_str:
            provenance_kind = "observed" if sources else "generated_or_inferred"
        corp = None
        if email_str and "@" in email_str:
            corp = email_str.rsplit("@", 1)[1].lower()
        return HunterFinderResult(
            email=email_str,
            score=score_int,
            corporate_domain=corp,
            provenance_kind=provenance_kind,
            sources=sources,
            retrieved_at=datetime.now().astimezone(),
            minimized_fields=minimized,
        )

    def verify_email(self, email: str) -> HunterVerifierResult:
        """Hunter Email Verifier - passive, non-deceptive (Hunter performs
        the checks; this adapter never opens its own SMTP session)."""
        if (
            self._verify_matrix_for_verifier.level(AuthorityDomain.EMAIL_VERIFICATION_AUTHORITY)
            is AuthorityLevel.NOT_AUTHORIZED
        ):
            raise ResolutionAuthorityError("EMAIL_VERIFICATION_AUTHORITY is NOT_AUTHORIZED")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ResolutionAuthorityError("not a syntactically valid email")
        raw = self._get("email-verifier", {"email": email})
        data = raw.get("data")
        d = data if isinstance(data, dict) else {}
        status = str(d.get("status", "unknown"))
        return HunterVerifierResult(
            email=email,
            status=status,
            is_catch_all=bool(d.get("accept_all")) or status == "accept_all",
            mx_records=bool(d.get("mx_records")),
            smtp_check=d.get("smtp_check") if isinstance(d.get("smtp_check"), bool) else None,
            score=int(d["score"]) if isinstance(d.get("score"), int | float) else None,
            verified_at=datetime.now().astimezone(),
        )
