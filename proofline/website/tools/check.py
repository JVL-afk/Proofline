#!/usr/bin/env python3
"""Verify the Proofline website against the content and privacy rules.

Stdlib only. Checks the source tree (default) or a built tree (--dir).

  - no analytics / tracking / advertising SDKs
  - no external scripts or stylesheets
  - no internal project vocabulary or provider names leak into public copy
  - required contact mailto present
  - privacy page exists
  - exact footer postal address present
  - basic SEO metadata present
  - all internal links resolve
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

MAILTO = "mailto:andrew@proofline.business"

ADDRESS_LINES = [
    "Str. Lucian Blaga, nr. 8",
    "Ciugud, Alba 517240",
    "Romania",
]

# Analytics / tracking / advertising vendors and hooks that must never appear.
FORBIDDEN_TRACKING = [
    "google-analytics",
    "googletagmanager",
    "gtag(",
    "ga(",
    "analytics.js",
    "plausible.io",
    "posthog",
    "mixpanel",
    "segment.com",
    "segment.io",
    "hotjar",
    "fathom",
    "matomo",
    "piwik",
    "fbevents",
    "facebook pixel",
    "connect.facebook.net",
    "clarity.ms",
    "amplitude",
    "heap.io",
    "doubleclick",
    "adservice",
    "adsbygoogle",
    "cdn.jsdelivr",
    "unpkg.com",
    "cdnjs",
    "fonts.googleapis",
    "fonts.gstatic",
]

# Internal vocabulary / third parties that must not be exposed publicly.
FORBIDDEN_INTERNAL = [
    "semantic envelope",
    "deterministic validator",
    "canonical reconciler",
    "inference taxonomy",
    "claim manifest",
    "output validator",
    "claude",
    "anthropic",
    "openai",
    "gpt-",
    "hunter.io",
    "lovable",
    "base44",
    "emergent",
    "posthog",
    "cloudflare bot",
    "milestone",
    "adr-",
    "primary_a",
    "project_owner",
]
FORBIDDEN_INTERNAL_RE = [
    re.compile(r"\bM[0-9]\b"),  # M1, M4, M6 ...
    re.compile(r"\bM[0-9]\.[0-9]"),  # M6.10 ...
]

# Overstated-traction words that would need real evidence to use.
FORBIDDEN_CLAIMS_RE = [
    re.compile(r"\b(our|trusted by|join)\s+\d[\d,]*\+?\s+(customers|clients|companies)", re.I),
    re.compile(r"\bfortune\s*500\b", re.I),
    re.compile(r"\bROI\b"),
    re.compile(r"\b\d+%\s+(increase|improvement|more|faster|higher)\b", re.I),
    re.compile(r"\bcase stud(y|ies)\b", re.I),
    re.compile(r"\btestimonial", re.I),
]

HREF_RE = re.compile(r'(?:href|src)="([^"]+)"')
TITLE_RE = re.compile(r"<title>[^<]+</title>", re.I)
DESC_RE = re.compile(r'<meta\s+name="description"\s+content="[^"]+"', re.I)


def fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="src", help="tree to check (src or dist)")
    args = ap.parse_args()

    base = (ROOT / args.dir).resolve()
    if not base.is_dir():
        print(f"error: {base} not found", file=sys.stderr)
        return 1

    html_files = sorted(base.rglob("*.html"))
    all_files = {p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()}
    errors: list[str] = []
    checked = 0

    for path in html_files:
        rel = path.relative_to(base).as_posix()
        raw = path.read_text(encoding="utf-8")
        low = raw.lower()
        checked += 1

        for needle in FORBIDDEN_TRACKING:
            if needle in low:
                fail(errors, f"{rel}: forbidden tracking/CDN token {needle!r}")
        for needle in FORBIDDEN_INTERNAL:
            if needle in low:
                fail(errors, f"{rel}: internal/provider token leaked: {needle!r}")
        for rx in FORBIDDEN_INTERNAL_RE:
            m = rx.search(raw)
            if m:
                fail(errors, f"{rel}: internal milestone-style token {m.group(0)!r}")
        for rx in FORBIDDEN_CLAIMS_RE:
            m = rx.search(raw)
            if m:
                fail(errors, f"{rel}: possible overstated claim {m.group(0)!r}")

        # external resources
        for url in HREF_RE.findall(raw):
            if url.startswith(("http://", "https://")):
                # allowed only in metadata (canonical / og / twitter), never as a
                # loaded script or stylesheet
                context = raw[max(0, raw.find(url) - 120) : raw.find(url)]
                if "<script" in context or 'rel="stylesheet"' in context:
                    fail(errors, f"{rel}: external resource loaded: {url}")
                continue
            if url.startswith(("mailto:", "tel:", "#", "data:")):
                continue
            target = url.split("#", 1)[0].split("?", 1)[0]
            if target in ("", "/"):
                target = "index.html"
            elif target.startswith("/"):
                target = target[1:]
            if target and target not in all_files:
                fail(errors, f"{rel}: broken internal link -> {url} (resolved {target!r})")

        if "<script" in low and "src=" in low:
            for m in re.finditer(r'<script[^>]*\bsrc="([^"]+)"', raw, re.I):
                if m.group(1).startswith(("http://", "https://", "//")):
                    fail(errors, f"{rel}: remote <script> {m.group(1)}")

    index = base / "index.html"
    privacy = base / "privacy.html"

    if not privacy.is_file():
        fail(errors, "privacy.html is missing")

    for path in (index, privacy):
        if not path.is_file():
            fail(errors, f"{path.name} is missing")
            continue
        txt = path.read_text(encoding="utf-8")
        if MAILTO not in txt:
            fail(errors, f"{path.name}: {MAILTO} not found")
        for line in ADDRESS_LINES:
            if line not in txt:
                fail(errors, f"{path.name}: footer/postal line missing: {line!r}")
        if 'lang="en"' not in txt:
            fail(errors, f"{path.name}: <html lang> missing")
        if not TITLE_RE.search(txt):
            fail(errors, f"{path.name}: <title> missing")
        if not DESC_RE.search(txt):
            fail(errors, f"{path.name}: meta description missing")

    if index.is_file():
        itxt = index.read_text(encoding="utf-8")
        for tag in (
            'property="og:title"',
            'property="og:description"',
            'property="og:url"',
            'property="og:image"',
            'rel="canonical"',
        ):
            if tag not in itxt:
                fail(errors, f"index.html: {tag} missing")

    print(f"checked {checked} HTML file(s) under {base}")
    if errors:
        print(f"\nFAIL ({len(errors)} issue(s)):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PASS - no tracking, no external resources, no leaked internals, links resolve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
