"""Deterministic, pure sitemap parsing for PHASE1_M1_V2_BOUNDED_SITE_CRAWL.

No I/O, no clock, no randomness. Handles ``urlset`` and ``sitemapindex`` (one
level of recursion is the caller's responsibility), plus gzip-compressed bodies.
Defensive against XML entity-expansion attacks: any DOCTYPE / ENTITY declaration
is rejected outright and the body size is bounded.
"""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass
from enum import StrEnum
from xml.etree import ElementTree

_GZIP_MAGIC = b"\x1f\x8b"
_MAX_SITEMAP_BYTES = 12_000_000
_DOCTYPE_OR_ENTITY = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)", re.IGNORECASE)
_LOC_TAG = "loc"


class SitemapKind(StrEnum):
    URLSET = "urlset"
    SITEMAPINDEX = "sitemapindex"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SitemapParseResult:
    kind: SitemapKind
    page_locs: tuple[str, ...]
    child_sitemap_locs: tuple[str, ...]
    total_loc_elements: int
    truncated: bool
    malformed: bool
    diagnostic: str


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower() if "}" in tag else tag.lower()


def _maybe_gunzip(body: bytes, content_encoding: str | None) -> bytes:
    encoding = (content_encoding or "").lower()
    if "gzip" in encoding or body[:2] == _GZIP_MAGIC:
        try:
            return gzip.decompress(body)
        except (OSError, EOFError, gzip.BadGzipFile):
            return body
    return body


def parse_sitemap(
    body: bytes, content_encoding: str | None, max_entries: int
) -> SitemapParseResult:
    if not body:
        return SitemapParseResult(
            SitemapKind.UNKNOWN, (), (), 0, False, True, "empty body"
        )
    decoded = _maybe_gunzip(body, content_encoding)
    if len(decoded) > _MAX_SITEMAP_BYTES:
        decoded = decoded[:_MAX_SITEMAP_BYTES]
    if _DOCTYPE_OR_ENTITY.search(decoded):
        return SitemapParseResult(
            SitemapKind.UNKNOWN, (), (), 0, False, True, "doctype or entity declaration rejected"
        )
    try:
        root = ElementTree.fromstring(decoded)
    except (ElementTree.ParseError, ValueError, TypeError):
        return SitemapParseResult(
            SitemapKind.UNKNOWN, (), (), 0, False, True, "xml parse error"
        )

    root_name = _local_name(root.tag)
    if root_name == "sitemapindex":
        kind = SitemapKind.SITEMAPINDEX
        wanted_parent = "sitemap"
    elif root_name == "urlset":
        kind = SitemapKind.URLSET
        wanted_parent = "url"
    else:
        kind = SitemapKind.UNKNOWN
        wanted_parent = ""

    locs: list[str] = []
    for entry in root:
        if wanted_parent and _local_name(entry.tag) != wanted_parent:
            continue
        for child in entry:
            if _local_name(child.tag) == _LOC_TAG and child.text and child.text.strip():
                locs.append(child.text.strip())
                break
    if not wanted_parent:
        # Fallback: collect any <loc> anywhere.
        for element in root.iter():
            if _local_name(element.tag) == _LOC_TAG and element.text and element.text.strip():
                locs.append(element.text.strip())

    total = len(locs)
    limit = max(0, max_entries)
    truncated = total > limit
    kept = tuple(locs[:limit])
    if kind is SitemapKind.SITEMAPINDEX:
        return SitemapParseResult(kind, (), kept, total, truncated, False, "ok")
    return SitemapParseResult(kind, kept, (), total, truncated, False, "ok")
