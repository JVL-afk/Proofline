"""A non-network fixture fetcher and deterministic HTML extractor."""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from opintel_m0.contracts import validate_fixture_uri
from opintel_m0.domain import (
    FetchedFixture,
    InvalidFixtureUriError,
    PermanentFixtureFetchError,
    TransientFixtureFetchError,
)
from opintel_m0.ports import Clock

MAX_FIXTURE_BYTES = 256 * 1024


class LocalFixtureFetcher:
    """Fetch controlled files only; this adapter has no HTTP client or socket use."""

    def __init__(self, fixture_root: Path, clock: Clock) -> None:
        self._fixture_root = fixture_root.resolve()
        self._clock = clock

    def fetch(self, fixture_uri: str, attempt_number: int) -> FetchedFixture:
        try:
            validate_fixture_uri(fixture_uri)
        except ValueError as error:
            raise InvalidFixtureUriError(str(error)) from error

        filename = urlsplit(fixture_uri).path.removeprefix("/")
        candidate = (self._fixture_root / filename).resolve()
        if candidate.parent != self._fixture_root:
            raise InvalidFixtureUriError("fixture path escaped the configured root")
        if filename == "transient-once.html" and attempt_number == 1:
            raise TransientFixtureFetchError("controlled transient fixture failure")
        if not candidate.is_file():
            raise PermanentFixtureFetchError("controlled fixture does not exist")

        content = candidate.read_bytes()
        if not content or len(content) > MAX_FIXTURE_BYTES:
            raise PermanentFixtureFetchError("controlled fixture size is invalid")
        content_hash = hashlib.sha256(content).hexdigest()
        return FetchedFixture(
            source_uri=fixture_uri,
            final_uri=fixture_uri,
            content=content,
            mime_type="text/html; charset=utf-8",
            captured_at=self._clock.now(),
            fixture_version=f"sha256:{content_hash}",
        )


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._in_title = False
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "template", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "template", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        normalized = " ".join(data.split())
        if not normalized or self._ignored_depth:
            return
        if self._in_title:
            self.title_parts.append(normalized)
        else:
            self.text_parts.append(normalized)


class FixtureHtmlExtractor:
    name = "controlled_fixture_html"
    version = "1"

    def extract(self, fixture: FetchedFixture) -> tuple[str, str, str]:
        try:
            text = fixture.content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise PermanentFixtureFetchError("fixture is not valid UTF-8") from error
        parser = _TextExtractor()
        parser.feed(text)
        title = " ".join(parser.title_parts).strip()
        excerpt = " ".join(parser.text_parts).strip()[:500]
        if not title or not excerpt:
            raise PermanentFixtureFetchError("fixture lacks required title or visible text")
        return title, excerpt, "html:title+body:visible-text[0:500]"
