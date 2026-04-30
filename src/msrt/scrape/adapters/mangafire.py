"""MangaFire best-effort scraper.

MangaFire is intentionally not promoted as an official public adapter:
the site can change DOM and challenge behaviour without notice. The
adapter therefore keeps the contract narrow: observe the normal reader
network response when it exposes page images, otherwise fall back to
scan-only browser capture. It does not bypass login, Turnstile, captcha,
or Cloudflare checks.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from msrt.scrape.base import ChapterScraper, FetchedPage, FetchError, FetchResult
from msrt.scrape.browser_capture import BrowserCaptureEngine, BrowserCaptureEngineProtocol
from msrt.scrape.downloader import (
    DownloadError,
    DownloadJob,
    download_pages,
    find_duplicate_pages,
)
from msrt.scrape.registry import register

_MANGAFIRE_HOSTS = frozenset({"mangafire.to", "www.mangafire.to"})
_READ_PATH_RE = re.compile(
    r"^/read/(?P<slug>[^/]+)(?:/(?P<language>[^/]+))?(?:/chapter-(?P<chapter>[^/]+))?/?$",
    re.IGNORECASE,
)
_PER_HOST_DELAY = 0.2
_READER_RESPONSE_TIMEOUT_MS = 20_000
_MANGAFIRE_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 "
    "Safari/537.36 msrt/0.0"
)


@dataclass(frozen=True)
class MangaFireReaderPages:
    """Image URLs observed from MangaFire's normal reader XHR."""

    image_urls: list[str]
    warnings: list[str] = field(default_factory=list)
    capture_mode: str = "browser-network"


class MangaFireReaderResolverProtocol(Protocol):
    async def resolve(self, url: str) -> MangaFireReaderPages:
        """Resolve ``url`` to ordered page image URLs."""


@register
class MangaFireScraper(ChapterScraper):
    """Best-effort MangaFire adapter.

    The first strategy observes the normal reader XHR that exposes page
    image URLs, then uses the shared downloader. If that fails, the
    adapter falls back to conservative browser screenshots.
    """

    name = "mangafire"

    def __init__(
        self,
        *,
        capture_engine: BrowserCaptureEngineProtocol | None = None,
        reader_resolver: MangaFireReaderResolverProtocol | None = None,
    ) -> None:
        self._capture_engine = capture_engine or BrowserCaptureEngine()
        self._reader_resolver = reader_resolver or MangaFireReaderResolver()

    def matches(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        host = (parsed.netloc or "").lower()
        return host in _MANGAFIRE_HOSTS and bool(_READ_PATH_RE.match(parsed.path))

    async def fetch(self, url: str, output_dir: Path) -> FetchResult:
        metadata = _metadata_from_url(url)
        if metadata is None:
            raise FetchError(
                f"URL MangaFire non valido: {url!r}. Atteso "
                "https://mangafire.to/read/<slug>/<lang>/chapter-<N>."
            )

        network_warning: str | None = None
        try:
            resolved = await self._reader_resolver.resolve(url)
            jobs = [
                DownloadJob(index=index, url=image_url, headers={"Referer": url})
                for index, image_url in enumerate(resolved.image_urls, start=1)
            ]
            files = await download_pages(
                jobs,
                output_dir=output_dir,
                concurrency=3,
                min_delay_per_host=_PER_HOST_DELAY,
                user_agent=_MANGAFIRE_BROWSER_UA,
            )
        except (FetchError, DownloadError) as exc:
            network_warning = f"Reader-network MangaFire fallito ({exc}); uso browser-capture."
        else:
            warnings = [*resolved.warnings, *find_duplicate_pages(files)]
            pages = [
                FetchedPage(
                    index=file.index,
                    url=file.url,
                    local_path=file.local_path,
                    sha256=file.sha256,
                    content_type=file.content_type,
                    size_bytes=file.size_bytes,
                )
                for file in files
            ]
            if not pages:
                raise FetchError("MangaFire reader-network non ha prodotto pagine.")
            return FetchResult(
                series=metadata.series,
                chapter_number=metadata.chapter_number,
                chapter_title=None,
                source_url=url,
                strategy="mangafire-reader-network",
                pages=pages,
                output_dir=output_dir,
                warnings=warnings,
                capture_mode=resolved.capture_mode,
            )

        try:
            capture = await self._capture_engine.capture(url, output_dir)
        except FetchError as exc:
            if network_warning:
                raise FetchError(f"{network_warning} Browser-capture fallito: {exc}") from exc
            raise
        except Exception as exc:
            raise FetchError(f"Browser capture MangaFire fallito: {exc}") from exc

        pages = [
            FetchedPage(
                index=page.index,
                url=page.url,
                local_path=page.local_path,
                sha256=page.sha256,
                content_type="image/png" if page.local_path.suffix.lower() == ".png" else None,
                size_bytes=page.size_bytes,
            )
            for page in capture.pages
        ]
        if not pages:
            raise FetchError("MangaFire browser capture non ha prodotto pagine.")

        return FetchResult(
            series=metadata.series,
            chapter_number=metadata.chapter_number,
            chapter_title=None,
            source_url=url,
            strategy="mangafire-browser-capture",
            pages=pages,
            output_dir=output_dir,
            warnings=([network_warning] if network_warning else []) + list(capture.warnings),
            capture_mode=capture.capture_mode,
            viewport={
                "width": capture.viewport_width,
                "height": capture.viewport_height,
            },
            device_scale_factor=capture.device_scale_factor,
            manual_intervention=capture.manual_intervention,
        )


class MangaFireReaderResolver:
    """Resolve page image URLs from MangaFire's reader network response.

    MangaFire computes the ``vrf`` query server-side/client-side inside
    its own reader JavaScript. We don't reimplement that token generation
    or forge requests. Instead, Playwright opens the chapter like a normal
    browser and we wait for the public ``/ajax/read/chapter/<id>``
    response that the reader itself issues.
    """

    def __init__(self, *, headless: bool = True) -> None:
        self._headless = headless

    async def resolve(self, url: str) -> MangaFireReaderPages:
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - optional extra
            raise FetchError(
                "Playwright non è installato. Esegui `uv sync --all-extras` "
                "e `uv run playwright install chromium` per usare MangaFire."
            ) from exc

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self._headless)
            context = await browser.new_context(
                viewport={"width": 1600, "height": 1200},
                user_agent=_MANGAFIRE_BROWSER_UA,
            )
            page = await context.new_page()
            loop = asyncio.get_running_loop()
            payload: asyncio.Future[str] = loop.create_future()

            async def capture_reader_response(response: Any) -> None:
                if payload.done():
                    return
                if "/ajax/read/chapter/" not in response.url or response.status != 200:
                    return
                try:
                    payload.set_result(await response.text())
                except Exception as exc:  # pragma: no cover - browser race
                    payload.set_exception(
                        FetchError(f"MangaFire reader response non leggibile: {exc}")
                    )

            page.on(
                "response",
                lambda response: asyncio.create_task(capture_reader_response(response)),
            )
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                text = await asyncio.wait_for(payload, timeout=_READER_RESPONSE_TIMEOUT_MS / 1000)
            except (TimeoutError, PlaywrightTimeoutError) as exc:
                raise FetchError(
                    "MangaFire non ha emesso la risposta reader con gli URL pagina "
                    f"entro {_READER_RESPONSE_TIMEOUT_MS // 1000}s."
                ) from exc
            finally:
                await context.close()
                await browser.close()

        return MangaFireReaderPages(image_urls=_image_urls_from_reader_payload(text))


class _MangaFireMetadata:
    def __init__(self, *, series: str, chapter_number: str) -> None:
        self.series = series
        self.chapter_number = chapter_number


def _metadata_from_url(url: str) -> _MangaFireMetadata | None:
    parsed = urlparse(url)
    match = _READ_PATH_RE.match(parsed.path)
    if not match:
        return None
    raw_slug = match.group("slug")
    chapter = match.group("chapter") or "?"
    series_slug = raw_slug.split(".", 1)[0]
    series = _title_from_slug(series_slug)
    chapter_number = chapter.strip() or "?"
    return _MangaFireMetadata(series=series, chapter_number=chapter_number)


def _title_from_slug(slug: str) -> str:
    words = [part for part in re.split(r"[-_\s]+", slug) if part]
    if not words:
        return "Untitled Series"
    return " ".join(word.capitalize() for word in words)


def _image_urls_from_reader_payload(payload: str) -> list[str]:
    try:
        data = json.loads(payload)
    except ValueError as exc:
        raise FetchError("MangaFire reader ha risposto JSON non valido.") from exc
    if not isinstance(data, dict) or data.get("status") != 200:
        raise FetchError("MangaFire reader ha risposto con status non valido.")
    result = data.get("result")
    if not isinstance(result, dict):
        raise FetchError("MangaFire reader payload senza result oggetto.")
    images = result.get("images")
    if not isinstance(images, list) or not images:
        raise FetchError("MangaFire reader payload senza immagini.")

    indexed_urls: list[tuple[int, str]] = []
    for fallback_index, item in enumerate(images, start=1):
        parsed = _reader_image_item(item, fallback_index)
        if parsed is not None:
            indexed_urls.append(parsed)
    if not indexed_urls:
        raise FetchError("MangaFire reader non ha esposto URL immagine validi.")
    indexed_urls.sort(key=lambda pair: pair[0])
    return [url for _index, url in indexed_urls]


def _reader_image_item(item: object, fallback_index: int) -> tuple[int, str] | None:
    if isinstance(item, str):
        return fallback_index, item
    if not isinstance(item, list) or not item:
        return None
    first = item[0]
    if not isinstance(first, str) or not first.startswith(("http://", "https://")):
        return None
    page_number = _coerce_positive_int(item[1] if len(item) > 1 else None) or fallback_index
    return page_number, first


def _coerce_positive_int(value: object) -> int | None:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        number = int(value)
        return number if number > 0 else None
    return None
