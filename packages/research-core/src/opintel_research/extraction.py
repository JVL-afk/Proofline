"""Pure observational HTML extraction. No business-value interpretation occurs here."""

from __future__ import annotations

import json
import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin
from uuid import UUID

from opintel_research.domain import ExtractedMaterial, MalformedContentError, PageSnapshot

_WHITESPACE = re.compile(r"\s+")
_EMAIL = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w-])", re.I)
_PHONE = re.compile(r"(?<!\d)(\+?\d[\d ().-]{6,}\d)(?!\d)")
_PROMPT_MARKERS = (
    "ignore previous instructions",
    "system prompt",
    "assistant:",
    "developer message",
    "execute this command",
)


def _clean(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip()


class _Parser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.metadata: list[tuple[str, str]] = []
        self.headings: list[tuple[int, str, str]] = []
        self.links: list[tuple[str, str, str]] = []
        self.forms: list[tuple[str, str, str]] = []
        self.buttons: list[tuple[str, str]] = []
        self.structured_data: list[str] = []
        self.technology_signals: list[tuple[str, str]] = []
        self._ignored = 0
        self._title = False
        self._heading: tuple[int, list[str]] | None = None
        self._link: tuple[str, str, list[str]] | None = None
        self._button: tuple[str, list[str]] | None = None
        self._json_ld: list[str] | None = None

    def handle_starttag(self, tag: str, attrs_raw: list[tuple[str, str | None]]) -> None:
        attrs = {name.lower(): value or "" for name, value in attrs_raw}
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "template", "svg"}:
            if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
                self._json_ld = []
            else:
                self._ignored += 1
            if tag == "script" and attrs.get("src"):
                source = attrs["src"].lower()
                for signature in ("wp-content", "shopify", "wixstatic", "squarespace"):
                    if signature in source:
                        self.technology_signals.append((signature, "script-src"))
            return
        if tag == "title":
            self._title = True
        if len(tag) == 2 and tag.startswith("h") and tag[1].isdigit():
            self._heading = (int(tag[1]), [])
        if tag == "meta":
            key = attrs.get("name") or attrs.get("property") or attrs.get("http-equiv")
            content = _clean(attrs.get("content", ""))
            if key and content:
                self.metadata.append((_clean(key).lower(), content[:2000]))
            generator = attrs.get("name", "").lower() == "generator"
            if generator and content:
                self.technology_signals.append((content[:200], "meta-generator"))
        if tag == "a" and attrs.get("href"):
            href = urljoin(self.base_url, attrs["href"])
            self._link = (href, attrs.get("rel", ""), [])
        if tag == "form":
            self.forms.append(
                (
                    urljoin(self.base_url, attrs.get("action", "")),
                    attrs.get("method", "get").lower(),
                    attrs.get("id") or attrs.get("name") or "",
                )
            )
        if tag in {"button", "input"}:
            kind = attrs.get("type", "button").lower()
            if tag == "input":
                label = attrs.get("value") or attrs.get("aria-label") or ""
                self.buttons.append((kind, _clean(label)[:500]))
            else:
                self._button = (kind, [])

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "template", "svg"}:
            if tag == "script" and self._json_ld is not None:
                value = "".join(self._json_ld).strip()
                if value:
                    try:
                        normalized = json.dumps(
                            json.loads(value), sort_keys=True, separators=(",", ":")
                        )
                    except (json.JSONDecodeError, TypeError, ValueError):
                        normalized = ""
                    if normalized:
                        self.structured_data.append(normalized[:20_000])
                self._json_ld = None
            elif self._ignored:
                self._ignored -= 1
            return
        if tag == "title":
            self._title = False
        if self._heading is not None and tag == f"h{self._heading[0]}":
            text = _clean(" ".join(self._heading[1]))
            if text:
                self.headings.append((self._heading[0], text, f"heading:{len(self.headings)}"))
            self._heading = None
        if tag == "a" and self._link is not None:
            href, rel, parts = self._link
            self.links.append((href, _clean(" ".join(parts))[:1000], rel))
            self._link = None
        if tag == "button" and self._button is not None:
            kind, parts = self._button
            self.buttons.append((kind, _clean(" ".join(parts))[:500]))
            self._button = None

    def handle_data(self, data: str) -> None:
        if self._json_ld is not None:
            self._json_ld.append(data)
            return
        if self._ignored:
            return
        value = _clean(data)
        if not value:
            return
        self.text_parts.append(value)
        if self._title:
            self.title_parts.append(value)
        if self._heading is not None:
            self._heading[1].append(value)
        if self._link is not None:
            self._link[2].append(value)
        if self._button is not None:
            self._button[1].append(value)


class ObservationalHtmlExtractor:
    name = "observational_html"
    version = "1"

    def extract(
        self, snapshot: PageSnapshot, material_id: UUID, now: datetime
    ) -> ExtractedMaterial:
        try:
            text = snapshot.content.decode(snapshot.charset, errors="replace")
        except LookupError as error:
            raise MalformedContentError("unknown character encoding") from error
        parser = _Parser(snapshot.final_url)
        try:
            parser.feed(text)
            parser.close()
        except (ValueError, AssertionError) as error:
            raise MalformedContentError("HTML parsing failed") from error
        visible = _clean(" ".join(parser.text_parts))[:100_000]
        contacts: list[tuple[str, str, str]] = []
        for match in _EMAIL.finditer(visible):
            contacts.append(
                ("email", match.group(1), f"visible-text:{match.start()}-{match.end()}")
            )
        for match in _PHONE.finditer(visible):
            contacts.append(
                ("phone", _clean(match.group(1)), f"visible-text:{match.start()}-{match.end()}")
            )
        lower = visible.lower()
        suspected = any(marker in lower for marker in _PROMPT_MARKERS)
        headers = {key.lower(): value for key, value in snapshot.response_headers}
        if headers.get("server"):
            parser.technology_signals.append((headers["server"][:200], "http-server-header"))
        if headers.get("x-powered-by"):
            parser.technology_signals.append((headers["x-powered-by"][:200], "x-powered-by-header"))
        return ExtractedMaterial(
            id=material_id,
            snapshot_id=snapshot.id,
            extractor_name=self.name,
            extractor_version=self.version,
            title=_clean(" ".join(parser.title_parts))[:1000] or None,
            metadata=tuple(parser.metadata[:100]),
            headings=tuple(parser.headings[:200]),
            visible_text=visible,
            links=tuple(parser.links[:1000]),
            forms=tuple(parser.forms[:100]),
            buttons=tuple(parser.buttons[:200]),
            contacts=tuple(contacts[:100]),
            structured_data=tuple(parser.structured_data[:50]),
            technology_signals=tuple(dict.fromkeys(parser.technology_signals)),
            prompt_injection_suspected=suspected,
            created_at=now,
        )
