"""Runtime-owned M4 security and disclosure policy constants."""

DISCLOSURE_TEMPLATE = (
    "Simulation for evaluation only. Not operated by or on behalf of {business}. No request is "
    "sent, no appointment is booked, and no external system is updated."
)
SAFETY_HANDOFF_MESSAGE = (
    "This simulation cannot evaluate safety-critical or emergency situations. A real deployment "
    "would route this case to an approved human emergency-handling process. No dispatch or "
    "emergency action has occurred."
)
CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; media-src 'self'; object-src 'none'; frame-src 'none'; "
    "frame-ancestors 'none'; form-action 'none'; base-uri 'none'; worker-src 'none'; "
    "manifest-src 'none'"
)
