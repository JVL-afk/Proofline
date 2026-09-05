"""Hard pre-send suppression gate.

``enforce_pre_send_suppression_gate`` has no override parameter of any kind:
there is structurally no way for a caller - human approval, provider output,
or a previously approved package - to pass a flag that skips the check. A
package approved before a recipient becomes suppressed is invalidated the
next time this gate runs, because eligibility is always re-checked at the
moment of the call, never cached from an earlier approval.
"""

from __future__ import annotations

from uuid import UUID

from opintel_suppression.application import SuppressionRegistryService
from opintel_suppression.domain import SuppressionCheckResult


class DeliveryBlockedSuppressed(Exception):
    """Raised by the pre-send gate. The only correct response is: do not send."""

    def __init__(self, result: SuppressionCheckResult) -> None:
        self.result = result
        super().__init__(
            "DELIVERY_BLOCKED_SUPPRESSED: "
            f"{result.matched_kind} matched for {result.normalized_email}"
        )


def enforce_pre_send_suppression_gate(
    service: SuppressionRegistryService, *, workspace_id: UUID, candidate_email: str
) -> SuppressionCheckResult:
    result = service.check_eligibility(workspace_id=workspace_id, candidate_email=candidate_email)
    if result.blocked:
        raise DeliveryBlockedSuppressed(result)
    return result
