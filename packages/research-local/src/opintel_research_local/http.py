"""Pinned-address HTTP transport and bounded safe-fetch adapter."""

from __future__ import annotations

import codecs
import http.client
import socket
import ssl
import zlib
from email.message import Message
from urllib.parse import urljoin

from opintel_m0.ports import Clock
from opintel_research.domain import (
    CrawlPolicy,
    FetchedDocument,
    FetchError,
    FetchTimeoutError,
    OversizedResponseError,
    RawHttpResponse,
    TransientFetchError,
    UnsupportedContentError,
    ValidatedUrl,
)
from opintel_research.ports import HttpTransport
from opintel_research.url_policy import PublicUrlPolicy, normalize_public_url

_REDIRECTS = {301, 302, 303, 307, 308}
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
_ALLOWED_TYPES = {"text/html", "application/xhtml+xml", "text/plain"}
_SAFE_HEADERS = {
    "content-type",
    "content-length",
    "content-encoding",
    "etag",
    "last-modified",
    "server",
    "x-powered-by",
    "location",
}


class StdlibPinnedTransport:
    """Connects to a validated IP while preserving TLS SNI/hostname validation."""

    def request(
        self, target: ValidatedUrl, timeout_seconds: float, max_bytes: int
    ) -> RawHttpResponse:
        last_error: Exception | None = None
        for address in target.addresses:
            connection: socket.socket | None = None
            try:
                connection = socket.create_connection((address, target.port), timeout_seconds)
                connection.settimeout(timeout_seconds)
                if target.scheme == "https":
                    connection = ssl.create_default_context().wrap_socket(
                        connection, server_hostname=target.host
                    )
                request = (
                    f"GET {target.request_target} HTTP/1.1\r\n"
                    f"Host: {target.host}\r\n"
                    "User-Agent: OpportunityIntelligenceResearch/1.0\r\n"
                    "Accept: text/html,application/xhtml+xml,text/plain;q=0.8\r\n"
                    "Accept-Encoding: gzip, deflate\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("ascii")
                connection.sendall(request)
                response = http.client.HTTPResponse(connection)
                response.begin()
                declared = response.getheader("Content-Length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise OversizedResponseError()
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise OversizedResponseError()
                headers = tuple(
                    (name.lower(), value)
                    for name, value in response.getheaders()
                    if name.lower() in _SAFE_HEADERS
                )
                return RawHttpResponse(response.status, headers, body)
            except TimeoutError as error:
                raise FetchTimeoutError() from error
            except OversizedResponseError:
                raise
            except (OSError, ssl.SSLError, http.client.HTTPException) as error:
                last_error = error
            finally:
                if connection is not None:
                    connection.close()
        raise TransientFetchError() from last_error


class SafeHttpFetcher:
    def __init__(
        self,
        url_policy: PublicUrlPolicy,
        transport: HttpTransport,
        clock: Clock,
    ) -> None:
        self._policy = url_policy
        self._transport = transport
        self._clock = clock

    def fetch(
        self,
        url: str,
        permitted_host: str,
        policy: CrawlPolicy,
        attempt_number: int,
    ) -> FetchedDocument:
        del attempt_number
        canonical = normalize_public_url(url)
        current = canonical
        for redirect_count in range(policy.max_redirects + 1):
            validated = self._policy.validate(current, permitted_host)
            raw = self._transport.request(
                validated,
                policy.request_timeout_seconds,
                policy.max_compressed_bytes,
            )
            headers = self._headers(raw.headers)
            if raw.status_code in _REDIRECTS:
                location = headers.get("location")
                if not location or redirect_count >= policy.max_redirects:
                    raise FetchError("invalid or excessive redirect")
                current = urljoin(current, location)
                continue
            if raw.status_code in _RETRYABLE_STATUS:
                raise TransientFetchError()
            if not 200 <= raw.status_code < 300:
                raise FetchError("non-success HTTP response")
            content_type, charset = self._content_type(headers.get("content-type", ""))
            if content_type not in _ALLOWED_TYPES:
                raise UnsupportedContentError()
            body = self._decode(
                raw.body, headers.get("content-encoding", ""), policy.max_response_bytes
            )
            return FetchedDocument(
                source_url=url,
                canonical_url=canonical,
                final_url=normalize_public_url(current),
                status_code=raw.status_code,
                headers=raw.headers,
                content=body,
                content_type=content_type,
                charset=charset,
                captured_at=self._clock.now(),
            )
        raise FetchError("redirect limit exceeded")

    @staticmethod
    def _headers(values: tuple[tuple[str, str], ...]) -> dict[str, str]:
        return {name.lower(): value for name, value in values}

    @staticmethod
    def _content_type(value: str) -> tuple[str, str]:
        message = Message()
        message["content-type"] = value or "application/octet-stream"
        content_type = message.get_content_type().lower()
        charset = message.get_content_charset() or "utf-8"
        try:
            codecs.lookup(charset)
        except LookupError as error:
            raise UnsupportedContentError("unsupported character encoding") from error
        return content_type, charset.lower()

    @staticmethod
    def _decode(body: bytes, encoding: str, limit: int) -> bytes:
        normalized = encoding.strip().lower()
        if not normalized or normalized == "identity":
            if len(body) > limit:
                raise OversizedResponseError()
            return body
        if normalized == "gzip":
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        elif normalized == "deflate":
            decoder = zlib.decompressobj()
        else:
            raise UnsupportedContentError("unsupported content encoding")
        try:
            output = decoder.decompress(body, limit + 1)
            if len(output) <= limit:
                output += decoder.flush(limit + 1 - len(output))
        except zlib.error as error:
            raise FetchError("malformed compressed response") from error
        if len(output) > limit or decoder.unconsumed_tail:
            raise OversizedResponseError()
        return output
