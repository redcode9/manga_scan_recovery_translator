"""Cover-art resolver per la libreria.

Strategia in quattro passi, dalla più affidabile alla più generica:

1. Se il manga proviene da un URL MangaDex con UUID titolo, usiamo la
   API ufficiale ``api.mangadex.org/cover?manga[]=<uuid>`` — è la
   cover *di quella stessa edizione* che l'utente sta leggendo.
2. Altrimenti, query a AniList GraphQL per nome (gratis, niente
   chiave). AniList ha un catalogo enorme e ``coverImage.extraLarge``
   tende a essere ad alta risoluzione (800x1200 dove disponibile).
3. **Fallback locale**: se le pagine del manga sono già scaricate sul
   disco (cartella ``out/.msrt-fetch/<adapter>/<series>/...``),
   generiamo un poster sintetico: ritaglio 3:4 della pagina più
   "rappresentativa" + gradiente in basso per leggibilità del titolo
   sovrapposto. Colori e stile vengono dai disegni reali, niente AI
   generativa esterna.
4. Se nessuna delle precedenti produce un'immagine, ritorniamo
   ``None`` e l'UI mostra il poster a gradiente.

Caching: ogni chiamata risolta viene cachata in
``cache_dir/covers/<key>.{bin,json}``. La cache vive ``_TTL_DAYS``
giorni; oltre, la prossima richiesta ri-tenta. La cache positiva e
quella negativa hanno TTL diversi così non bombardiamo AniList per
serie che semplicemente non esistono ancora nel loro catalogo.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageDraw

_LOG = logging.getLogger(__name__)
_CACHE_SUBDIR = "covers"
_TTL_DAYS_HIT = 60
_TTL_DAYS_MISS = 1
_TIMEOUT = 15.0

_USER_AGENT = "msrt/0.0 (+local) cover-resolver"
_ANILIST_ENDPOINT = "https://graphql.anilist.co"
_MANGADEX_API = "https://api.mangadex.org"
_MANGADEX_UPLOADS = "https://uploads.mangadex.org/covers"

_MANGADEX_UUID_RE = re.compile(
    r"/(?:title|manga)/(?P<uuid>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


@dataclass(frozen=True)
class CoverResult:
    """Bytes + metadata returned by ``resolve_cover``."""

    content: bytes
    content_type: str
    source: str  # "mangadex" / "anilist" / "cache:<source>"


async def resolve_cover(
    series: str,
    *,
    cache_dir: Path,
    source_url: str | None = None,
    out_dir: Path | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> CoverResult | None:
    """Best-effort cover lookup with on-disk cache.

    ``out_dir`` is the user's library output directory; when provided,
    the resolver can fall back to a synthetic poster generated from
    the manga's own scanned pages (``.msrt-fetch/...``) — useful for
    series that don't appear on MangaDex/AniList.
    """

    cleaned = (series or "").strip()
    if not cleaned:
        return None

    cache_root = cache_dir / _CACHE_SUBDIR
    cache_root.mkdir(parents=True, exist_ok=True)
    key = _cache_key(cleaned)
    img_path = cache_root / f"{key}.bin"
    meta_path = cache_root / f"{key}.json"

    cached = _read_cached(img_path, meta_path)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(
        timeout=_TIMEOUT,
        headers={"User-Agent": _USER_AGENT},
        transport=transport,
        follow_redirects=True,
    ) as client:
        # 1. MangaDex path is the most accurate when applicable.
        mangadex_uuid = _mangadex_title_uuid(source_url)
        if mangadex_uuid:
            cover = await _fetch_mangadex_cover(client, mangadex_uuid)
            if cover is not None:
                _write_cached(img_path, meta_path, cover)
                return cover

        # 2. AniList by series title.
        cover = await _fetch_anilist_cover(client, cleaned)
        if cover is not None:
            _write_cached(img_path, meta_path, cover)
            return cover

    # 3. Local composite from on-disk scans — works offline and for
    #    series that aren't catalogued anywhere.
    if out_dir is not None:
        composite = await _local_composite_cover(cleaned, out_dir=out_dir)
        if composite is not None:
            _write_cached(img_path, meta_path, composite)
            return composite

    # 4. No hit — write a small "miss marker" so we don't hammer the
    #    APIs for a title that simply isn't in their catalogue.
    _write_miss(meta_path)
    return None


def _cache_key(series: str) -> str:
    return hashlib.sha256(series.lower().encode("utf-8")).hexdigest()[:16]


def _read_cached(img_path: Path, meta_path: Path) -> CoverResult | None:
    if not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    fetched_at = meta.get("fetched_at")
    is_miss = bool(meta.get("miss"))
    if fetched_at is None:
        return None
    try:
        ts = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    age = datetime.now(UTC) - ts
    ttl = timedelta(days=_TTL_DAYS_MISS if is_miss else _TTL_DAYS_HIT)
    if age > ttl:
        return None
    if is_miss:
        return None
    if not img_path.is_file():
        return None
    try:
        content = img_path.read_bytes()
    except OSError:
        return None
    return CoverResult(
        content=content,
        content_type=str(meta.get("content_type") or "image/jpeg"),
        source=f"cache:{meta.get('source', 'unknown')}",
    )


def _write_cached(img_path: Path, meta_path: Path, cover: CoverResult) -> None:
    img_path.write_bytes(cover.content)
    meta_path.write_text(
        json.dumps(
            {
                "content_type": cover.content_type,
                "source": cover.source,
                "fetched_at": datetime.now(UTC).isoformat(),
            }
        ),
        encoding="utf-8",
    )


def _write_miss(meta_path: Path) -> None:
    meta_path.write_text(
        json.dumps(
            {
                "miss": True,
                "fetched_at": datetime.now(UTC).isoformat(),
            }
        ),
        encoding="utf-8",
    )


def _mangadex_title_uuid(source_url: str | None) -> str | None:
    """Extract a MangaDex *title* UUID. ``/chapter/<uuid>`` URLs
    contain a chapter UUID which does NOT identify the title; we
    can't resolve the cover from those without an extra API hop, so
    we skip them and let AniList handle the search."""

    if not source_url:
        return None
    try:
        parsed = urlparse(source_url)
    except ValueError:
        return None
    host = (parsed.netloc or "").lower()
    if "mangadex.org" not in host:
        return None
    match = _MANGADEX_UUID_RE.search(parsed.path)
    return match.group("uuid") if match else None


async def _fetch_mangadex_cover(
    client: httpx.AsyncClient, manga_uuid: str
) -> CoverResult | None:
    """Resolve the title's primary cover via MangaDex's public API."""

    try:
        meta_resp = await client.get(
            f"{_MANGADEX_API}/manga/{manga_uuid}",
            params={"includes[]": "cover_art"},
        )
    except httpx.HTTPError as exc:
        _LOG.debug("MangaDex cover lookup failed for %s: %s", manga_uuid, exc)
        return None
    if meta_resp.status_code != 200:
        return None
    try:
        body = meta_resp.json()
    except ValueError:
        return None
    relationships = (body.get("data") or {}).get("relationships") or []
    file_name: str | None = None
    for rel in relationships:
        if (
            isinstance(rel, dict)
            and rel.get("type") == "cover_art"
            and isinstance(rel.get("attributes"), dict)
        ):
            file_name = rel["attributes"].get("fileName")
            if file_name:
                break
    if not file_name:
        return None
    image_url = f"{_MANGADEX_UPLOADS}/{manga_uuid}/{file_name}"
    try:
        image_resp = await client.get(image_url)
    except httpx.HTTPError:
        return None
    if image_resp.status_code != 200 or not image_resp.content:
        return None
    return CoverResult(
        content=image_resp.content,
        content_type=image_resp.headers.get("content-type") or "image/jpeg",
        source="mangadex",
    )


_ANILIST_QUERY = """
query ($search: String) {
  Media(search: $search, type: MANGA, sort: SEARCH_MATCH) {
    id
    title { romaji english native }
    coverImage { extraLarge large }
  }
}
""".strip()


async def _local_composite_cover(
    series: str, *, out_dir: Path
) -> CoverResult | None:
    """Generate a poster from the manga's own pages.

    Picks the highest-resolution first-page from any chapter under
    ``out_dir/.msrt-fetch/<adapter>/<series-slug>/...`` and runs a
    cheap PIL pipeline:

    1. cover-fit crop to 3:4 (manga poster ratio), top-aligned because
       the upper third of a manga page tends to carry the dramatic
       imagery,
    2. add a darkening vignette in the bottom third so the title
       overlay rendered by the UI stays legible,
    3. JPEG-encode at quality 85.

    Returns ``None`` when no scanned page is found — the call site
    will then write a negative cache marker.
    """

    page = await asyncio.to_thread(_find_best_local_page, series, out_dir)
    if page is None:
        return None
    poster_bytes = await asyncio.to_thread(_compose_poster_from_page, page)
    if poster_bytes is None:
        return None
    return CoverResult(
        content=poster_bytes,
        content_type="image/jpeg",
        source="local-composite",
    )


def _find_best_local_page(series: str, out_dir: Path) -> Path | None:
    """Find a first-page candidate under ``out_dir/.msrt-fetch``.

    We slugify the series name and pattern-match against the directory
    layout produced by the URL pipeline:
    ``.msrt-fetch/<adapter>/<series-slug>/<chapter-slug>/001.jpg``.
    The page with the largest file size wins (a proxy for "richest
    image" — colour pages and detailed compositions weigh more than
    plain text pages).
    """

    fetch_root = out_dir / ".msrt-fetch"
    if not fetch_root.is_dir():
        return None
    series_token = _slugify_for_fs(series)
    candidates: list[Path] = []
    for adapter_dir in fetch_root.iterdir():
        if not adapter_dir.is_dir():
            continue
        for series_dir in adapter_dir.iterdir():
            if not series_dir.is_dir():
                continue
            if series_token not in series_dir.name.lower():
                continue
            for chapter_dir in series_dir.iterdir():
                if not chapter_dir.is_dir():
                    continue
                for ext in (".jpg", ".jpeg", ".png", ".webp"):
                    candidate = chapter_dir / f"001{ext}"
                    if candidate.is_file():
                        candidates.append(candidate)
                        break
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_size)


def _compose_poster_from_page(page_path: Path) -> bytes | None:
    """Render a poster from one source page. PIL-only, no extra deps."""

    try:
        with Image.open(page_path) as src:
            src.load()
            img = src.convert("RGB")
    except (OSError, ValueError):
        return None

    target_w, target_h = 600, 800
    src_w, src_h = img.size
    if src_w == 0 or src_h == 0:
        return None
    # cover-fit (max-scale) and crop, top-aligned so the focal point
    # of the manga page (usually upper-third) survives the crop.
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(target_w, int(src_w * scale))
    new_h = max(target_h, int(src_h * scale))
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - target_w) // 2)
    top = 0
    img = img.crop((left, top, left + target_w, top + target_h))

    # Bottom-third darkening overlay so the UI title remains legible.
    overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    fade_start = target_h * 2 // 3
    for y in range(fade_start, target_h):
        # Alpha rises linearly from 0 at fade_start to ~190 at the
        # bottom edge — strong enough for text contrast, soft enough
        # to keep the artwork visible.
        alpha = int(190 * (y - fade_start) / max(1, target_h - fade_start))
        draw.line([(0, y), (target_w, y)], fill=(0, 0, 0, alpha))
    composed = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    buf = io.BytesIO()
    composed.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()


def _slugify_for_fs(value: str) -> str:
    """Match the filesystem slug used by ``msrt.pipeline.slugify`` so
    we can find ``out/.msrt-fetch/<adapter>/<series-slug>/`` reliably."""

    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


async def _fetch_anilist_cover(
    client: httpx.AsyncClient, series: str
) -> CoverResult | None:
    try:
        resp = await client.post(
            _ANILIST_ENDPOINT,
            json={"query": _ANILIST_QUERY, "variables": {"search": series}},
        )
    except httpx.HTTPError as exc:
        _LOG.debug("AniList lookup failed for %s: %s", series, exc)
        return None
    if resp.status_code != 200:
        return None
    try:
        payload = resp.json()
    except ValueError:
        return None
    media = ((payload.get("data") or {}).get("Media")) or {}
    image = (media.get("coverImage") or {}).get("extraLarge") or (
        media.get("coverImage") or {}
    ).get("large")
    if not isinstance(image, str) or not image.startswith(("http://", "https://")):
        return None
    try:
        image_resp = await client.get(image)
    except httpx.HTTPError:
        return None
    if image_resp.status_code != 200 or not image_resp.content:
        return None
    return CoverResult(
        content=image_resp.content,
        content_type=image_resp.headers.get("content-type") or "image/jpeg",
        source="anilist",
    )
