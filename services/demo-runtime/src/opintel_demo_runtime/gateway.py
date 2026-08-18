"""Narrow local HTTP gateway; the capability itself is the only authority sent to core."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from opintel_demo.contracts import CapabilityExchangeRequest, RuntimeEventRequest


class CoreHttpRuntimeGateway:
    def __init__(self, core_origin: str = "http://127.0.0.1:8000") -> None:
        self._core_origin = core_origin.rstrip("/")

    def exchange(self, command: CapabilityExchangeRequest) -> dict[str, object]:
        return self._post(
            "/internal/demo-runtime/capabilities/exchange", command.model_dump(mode="json")
        )

    def event(self, command: RuntimeEventRequest) -> dict[str, object]:
        return self._post("/internal/demo-runtime/events", command.model_dump(mode="json"))

    def _post(self, path: str, body: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self._core_origin}{path}",
            data=json.dumps(body, separators=(",", ":")).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RuntimeError("core runtime gateway request failed") from error
        if not isinstance(payload, dict):
            raise RuntimeError("core runtime gateway returned an invalid body")
        return payload
