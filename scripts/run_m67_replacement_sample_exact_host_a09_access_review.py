"""Collect minimized A-09 access evidence for the replacement Phase 1 sample.

The runner is one-shot, follows no redirects, never approves a host, and writes
content-minimized checkpoint evidence after every request outcome.
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
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ACCOUNT = "785072247535"
REGION = "us-east-2"
EVENT = "AUTHORIZE_REPLACEMENT_SAMPLE_EXACT_HOST_A09_ACCESS_REVIEW"
PACKAGE_FILE_SHA256 = "0283f0a6956f6bd11e9326419d9671a61cc57dac0b6d376b9e2b7a11f0507a70"
PACKAGE_SEMANTIC_SHA256 = "3419a018a0cfb39c7fe6391c19b3acb43378b7b88e92337a2c70af305d345b5b"
ORDERED_FRAME_EVIDENCE_SHA256 = "23a2efe438dcc51e2dc290da49d5d73f10cd8af9e94743ed8a6da62cfa09980a"
USER_AGENT = "M67ReplacementSampleA09Review/1.0"
LEGAL_MARKERS = ("terms", "legal", "conditions", "acceptable-use")
RESTRICTION_MARKERS = ("automated", "scrap", "robot", "crawl", "commercial", "license")
WORD_RE = re.compile(r"[a-z0-9]+")
PERMISSIONS = (
    "REAL_BUSINESS_DISCOVERY",
    "REAL_PUBLIC_RESEARCH",
    "PROFESSIONAL_IDENTITY_RESOLUTION",
    "REAL_CONTACT_STORAGE",
    "CONTACT_VERIFICATION",
    "SHADOW_ELIGIBILITY_EVALUATION",
    "SHADOW_READY_ASSESSMENT",
)


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
        self._label: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.lower(): value or "" for name, value in attrs}
        if tag.lower() == "a" and values.get("href"):
            self._href = values["href"]
            self._label = []
        for name in ("content", "alt", "title"):
            if values.get(name):
                self.text.append(values[name])

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._label)))
            self._href = None
            self._label = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self._href is not None:
            self._label.append(data)


def safe_legal_path(host: str, links: list[tuple[str, str]]) -> str | None:
    candidates: set[str] = set()
    for href, label in links:
        if not any(marker in f"{href} {label}".lower() for marker in LEGAL_MARKERS):
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
    excluded = {
        "and",
        "air",
        "conditioning",
        "heating",
        "mechanical",
        "services",
        "service",
        "company",
        "plumbing",
        "cooling",
        "inc",
        "llc",
    }
    expected = {
        word
        for word in WORD_RE.findall(business_name.lower())
        if word not in excluded and len(word) > 2
    }
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
    opener: urllib.request.OpenerDirector, url: str, max_bytes: int
) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
            "Accept-Encoding": "identity",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        response: Any = opener.open(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(max_bytes + 1)
        headers = {str(name).lower(): str(value) for name, value in response.headers.items()}
        return int(response.status), headers, raw


def safe_transport_failure(error: BaseException) -> dict[str, str]:
    name = type(error).__name__
    reason = getattr(error, "reason", None)
    if reason is not None:
        name = f"{name}:{type(reason).__name__}"
    return {"outcome": "TRANSPORT_FAILURE", "failure_class": name}


def write_checkpoint(path: Path, evidence: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(canonical_bytes(evidence))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def run(
    authorization_path: Path,
    configuration_path: Path,
    ordered_package_path: Path,
    ordered_frame_evidence_path: Path,
    output_path: Path,
    *,
    opener: urllib.request.OpenerDirector | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    now: datetime | None = None,
) -> dict[str, Any]:
    config_raw = configuration_path.read_bytes()
    config = json.loads(config_raw)
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    observed_at = now or datetime.now(UTC)
    starts = datetime.fromisoformat(config["window"]["starts_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(config["window"]["expires_at"].replace("Z", "+00:00"))
    if not starts <= observed_at <= expires:
        raise RuntimeError("authorization window is not active")
    if authorization.get("event") != EVENT or authorization.get("state") != "APPROVED":
        raise RuntimeError("exact replacement-sample A-09 authorization is absent")
    if authorization.get("configuration_sha256") != sha256_bytes(config_raw):
        raise RuntimeError("configuration hash mismatch")
    if authorization.get("exact_executable_sha256") != sha256_bytes(Path(__file__).read_bytes()):
        raise RuntimeError("executable hash mismatch")
    package_raw = ordered_package_path.read_bytes()
    if sha256_bytes(package_raw) != PACKAGE_FILE_SHA256:
        raise RuntimeError("ordered package file hash mismatch")
    package = json.loads(package_raw)
    if package.get("package_sha256") != PACKAGE_SEMANTIC_SHA256:
        raise RuntimeError("ordered package semantic hash mismatch")
    if sha256_bytes(ordered_frame_evidence_path.read_bytes()) != ORDERED_FRAME_EVIDENCE_SHA256:
        raise RuntimeError("ordered-frame evidence hash mismatch")
    slots = package.get("slots")
    if not isinstance(slots, list) or [row.get("slot") for row in slots] != list(range(1, 25)):
        raise RuntimeError("immutable replacement slot mapping mismatch")
    expected_hosts = config["scope"]["exact_hosts_in_slot_order"]
    if [row.get("candidate_hostname") for row in slots] != expected_hosts:
        raise RuntimeError("exact host sequence mismatch")

    client = opener or urllib.request.build_opener(
        NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    max_response = int(config["limits"]["max_response_bytes"])
    max_total = int(config["limits"]["max_total_response_bytes"])
    max_requests = int(config["limits"]["logical_http_requests"])
    delay = float(config["limits"]["minimum_delay_seconds"])
    total_bytes = 0
    requests = 0
    decisions: list[dict[str, Any]] = []

    evidence: dict[str, Any] = {
        "record_type": "M67_REPLACEMENT_SAMPLE_EXACT_HOST_A09_ACCESS_REVIEW_EVIDENCE",
        "state": "IN_PROGRESS_CONTENT_MINIMIZED_CHECKPOINT",
        "account": ACCOUNT,
        "region": REGION,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "ordered_package_file_sha256": PACKAGE_FILE_SHA256,
        "ordered_package_semantic_sha256": PACKAGE_SEMANTIC_SHA256,
        "slot_count": 24,
        "logical_http_requests": 0,
        "response_bytes": 0,
        "redirects_followed": 0,
        "raw_bodies_persisted": False,
        "page_text_persisted": False,
        "person_contact_values_persisted": False,
        "browser_sessions": 0,
        "ai_calls": 0,
        "m1_m5_operations": 0,
        "replacements": 0,
        "kill_switch_final_state": "TRIPPED_UNCHANGED",
        "m67_permissions": {name: "NOT_AUTHORIZED" for name in PERMISSIONS},
        "decisions": decisions,
    }

    for row in slots:
        host = row["candidate_hostname"]
        observations: dict[str, Any] = {}
        legal_path: str | None = None
        for label, path in (("robots", "/robots.txt"), ("root", "/")):
            if requests:
                sleeper(delay)
            if requests >= max_requests:
                raise RuntimeError("logical request ceiling exceeded")
            try:
                status, headers, raw = fetch(client, f"https://{host}{path}", max_response)
                requests += 1
                total_bytes += len(raw)
                if len(raw) > max_response or total_bytes > max_total:
                    raise RuntimeError("response byte ceiling exceeded")
                location = headers.get("location")
                redirect_host = None
                if location:
                    joined = urllib.parse.urljoin(f"https://{host}{path}", location)
                    redirect_host = (urllib.parse.urlsplit(joined).hostname or "").lower()
                observation: dict[str, Any] = {
                    "outcome": "HTTP_RESPONSE",
                    "status": status,
                    "content_type": headers.get("content-type"),
                    "body_bytes": len(raw),
                    "body_sha256": sha256_bytes(raw),
                    "redirect_host": redirect_host,
                }
                text = raw.decode("utf-8", errors="replace")
                if label == "robots":
                    parser = urllib.robotparser.RobotFileParser()
                    parser.set_url(f"https://{host}/robots.txt")
                    parser.parse(text.splitlines())
                    observation["root_allowed_for_review_agent"] = (
                        status != 200 or parser.can_fetch(USER_AGENT, "/")
                    )
                else:
                    signals = PageSignals()
                    signals.feed(text)
                    observation["identity_signal"] = identity_signal(
                        row["company_name"], " ".join(signals.text)
                    )
                    legal_path = safe_legal_path(host, signals.links)
                    observation["same_host_legal_path"] = legal_path
                observations[label] = observation
            except (OSError, ssl.SSLError, urllib.error.URLError) as error:
                requests += 1
                observations[label] = safe_transport_failure(error)
            evidence["logical_http_requests"] = requests
            evidence["response_bytes"] = total_bytes
            write_checkpoint(output_path, evidence)

        if legal_path:
            sleeper(delay)
            if requests >= max_requests:
                raise RuntimeError("logical request ceiling exceeded")
            try:
                status, headers, raw = fetch(client, f"https://{host}{legal_path}", max_response)
                requests += 1
                total_bytes += len(raw)
                if len(raw) > max_response or total_bytes > max_total:
                    raise RuntimeError("response byte ceiling exceeded")
                location = headers.get("location")
                observations["legal"] = {
                    "outcome": "HTTP_RESPONSE",
                    "path": legal_path,
                    "status": status,
                    "content_type": headers.get("content-type"),
                    "body_bytes": len(raw),
                    "body_sha256": sha256_bytes(raw),
                    "restriction_marker_flags": restriction_flags(
                        raw.decode("utf-8", errors="replace")
                    ),
                    "redirect_host": (
                        (
                            urllib.parse.urlsplit(
                                urllib.parse.urljoin(f"https://{host}{legal_path}", location)
                            ).hostname
                            or ""
                        ).lower()
                        if location
                        else None
                    ),
                }
            except (OSError, ssl.SSLError, urllib.error.URLError) as error:
                requests += 1
                observations["legal"] = {"path": legal_path, **safe_transport_failure(error)}
            evidence["logical_http_requests"] = requests
            evidence["response_bytes"] = total_bytes
            write_checkpoint(output_path, evidence)

        redirects = [
            item.get("redirect_host") for item in observations.values() if item.get("redirect_host")
        ]
        robots_denied = observations.get("robots", {}).get("root_allowed_for_review_agent") is False
        transport_failed = any(
            item.get("outcome") == "TRANSPORT_FAILURE" for item in observations.values()
        )
        foreign_redirect = any(target != host for target in redirects)
        if robots_denied:
            recommendation = "REJECT"
        elif foreign_redirect:
            recommendation = "REQUIRES_SUCCESSOR_HOST_REVIEW"
        elif transport_failed:
            recommendation = "REQUIRES_FURTHER_HUMAN_REVIEW"
        else:
            recommendation = "REQUIRES_FURTHER_HUMAN_REVIEW"
        decisions.append(
            {
                "slot": row["slot"],
                "public_business_name": row["company_name"],
                "candidate_hostname": host,
                "mapping_immutable": True,
                "prior_a09_state_inherited": False,
                "observations": observations,
                "automated_disposition": "REJECTED" if robots_denied else "REQUIRES_HUMAN_REVIEW",
                "human_review_recommendation": recommendation,
                "approval_for_public_research": False,
            }
        )
        write_checkpoint(output_path, evidence)

    evidence["state"] = "READY_FOR_REPLACEMENT_SAMPLE_EXACT_HOST_A09_HUMAN_DECISION"
    write_checkpoint(output_path, evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument("--ordered-package", type=Path, required=True)
    parser.add_argument("--ordered-frame-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        args.authorization,
        args.configuration,
        args.ordered_package,
        args.ordered_frame_evidence,
        args.output,
    )
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "decisions"}, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
