from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from io import BytesIO
from pathlib import Path
from typing import Any, TypeVar

import pytest
from PIL import Image

from msrt.scrape.adapters.mangafire import (
    MangaFireReaderPages,
    MangaFireScraper,
    _chapter_links_from_reader_payload,
    _image_urls_from_reader_payload,
)
from msrt.scrape.base import ChapterLink, FetchError
from msrt.scrape.browser_capture import BrowserCapturedPage, BrowserCaptureResult
from msrt.scrape.downloader import DownloadedFile
from msrt.scrape.registry import scraper_for_url


def _png_bytes(seed: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (8, 8), (seed, seed, seed)).save(buf, format="PNG")
    return buf.getvalue()


_T = TypeVar("_T")


def _run(coro: Coroutine[Any, Any, _T]) -> _T:
    return asyncio.run(coro)


class _FakeCaptureEngine:
    def __init__(self, *, raise_error: bool = False) -> None:
        self.raise_error = raise_error
        self.seen_url: str | None = None

    async def capture(self, url: str, output_dir: Path) -> BrowserCaptureResult:
        self.seen_url = url
        if self.raise_error:
            raise FetchError("scan non visibile")
        output_dir.mkdir(parents=True, exist_ok=True)
        pages: list[BrowserCapturedPage] = []
        for index in (1, 2):
            path = output_dir / f"{index:03d}.png"
            body = _png_bytes(index * 20)
            path.write_bytes(body)
            pages.append(
                BrowserCapturedPage(
                    index=index,
                    url=f"{url}#page-{index}",
                    local_path=path,
                    sha256=f"sha256:{index}",
                    size_bytes=len(body),
                    capture_mode="browser-element-screenshot",
                )
            )
        return BrowserCaptureResult(
            pages=pages,
            warnings=["low-resolution capture"],
            manual_intervention=True,
            viewport_width=1600,
            viewport_height=1200,
            device_scale_factor=2.0,
        )


class _FakeReaderResolver:
    def __init__(self, *, raise_error: bool = False) -> None:
        self.raise_error = raise_error
        self.seen_url: str | None = None

    async def resolve(self, url: str) -> MangaFireReaderPages:
        self.seen_url = url
        if self.raise_error:
            raise FetchError("reader endpoint non disponibile")
        return MangaFireReaderPages(
            image_urls=[
                "https://img.example.test/page-2.jpg",
                "https://img.example.test/page-1.jpg",
            ],
            warnings=["reader-network warning"],
        )

    async def list_chapters(self, url: str):  # type: ignore[no-untyped-def]
        self.seen_url = url
        if self.raise_error:
            raise FetchError("chapter list non disponibile")
        return type(
            "FakeIndex",
            (),
            {
                "chapters": [
                    ChapterLink(
                        url=f"{url.rsplit('/', 1)[0]}/chapter-0",
                        chapter_number="0",
                        series="Wistoria",
                    ),
                    ChapterLink(
                        url=f"{url.rsplit('/', 1)[0]}/chapter-1",
                        chapter_number="1",
                        series="Wistoria",
                    ),
                ]
            },
        )()


@pytest.mark.parametrize(
    "url",
    [
        "https://mangafire.to/read/wistoria-wand-and-swordd.02n57/en/chapter-44",
        "https://www.mangafire.to/read/readerr.3rl1y",
    ],
)
def test_mangafire_matches_reader_urls(url: str) -> None:
    assert MangaFireScraper().matches(url)


def test_mangafire_does_not_match_unrelated_urls() -> None:
    assert not MangaFireScraper().matches("https://mangadex.org/chapter/abc")
    assert not MangaFireScraper().matches("https://mangafire.to/types")


def test_registry_routes_mangafire_url() -> None:
    scraper = scraper_for_url(
        "https://mangafire.to/read/wistoria-wand-and-swordd.02n57/en/chapter-44"
    )
    assert scraper.name == "mangafire"


def test_mangafire_fetch_uses_browser_capture_result(tmp_path: Path) -> None:
    engine = _FakeCaptureEngine()
    resolver = _FakeReaderResolver(raise_error=True)
    scraper = MangaFireScraper(capture_engine=engine, reader_resolver=resolver)
    url = "https://mangafire.to/read/wistoria-wand-and-swordd.02n57/en/chapter-44"

    result = _run(scraper.fetch(url, tmp_path))

    assert resolver.seen_url == url
    assert engine.seen_url == url
    assert result.series == "Wistoria Wand And Swordd"
    assert result.chapter_number == "44"
    assert result.strategy == "mangafire-browser-capture"
    assert result.capture_mode == "browser-capture"
    assert result.manual_intervention is True
    assert result.viewport == {"width": 1600, "height": 1200}
    assert result.device_scale_factor == 2.0
    assert result.warnings == [
        "Reader-network MangaFire fallito (reader endpoint non disponibile); uso browser-capture.",
        "low-resolution capture",
    ]
    assert [page.local_path.name for page in result.pages] == ["001.png", "002.png"]


def test_mangafire_fetch_prefers_reader_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolver = _FakeReaderResolver()
    capture = _FakeCaptureEngine(raise_error=True)
    scraper = MangaFireScraper(capture_engine=capture, reader_resolver=resolver)

    async def fake_download_pages(jobs, **kwargs):  # type: ignore[no-untyped-def]
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        files: list[DownloadedFile] = []
        for job in jobs:
            path = output_dir / f"{job.index:03d}.png"
            body = _png_bytes(job.index * 30)
            path.write_bytes(body)
            files.append(
                DownloadedFile(
                    index=job.index,
                    url=job.url,
                    local_path=path,
                    sha256=f"sha256:download-{job.index}",
                    size_bytes=len(body),
                    content_type="image/png",
                )
            )
        return files

    monkeypatch.setattr("msrt.scrape.adapters.mangafire.download_pages", fake_download_pages)
    url = "https://mangafire.to/read/wistoria-wand-and-swordd.02n57/en/chapter-44"

    result = _run(scraper.fetch(url, tmp_path))

    assert resolver.seen_url == url
    assert capture.seen_url is None
    assert result.strategy == "mangafire-reader-network"
    assert result.capture_mode == "browser-network"
    assert result.warnings == ["reader-network warning"]
    assert [page.url for page in result.pages] == [
        "https://img.example.test/page-2.jpg",
        "https://img.example.test/page-1.jpg",
    ]


def test_mangafire_fetch_propagates_capture_error(tmp_path: Path) -> None:
    scraper = MangaFireScraper(
        capture_engine=_FakeCaptureEngine(raise_error=True),
        reader_resolver=_FakeReaderResolver(raise_error=True),
    )

    with pytest.raises(FetchError, match="Browser-capture fallito: scan non visibile"):
        _run(
            scraper.fetch(
                "https://mangafire.to/read/wistoria-wand-and-swordd.02n57/en/chapter-44",
                tmp_path,
            )
        )


def test_image_urls_from_reader_payload_sorts_by_page_number() -> None:
    payload = """
    {
      "status": 200,
      "result": {
        "images": [
          ["https://img.example.test/003.webp", 3, 0],
          ["https://img.example.test/001.webp", 1, 0],
          ["https://img.example.test/002.webp", "2", 0]
        ]
      }
    }
    """

    assert _image_urls_from_reader_payload(payload) == [
        "https://img.example.test/001.webp",
        "https://img.example.test/002.webp",
        "https://img.example.test/003.webp",
    ]


def test_image_urls_from_reader_payload_rejects_missing_images() -> None:
    with pytest.raises(FetchError, match="senza immagini"):
        _image_urls_from_reader_payload('{"status":200,"result":{"html":"no pages"}}')


def test_chapter_links_from_reader_payload_sorts_chapters() -> None:
    payload = """
    {
      "status": 200,
      "result": {
        "html": "<ul><li><a href=\\"/read/wistoria.abc/en/chapter-2\\" data-number=\\"2\\" title=\\"B\\">Chap 2</a></li><li><a href=\\"/read/wistoria.abc/en/chapter-0\\" data-number=\\"0\\" title=\\"A\\">Chap 0</a></li></ul>"
      }
    }
    """

    chapters = _chapter_links_from_reader_payload(
        payload,
        base_url="https://mangafire.to/read/wistoria.abc/en/chapter-1",
        series="Wistoria",
    )

    assert [chapter.chapter_number for chapter in chapters] == ["0", "2"]
    assert chapters[0].url == "https://mangafire.to/read/wistoria.abc/en/chapter-0"
    assert chapters[0].series == "Wistoria"


def test_chapter_links_from_reader_payload_accepts_single_quotes_and_href_number() -> None:
    payload = """
    {
      "status": 200,
      "result": {
        "html": "<a href='/read/wistoria.abc/en/chapter-10' title='Ten'>10</a>"
      }
    }
    """

    chapters = _chapter_links_from_reader_payload(
        payload,
        base_url="https://mangafire.to/read/wistoria.abc/en/chapter-1",
        series="Wistoria",
    )

    assert len(chapters) == 1
    assert chapters[0].chapter_number == "10"
    assert chapters[0].title == "Ten"


def test_mangafire_list_chapters_uses_reader_resolver() -> None:
    resolver = _FakeReaderResolver()
    scraper = MangaFireScraper(reader_resolver=resolver)
    url = "https://mangafire.to/read/wistoria-wand-and-swordd.02n57/en/chapter-44"

    chapters = _run(scraper.list_chapters(url))

    assert resolver.seen_url == url
    assert [chapter.chapter_number for chapter in chapters] == ["0", "1"]
