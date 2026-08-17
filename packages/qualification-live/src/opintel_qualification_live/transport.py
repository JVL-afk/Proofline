"""Small HTTPS JSON transport that never includes response bodies or headers in errors."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Mapping

from opintel_qualification_live.contracts import HttpResponse


class UrllibJsonTransport:
    def __init__(self, max_response_bytes: int = 1_048_576) -> None:
        self._max_response_bytes = max_response_bytes

    def post(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> HttpResponse:
        if not url.startswith("https://"):
            raise RuntimeError("provider_transport_requires_https")
        body = json.dumps(payload, separators=(",", ":")).encode()
        request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
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
