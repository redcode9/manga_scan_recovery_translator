"""MangaDex chapter scraper.

Drives the public MangaDex API end-to-end:

1. Resolve the URL to a chapter UUID. ``/chapter/<UUID>`` maps directly;
   ``/title/<UUID>`` triggers a feed lookup, sorted by chapter number
   ascending, picking the first English chapter that isn't an external
   redirect. Range / explicit-chapter selection lands in v0.3.
2. ``GET /chapter/{id}`` for manga relationship + chapter number / title.
   ``externalUrl`` here is surfaced as a clear ``FetchError``: MangaDex
   doesn't host the images for those entries.
3. ``GET /manga/{id}`` for the canonical English series title.
4. ``GET /at-home/server/{chapter_id}`` for ``baseUrl``, ``chapter.hash``
   and the ordered list of page filenames.
5. Build ``DownloadJob`` per page and call ``download_pages`` with a
   0.2 sec per-host delay to honour MangaDex's public guideline of
   ≤5 req/s. The downloader's magic-byte validator rejects soft-fail
   pages even when the CDN serves them with ``image/*`` headers.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from msrt.scrape.base import ChapterScraper, FetchedPage, FetchError, FetchResult
from msrt.scrape.downloader import (
    DownloadError,
    DownloadJob,
    download_pages,
    find_duplicate_pages,
)
from msrt.scrape.registry import register

_MANGADEX_HOSTS: frozenset[str] = frozenset(
    {"mangadex.org", "www.mangadex.org", "canary.mangadex.dev"}
)
_API_BASE = "https://api.mangadex.org"

_UUID_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_CHAPTER_PATH_RE = re.compile(rf"^/chapter/(?P<uuid>{_UUID_PATTERN})(?:/.*)?$", re.IGNORECASE)
_TITLE_PATH_RE = re.compile(rf"^/title/(?P<uuid>{_UUID_PATTERN})(?:/.*)?$", re.IGNORECASE)
_PREFERRED_LANGUAGE = "en"
_PER_HOST_DELAY = 0.2
_FEED_PAGE_SIZE = 100


@register
class MangaDexScraper(ChapterScraper):
    """MangaDex API-driven scraper.

    ``transport`` lets tests inject ``httpx.MockTransport`` so unit
    tests can drive the entire fetch flow against fixture JSON without
    hitting the network. Production callers leave it ``None``.
    """

    name = "mangadex"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def matches(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        host = (parsed.netloc or "").lower()
        if host not in _MANGADEX_HOSTS:
            return False
        return bool(_CHAPTER_PATH_RE.match(parsed.path) or _TITLE_PATH_RE.match(parsed.path))

    async def fetch(self, url: str, output_dir: Path) -> FetchResult:
        path = urlparse(url).path
        chapter_match = _CHAPTER_PATH_RE.match(path)
        title_match = _TITLE_PATH_RE.match(path)
        if not (chapter_match or title_match):
            raise FetchError(
                f"URL MangaDex non valido: {url!r}. Atteso /chapter/<UUID> o /title/<UUID>."
            )

        async with httpx.AsyncClient(
            base_url=_API_BASE,
            timeout=30.0,
            follow_redirects=True,
            transport=self._transport,
            headers={"User-Agent": "msrt/0.0 (+local)"},
        ) as api_client:
            if chapter_match is not None:
                chapter_id = chapter_match.group("uuid").lower()
            else:
                assert title_match is not None  # mypy / runtime
                manga_id = title_match.group("uuid").lower()
                chapter_id = await _first_chapter_for_manga(api_client, manga_id)

            chapter_payload = await _api_get(api_client, f"/chapter/{chapter_id}")
            chapter_data = chapter_payload.get("data") or {}
            chapter_attrs = chapter_data.get("attributes") or {}

            external_url = chapter_attrs.get("externalUrl")
            if external_url:
                raise FetchError(
                    f"Capitolo {chapter_id} è esterno: {external_url}. "
                    "MangaDex non ospita le immagini per questa release; "
                    "salta o cerca un'altra traduzione."
                )

            manga_id_resolved = _related_id(chapter_data, "manga")
            if manga_id_resolved is None:
                raise FetchError(f"Capitolo {chapter_id} senza relazione 'manga' nei metadata.")

            manga_payload = await _api_get(api_client, f"/manga/{manga_id_resolved}")
            series_title = _pick_series_title(manga_payload.get("data") or {})

            at_home_payload = await _api_get(api_client, f"/at-home/server/{chapter_id}")
            page_urls = _build_page_urls(at_home_payload)
            if not page_urls:
                raise FetchError(f"Nessuna pagina elencata per il capitolo {chapter_id}.")

            jobs = [
                DownloadJob(index=i, url=page_url) for i, page_url in enumerate(page_urls, start=1)
            ]
            try:
                files = await download_pages(
                    jobs,
                    output_dir=output_dir,
                    min_delay_per_host=_PER_HOST_DELAY,
                    transport=self._transport,
                )
            except DownloadError as exc:
                raise FetchError(f"Download MangaDex fallito: {exc}") from exc

        warnings = find_duplicate_pages(files)
        translated_lang = chapter_attrs.get("translatedLanguage")
        if translated_lang and translated_lang != _PREFERRED_LANGUAGE:
            warnings.append(
                f"Capitolo in lingua {translated_lang!r} "
                f"(atteso {_PREFERRED_LANGUAGE!r}); verifica che la traduzione "
                "successiva sia coerente."
            )

        pages = [
            FetchedPage(
                index=f.index,
                url=f.url,
                local_path=f.local_path,
                sha256=f.sha256,
                content_type=f.content_type,
                size_bytes=f.size_bytes,
            )
            for f in files
        ]
        return FetchResult(
            series=series_title,
            chapter_number=str(chapter_attrs.get("chapter") or "?"),
            chapter_title=chapter_attrs.get("title") or None,
            source_url=url,
            strategy="mangadex-api",
            pages=pages,
            output_dir=output_dir,
            warnings=warnings,
        )


async def _api_get(client: httpx.AsyncClient, path: str) -> dict[str, Any]:
    """GET helper that enforces MangaDex's ``result == "ok"`` envelope."""

    response = await client.get(path)
    if response.status_code >= 400:
        raise FetchError(
            f"MangaDex API HTTP {response.status_code} su {path}: {response.text[:200]}"
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise FetchError(f"MangaDex API ha risposto JSON non valido su {path}.") from exc
    if not isinstance(data, dict):
        raise FetchError(f"MangaDex API ha risposto un payload non-oggetto su {path}.")
    if data.get("result") != "ok":
        errors = data.get("errors") or "?"
        raise FetchError(f"MangaDex API errore su {path}: {errors}")
    return data


async def _first_chapter_for_manga(client: httpx.AsyncClient, manga_id: str) -> str:
    """Return the chapter UUID of the earliest available English chapter
    for ``manga_id``. Falls back to any-language if no English chapter
    exists. Raises ``FetchError`` when the feed has no eligible entries
    (empty manga, or every chapter is ``externalUrl``)."""

    payload = await _api_get(
        client,
        f"/manga/{manga_id}/feed"
        f"?limit={_FEED_PAGE_SIZE}"
        f"&order[chapter]=asc"
        f"&translatedLanguage[]={_PREFERRED_LANGUAGE}",
    )
    items = payload.get("data") or []
    if not items:
        # Retry without language filter — better than failing outright.
        payload = await _api_get(
            client,
            f"/manga/{manga_id}/feed?limit={_FEED_PAGE_SIZE}&order[chapter]=asc",
        )
        items = payload.get("data") or []
    if not items:
        raise FetchError(f"Nessun capitolo elencato per la serie {manga_id}.")

    for entry in items:
        attrs = entry.get("attributes") or {}
        if not attrs.get("externalUrl") and entry.get("id"):
            return str(entry["id"])
    raise FetchError(
        f"Tutti i capitoli di {manga_id} sono externalUrl; nessuno è scaricabile via MangaDex."
    )


def _related_id(chapter_data: dict[str, Any], rel_type: str) -> str | None:
    for rel in chapter_data.get("relationships") or []:
        if rel.get("type") == rel_type and rel.get("id"):
            return str(rel["id"])
    return None


def _pick_series_title(manga_data: dict[str, Any]) -> str:
    """Pick the series title from a ``/manga/{id}`` payload.

    MangaDex stores titles as a language → string dict (``{"en": "…",
    "ja": "…"}``). We prefer English; otherwise return the first
    non-empty entry sorted alphabetically (deterministic across runs).
    Falls back to ``"Untitled Series"`` when nothing usable is present.
    """

    attributes = manga_data.get("attributes") or {}
    title = attributes.get("title") or {}
    if not isinstance(title, dict):
        return "Untitled Series"
    if title.get(_PREFERRED_LANGUAGE):
        return str(title[_PREFERRED_LANGUAGE])
    for _key, value in sorted(title.items()):
        if value:
            return str(value)
    return "Untitled Series"


def _build_page_urls(at_home_payload: dict[str, Any]) -> list[str]:
    base_url = at_home_payload.get("baseUrl")
    chapter = at_home_payload.get("chapter") or {}
    chapter_hash = chapter.get("hash")
    filenames = chapter.get("data") or []
    if not (
        isinstance(base_url, str)
        and isinstance(chapter_hash, str)
        and isinstance(filenames, list)
        and filenames
    ):
        return []
    return [f"{base_url}/data/{chapter_hash}/{filename}" for filename in filenames]
