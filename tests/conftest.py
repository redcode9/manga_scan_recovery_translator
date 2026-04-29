"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_scrape_registry():  # type: ignore[no-untyped-def]
    """Snapshot and restore the global scraper registry around every test.

    Tests that use ``@register`` to introduce dummy ``ChapterScraper``
    subclasses would otherwise leak those entries into later tests,
    affecting the routing behaviour of ``scraper_for_url``. The registry
    is intentionally process-global (so adapters self-register at import
    time) — we make it test-local with a fixture instead.
    """

    from msrt.scrape import registry as reg

    snapshot = list(reg._REGISTRY)
    try:
        yield
    finally:
        reg._REGISTRY[:] = snapshot
