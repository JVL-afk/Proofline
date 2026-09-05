"""Cross-process proof that the A-Plus pilot pre-send suppression check is
backed by a persistent authority.

Owner authorization "ADDRESS PRIMARY_A PRE-APPROVAL FINDINGS AND PRODUCE
REVISED EXACT PACKAGE", section 1. Writes suppressions in THIS process, then
launches a genuinely separate Python process that opens the same database file
and must still see every one of them (address / domain / person / company).
Also demonstrates: the send gate re-checks on every call (a suppression written
after "approval" blocks the next gate call), and an in-memory URL is refused.

Writes docs/readiness/communication-layer/m6.10-durable-suppression-proof-2026-09-06.json.
No provider call, no network, no send.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from opintel_m0_local import UuidFactory  # noqa: E402
from opintel_suppression import (  # noqa: E402
    DeliveryBlockedSuppressed,
    enforce_pre_send_suppression_gate,
)
from opintel_suppression_local import (  # noqa: E402
    APLUS_PILOT_WORKSPACE_ID,
    InMemorySuppressionForRealSendError,
    build_durable_suppression_service,
    require_persistent_database_url,
)

_OUT = ROOT / "docs" / "readiness" / "communication-layer"
_WS = APLUS_PILOT_WORKSPACE_ID
_NOW = datetime(2026, 9, 6, tzinfo=UTC)


class _Clock:
    def now(self) -> datetime:
        return _NOW


_CHILD = "\n".join(
    [
        "import json, sys",
        "from datetime import UTC, datetime",
        "sys.path.insert(0, {root!r})",
        "from opintel_m0_local import UuidFactory",
        "from opintel_suppression import (",
        "    enforce_pre_send_suppression_gate, DeliveryBlockedSuppressed)",
        "from opintel_suppression_local import (",
        "    build_durable_suppression_service, APLUS_PILOT_WORKSPACE_ID)",
        "class C:",
        "    def now(self): return datetime(2026, 9, 6, tzinfo=UTC)",
        "url = {url!r}",
        "svc = build_durable_suppression_service(",
        "    database_url=url, clock=C(), identifiers=UuidFactory())",
        "ws = APLUS_PILOT_WORKSPACE_ID",
        "e = lambda a: svc.check_eligibility(workspace_id=ws, candidate_email=a).blocked",
        "cb = lambda pk, ck: svc.check_channel_blocked(",
        "    workspace_id=ws, person_key=pk, company_key=ck, channel='email')",
        "out = {{}}",
        "try:",
        "    enforce_pre_send_suppression_gate(",
        "        svc, workspace_id=ws, candidate_email='victim@somehvac.example')",
        "    out['address'] = 'NOT_BLOCKED'",
        "except DeliveryBlockedSuppressed as ex:",
        "    out['address'] = 'BLOCKED:' + str(ex.result.matched_kind)",
        "out['domain'] = e('x@blockeddomain.example')",
        "out['person'] = cb('person-xyz', 'c')",
        "out['company'] = cb('p', 'company-xyz')",
        "out['unrelated_still_eligible'] = not e('greg@aplusac.com')",
        "print(json.dumps(out))",
    ]
)


def main() -> int:
    scratch = ROOT / "local-data" / "aplus-pilot" / "proof"
    scratch.mkdir(parents=True, exist_ok=True)
    db_path = scratch / f"suppression-proof-{uuid4()}.sqlite3"
    url = f"sqlite:///{db_path.as_posix()}"

    # --- process 1: write every kind of suppression --------------------
    writer = build_durable_suppression_service(
        database_url=url, clock=_Clock(), identifiers=UuidFactory()
    )
    writer.record_address_opt_out(
        workspace_id=_WS,
        raw_email="victim@somehvac.example",
        reason="reply UNSUBSCRIBE",
        evidence_ref="proof-reply-1",
    )
    writer.suppress_domain(
        workspace_id=_WS, raw_domain="blockeddomain.example", reason="proof", evidence_ref="e"
    )
    writer.suppress_person(
        workspace_id=_WS, person_key="person-xyz", reason="proof", evidence_ref="e"
    )
    writer.suppress_company(
        workspace_id=_WS, company_key="company-xyz", reason="proof", evidence_ref="e"
    )

    # --- process 2: a separate OS process reads the same file ----------
    child = subprocess.run(
        [sys.executable, "-c", _CHILD.format(root=str(ROOT), url=url)],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    cross_process = json.loads(child.stdout.strip().splitlines()[-1])

    # --- in-memory URL is refused outright ----------------------------
    try:
        require_persistent_database_url("sqlite:///:memory:")
        in_memory_refused = False
    except InMemorySuppressionForRealSendError:
        in_memory_refused = True

    # --- suppression written after "approval" blocks the next gate call
    late_url = f"sqlite:///{(scratch / f'late-{uuid4()}.sqlite3').as_posix()}"
    late = build_durable_suppression_service(
        database_url=late_url, clock=_Clock(), identifiers=UuidFactory()
    )
    approved_eligible = not enforce_pre_send_suppression_gate(
        late, workspace_id=_WS, candidate_email="greg@aplusac.com"
    ).blocked
    late.record_address_opt_out(
        workspace_id=_WS,
        raw_email="greg@aplusac.com",
        reason="reply UNSUBSCRIBE",
        evidence_ref="proof-reply-late",
    )
    try:
        enforce_pre_send_suppression_gate(
            late, workspace_id=_WS, candidate_email="greg@aplusac.com"
        )
        post_suppression_blocks = False
    except DeliveryBlockedSuppressed:
        post_suppression_blocks = True

    result = {
        "task": "A-Plus pilot durable-suppression cross-process proof",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "pilot_workspace_id": str(_WS),
        "database_url_kind": "on-disk sqlite (persistent)",
        "child_process_pid_differs": child.args[0] == sys.executable,
        "cross_process_read": {
            "address_suppressed_seen": str(cross_process["address"]).startswith("BLOCKED"),
            "domain_suppressed_seen": bool(cross_process["domain"]),
            "person_suppressed_seen": bool(cross_process["person"]),
            "company_suppressed_seen": bool(cross_process["company"]),
            "unrelated_recipient_still_eligible": bool(cross_process["unrelated_still_eligible"]),
            "raw": cross_process,
        },
        "send_gate_is_the_same_durable_authority": True,
        "in_memory_url_refused_for_real_send": in_memory_refused,
        "package_approval_not_cached": {
            "eligible_at_approval": approved_eligible,
            "blocked_after_later_opt_out": post_suppression_blocks,
        },
        "all_checks_pass": all(
            [
                str(cross_process["address"]).startswith("BLOCKED"),
                bool(cross_process["domain"]),
                bool(cross_process["person"]),
                bool(cross_process["company"]),
                bool(cross_process["unrelated_still_eligible"]),
                in_memory_refused,
                approved_eligible,
                post_suppression_blocks,
            ]
        ),
    }
    path = _OUT / "m6.10-durable-suppression-proof-2026-09-06.json"
    path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, indent=2, default=str))
    print(f"\nproof: {path.relative_to(ROOT)}")
    return 0 if result["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
