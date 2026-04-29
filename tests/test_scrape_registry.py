from __future__ import annotations

from pathlib import Path

import pytest

from msrt.scrape.base import ChapterScraper, FetchError, FetchResult
from msrt.scrape.registry import register, scraper_for_url


def test_scraper_for_url_routes_mangadex_to_skeleton() -> None:
    scraper = scraper_for_url("https://mangadex.org/chapter/12345678-1234-1234-1234-1234567890ab")
    assert scraper.name == "mangadex"


def test_scraper_for_url_explicit_site_overrides_match() -> None:
    """``--site mangadex`` returns the MangaDex scraper even on an URL it
    wouldn't normally claim. v0.2b will use this when the user wants to
    force a specific adapter."""

    scraper = scraper_for_url("https://example.com/manga/foo", site="mangadex")
    assert scraper.name == "mangadex"


def test_scraper_for_url_unsupported_raises_fetch_error() -> None:
    with pytest.raises(FetchError, match="Nessun adapter supporta"):
        scraper_for_url("https://example.com/random/page")


def test_scraper_for_url_unknown_site_raises_fetch_error() -> None:
    with pytest.raises(FetchError, match="non disponibile"):
        scraper_for_url("https://mangadex.org/...", site="not-a-real-adapter")


def test_register_decorator_is_idempotent() -> None:
    """Registering the same class twice must not duplicate it in the
    registry — otherwise the auto-routing logic would call ``matches()``
    twice and could pick a duplicate match unexpectedly."""

    @register
    class Dummy(ChapterScraper):
        name = "dummy-test-once"

        def matches(self, url: str) -> bool:
            return False

        async def fetch(self, url: str, output_dir: Path) -> FetchResult:
            raise NotImplementedError

    @register
    class _DummyAgain(Dummy):
        # Inherits everything; same registration target.
        pass

    # Re-applying @register on the *same* class is a no-op.
    register(Dummy)
    register(Dummy)
    from msrt.scrape.registry import _REGISTRY  # type: ignore[attr-defined]

    occurrences = sum(1 for cls in _REGISTRY if cls is Dummy)
    assert occurrences == 1
