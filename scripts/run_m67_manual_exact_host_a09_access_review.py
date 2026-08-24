"""Bounded exact-host A-09 evidence collection for the frozen manual sample.

This runner never approves a host. It collects minimized source-access evidence
for a later accountable per-host decision and follows no redirects.
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

ACCOUNT = "785072247535"
REGION = "us-east-2"
EVENT = "AUTHORIZE_MANUAL_PHASE1_EXACT_HOST_A09_ACCESS_REVIEW"
EXPECTED_PACKAGE_FILE_SHA256 = "755279cb8e5ac06c579c411857bfc6d380602722813de1cda21175b9385b5467"
EXPECTED_PACKAGE_SEMANTIC_SHA256 = "8a0703e6a441e28a62ae5f5ed32faf0279502c695d34779132ffa48979074050"
EXPECTED_OFFLINE_EVIDENCE_SHA256 = "049088a62eba7cd927bf1dffbc0a11b2e3f68cd8eb339df9ca3047c8bd4ee7ec"
USER_AGENT = "M67Phase1A09Review/1.0"
LEGAL_MARKERS = ("terms", "legal", "conditions", "acceptable-use")
RESTRICTION_MARKERS = ("automated", "scrap", "robot", "crawl", "commercial", "license")
WORD_RE = re.compile(r"[a-z0-9]+")


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


class PageSignals(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        if tag.lower() == "a" and values.get("href"):
            self._href = values["href"]
            self._link_text = []
        for name in ("content", "alt", "title"):
            if values.get(name):
                self.text.append(values[name])

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._link_text)))
            self._href = None
            self._link_text = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self._href is not None:
            self._link_text.append(data)


def safe_legal_path(host: str, links: list[tuple[str, str]]) -> str | None:
    candidates: set[str] = set()
    for href, label in links:
        joined = f"{href} {label}".lower()
        if not any(marker in joined for marker in LEGAL_MARKERS):
            continue
        parsed = urllib.parse.urlsplit(urllib.parse.urljoin(f"https://{host}/", href))
        if parsed.scheme != "https" or (parsed.hostname or "").lower() != host:
            continue
        if parsed.username or parsed.password or parsed.port not in (None, 443):
            continue
        path = parsed.path or "/"
        if len(path) <= 160 and not parsed.query and not parsed.fragment:
            candidates.add(path)
    return min(candidates) if candidates else None


def identity_signal(business_name: str, visible_text: str) -> str:
    excluded = {"and", "air", "conditioning", "heating", "mechanical", "services", "service", "company", "plumbing"}
    expected = {word for word in WORD_RE.findall(business_name.lower()) if word not in excluded and len(word) > 2}
    observed = set(WORD_RE.findall(visible_text.lower()))
    if expected and expected <= observed:
        return "BUSINESS_NAME_TOKENS_PRESENT"
    if expected & observed:
        return "PARTIAL_BUSINESS_NAME_TOKEN_MATCH"
    return "BUSINESS_NAME_NOT_CORROBORATED"


def restriction_flags(text: str) -> list[str]:
    lowered = text.lower()
    return [marker.upper().replace("-", "_") for marker in RESTRICTION_MARKERS if marker in lowered]


def fetch(
    opener: urllib.request.OpenerDirector,
    url: str,
    max_bytes: int,
) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, method="GET", headers={
        "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
        "Accept-Encoding": "identity",
        "User-Agent": USER_AGENT,
    })
    try:
        response: Any = opener.open(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(max_bytes + 1)
        headers = {str(name).lower(): str(value) for name, value in response.headers.items()}
        return int(response.status), headers, raw


def run(
    authorization_path: Path,
    configuration_path: Path,
    ordered_package_path: Path,
    offline_evidence_path: Path,
    output_path: Path,
    *,
    opener: urllib.request.OpenerDirector | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    now: datetime | None = None,
) -> dict[str, Any]:
    config_raw = configuration_path.read_bytes()
    config = json.loads(config_raw)
    auth = json.loads(authorization_path.read_text(encoding="utf-8"))
    observed_at = now or datetime.now(UTC)
    starts = datetime.fromisoformat(config["window"]["starts_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(config["window"]["expires_at"].replace("Z", "+00:00"))
    if not starts <= observed_at <= expires:
        raise RuntimeError("authorization window is not active")
    if auth.get("event") != EVENT or auth.get("state") != "APPROVED":
        raise RuntimeError("exact A-09 access-review authorization is absent")
    if auth.get("configuration_sha256") != sha256_bytes(config_raw):
        raise RuntimeError("configuration hash mismatch")
    if auth.get("exact_executable_sha256") != sha256_bytes(Path(__file__).read_bytes()):
        raise RuntimeError("executable hash mismatch")
    package_raw = ordered_package_path.read_bytes()
    if sha256_bytes(package_raw) != EXPECTED_PACKAGE_FILE_SHA256:
        raise RuntimeError("ordered package file hash mismatch")
    package = json.loads(package_raw)
    if package.get("package_sha256") != EXPECTED_PACKAGE_SEMANTIC_SHA256:
        raise RuntimeError("ordered package semantic hash mismatch")
    if sha256_bytes(offline_evidence_path.read_bytes()) != EXPECTED_OFFLINE_EVIDENCE_SHA256:
        raise RuntimeError("offline A-09 evidence hash mismatch")
    slots = package.get("slots")
    if not isinstance(slots, list) or [item.get("slot") for item in slots] != list(range(1, 25)):
        raise RuntimeError("immutable slot mapping mismatch")

    client = opener or urllib.request.build_opener(
        NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    max_response = int(config["limits"]["max_response_bytes"])
    max_total = int(config["limits"]["max_total_response_bytes"])
    delay = float(config["limits"]["minimum_delay_seconds"])
    total_bytes = 0
    requests = 0
    decisions: list[dict[str, Any]] = []

    for slot_index, row in enumerate(slots):
        host = row["candidate_hostname"]
        observations: dict[str, Any] = {}
        visible_text = ""
        legal_path: str | None = None
        for path_name, path in (("robots", "/robots.txt"), ("root", "/")):
            if requests:
                sleeper(delay)
            status, headers, raw = fetch(client, f"https://{host}{path}", max_response)
            requests += 1
            total_bytes += len(raw)
            if len(raw) > max_response or total_bytes > max_total:
                raise RuntimeError("response byte ceiling exceeded")
            location = headers.get("location")
            redirect_host = None
            if location:
                redirect_host = (urllib.parse.urlsplit(urllib.parse.urljoin(f"https://{host}{path}", location)).hostname or "").lower()
            observations[path_name] = {
                "status": status,
                "content_type": headers.get("content-type"),
                "body_bytes": len(raw),
                "body_sha256": sha256_bytes(raw),
                "redirect_host": redirect_host,
            }
            text = raw.decode("utf-8", errors="replace")
            if path_name == "robots":
                parser = urllib.robotparser.RobotFileParser()
                parser.set_url(f"https://{host}/robots.txt")
                parser.parse(text.splitlines())
                observations[path_name]["root_allowed_for_review_agent"] = status != 200 or parser.can_fetch(USER_AGENT, "/")
            else:
                signals = PageSignals()
                signals.feed(text)
                visible_text = " ".join(signals.text)
                legal_path = safe_legal_path(host, signals.links)
                observations[path_name]["identity_signal"] = identity_signal(row["public_business_name"], visible_text)
                observations[path_name]["same_host_legal_path"] = legal_path

        if legal_path:
            sleeper(delay)
            status, headers, raw = fetch(client, f"https://{host}{legal_path}", max_response)
            requests += 1
            total_bytes += len(raw)
            if len(raw) > max_response or total_bytes > max_total:
                raise RuntimeError("response byte ceiling exceeded")
            observations["legal"] = {
                "path": legal_path,
                "status": status,
                "content_type": headers.get("content-type"),
                "body_bytes": len(raw),
                "body_sha256": sha256_bytes(raw),
                "restriction_marker_flags": restriction_flags(raw.decode("utf-8", errors="replace")),
                "redirect_host": (urllib.parse.urlsplit(urllib.parse.urljoin(f"https://{host}{legal_path}", headers.get("location", ""))).hostname or "").lower() if headers.get("location") else None,
            }

        redirects = [value.get("redirect_host") for value in observations.values() if value.get("redirect_host")]
        robots_denied = observations["robots"].get("root_allowed_for_review_agent") is False
        foreign_redirect = any(target != host for target in redirects)
        decision = "REJECTED" if robots_denied or foreign_redirect else "REQUIRES_HUMAN_REVIEW"
        decisions.append({
            "slot": row["slot"],
            "public_business_name_sha256": sha256_bytes(row["public_business_name"].encode()),
            "candidate_hostname": host,
            "mapping_immutable": True,
            "observations": observations,
            "decision": decision,
            "approval_for_public_research": False,
        })

    evidence = {
        "record_type": "M67_MANUAL_PHASE1_EXACT_HOST_A09_ACCESS_REVIEW_EVIDENCE",
        "state": "READY_FOR_EXACT_HOST_A09_HUMAN_DECISION",
        "account": ACCOUNT,
        "region": REGION,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "ordered_package_semantic_sha256": EXPECTED_PACKAGE_SEMANTIC_SHA256,
        "slot_count": 24,
        "logical_http_requests": requests,
        "response_bytes": total_bytes,
        "redirects_followed": 0,
        "raw_bodies_persisted": False,
        "person_contact_values_persisted": False,
        "browser_sessions": 0,
        "ai_calls": 0,
        "m1_m5_operations": 0,
        "replacements": 0,
        "kill_switch_final_state": "TRIPPED",
        "m67_permissions": {name: "NOT_AUTHORIZED" for name in (
            "REAL_BUSINESS_DISCOVERY", "REAL_PUBLIC_RESEARCH", "PROFESSIONAL_IDENTITY_RESOLUTION",
            "REAL_CONTACT_STORAGE", "CONTACT_VERIFICATION", "SHADOW_ELIGIBILITY_EVALUATION",
            "SHADOW_READY_ASSESSMENT",
        )},
        "decisions": decisions,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as handle:
        handle.write(canonical_bytes(evidence))
        handle.flush()
        os.fsync(handle.fileno())
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument("--ordered-package", type=Path, required=True)
    parser.add_argument("--offline-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.authorization, args.configuration, args.ordered_package, args.offline_evidence, args.output)
    print(json.dumps({key: value for key, value in result.items() if key != "decisions"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
