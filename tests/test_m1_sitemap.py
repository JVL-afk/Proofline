"""Pure-unit tests for the PHASE1_M1_V2_BOUNDED_SITE_CRAWL sitemap parser."""

from __future__ import annotations

import gzip

from opintel_research.sitemap import SitemapKind, parse_sitemap

_NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'


def _urlset(paths: list[str]) -> bytes:
    body = "".join(f"<url><loc>https://x.example{p}</loc></url>" for p in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset {_NS}>{body}</urlset>'.encode()


def test_parses_urlset_in_document_order() -> None:
    result = parse_sitemap(_urlset(["/a", "/b", "/c"]), None, 2000)
    assert result.kind is SitemapKind.URLSET
    assert result.page_locs == (
        "https://x.example/a",
        "https://x.example/b",
        "https://x.example/c",
    )
    assert not result.truncated


def test_truncates_to_max_entries_in_document_order() -> None:
    result = parse_sitemap(_urlset([f"/p{i}" for i in range(500)]), None, 100)
    assert len(result.page_locs) == 100
    assert result.total_loc_elements == 500
    assert result.truncated is True
    assert result.page_locs[0] == "https://x.example/p0"


def test_parses_sitemapindex_children_only() -> None:
    body = (
        f'<sitemapindex {_NS}>'
        "<sitemap><loc>https://x.example/sitemap-1.xml</loc></sitemap>"
        "<sitemap><loc>https://x.example/sitemap-2.xml</loc></sitemap>"
        "</sitemapindex>"
    ).encode()
    result = parse_sitemap(body, None, 2000)
    assert result.kind is SitemapKind.SITEMAPINDEX
    assert result.child_sitemap_locs == (
        "https://x.example/sitemap-1.xml",
        "https://x.example/sitemap-2.xml",
    )
    assert result.page_locs == ()


def test_gzip_body_by_magic_bytes() -> None:
    result = parse_sitemap(gzip.compress(_urlset(["/a", "/b"])), None, 2000)
    assert result.page_locs == ("https://x.example/a", "https://x.example/b")


def test_gzip_body_by_content_encoding_header() -> None:
    result = parse_sitemap(gzip.compress(_urlset(["/only"])), "gzip", 2000)
    assert result.page_locs == ("https://x.example/only",)


def test_rejects_doctype_entity_expansion() -> None:
    evil = (
        b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]>'
        b'<urlset><url><loc>https://x.example/a</loc></url></urlset>'
    )
    result = parse_sitemap(evil, None, 2000)
    assert result.malformed is True
    assert result.page_locs == ()


def test_malformed_xml_is_flagged_not_raised() -> None:
    result = parse_sitemap(b"<urlset><url><loc>https://x.example/a", None, 2000)
    assert result.malformed is True


def test_empty_body() -> None:
    result = parse_sitemap(b"", None, 2000)
    assert result.malformed is True


def test_deterministic_repeat() -> None:
    body = _urlset(["/a", "/b", "/c", "/d"])
    assert parse_sitemap(body, None, 3) == parse_sitemap(body, None, 3)
