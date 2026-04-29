"""End-to-end tests for ``MangaDexScraper.fetch``.

Every test wires an ``httpx.MockTransport`` that responds to both the
MangaDex API endpoints (``api.mangadex.org``) and the upload CDN
(``uploads.mangadex.org``). Fixtures under ``tests/fixtures/mangadex/``
mirror the real API envelope shape, so the parser would catch a
contract drift the same way it would in production.
"""

from __future__ import annotations

import asyncio
import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from msrt.scrape.adapters.mangadex import MangaDexScraper
from msrt.scrape.base import FetchError

FIXTURES = Path(__file__).parent / "fixtures" / "mangadex"

CHAPTER_ID = "11111111-1111-1111-1111-111111111111"
EXTERNAL_CHAPTER_ID = "ee111111-1111-1111-1111-111111111111"
MANGA_ID = "22222222-2222-2222-2222-222222222222"
PAGE_FILENAMES = ["1-page.png", "2-page.png", "3-page.png"]


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _real_png_bytes(seed: int = 0x10) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (4, 4), (seed, seed, seed)).save(buf, format="PNG")
    return buf.getvalue()


def _run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def _build_handler(
    *,
    chapter_payload: dict | None = None,
    manga_payload: dict | None = None,
    feed_payloads: list[dict] | None = None,
    at_home_payload: dict | None = None,
    pages_serve_real_image: bool = True,
):  # type: ignore[no-untyped-def]
    """Compose a MockTransport handler that routes by URL path.

    ``feed_payloads`` is a list because MangaDex's feed endpoint may be
    called twice — once with a language filter and once without — and
    the scraper expects to iterate through both responses if the first
    one is empty.
    """

    feed_queue = list(feed_payloads or [])
    chapter_payload = chapter_payload or _load_fixture("chapter_normal.json")
    manga_payload = manga_payload or _load_fixture("manga_wistoria.json")
    at_home_payload = at_home_payload or _load_fixture("at_home.json")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith("https://api.mangadex.org/chapter/"):
            return httpx.Response(200, json=chapter_payload)
        if url.startswith("https://api.mangadex.org/manga/"):
            if "/feed" in url:
                if not feed_queue:
                    raise AssertionError(f"Unexpected extra feed request: {url}")
                return httpx.Response(200, json=feed_queue.pop(0))
            return httpx.Response(200, json=manga_payload)
        if url.startswith("https://api.mangadex.org/at-home/server/"):
            return httpx.Response(200, json=at_home_payload)
        if url.startswith("https://uploads.mangadex.org/"):
            if pages_serve_real_image:
                # Vary seed by URL so the magic-byte validator and the
                # duplicate-pages check both see distinct payloads.
                seed = (sum(url.encode()) % 200) + 16
                return httpx.Response(
                    200,
                    content=_real_png_bytes(seed),
                    headers={"content-type": "image/png"},
                )
            return httpx.Response(404, content=b"missing")
        raise AssertionError(f"Unrouted MangaDex test URL: {url}")

    return handler


def test_fetch_chapter_url_returns_full_result(tmp_path: Path) -> None:
    transport = httpx.MockTransport(_build_handler())
    scraper = MangaDexScraper(transport=transport)
    url = f"https://mangadex.org/chapter/{CHAPTER_ID}"

    result = _run(scraper.fetch(url, tmp_path))

    assert result.series == "Wistoria: Wand and Sword"
    assert result.chapter_number == "44"
    assert result.chapter_title == "The Trial"
    assert result.strategy == "mangadex-api"
    assert result.source_url == url
    assert len(result.pages) == 3
    assert [p.local_path.name for p in result.pages] == ["001.png", "002.png", "003.png"]
    expected_url_prefix = "https://uploads.mangadex.org/test-upload/data/abcd1234hashforchapter44/"
    for page, filename in zip(result.pages, PAGE_FILENAMES, strict=True):
        assert page.url == expected_url_prefix + filename
        assert page.local_path.parent == tmp_path
        assert page.local_path.exists()
    assert result.warnings == []


def test_fetch_title_url_resolves_first_chapter(tmp_path: Path) -> None:
    """A ``/title/<UUID>`` URL must follow the feed → first eligible
    chapter → fetch flow without any extra interaction."""

    feed_handler = _build_handler(feed_payloads=[_load_fixture("manga_feed.json")])
    scraper = MangaDexScraper(transport=httpx.MockTransport(feed_handler))
    url = f"https://mangadex.org/title/{MANGA_ID}/wistoria"

    result = _run(scraper.fetch(url, tmp_path))

    assert result.chapter_number == "44"
    assert result.series == "Wistoria: Wand and Sword"
    assert len(result.pages) == 3


def test_fetch_title_url_falls_back_when_english_feed_empty(tmp_path: Path) -> None:
    """When the language-filtered feed is empty, the scraper retries
    without the filter. We simulate that by handing the handler two
    feed payloads."""

    handler = _build_handler(
        feed_payloads=[
            _load_fixture("manga_feed_empty.json"),
            _load_fixture("manga_feed.json"),
        ]
    )
    scraper = MangaDexScraper(transport=httpx.MockTransport(handler))
    url = f"https://mangadex.org/title/{MANGA_ID}"

    result = _run(scraper.fetch(url, tmp_path))

    assert result.chapter_number == "44"


def test_fetch_title_url_raises_when_no_chapters(tmp_path: Path) -> None:
    handler = _build_handler(
        feed_payloads=[
            _load_fixture("manga_feed_empty.json"),
            _load_fixture("manga_feed_empty.json"),
        ]
    )
    scraper = MangaDexScraper(transport=httpx.MockTransport(handler))
    url = f"https://mangadex.org/title/{MANGA_ID}"

    with pytest.raises(FetchError, match="Nessun capitolo"):
        _run(scraper.fetch(url, tmp_path))


def test_fetch_external_url_chapter_raises_with_clear_message(tmp_path: Path) -> None:
    """When MangaDex points at an externalUrl we can't download the
    pages — surface that immediately instead of attempting opaque
    downloads."""

    handler = _build_handler(chapter_payload=_load_fixture("chapter_external.json"))
    scraper = MangaDexScraper(transport=httpx.MockTransport(handler))
    url = f"https://mangadex.org/chapter/{EXTERNAL_CHAPTER_ID}"

    with pytest.raises(FetchError, match="esterno"):
        _run(scraper.fetch(url, tmp_path))


def test_fetch_raises_when_at_home_has_no_pages(tmp_path: Path) -> None:
    empty_at_home = {
        "result": "ok",
        "baseUrl": "https://uploads.mangadex.org/empty",
        "chapter": {"hash": "abc", "data": [], "dataSaver": []},
    }
    handler = _build_handler(at_home_payload=empty_at_home)
    scraper = MangaDexScraper(transport=httpx.MockTransport(handler))
    url = f"https://mangadex.org/chapter/{CHAPTER_ID}"

    with pytest.raises(FetchError, match="Nessuna pagina"):
        _run(scraper.fetch(url, tmp_path))


def test_fetch_raises_on_api_error_envelope(tmp_path: Path) -> None:
    """A response with ``result != "ok"`` is the API's documented way to
    signal an error — turn it into a clear FetchError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": "error",
                "errors": [{"id": "abc", "title": "Not Found"}],
            },
        )

    scraper = MangaDexScraper(transport=httpx.MockTransport(handler))
    url = f"https://mangadex.org/chapter/{CHAPTER_ID}"

    with pytest.raises(FetchError, match="MangaDex API errore"):
        _run(scraper.fetch(url, tmp_path))


def test_fetch_warns_on_non_english_chapter(tmp_path: Path) -> None:
    """If the resolved chapter is in a different language than the
    preferred one, surface a warning so the user can decide whether to
    re-run with explicit selection later."""

    chapter_other_lang = _load_fixture("chapter_normal.json")
    chapter_other_lang["data"]["attributes"]["translatedLanguage"] = "es"
    handler = _build_handler(chapter_payload=chapter_other_lang)
    scraper = MangaDexScraper(transport=httpx.MockTransport(handler))
    url = f"https://mangadex.org/chapter/{CHAPTER_ID}"

    result = _run(scraper.fetch(url, tmp_path))

    assert any("'es'" in w and "atteso" in w for w in result.warnings)


def test_fetch_propagates_download_failure_as_fetch_error(tmp_path: Path) -> None:
    handler = _build_handler(pages_serve_real_image=False)
    scraper = MangaDexScraper(transport=httpx.MockTransport(handler))
    url = f"https://mangadex.org/chapter/{CHAPTER_ID}"

    with pytest.raises(FetchError, match="Download MangaDex fallito"):
        _run(scraper.fetch(url, tmp_path))


def test_pick_series_title_falls_back_to_japanese_when_english_missing(
    tmp_path: Path,
) -> None:
    manga_no_en = _load_fixture("manga_wistoria.json")
    manga_no_en["data"]["attributes"]["title"] = {"ja": "杖と剣のウィストリア"}
    handler = _build_handler(manga_payload=manga_no_en)
    scraper = MangaDexScraper(transport=httpx.MockTransport(handler))
    url = f"https://mangadex.org/chapter/{CHAPTER_ID}"

    result = _run(scraper.fetch(url, tmp_path))

    assert result.series == "杖と剣のウィストリア"
