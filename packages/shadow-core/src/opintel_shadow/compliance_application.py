"""Deterministic Phase 1 minimization, retention, incident, and host-review services."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser

from opintel_shadow.compliance_domain import (
    AuthorityVerification,
    CaptureDisposition,
    DestructionMethod,
    HostReviewState,
    IncidentAssessment,
    IncidentDeadline,
    IncidentDecision,
    IncidentWorkflowState,
    MinimizedCapture,
    PerHostSourceReview,
    PhaseOneDataClass,
    PhaseOneRetentionPolicy,
    RedactedReviewArtifact,
    RetentionRule,
    StatutoryAuthority,
)
from opintel_shadow.domain import stable_hash

_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?1[ .()-]*)?(?:\d[ .()-]*){10}(?!\w)")
_CONTACT_MARKERS = frozenset(
    {"contact", "staff", "team", "employee", "person", "vcard", "phone", "email", "tel"}
)
_ALLOWED_EVIDENCE_TERMS = (
    "texas",
    "tx",
    "commercial",
    "hvac",
    "heating",
    "cooling",
    "air conditioning",
    "business",
    "company",
    "facility",
    "service",
    "request",
    "quote",
    "estimate",
    "inquiry",
    "form",
)
_SKIP_TAGS = frozenset({"script", "style", "noscript", "template", "svg"})
_ALL_STORES = ("primary", "replicas", "object_versions", "backups", "derived_stores")


class _MinimizingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.fragments: list[str] = []
        self.removed_blocks = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = " ".join(value or "" for key, value in attrs if key in {"id", "class", "itemtype"})
        tokens = {item.lower() for item in re.split(r"[^a-zA-Z]+", values) if item}
        if self._skip_depth or tag.lower() in _SKIP_TAGS or tokens & _CONTACT_MARKERS:
            if self._skip_depth == 0 and (tokens & _CONTACT_MARKERS):
                self.removed_blocks += 1
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        del tag
        if self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.fragments.append(" ".join(data.split()))


class PhaseOneMinimizer:
    """Transforms an ephemeral body into minimized text or a content-free quarantine record."""

    def minimize(
        self,
        *,
        source_uri: str,
        captured_at: datetime,
        raw_body: bytes,
        required_evidence_markers: tuple[str, ...],
    ) -> MinimizedCapture:
        raw_hash = hashlib.sha256(raw_body).hexdigest()
        try:
            decoded = raw_body.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return self._quarantine(
                source_uri, captured_at, raw_hash, required_evidence_markers, "UNSAFE_ENCODING"
            )

        parser = _MinimizingParser()
        try:
            parser.feed(decoded)
            parser.close()
        except Exception:  # HTMLParser can surface malformed entity/input failures.
            return self._quarantine(
                source_uri, captured_at, raw_hash, required_evidence_markers, "MALFORMED_CONTENT"
            )
        visible = "\n".join(parser.fragments)
        email_count = len(_EMAIL.findall(decoded))
        phone_count = len(_PHONE.findall(decoded))
        structured_count = parser.removed_blocks + len(
            re.findall(r'(?i)["\']@type["\']\s*:\s*["\'](?:ContactPoint|Person)["\']', decoded)
        )
        redacted = _PHONE.sub("[PHONE_REDACTED]", _EMAIL.sub("[EMAIL_REDACTED]", visible))
        permitted_terms = tuple(item.casefold() for item in required_evidence_markers) + (
            _ALLOWED_EVIDENCE_TERMS
        )
        minimized = "\n".join(
            line
            for line in redacted.splitlines()
            if line.strip() and any(term in line.casefold() for term in permitted_terms)
        )
        missing = tuple(
            marker
            for marker in required_evidence_markers
            if marker.casefold() not in minimized.casefold()
        )
        if missing:
            return MinimizedCapture(
                source_uri=source_uri,
                captured_at=captured_at,
                raw_content_sha256=raw_hash,
                minimized_content_sha256=None,
                minimized_text=None,
                disposition=CaptureDisposition.QUARANTINE_AND_REVIEW,
                removed_email_count=email_count,
                removed_phone_count=phone_count,
                removed_structured_contact_blocks=structured_count,
                required_evidence_markers=required_evidence_markers,
                quarantine_reasons=tuple(
                    f"REQUIRED_EVIDENCE_NOT_SAFELY_PRESERVED:{item}" for item in missing
                ),
            )
        return MinimizedCapture(
            source_uri=source_uri,
            captured_at=captured_at,
            raw_content_sha256=raw_hash,
            minimized_content_sha256=hashlib.sha256(minimized.encode()).hexdigest(),
            minimized_text=minimized,
            disposition=CaptureDisposition.DURABLE_MINIMIZED_CAPTURE,
            removed_email_count=email_count,
            removed_phone_count=phone_count,
            removed_structured_contact_blocks=structured_count,
            required_evidence_markers=required_evidence_markers,
            quarantine_reasons=(),
        )

    @staticmethod
    def _quarantine(
        source_uri: str,
        captured_at: datetime,
        raw_hash: str,
        markers: tuple[str, ...],
        reason: str,
    ) -> MinimizedCapture:
        return MinimizedCapture(
            source_uri=source_uri,
            captured_at=captured_at,
            raw_content_sha256=raw_hash,
            minimized_content_sha256=None,
            minimized_text=None,
            disposition=CaptureDisposition.QUARANTINE_AND_REVIEW,
            removed_email_count=0,
            removed_phone_count=0,
            removed_structured_contact_blocks=0,
            required_evidence_markers=markers,
            quarantine_reasons=(reason,),
        )

    def build_review_artifact(
        self,
        *,
        review_id: str,
        capture: MinimizedCapture,
        evidence_locator: str,
        excerpt: str,
    ) -> RedactedReviewArtifact:
        if capture.disposition is not CaptureDisposition.DURABLE_MINIMIZED_CAPTURE:
            raise ValueError("quarantined capture cannot produce a review artifact")
        if excerpt not in (capture.minimized_text or ""):
            raise ValueError("review excerpt must come from the minimized capture")
        if _EMAIL.search(excerpt) or _PHONE.search(excerpt):
            raise ValueError("review excerpt contains an unredacted contact value")
        return RedactedReviewArtifact(
            review_id=review_id,
            minimized_capture_sha256=capture.minimized_content_sha256 or "",
            evidence_locator=evidence_locator,
            redacted_excerpt=excerpt,
        )


def approved_phase_one_retention_policy() -> PhaseOneRetentionPolicy:
    days = {
        PhaseOneDataClass.SUCCESSFUL_MINIMIZED_SNAPSHOT: 90,
        PhaseOneDataClass.FAILED_ABORTED_CAPTURE: 30,
        PhaseOneDataClass.EXTRACTED_TEXT: 90,
        PhaseOneDataClass.EVIDENCE_EXCERPT_LOCATOR: 90,
        PhaseOneDataClass.ANALYSIS_ARTIFACT: 180,
        PhaseOneDataClass.HUMAN_REVIEW_RECORD: 365,
        PhaseOneDataClass.COMPANY_METRIC: 180,
        PhaseOneDataClass.APPROVED_AGGREGATE_METRIC: 365,
        PhaseOneDataClass.OPERATIONAL_LOG: 90,
        PhaseOneDataClass.SECURITY_ACCESS_LOG: 365,
        PhaseOneDataClass.ENCRYPTED_BACKUP: 30,
        PhaseOneDataClass.DELETION_TOMBSTONE: 730,
    }
    rules = []
    for data_class in PhaseOneDataClass:
        overhang = (
            0
            if data_class
            in {
                PhaseOneDataClass.ENCRYPTED_BACKUP,
                PhaseOneDataClass.DELETION_TOMBSTONE,
            }
            else 30
        )
        methods: tuple[DestructionMethod, ...]
        if data_class is PhaseOneDataClass.ENCRYPTED_BACKUP:
            methods = (DestructionMethod.CRYPTOGRAPHIC_ERASURE,)
        elif data_class is PhaseOneDataClass.DELETION_TOMBSTONE:
            methods = (DestructionMethod.CONTENT_FREE_TOMBSTONE,)
        elif data_class in {
            PhaseOneDataClass.OPERATIONAL_LOG,
            PhaseOneDataClass.SECURITY_ACCESS_LOG,
        }:
            methods = (DestructionMethod.LOG_EXPIRY, DestructionMethod.CRYPTOGRAPHIC_ERASURE)
        else:
            methods = (
                DestructionMethod.HARD_DELETE_PRIMARY_AND_DERIVED,
                DestructionMethod.OBJECT_VERSION_LIFECYCLE_DELETE,
                DestructionMethod.CRYPTOGRAPHIC_ERASURE,
                DestructionMethod.CONTENT_FREE_TOMBSTONE,
            )
        rules.append(
            RetentionRule(
                data_class=data_class,
                retention_days=days[data_class],
                backup_overhang_days=overhang,
                maximum_effective_retention_days=days[data_class] + overhang,
                destruction_methods=methods,
                applies_to_stores=_ALL_STORES,
                redacted_excerpts_only=data_class is PhaseOneDataClass.HUMAN_REVIEW_RECORD,
            )
        )
    return PhaseOneRetentionPolicy(
        policy_id="A08_PHASE1_MINIMIZED_RETENTION_V1",
        state="APPROVED_POLICY_NOT_LIVE_EFFECTIVE",
        rules=tuple(rules),
        tombstone_allowed_fields=(
            "artifact_hash",
            "internal_artifact_id",
            "data_class",
            "deletion_reason_code",
            "deleted_at",
            "policy_revision",
        ),
        approval_actor_binding="OWNER_SUBJECT_PENDING_IDP_BINDING",
    )


class Chapter521IncidentService:
    """Computes no notification side effect; unresolved authority always fails closed."""

    def evaluate(
        self,
        assessment: IncidentAssessment,
        authorities: tuple[StatutoryAuthority, ...],
    ) -> IncidentDecision:
        by_id = {item.authority_id: item for item in authorities}
        unresolved: list[str] = []
        deadlines: list[IncidentDeadline] = []
        required_fields = (
            assessment.sensitive_information_maintained,
            assessment.breach_determined,
            assessment.breach_determined_at,
            assessment.affected_texas_residents,
            assessment.notification_required,
        )
        if (
            any(item is None for item in required_fields)
            or not assessment.affected_subjects_determined
        ):
            unresolved.append("INCIDENT_FACTS_INCOMPLETE")
        elif assessment.breach_determined and assessment.notification_required:
            determined_at = assessment.breach_determined_at
            if determined_at is None:  # Defensive narrowing; handled by the branch above.
                raise AssertionError("breach determination timestamp unexpectedly absent")
            individual = by_id.get("TX-BC-521.053-B")
            if (
                individual is None
                or individual.verification is not AuthorityVerification.STATUTORILY_VERIFIED
            ):
                unresolved.append("INDIVIDUAL_NOTIFICATION_AUTHORITY_UNVERIFIED")
            else:
                deadlines.append(
                    IncidentDeadline(
                        recipient_class="AFFECTED_INDIVIDUAL",
                        deadline_at=determined_at + timedelta(days=60),
                        authority_id=individual.authority_id,
                        authority_section=f"{individual.section}{individual.subsection}",
                    )
                )
            if (assessment.affected_texas_residents or 0) >= 250:
                attorney_general = by_id.get("TX-BC-521.053-I")
                if (
                    attorney_general is None
                    or attorney_general.verification
                    is not AuthorityVerification.STATUTORILY_VERIFIED
                ):
                    unresolved.append("TEXAS_AG_NOTIFICATION_AUTHORITY_UNVERIFIED")
                else:
                    deadlines.append(
                        IncidentDeadline(
                            recipient_class="TEXAS_ATTORNEY_GENERAL",
                            deadline_at=determined_at + timedelta(days=30),
                            authority_id=attorney_general.authority_id,
                            authority_section=f"{attorney_general.section}{attorney_general.subsection}",
                        )
                    )
        state = (
            IncidentWorkflowState.LEGAL_REVIEW_REQUIRED
            if unresolved
            else IncidentWorkflowState.NOTIFICATION_DECISION_READY
        )
        payload = {
            "incident_id": assessment.incident_id,
            "state": state,
            "deadlines": tuple((item.recipient_class, item.deadline_at) for item in deadlines),
            "authority_ids": tuple(item.authority_id for item in deadlines),
            "unresolved": tuple(unresolved),
        }
        return IncidentDecision(
            incident_id=assessment.incident_id,
            state=state,
            deadlines=tuple(deadlines),
            authority_ids=tuple(item.authority_id for item in deadlines),
            unresolved_rules=tuple(unresolved),
            immutable_record_hash=stable_hash(payload),
        )


def evaluate_per_host_review(
    *,
    source_id: str,
    exact_host: str,
    reviewed_at: datetime,
    reviewer_actor_binding: str,
    terms_reviewed: bool,
    robots_reviewed: bool,
    access_restrictions_reviewed: bool,
    automated_access_restrictions_reviewed: bool,
    capture_storage_reuse_reviewed: bool,
    unresolved_copyright_or_contract_issue: bool,
    material_prohibition: bool,
) -> PerHostSourceReview:
    completed = all(
        (
            terms_reviewed,
            robots_reviewed,
            access_restrictions_reviewed,
            automated_access_restrictions_reviewed,
            capture_storage_reuse_reviewed,
        )
    )
    state = (
        HostReviewState.SOURCE_BLOCKED
        if material_prohibition or unresolved_copyright_or_contract_issue
        else HostReviewState.APPROVED
        if completed
        else HostReviewState.PENDING_PER_HOST_REVIEW
    )
    return PerHostSourceReview(
        source_id=source_id,
        exact_host=exact_host,
        reviewed_at=reviewed_at,
        reviewer_actor_binding=reviewer_actor_binding,
        terms_reviewed=terms_reviewed,
        robots_reviewed=robots_reviewed,
        access_restrictions_reviewed=access_restrictions_reviewed,
        automated_access_restrictions_reviewed=automated_access_restrictions_reviewed,
        capture_storage_reuse_reviewed=capture_storage_reuse_reviewed,
        unresolved_copyright_or_contract_issue=unresolved_copyright_or_contract_issue,
        material_prohibition=material_prohibition,
        state=state,
    )


__all__ = [
    "Chapter521IncidentService",
    "PhaseOneMinimizer",
    "approved_phase_one_retention_policy",
    "evaluate_per_host_review",
]
