"""Customer-facing opt-out copy and SLA constants.

Configurable per sender identity; defaults to the exact pilot copy supplied by
PROJECT_OWNER for Proofline. No unsubscribe URL is ever included here - the
only externally permitted URL in the pilot is the separately-authorized demo
URL (ADR-0079).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

OPT_OUT_SUPPRESSION_MAX_SLA = timedelta(days=3)


@dataclass(frozen=True)
class SenderIdentityConfig:
    sender_person_name: str
    company_display_name: str
    reply_to_mailbox: str
    postal_disclosure: str

    @property
    def signature_block(self) -> str:
        return f"{self.sender_person_name}\n{self.company_display_name}\n{self.reply_to_mailbox}"


PROOFLINE_SENDER_IDENTITY = SenderIdentityConfig(
    sender_person_name="Andrew",
    company_display_name="Proofline",
    reply_to_mailbox="andrew@proofline.business",
    postal_disclosure="Proofline, Str. Lucian Blaga, nr. 8, Ciugud, Alba 517240, Romania",
)


def render_opt_out_notice(sender: SenderIdentityConfig) -> str:
    return (
        f"To stop receiving email from {sender.company_display_name}, reply to this "
        "message with the word UNSUBSCRIBE. We will remove your address within three days."
    )


DEFAULT_OPT_OUT_NOTICE = render_opt_out_notice(PROOFLINE_SENDER_IDENTITY)


_SENDER_SIGNATURE_SLOT = "{{verified_sender_signature}}"
_POSTAL_DISCLOSURE_SLOT = "{{required_postal_disclosure}}"
_OPT_OUT_INSTRUCTION_SLOT = "{{approved_opt_out_instruction}}"
_FUNCTIONAL_ROLE_OR_TEAM_SLOT = "{{functional_role_or_team}}"

KNOWN_DISCLOSURE_SLOTS = (
    _SENDER_SIGNATURE_SLOT,
    _POSTAL_DISCLOSURE_SLOT,
    _OPT_OUT_INSTRUCTION_SLOT,
    _FUNCTIONAL_ROLE_OR_TEAM_SLOT,
)


def resolve_known_disclosure_slots(body: str, sender: SenderIdentityConfig) -> str:
    """Fills exactly the four disclosure slots this pilot's supplied
    configuration can resolve without inventing anything. ``functional_role_or_team``
    resolves to a generic team-level descriptor derived directly from the
    already-supplied company name (no personal title was supplied, and none is
    invented here). Any other placeholder (for example the demo-URL slot) is
    left untouched."""
    resolved = body
    resolved = resolved.replace(_SENDER_SIGNATURE_SLOT, sender.signature_block)
    resolved = resolved.replace(_POSTAL_DISCLOSURE_SLOT, sender.postal_disclosure)
    resolved = resolved.replace(_OPT_OUT_INSTRUCTION_SLOT, render_opt_out_notice(sender))
    resolved = resolved.replace(
        _FUNCTIONAL_ROLE_OR_TEAM_SLOT, f"the {sender.company_display_name} team"
    )
    return resolved
