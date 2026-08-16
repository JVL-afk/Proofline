"""Minimal, fail-closed Playwright browser subprocess."""

from __future__ import annotations

import base64
import json
import sys
from urllib.parse import urlsplit

from opintel_research.domain import UrlPolicyError, ValidatedUrl
from opintel_research.ports import Resolver
from opintel_research.url_policy import PublicUrlPolicy, SocketResolver, normalize_public_url
from playwright.sync_api import Route, sync_playwright


def _fail(code: str) -> None:
    sys.stderr.write(json.dumps({"error": code}))
    raise SystemExit(2)


def validate_browser_request(
    url: str, permitted_host: str, method: str, resolver: Resolver
) -> ValidatedUrl:
    """Apply the complete browser egress policy before a request can continue."""
    if method not in {"GET", "HEAD"}:
        raise UrlPolicyError("browser method is prohibited")
    return PublicUrlPolicy(resolver).validate(url, permitted_host)


def browser_launch_args(target: ValidatedUrl) -> list[str]:
    """Pin Chromium to a policy-validated address to close the DNS-rebinding window."""
    address = next((value for value in target.addresses if ":" not in value), target.addresses[0])
    return [
        "--disable-background-networking",
        "--disable-sync",
        "--no-first-run",
        f"--host-resolver-rules=MAP {target.host} {address}, EXCLUDE localhost",
    ]


def run() -> None:
    try:
        job = json.loads(sys.stdin.read(16_384))
        if job.get("version") != 1:
            _fail("unsupported_job")
        url = normalize_public_url(str(job["url"]))
        permitted_host = str(job["permitted_host"])
        timeout_ms = min(int(float(job["timeout_seconds"]) * 1000), 30_000)
        max_bytes = min(int(job["max_bytes"]), 1_000_000)
        validated_target = validate_browser_request(url, permitted_host, "GET", SocketResolver())
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, UrlPolicyError):
        _fail("invalid_job")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=browser_launch_args(validated_target),
        )
        context = browser.new_context(
            accept_downloads=False,
            service_workers="block",
            java_script_enabled=True,
        )
        page = context.new_page()

        def route_request(route: Route) -> None:
            request_url = route.request.url
            try:
                normalized = normalize_public_url(request_url)
                if (urlsplit(normalized).hostname or "") != permitted_host:
                    route.abort("blockedbyclient")
                    return
                validate_browser_request(
                    normalized, permitted_host, route.request.method, SocketResolver()
                )
            except UrlPolicyError:
                route.abort("blockedbyclient")
                return
            if route.request.resource_type in {"media", "font", "websocket"}:
                route.abort("blockedbyclient")
                return
            route.continue_()

        page.route("**/*", route_request)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            content = page.content().encode("utf-8")
            if len(content) > max_bytes:
                _fail("rendered_content_too_large")
            final_url = normalize_public_url(page.url)
            if (urlsplit(final_url).hostname or "") != permitted_host:
                _fail("redirect_outside_permit")
            sys.stdout.write(
                json.dumps(
                    {
                        "final_url": final_url,
                        "content_base64": base64.b64encode(content).decode("ascii"),
                    }
                )
            )
        except Exception:
            _fail("browser_navigation_failed")
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    run()
