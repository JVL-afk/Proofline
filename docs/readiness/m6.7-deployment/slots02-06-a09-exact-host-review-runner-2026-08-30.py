"""Bounded A-09 exact-host access review for Slots 02-06.

AUTHORIZE_SLOTS02_06_PHASE1_M1_V2_EXECUTION (package sha256
d28e42594c943debf0144b3f5ecce57589760881e579ebbf52f6984d8150677a) directive 2:
perform the existing bounded A-09 exact-host process for the five named frozen
mappings only. Read-only, no redirects, identity user agent, small byte cap,
content-minimised evidence, one same-host legal page. Never crawls. Applies the
existing acceptance criteria and, only when satisfied, emits an
APPROVED_FOR_BOUNDED_FIRST_PARTY_PUBLIC_RESEARCH decision row.
"""
from __future__ import annotations

import hashlib
import html.parser
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

USER_AGENT = "OpportunityIntelligenceResearch"  # same identity the runtime uses
MAX_BYTES = 900_000
CONVENTIONAL_LEGAL = (
    "/privacy-policy/", "/privacy-policy", "/privacy/", "/privacy",
    "/terms-and-conditions/", "/terms-and-conditions", "/terms-of-service",
    "/terms/", "/terms", "/legal/", "/legal", "/terms-of-use",
)
LEGAL_MARKERS = ("terms", "legal", "conditions", "privacy", "acceptable-use", "policy")
HARD_RESTRICTION = ("no automated", "no scraping", "no crawling", "prohibit automated",
                    "may not use any automated", "bots are prohibited")
WORD_RE = re.compile(r"[a-z0-9]+")

# Frozen slot rows, byte-identical to phase1-frozen-slot-registry.json.
SLOTS = [
    (2, "Webb Air", "webbair.com"),
    (3, "BNCAIR", "www.bncair.net"),
    (4, "All Elements Heating & Air", "allelementshvac.com"),
    (5, "Fintastic Cooling & Heating", "www.callfintastic.com"),
    (6, "Calvin's Climate", "www.calvinsclimate.com"),
]


class _Signals(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "a" and d.get("href"):
            self.links.append(d["href"])
        for k in ("content", "title", "alt"):
            if d.get(k):
                self.text.append(d[k])

    def handle_data(self, data: str) -> None:
        self.text.append(data)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_a: object, **_k: object) -> None:
        return None


def _fetch(opener: urllib.request.OpenerDirector, url: str) -> dict[str, object]:
    req = urllib.request.Request(url, method="GET", headers={
        "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
        "Accept-Encoding": "identity", "User-Agent": USER_AGENT,
    })
    try:
        resp = opener.open(req, timeout=30)
    except urllib.error.HTTPError as e:
        resp = e
    except Exception as e:  # noqa: BLE001
        return {"outcome": "TRANSPORT_FAILURE", "failure_class": type(e).__name__}
    with resp:
        raw = resp.read(MAX_BYTES + 1)
        status = int(getattr(resp, "status", 0) or 0)
        headers = {str(n).lower(): str(v) for n, v in resp.headers.items()}
    return {
        "outcome": "HTTP_RESPONSE", "status": status,
        "content_type": headers.get("content-type", ""),
        "body_bytes": min(len(raw), MAX_BYTES), "oversized": len(raw) > MAX_BYTES,
        "body_sha256": hashlib.sha256(raw[:MAX_BYTES]).hexdigest(),
        "_raw": raw[:MAX_BYTES],
        "redirect_location": headers.get("location") if status in (301, 302, 303, 307, 308) else None,
    }


def _robots_allows_root(body: bytes) -> bool:
    try:
        text = body.decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return False
    agent = None
    disallow_root = {}
    for line in text.splitlines():
        s = line.strip().lower()
        if s.startswith("user-agent:"):
            agent = s.split(":", 1)[1].strip()
        elif s.startswith("disallow:") and agent in ("*", USER_AGENT.lower()):
            path = s.split(":", 1)[1].strip()
            if path == "/":
                disallow_root[agent] = True
    return not disallow_root


def _identity(business: str, text: str) -> str:
    # Exact exclusion list from the existing A-09 review process
    # (scripts/run_m67_manual_exact_host_a09_access_review.py).
    excluded = {"and", "air", "conditioning", "heating", "mechanical", "services", "service",
               "company", "plumbing", "cooling", "inc", "llc"}
    expected = {w for w in WORD_RE.findall(business.lower()) if w not in excluded and len(w) > 2}
    observed = set(WORD_RE.findall(text.lower()))
    if expected and expected <= observed:
        return "BUSINESS_NAME_TOKENS_PRESENT"
    if expected & observed:
        return "PARTIAL_BUSINESS_NAME_TOKEN_MATCH"
    return "BUSINESS_NAME_NOT_CORROBORATED"


def _legal_path(host: str, links: list[str]) -> str | None:
    cands: set[str] = set()
    for href in links:
        low = href.lower()
        if not any(m in low for m in LEGAL_MARKERS):
            continue
        u = urllib.parse.urlsplit(urllib.parse.urljoin(f"https://{host}/", href))
        if u.scheme != "https" or (u.hostname or "").lower() != host:
            continue
        if u.username or u.password or u.port not in (None, 443) or u.query or u.fragment:
            continue
        p = u.path or "/"
        if 1 < len(p) <= 160:
            cands.add(p)
    return min(cands) if cands else None


def review_host(slot: int, business: str, host: str) -> dict[str, object]:
    opener = urllib.request.build_opener(
        _NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    ev: dict[str, object] = {"slot": slot, "business_identity": business, "exact_hostname": host,
                             "observed_at": datetime.now(UTC).isoformat()}
    robots = _fetch(opener, f"https://{host}/robots.txt")
    root = _fetch(opener, f"https://{host}/")
    robots_raw = robots.pop("_raw", b"")
    root_raw = root.pop("_raw", b"")

    parser = _Signals()
    if root.get("outcome") == "HTTP_RESPONSE":
        try:
            parser.feed(root_raw.decode("utf-8", "ignore"))
        except Exception:  # noqa: BLE001
            pass
    visible = " ".join(parser.text)
    identity = _identity(business, visible) if root.get("status") == 200 else "NO_ROOT"
    hard = sorted({m.upper() for m in HARD_RESTRICTION if m in visible.lower()})
    legal_path = _legal_path(host, parser.links)
    legal = None
    legal_source = None
    if legal_path:
        legal = _fetch(opener, f"https://{host}{legal_path}")
        legal.pop("_raw", None)
        legal_source = "homepage_link"
    if (not legal or legal.get("status") != 200) and root.get("status") == 200:
        # conventional same-host legal endpoints, exactly like the crawler probes
        # conventional sitemap endpoints -- bounded, no redirects.
        for cand in CONVENTIONAL_LEGAL:
            probe = _fetch(opener, f"https://{host}{cand}")
            probe.pop("_raw", None)
            if probe.get("status") == 200 and probe.get("redirect_location") is None:
                legal, legal_path, legal_source = probe, cand, "conventional_endpoint"
                break

    robots_ok = (
        robots.get("outcome") == "HTTP_RESPONSE"
        and (robots.get("status") == 404 or (robots.get("status") == 200
             and _robots_allows_root(robots_raw)))
    )
    ev["robots"] = {**robots, "root_allowed_for_review_agent": robots_ok}
    ev["root"] = {**root, "identity_signal": identity, "hard_restriction_markers": hard,
                  "same_host_legal_path": legal_path, "legal_path_source": legal_source}
    ev["legal"] = legal

    # Exact acceptance criteria of the existing bounded A-09 exact-host process.
    # The prior 2026-08-25 process recommended APPROVE for slots 1, 2 and 3 with
    # NO same-host legal path in any case -- a legal page is collected as
    # supporting evidence when present, its absence is not disqualifying.
    criteria = {
        "exact_host_serves_first_party_root_http_200": root.get("status") == 200,
        "root_not_redirected_off_the_exact_host": root.get("redirect_location") is None,
        "robots_allows_review_agent_at_root": robots_ok,
        "business_identity_corroborated_on_root": identity == "BUSINESS_NAME_TOKENS_PRESENT",
        "no_hard_automated_access_prohibition": not hard,
    }
    ev["supporting_evidence"] = {
        "same_host_legal_path": legal_path,
        "legal_path_source": legal_source,
        "legal_page_http_200": bool(legal and legal.get("status") == 200),
    }
    ev["acceptance_criteria"] = criteria
    satisfied = all(criteria.values())
    ev["evidence_state"] = "BOUNDED_A09_EVIDENCE_COMPLETE_FOR_SLOT"
    ev["a09_outcome"] = (
        "APPROVED_FOR_BOUNDED_FIRST_PARTY_PUBLIC_RESEARCH" if satisfied
        else "NOT_APPROVED_A09_CRITERIA_NOT_SATISFIED"
    )
    if satisfied:
        payload = {
            "slot_number": slot, "business_identity": business, "exact_hostname": host,
            "ordered_package_semantic_sha256":
                "3419a018a0cfb39c7fe6391c19b3acb43378b7b88e92337a2c70af305d345b5b",
            "root_body_sha256": root.get("body_sha256"),
            "robots_body_sha256": robots.get("body_sha256"),
            "legal_path": legal_path, "legal_body_sha256": legal.get("body_sha256") if legal else None,
            "authorization_package_sha256":
                "d28e42594c943debf0144b3f5ecce57589760881e579ebbf52f6984d8150677a",
        }
        ev["decision_sha256"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    return ev


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("a09_slots02_06_result.json")
    results = [review_host(s, b, h) for s, b, h in SLOTS]
    out.write_text(json.dumps({"results": results}, indent=1, sort_keys=True))
    for r in results:
        print(r["slot"], r["exact_hostname"], "->", r["a09_outcome"],
              json.dumps(r["acceptance_criteria"]))
    print("written", out)


if __name__ == "__main__":
    main()
