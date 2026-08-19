"""Small HTTPS JSON transport that never includes response bodies or headers in errors."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping

from opintel_qualification_live.contracts import HttpResponse


class _AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: frozenset[str]) -> None:
        super().__init__()
        self._allowed_hosts = allowed_hosts

    def redirect_request(  # type: ignore[no-untyped-def]
        self, req, fp, code, msg, headers, newurl
    ):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname not in self._allowed_hosts:
            raise RuntimeError("provider_redirect_outside_egress_allowlist")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibJsonTransport:
    def __init__(
        self,
        max_response_bytes: int = 1_048_576,
        *,
        allowed_hosts: frozenset[str] | None = None,
    ) -> None:
        self._max_response_bytes = max_response_bytes
        self._allowed_hosts = allowed_hosts
        handlers: list[urllib.request.BaseHandler] = []
        if allowed_hosts is not None:
            if not allowed_hosts:
                raise ValueError("provider egress allowlist cannot be empty")
            handlers.append(_AllowlistRedirectHandler(allowed_hosts))
        self._opener = urllib.request.build_opener(*handlers)

    def post(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> HttpResponse:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https":
            raise RuntimeError("provider_transport_requires_https")
        if self._allowed_hosts is not None and parsed.hostname not in self._allowed_hosts:
            raise RuntimeError("provider_host_outside_egress_allowlist")
        body = json.dumps(payload, separators=(",", ":")).encode()
        request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
        started = time.perf_counter()
        try:
            with self._opener.open(request, timeout=timeout_seconds) as response:
                data = response.read(self._max_response_bytes + 1)
                if len(data) > self._max_response_bytes:
                    raise RuntimeError("provider_response_too_large")
                return HttpResponse(
                    response.status,
                    {key.lower(): value for key, value in response.headers.items()},
                    data,
                    round((time.perf_counter() - started) * 1000),
                )
        except urllib.error.HTTPError as exc:
            data = exc.read(self._max_response_bytes + 1)
            if len(data) > self._max_response_bytes:
                data = b""
            return HttpResponse(
                exc.code,
                {key.lower(): value for key, value in exc.headers.items()},
                data,
                round((time.perf_counter() - started) * 1000),
            )
        except TimeoutError as exc:
            raise TimeoutError("provider_timeout") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("provider_transport_failure") from exc
