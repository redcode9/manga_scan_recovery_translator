"""Async page downloader with retry, dedup, validation, and atomic staging.

The downloader is decoupled from any specific site adapter — adapters
build a list of ``DownloadJob`` (URL + index + optional headers) and
hand it to ``download_pages``. The result is a list of
``DownloadedFile`` objects that the adapter can wrap into a
``FetchResult``.

Three guarantees that matter for the URL pipeline:

1. **Image validation** — a HTTP 200 with HTML/text body never lands as
   a "successful" page. We check the Content-Type, the URL extension,
   and the body's magic bytes; mismatches raise as non-retryable errors
   so the caller learns the site is serving a soft-fail page.
2. **Per-host rate limit** — ``min_delay_per_host`` enforces a minimum
   gap between consecutive requests to the same host (independent of
   concurrency). MangaDex's public guidelines ask for ~5 req/s, and we
   want to respect that even when the user runs multiple chapters in
   parallel.
3. **Atomic staging** — pages are written to ``output_dir/.staging``
   first; only when *every* page in the batch succeeds do we rename
   them into ``output_dir/``. A partial failure leaves the staging dir
   in place for inspection but never pollutes the canonical output dir.

We expose ``transport`` so tests can inject ``httpx.MockTransport`` and
exercise retry / dedup logic without hitting the network.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

_LOG = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "msrt/0.0 (+local)"
# Cloudflare-specific 520-524 are intermittent edge errors that
# routinely flip green on retry; we treat them like 5xx.
_RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524})
_STAGING_DIR_NAME = ".staging"
# Files matching ``001.png``, ``042.jpg``, etc. — the canonical names
# emitted by ``download_pages``. Used to clear an output dir before
# promoting a new batch, so a 50-page chapter doesn't leak its pages
# into a subsequent 3-page fetch sharing the same dir.
_CANONICAL_PAGE_RE = re.compile(r"^\d{3,}\.(?:png|jpe?g|webp|gif|avif|bin)$", re.IGNORECASE)


@dataclass(frozen=True)
class DownloadJob:
    """One page to download.

    ``index`` drives the on-disk filename (``001.png``, ``002.jpg``, …).
    ``headers`` are merged on top of the client defaults — useful when an
    adapter needs to forward a Referer or auth token specific to a page.
    """

    index: int
    url: str
    headers: dict[str, str] | None = None


@dataclass(frozen=True)
class DownloadedFile:
    index: int
    url: str
    local_path: Path
    sha256: str
    size_bytes: int
    content_type: str | None


class DownloadError(RuntimeError):
    """Raised when a single page exhausts all retry attempts or returns
    a payload that fails image validation."""


async def download_pages(
    jobs: Iterable[DownloadJob],
    *,
    output_dir: Path,
    concurrency: int = 4,
    min_delay_per_host: float = 0.0,
    max_retries: int = 3,
    timeout: float = 30.0,
    user_agent: str = DEFAULT_USER_AGENT,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[DownloadedFile]:
    """Download every page concurrently and return the results in order.

    Files are first written to ``output_dir/.staging`` and only promoted
    to ``output_dir`` after the whole batch succeeds; a partial failure
    leaves the staging dir in place so the user can inspect / clean it
    manually but never pollutes the canonical output directory with a
    stale half-chapter.

    ``concurrency`` is a soft rate-limit on in-flight downloads.
    ``min_delay_per_host`` is the minimum number of seconds between
    consecutive requests to the same host (e.g. ``0.2`` ≈ 5 req/s).
    ``max_retries`` is the number of *additional* attempts after the
    first try (so ``max_retries=3`` means up to 4 attempts total).
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = output_dir / _STAGING_DIR_NAME
    staging_dir.mkdir(parents=True, exist_ok=True)
    jobs_list = list(jobs)
    if not jobs_list:
        # Nothing to do — keep the empty staging dir out of the user's way.
        with contextlib.suppress(OSError):
            staging_dir.rmdir()
        return []

    semaphore = asyncio.Semaphore(max(1, concurrency))
    rate_limiter = _HostRateLimiter(min_delay_per_host)
    headers = {"User-Agent": user_agent}

    async with httpx.AsyncClient(
        timeout=timeout, headers=headers, transport=transport, follow_redirects=True
    ) as client:
        tasks = [
            _download_one(client, job, staging_dir, semaphore, rate_limiter, max_retries)
            for job in jobs_list
        ]
        staged = await asyncio.gather(*tasks)

    # Promote: every page succeeded. First, purge any canonical pages
    # left over from a previous fetch into this output dir — otherwise a
    # 50-page chapter followed by a 3-page chapter would leak the
    # 4..50 pages into the smaller chapter's output (same class of bug
    # as v0.1.z translated-pages cleanup, on the fetch side).
    _purge_canonical_pages(output_dir)
    staged_sorted = sorted(staged, key=lambda f: f.index)
    promoted: list[DownloadedFile] = []
    for file in staged_sorted:
        final_path = output_dir / file.local_path.name
        file.local_path.replace(final_path)
        promoted.append(
            DownloadedFile(
                index=file.index,
                url=file.url,
                local_path=final_path,
                sha256=file.sha256,
                size_bytes=file.size_bytes,
                content_type=file.content_type,
            )
        )
    # Non-fatal if there are leftover files from a previous failed run; the
    # next invocation will overwrite them.
    with contextlib.suppress(OSError):
        staging_dir.rmdir()
    return promoted


async def _download_one(
    client: httpx.AsyncClient,
    job: DownloadJob,
    staging_dir: Path,
    semaphore: asyncio.Semaphore,
    rate_limiter: _HostRateLimiter,
    max_retries: int,
) -> DownloadedFile:
    last_error: Exception | None = None
    host = (urlparse(job.url).netloc or "").lower()
    async with semaphore:
        for attempt in range(max_retries + 1):
            await rate_limiter.acquire(host)
            try:
                response = await client.get(job.url, headers=job.headers or {})
            except (httpx.HTTPError, httpx.InvalidURL) as exc:
                last_error = exc
                _LOG.debug("download attempt %d failed: %s", attempt + 1, exc)
                await asyncio.sleep(_backoff_seconds(attempt))
                continue

            if response.status_code == 200:
                body = response.content
                content_type = response.headers.get("content-type")
                extension = _validated_extension(content_type, job.url, body)
                if extension is None:
                    snippet = body[:64]
                    raise DownloadError(
                        f"Risposta non immagine per {job.url} "
                        f"(content-type={content_type!r}, magic bytes={snippet!r}). "
                        "Probabile pagina di errore o login servita con HTTP 200."
                    )
                digest = hashlib.sha256(body).hexdigest()
                out_path = staging_dir / f"{job.index:03d}{extension}"
                out_path.write_bytes(body)
                return DownloadedFile(
                    index=job.index,
                    url=job.url,
                    local_path=out_path,
                    sha256=f"sha256:{digest}",
                    size_bytes=len(body),
                    content_type=content_type,
                )

            if response.status_code in _RETRYABLE_STATUSES:
                last_error = DownloadError(f"HTTP {response.status_code} su {job.url}")
                _LOG.debug(
                    "retryable HTTP %d on %s (attempt %d)",
                    response.status_code,
                    job.url,
                    attempt + 1,
                )
                await asyncio.sleep(_backoff_seconds(attempt))
                continue

            # Non-retryable HTTP error — raise with a short summary.
            # We do NOT include 200 chars of HTML boilerplate (e.g. the
            # full Cloudflare error page) because that string ends up in
            # the manifest, the diagnostics bundle and the UI errors
            # panel; readability matters more than completeness here.
            raise DownloadError(
                f"HTTP {response.status_code} su {job.url}: {_summarize_error_body(response)}"
            )

    raise DownloadError(
        f"Download fallito dopo {max_retries + 1} tentativi su {job.url}: {last_error}"
    )


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff with a small floor — 1s, 2s, 4s, 8s, …"""

    return float(2**attempt)


def _summarize_error_body(response: httpx.Response) -> str:
    """Build a short, log-safe description of a non-retryable HTTP body.

    HTML responses (typical Cloudflare error pages) collapse to
    ``[HTML <bytes>]``; everything else falls back to the first 160
    chars of the textual body.
    """

    content_type = (response.headers.get("content-type") or "").lower()
    if "html" in content_type:
        return f"[HTML {len(response.content)}B]"
    snippet = response.text[:160] if response.text else ""
    return snippet.strip() or f"[{content_type or 'opaque'} {len(response.content)}B]"


def _validated_extension(
    content_type: str | None,
    url: str,
    body: bytes,
) -> str | None:
    """Pick a file extension iff ``body`` is a real image.

    The body's **magic bytes are authoritative**. A server claiming
    ``Content-Type: image/png`` while sending HTML, JSON, or zero bytes
    has lied; honouring that header would re-open the soft-fail bug we
    closed in v0.2a.1. Content-Type and URL path are intentionally
    ignored here so the caller can't be tricked by spoofed metadata —
    if a real image format ever needs to be supported without a magic
    byte signature (e.g. ``image/svg+xml``), we'll add it explicitly to
    ``_detect_image_magic``.

    Returns ``None`` when the body doesn't start with a recognised
    image-format signature, including for empty bodies. The caller
    raises ``DownloadError`` on ``None``.
    """

    if not body:
        return None
    return _detect_image_magic(body)


def image_extension_from_magic(body: bytes) -> str | None:
    """Public wrapper for callers that already have image bytes locally.

    Browser capture receives bytes from Playwright screenshots or from a
    browser-context fetch; it should use the same magic-byte allowlist as
    the HTTP downloader without depending on a private helper.
    """

    return _detect_image_magic(body)


def _detect_image_magic(body: bytes) -> str | None:
    """Return an extension if ``body`` starts with a recognised image
    magic-byte sequence, otherwise ``None``."""

    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if body.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if body.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return ".webp"
    if body[4:8] == b"ftyp" and body[8:12] in {b"avif", b"avis"}:
        return ".avif"
    return None


def _purge_canonical_pages(output_dir: Path) -> None:
    """Remove ``NNN.<ext>`` files from ``output_dir`` in place.

    Only files whose name matches ``_CANONICAL_PAGE_RE`` are touched —
    arbitrary user files (e.g. a manually saved ``cover.jpg``) and
    subdirectories (the ``.staging`` dir, ``msrt-run.json``, …) are
    left alone.
    """

    if not output_dir.exists():
        return
    for entry in output_dir.iterdir():
        if entry.is_file() and _CANONICAL_PAGE_RE.match(entry.name):
            with contextlib.suppress(OSError):
                entry.unlink()


def find_duplicate_pages(files: Sequence[DownloadedFile]) -> list[str]:
    """Return human-readable warnings for any pages with identical SHA256.

    Returns an empty list when every page is unique. Adapters can fold
    these into their ``FetchResult.warnings`` so the user sees a concrete
    hint when a site silently serves placeholder pages.
    """

    seen: dict[str, DownloadedFile] = {}
    warnings: list[str] = []
    for file in files:
        prior = seen.get(file.sha256)
        if prior is None:
            seen[file.sha256] = file
            continue
        warnings.append(
            f"Pagina {file.local_path.name} è duplicata di "
            f"{prior.local_path.name} (sha256 identico)."
        )
    return warnings


class _HostRateLimiter:
    """Per-host minimum delay between consecutive requests.

    A request to host A doesn't block on the queue for host B: each host
    has its own asyncio.Lock plus a "last sent" timestamp. ``acquire``
    sleeps just enough so the host's quota is met, then records the new
    timestamp. With ``min_delay <= 0`` the limiter is a no-op.
    """

    def __init__(self, min_delay: float) -> None:
        self.min_delay = max(0.0, min_delay)
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_at: dict[str, float] = {}
        self._registry_lock = asyncio.Lock()

    async def acquire(self, host: str) -> None:
        if self.min_delay <= 0.0:
            return
        async with self._registry_lock:
            host_lock = self._locks.setdefault(host, asyncio.Lock())
        async with host_lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            last = self._last_at.get(host, 0.0)
            wait = (last + self.min_delay) - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = loop.time()
            self._last_at[host] = now
