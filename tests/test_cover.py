"""Cover-art resolver tests.

We mock the network entirely (httpx ``MockTransport``) so the tests
stay offline and deterministic. Three scenarios:

- A MangaDex title URL resolves via the MangaDex API (preferred path).
- An AniList lookup is used when MangaDex is not applicable.
- A repeated call hits the on-disk cache without re-fetching.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx

from msrt.scrape.cover import resolve_cover


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


_PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def test_cover_resolver_uses_mangadex_when_url_has_title_uuid(tmp_path: Path) -> None:
    uuid = "12345678-1234-1234-1234-123456789012"
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path.startswith(f"/manga/{uuid}"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": uuid,
                        "relationships": [
                            {
                                "type": "cover_art",
                                "attributes": {"fileName": "abc.jpg"},
                            }
                        ],
                    }
                },
            )
        if "/covers/" in str(request.url) and "abc.jpg" in str(request.url):
            return httpx.Response(
                200,
                content=_PNG_MAGIC,
                headers={"content-type": "image/jpeg"},
            )
        if "graphql.anilist.co" in str(request.url):  # pragma: no cover
            raise AssertionError("AniList must not be called when MangaDex hits")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    cover = _run(
        resolve_cover(
            "Wistoria Wand and Sword",
            cache_dir=tmp_path,
            source_url=f"https://mangadex.org/title/{uuid}/wistoria-wand-and-sword",
            transport=transport,
        )
    )

    assert cover is not None
    assert cover.source == "mangadex"
    assert cover.content == _PNG_MAGIC
    assert cover.content_type == "image/jpeg"
    assert (tmp_path / "covers").is_dir()


def test_cover_resolver_falls_back_to_anilist_for_non_mangadex_url(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "graphql.anilist.co" in url and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "Media": {
                            "id": 42,
                            "title": {"romaji": "Wistoria"},
                            "coverImage": {
                                "extraLarge": "https://media.example.test/cover.jpg",
                                "large": None,
                            },
                        }
                    }
                },
            )
        if "media.example.test/cover.jpg" in url:
            return httpx.Response(
                200,
                content=_PNG_MAGIC,
                headers={"content-type": "image/jpeg"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    cover = _run(
        resolve_cover(
            "Wistoria",
            cache_dir=tmp_path,
            source_url="https://mangafire.to/read/wistoria-wand-and-swordd.02n57/en/chapter-1",
            transport=transport,
        )
    )

    assert cover is not None
    assert cover.source == "anilist"


def test_cover_resolver_uses_disk_cache_on_second_call(tmp_path: Path) -> None:
    fetches = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        fetches["count"] += 1
        if "graphql.anilist.co" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "Media": {
                            "coverImage": {
                                "extraLarge": "https://media.example.test/cover.jpg"
                            }
                        }
                    }
                },
            )
        return httpx.Response(
            200,
            content=_PNG_MAGIC,
            headers={"content-type": "image/jpeg"},
        )

    transport = httpx.MockTransport(handler)
    args = {"cache_dir": tmp_path, "transport": transport}
    first = _run(resolve_cover("Wistoria", **args))  # type: ignore[arg-type]
    fetches_after_first = fetches["count"]
    second = _run(resolve_cover("Wistoria", **args))  # type: ignore[arg-type]
    assert first is not None
    assert second is not None
    assert second.source == "cache:anilist"
    # Cached lookup must not hit the network at all.
    assert fetches["count"] == fetches_after_first


def test_cover_resolver_falls_back_to_local_composite_when_apis_miss(
    tmp_path: Path,
) -> None:
    """When MangaDex and AniList both return nothing, the resolver
    should generate a poster from the manga's own scanned pages so
    the user never gets stuck with the bare gradient placeholder."""

    from io import BytesIO

    from PIL import Image

    # Create a fake fetch tree with one chapter and a colourful page.
    series_dir = tmp_path / "out" / ".msrt-fetch" / "fakeadapter" / "untraced-series"
    chapter_dir = series_dir / "1"
    chapter_dir.mkdir(parents=True)
    page = Image.new("RGB", (1200, 1800), (180, 90, 30))
    # Draw a couple of stripes so JPEG compression doesn't collapse it
    # to a single colour and the file size stays meaningful.
    from PIL import ImageDraw

    draw = ImageDraw.Draw(page)
    draw.rectangle([(0, 0), (1200, 600)], fill=(255, 200, 100))
    draw.rectangle([(0, 600), (1200, 1200)], fill=(80, 30, 200))
    page.save(chapter_dir / "001.jpg", format="JPEG", quality=85)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    cover = _run(
        resolve_cover(
            "Untraced Series",
            cache_dir=tmp_path,
            out_dir=tmp_path / "out",
            transport=transport,
        )
    )

    assert cover is not None, "composite must produce something when scans exist"
    assert cover.source == "local-composite"
    assert cover.content_type == "image/jpeg"
    # The output should be a valid 600x800 JPEG.
    img = Image.open(BytesIO(cover.content))
    assert img.size == (600, 800)
    assert img.format == "JPEG"


def test_cover_resolver_caches_negative_lookups_to_avoid_hammering(tmp_path: Path) -> None:
    fetches = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        fetches["count"] += 1
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    args = {"cache_dir": tmp_path, "transport": transport}
    first = _run(resolve_cover("Untraced Series", **args))  # type: ignore[arg-type]
    second = _run(resolve_cover("Untraced Series", **args))  # type: ignore[arg-type]
    assert first is None
    assert second is None
    # Negative cache: only the first attempt actually hits the network.
    assert fetches["count"] >= 1
