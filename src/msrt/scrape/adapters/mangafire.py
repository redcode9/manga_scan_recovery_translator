"""MangaFire best-effort scraper.

MangaFire is intentionally not promoted as an official public adapter:
the site can change DOM and challenge behaviour without notice. The
adapter therefore keeps the contract narrow: observe the normal reader
network response when it exposes page images, otherwise fall back to
scan-only browser capture. It does not bypass login, Turnstile, captcha,
or Cloudflare checks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse

from msrt.scrape.base import ChapterLink, ChapterScraper, FetchedPage, FetchError, FetchResult
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


@dataclass(frozen=True)
class MangaFireChapterIndex:
    chapters: list[ChapterLink]


class MangaFireReaderResolverProtocol(Protocol):
    async def resolve(self, url: str) -> MangaFireReaderPages:
        """Resolve ``url`` to ordered page image URLs."""

    async def list_chapters(self, url: str) -> MangaFireChapterIndex:
        """Resolve ``url`` to every chapter URL exposed by the reader."""


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

    async def list_chapters(self, url: str) -> list[ChapterLink]:
        metadata = _metadata_from_url(url)
        if metadata is None:
            raise FetchError(
                f"URL MangaFire non valido: {url!r}. Atteso "
                "https://mangafire.to/read/<slug>/<lang>/chapter-<N>."
            )
        result = await self._reader_resolver.list_chapters(url)
        return [
            ChapterLink(
                url=chapter.url,
                chapter_number=chapter.chapter_number,
                title=chapter.title,
                series=chapter.series or metadata.series,
            )
            for chapter in result.chapters
        ]


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
        text = await self._first_reader_payload(
            url,
            response_path_fragment="/ajax/read/chapter/",
            error_message="MangaFire non ha emesso la risposta reader con gli URL pagina",
        )
        return MangaFireReaderPages(image_urls=_image_urls_from_reader_payload(text))

    async def list_chapters(self, url: str) -> MangaFireChapterIndex:
        text = await self._first_reader_payload(
            url,
            response_path_fragment="/ajax/read/",
            exclude_path_fragment="/ajax/read/chapter/",
            error_message="MangaFire non ha emesso la risposta con la lista capitoli",
        )
        metadata = _metadata_from_url(url)
        series = metadata.series if metadata is not None else None
        chapters = _chapter_links_from_reader_payload(text, base_url=url, series=series)
        return MangaFireChapterIndex(chapters=chapters)

    async def _first_reader_payload(
        self,
        url: str,
        *,
        response_path_fragment: str,
        exclude_path_fragment: str | None = None,
        error_message: str,
    ) -> str:
        """Wait for the first matching reader response and return its body.

        We use ``page.expect_response`` instead of the (older) racy
        ``page.on("response", ...)`` pattern: ``expect_response`` keeps
        the response resource alive on the Chromium side until we've
        actually read the body, so we no longer hit
        *"Network.getResponseBody: No resource with given identifier
        found"* when MangaFire navigates from a "shell" chapter
        (e.g. ``chapter-1``) to its sub-chapter (``chapter-1.1``)
        before our handler had a chance to read the body.
        """

        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - optional extra
            raise FetchError(
                "Playwright non è installato. Esegui `uv sync --all-extras` "
                "e `uv run playwright install chromium` per usare MangaFire."
            ) from exc

        timeout_ms = _READER_RESPONSE_TIMEOUT_MS

        def predicate(response: Any) -> bool:
            if response.status != 200:
                return False
            if response_path_fragment not in response.url:
                return False
            return not (exclude_path_fragment and exclude_path_fragment in response.url)

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self._headless)
            context = await browser.new_context(
                viewport={"width": 1600, "height": 1200},
                user_agent=_MANGAFIRE_BROWSER_UA,
            )
            page = await context.new_page()
            try:
                async with page.expect_response(predicate, timeout=timeout_ms) as info:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                response = await info.value
                try:
                    return await response.text()
                except Exception as exc:  # pragma: no cover - browser race
                    raise FetchError(f"MangaFire reader response non leggibile: {exc}") from exc
            except PlaywrightTimeoutError as exc:
                raise FetchError(f"{error_message} entro {timeout_ms // 1000}s.") from exc
            finally:
                await context.close()
                await browser.close()


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


def _chapter_links_from_reader_payload(
    payload: str,
    *,
    base_url: str,
    series: str | None = None,
) -> list[ChapterLink]:
    try:
        data = json.loads(payload)
    except ValueError as exc:
        raise FetchError("MangaFire chapter list ha risposto JSON non valido.") from exc
    if not isinstance(data, dict) or data.get("status") != 200:
        raise FetchError("MangaFire chapter list ha risposto con status non valido.")
    result = data.get("result")
    if not isinstance(result, dict):
        raise FetchError("MangaFire chapter list payload senza result oggetto.")
    html = result.get("html")
    if not isinstance(html, str) or not html:
        raise FetchError("MangaFire chapter list payload senza HTML capitoli.")

    chapters: dict[str, ChapterLink] = {}
    for anchor in re.findall(r"<a\b[^>]*>", html, flags=re.IGNORECASE):
        href = _html_attr(anchor, "href")
        if href is None:
            continue
        number = _html_attr(anchor, "data-number") or _chapter_number_from_href(href)
        if number is None:
            continue
        title = _html_attr(anchor, "title")
        absolute_url = urljoin(base_url, unescape(href))
        chapters[number] = ChapterLink(
            url=absolute_url,
            chapter_number=number,
            title=title or None,
            series=series,
        )
    if not chapters:
        raise FetchError("MangaFire non ha esposto link capitoli validi.")
    return sorted(chapters.values(), key=lambda chapter: _chapter_sort_key(chapter.chapter_number))


def _html_attr(tag: str, attr: str) -> str | None:
    match = re.search(
        rf"""\b{re.escape(attr)}\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""",
        tag,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    value = next(group for group in match.groups() if group is not None)
    return unescape(value).strip()


def _chapter_number_from_href(href: str) -> str | None:
    match = re.search(r"/chapter-([^/?#]+)", href, flags=re.IGNORECASE)
    if not match:
        return None
    return unescape(match.group(1)).strip() or None


def _chapter_sort_key(value: str) -> tuple[int, tuple[int, ...], str]:
    parts = tuple(int(part) for part in re.findall(r"\d+", value))
    return (0 if parts else 1, parts, value)


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
