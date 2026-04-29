from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from msrt.scrape.adapters.mangadex import MangaDexScraper
from msrt.scrape.base import FetchError


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


@pytest.mark.parametrize(
    "url",
    [
        "https://mangadex.org/chapter/12345678-1234-1234-1234-123456789012",
        "https://www.mangadex.org/title/12345678-1234-1234-1234-123456789012/some-slug",
        "https://mangadex.org/chapter/12345678-1234-1234-1234-123456789012/",
    ],
)
def test_mangadex_matches_known_url_shapes(url: str) -> None:
    assert MangaDexScraper().matches(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://mangadex.org/",
        "https://example.com/chapter/12345678-1234-1234-1234-123456789012",
        "not a url at all",
        "https://mangadex.org/chapter/not-a-uuid",
        # UUID embedded mid-path doesn't count — only /chapter/ or /title/.
        "https://mangadex.org/follows/12345678-1234-1234-1234-123456789012",
        "https://mangadex.org/random/path/12345678-1234-1234-1234-123456789012",
    ],
)
def test_mangadex_does_not_match_unrelated_urls(url: str) -> None:
    assert not MangaDexScraper().matches(url)


def test_mangadex_matches_uppercase_uuid() -> None:
    """Real-world copy/pasted links sometimes carry uppercase UUIDs.
    The regex must be case-insensitive."""

    url = "https://mangadex.org/chapter/12345678-ABCD-1234-1234-1234567890AB"
    assert MangaDexScraper().matches(url)


def test_mangadex_fetch_rejects_invalid_url(tmp_path: Path) -> None:
    scraper = MangaDexScraper()

    with pytest.raises(FetchError, match="non valido"):
        _run(scraper.fetch("https://example.com/wrong", tmp_path))
