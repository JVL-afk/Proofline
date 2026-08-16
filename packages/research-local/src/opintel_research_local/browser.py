"""Credential-free subprocess boundary for optional Playwright fallback."""

from __future__ import annotations

import base64
import json
import os
import subprocess
from collections.abc import Sequence

from opintel_m0.ports import Clock
from opintel_research.domain import BrowserFallbackUnavailable, FetchedDocument


class DisabledBrowserFallback:
    def render(self, url: str, permitted_host: str) -> FetchedDocument:
        del url, permitted_host
        raise BrowserFallbackUnavailable()


class IsolatedBrowserFallback:
    def __init__(self, command: Sequence[str], clock: Clock, timeout_seconds: float = 20.0) -> None:
        self._command = tuple(command)
        self._clock = clock
        self._timeout = timeout_seconds

    def render(self, url: str, permitted_host: str) -> FetchedDocument:
        safe_environment = {
            key: os.environ[key]
            for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
            if key in os.environ
        }
        job = json.dumps(
            {
                "version": 1,
                "url": url,
                "permitted_host": permitted_host,
                "timeout_seconds": self._timeout,
                "max_bytes": 512_000,
            }
        )
        try:
            result = subprocess.run(
                self._command,
                input=job,
                capture_output=True,
                text=True,
                timeout=self._timeout + 5,
                check=False,
                env=safe_environment,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise BrowserFallbackUnavailable() from error
        if result.returncode != 0:
            raise BrowserFallbackUnavailable()
        try:
            payload = json.loads(result.stdout)
            content = base64.b64decode(payload["content_base64"], validate=True)
            final_url = str(payload["final_url"])
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise BrowserFallbackUnavailable() from error
        if len(content) > 512_000:
            raise BrowserFallbackUnavailable()
        return FetchedDocument(
            source_url=url,
            canonical_url=url,
            final_url=final_url,
            status_code=200,
            headers=(("content-type", "text/html; charset=utf-8"),),
            content=content,
            content_type="text/html",
            charset="utf-8",
            captured_at=self._clock.now(),
        )
