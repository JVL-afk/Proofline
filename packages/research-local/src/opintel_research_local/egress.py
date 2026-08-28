"""Private controlled-egress client and exact-host gateway runtime."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from opintel_research.domain import FetchError, RawHttpResponse, TransientFetchError, ValidatedUrl
from opintel_research.ports import HttpTransport
from opintel_research.url_policy import PublicUrlPolicy, SocketResolver, normalize_public_url

from opintel_research_local.http import StdlibPinnedTransport


class ControlledEgressTransport:
    """Delegates a validated GET to the private gateway; it never opens a public socket."""

    def __init__(
        self,
        gateway_url: str,
        policy_revision: str | Callable[[], str],
        capability_provider: Callable[[], dict[str, object]] | None = None,
    ) -> None:
        if not gateway_url.startswith("http://"):
            raise ValueError("controlled egress gateway must be a private HTTP endpoint")
        if not policy_revision:
            raise ValueError("controlled egress policy revision is required")
        self._url = gateway_url.rstrip("/") + "/v1/fetch"
        self._readiness_url = gateway_url.rstrip("/") + "/v1/readiness"
        self._revision = policy_revision
        self._capability_provider = capability_provider

    def _authority_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "policy_revision": (self._revision() if callable(self._revision) else self._revision)
        }
        if self._capability_provider is not None:
            payload["capability"] = self._capability_provider()
        return payload

    def await_ready(
        self,
        *,
        timeout_seconds: float,
        poll_seconds: float = 0.5,
    ) -> None:
        """Wait for the private gateway to acknowledge the exact current capability."""
        if timeout_seconds <= 0 or poll_seconds <= 0:
            raise ValueError("controlled egress readiness bounds must be positive")
        deadline = time.monotonic() + timeout_seconds
        payload = json.dumps(
            self._authority_payload(), sort_keys=True, separators=(",", ":")
        ).encode()
        while True:
            request = Request(
                self._readiness_url,
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
            )
            try:
                with urlopen(request, timeout=min(2.0, timeout_seconds)) as response:
                    if response.status == 204:
                        return
            except HTTPError as error:
                if error.code in {400, 403}:
                    raise FetchError(
                        "controlled_egress_not_authorized",
                        "controlled egress readiness denied exact authority",
                    ) from error
            except (URLError, TimeoutError, OSError, ValueError):
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FetchError(
                    "controlled_egress_not_ready",
                    "controlled egress did not become ready within the bounded interval",
                )
            time.sleep(min(poll_seconds, remaining))

    def request(
        self, target: ValidatedUrl, timeout_seconds: float, max_bytes: int
    ) -> RawHttpResponse:
        request_value = self._authority_payload()
        request_value.update(
            {
                "url": target.normalized_url,
                "max_bytes": max_bytes,
                "timeout_seconds": timeout_seconds,
            }
        )
        payload = json.dumps(
            request_value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        request = Request(
            self._url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
        )
        try:
            with urlopen(request, timeout=timeout_seconds + 1) as response:
                value = json.loads(response.read(max_bytes + 16384))
        except HTTPError as error:
            if error.code in {400, 403}:
                raise FetchError(
                    "controlled_egress_denied", "controlled egress denied request"
                ) from error
            raise TransientFetchError("controlled egress request failed") from error
        except (URLError, TimeoutError, OSError, ValueError) as error:
            raise TransientFetchError("controlled egress request failed") from error
        return RawHttpResponse(
            status_code=int(value["status_code"]),
            headers=tuple((str(k), str(v)) for k, v in value["headers"]),
            body=base64.b64decode(value["body_b64"], validate=True),
        )


def build_gateway_handler(
    allowed_hosts: frozenset[str],
    policy_revision: str,
    transport: HttpTransport | None = None,
    policy: PublicUrlPolicy | None = None,
    policy_provider: Callable[[], tuple[frozenset[str], str]] | None = None,
    capability_provider: Callable[[], dict[str, object]] | None = None,
) -> type[BaseHTTPRequestHandler]:
    if policy_provider is None and (not allowed_hosts or not policy_revision):
        raise ValueError("gateway requires a non-empty exact-host policy revision")
    gateway_transport = transport or StdlibPinnedTransport()
    gateway_policy = policy or PublicUrlPolicy(SocketResolver())

    class Handler(BaseHTTPRequestHandler):
        server_version = "M67ControlledEgress/1"

        def do_POST(self) -> None:
            if self.path not in {"/v1/fetch", "/v1/readiness"}:
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 8192:
                    raise ValueError("invalid request size")
                request_value = json.loads(self.rfile.read(length))
                current_hosts, current_revision = (
                    policy_provider()
                    if policy_provider is not None
                    else (allowed_hosts, policy_revision)
                )
                if request_value.get("policy_revision") != current_revision:
                    raise PermissionError("policy revision mismatch")
                if capability_provider is not None:
                    current_capability = capability_provider()
                    if request_value.get("capability") != current_capability:
                        raise PermissionError("exact egress capability mismatch")
                if self.path == "/v1/readiness":
                    self.send_response(204)
                    self.end_headers()
                    return
                normalized = normalize_public_url(str(request_value["url"]))
                parsed_host = urlsplit(normalized).hostname
                if parsed_host is None:
                    raise ValueError("URL host is required")
                host = gateway_policy.validate(normalized, parsed_host).host
                if host not in current_hosts:
                    raise PermissionError("host is not authorized")
                max_bytes = min(int(request_value["max_bytes"]), 524288)
                timeout = min(float(request_value["timeout_seconds"]), 10.0)
                target = gateway_policy.validate(normalized, host)
                if (
                    capability_provider is not None
                    and request_value.get("capability") != capability_provider()
                ):
                    raise PermissionError("exact egress capability changed before transport")
                raw = gateway_transport.request(target, timeout, max_bytes)
                encoded = json.dumps(
                    {
                        "status_code": raw.status_code,
                        "headers": raw.headers,
                        "body_b64": base64.b64encode(raw.body).decode("ascii"),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
                logging.info(
                    json.dumps(
                        {
                            "event": "controlled_egress.fetch",
                            "host_sha256": hashlib.sha256(host.encode()).hexdigest(),
                            "policy_revision": current_revision,
                            "status_code": raw.status_code,
                        },
                        sort_keys=True,
                    )
                )
            except PermissionError:
                self.send_error(403)
            except (KeyError, TypeError, ValueError):
                self.send_error(400)
            except Exception:
                # Runtime release lookup and transport failures are content-free and fail closed.
                self.send_error(403)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    return Handler


def run_gateway(
    allowed_hosts: frozenset[str],
    policy_revision: str,
    host: str = "0.0.0.0",
    port: int = 8080,
    server_factory: Callable[..., ThreadingHTTPServer] = ThreadingHTTPServer,
    policy_provider: Callable[[], tuple[frozenset[str], str]] | None = None,
    capability_provider: Callable[[], dict[str, object]] | None = None,
) -> None:
    server_factory(
        (host, port),
        build_gateway_handler(
            allowed_hosts,
            policy_revision,
            policy_provider=policy_provider,
            capability_provider=capability_provider,
        ),
    ).serve_forever()


__all__ = ["ControlledEgressTransport", "build_gateway_handler", "run_gateway"]
