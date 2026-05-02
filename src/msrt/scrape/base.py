"""Scraper interfaces and shared dataclasses.

A *scraper* takes a chapter URL and produces a local folder of page images
plus structured metadata (series title, chapter number, page order). It is
the bridge between the URL pipeline (``msrt fetch``, ``msrt run``) and the
already-stable local pipeline (``msrt run-local``): once a scraper has
populated an output dir, downstream code never needs to know whether the
images came from MangaDex, MangaFire, or a manual download.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FetchedPage:
    """A single page that has been downloaded to disk."""

    index: int
    url: str
    local_path: Path
    sha256: str
    content_type: str | None
    size_bytes: int


@dataclass(frozen=True)
class ChapterLink:
    """One chapter URL discovered from a series/reader page."""

    url: str
    chapter_number: str
    title: str | None = None
    series: str | None = None


@dataclass
class FetchResult:
    """Outcome of a scraper.fetch() call.

    The contract is intentionally close to ``msrt.models.Chapter``: enough
    metadata to populate ``run-local`` without further user input. The
    scraper is free to leave ``chapter_title`` ``None`` if the source
    doesn't expose a clean title.
    """

    series: str
    chapter_number: str
    chapter_title: str | None
    source_url: str
    strategy: str
    pages: list[FetchedPage]
    output_dir: Path
    warnings: list[str] = field(default_factory=list)
    capture_mode: str | None = None
    viewport: dict[str, int] | None = None
    device_scale_factor: float | None = None
    manual_intervention: bool = False


class FetchError(RuntimeError):
    """Raised when a scraper cannot fulfil a fetch (bad URL, network, etc.)."""


class ChapterScraper(ABC):
    """Abstract base for site-specific scrapers."""

    #: Stable lowercase identifier used by the CLI ``--site`` flag.
    name: str = ""

    @abstractmethod
    def matches(self, url: str) -> bool:
        """Return ``True`` if this scraper claims responsibility for ``url``."""

    @abstractmethod
    async def fetch(self, url: str, output_dir: Path) -> FetchResult:
        """Download ``url`` into ``output_dir`` and return structured metadata.

        Implementations must be **idempotent on naming**: page files should
        always end up named ``001.png``, ``002.jpg``, etc. so the local
        pipeline can pick them up via natural sort.
        """

    async def list_chapters(self, url: str) -> list[ChapterLink]:
        """Return every chapter URL for the series containing ``url``.

        Site adapters that cannot resolve a series/chapter list should leave
        the default implementation in place.
        """

        raise FetchError(f"Adapter '{self.name}' non supporta --all-chapters.")
