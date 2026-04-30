"""Browser-based scan capture fallback.

The browser fallback is deliberately conservative: it does not bypass
human checks, does not forge tokens, and does not use stealth plugins.
It only captures manga pages that are already visible in a normal browser
session, then hands normal image files to the existing local pipeline.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urljoin

from msrt.scrape.base import FetchError
from msrt.scrape.downloader import image_extension_from_magic


@dataclass(frozen=True)
class BrowserCaptureOptions:
    viewport_width: int = 1600
    viewport_height: int = 1200
    device_scale_factor: float = 2.0
    min_width: int = 500
    min_height: int = 700
    max_pages: int = 250
    page_settle_ms: int = 800
    manual_timeout_seconds: float = 180.0
    headless: bool = False


@dataclass(frozen=True)
class ElementCandidate:
    index: int
    kind: str
    url: str | None
    x: float
    y: float
    width: float
    height: float
    natural_width: float
    natural_height: float
    visible: bool = True

    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass(frozen=True)
class BrowserCapturedPage:
    index: int
    url: str
    local_path: Path
    sha256: str
    size_bytes: int
    capture_mode: str


@dataclass(frozen=True)
class BrowserCaptureResult:
    pages: list[BrowserCapturedPage]
    warnings: list[str] = field(default_factory=list)
    manual_intervention: bool = False
    viewport_width: int = 1600
    viewport_height: int = 1200
    device_scale_factor: float = 2.0
    capture_mode: str = "browser-capture"


class BrowserCaptureEngineProtocol(Protocol):
    async def capture(self, url: str, output_dir: Path) -> BrowserCaptureResult:
        """Capture visible manga pages from ``url`` into ``output_dir``."""


_HUMAN_CHECK_PATTERNS = (
    "turnstile",
    "captcha",
    "cloudflare",
    "verify you are human",
    "checking your browser",
    "access denied",
    "sign in",
    "log in",
)

_PAGE_PROGRESS_RE = re.compile(r"\bpage\s*(\d+)\s*/\s*(\d+)\b", re.IGNORECASE)
_FRACTION_PROGRESS_RE = re.compile(r"\b(\d+)\s*/\s*(\d+)\b")


def looks_like_human_check(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in _HUMAN_CHECK_PATTERNS)


def parse_page_progress(text: str) -> tuple[int, int] | None:
    """Parse reader labels such as ``Page 1/45``.

    Returns ``None`` when the text doesn't expose a plausible current/total
    pair. The pair is only accepted when both sides are positive and current
    is not greater than total.
    """

    match = _PAGE_PROGRESS_RE.search(text) or _FRACTION_PROGRESS_RE.search(text)
    if not match:
        return None
    current, total = int(match.group(1)), int(match.group(2))
    if current <= 0 or total <= 0 or current > total:
        return None
    return current, total


def choose_scan_candidate(
    candidates: Sequence[ElementCandidate],
    options: BrowserCaptureOptions | None = None,
) -> ElementCandidate | None:
    """Return the best visible manga page candidate from DOM geometry."""

    opts = options or BrowserCaptureOptions()
    valid = [candidate for candidate in candidates if _is_valid_scan_candidate(candidate, opts)]
    if not valid:
        return None
    return max(valid, key=lambda candidate: (_candidate_score(candidate), candidate.area))


def _is_valid_scan_candidate(candidate: ElementCandidate, options: BrowserCaptureOptions) -> bool:
    if not candidate.visible:
        return False
    width = max(candidate.width, candidate.natural_width)
    height = max(candidate.height, candidate.natural_height)
    if width < options.min_width or height < options.min_height:
        return False
    ratio = height / max(width, 1)
    # Single manga pages are usually portrait; double-spread/landscape pages
    # can be wider, so the lower bound is intentionally permissive.
    return 0.45 <= ratio <= 4.5


def _candidate_score(candidate: ElementCandidate) -> tuple[int, float, float]:
    kind_score = 2 if candidate.kind == "img" else 1 if candidate.kind == "canvas" else 0
    natural_area = candidate.natural_width * candidate.natural_height
    return kind_score, natural_area, candidate.area


class BrowserCaptureEngine:
    def __init__(self, options: BrowserCaptureOptions | None = None) -> None:
        self.options = options or BrowserCaptureOptions()

    async def capture(self, url: str, output_dir: Path) -> BrowserCaptureResult:
        """Capture visible manga pages from ``url`` into ``output_dir``.

        Playwright is imported lazily so normal MangaDex/local workflows do
        not require the optional ``scrape`` extra at import time.
        """

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise FetchError(
                "Playwright non è installato. Esegui `uv sync --all-extras` "
                "e `uv run playwright install chromium` per usare browser-capture."
            ) from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        warnings: list[str] = []
        manual_intervention = False
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.options.headless)
            context = await browser.new_context(
                viewport={
                    "width": self.options.viewport_width,
                    "height": self.options.viewport_height,
                },
                device_scale_factor=self.options.device_scale_factor,
                user_agent=(
                    "msrt/0.0 browser-capture (best-effort scan capture; no stealth or bypass)"
                ),
            )
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                await page.wait_for_timeout(self.options.page_settle_ms)
                text = await _safe_text_content(page)
                if looks_like_human_check(text):
                    manual_intervention = True
                    warnings.append(
                        "Verifica/login rilevati: completa manualmente nel browser; "
                        "msrt riprenderà quando una scan valida è visibile."
                    )
                    await self._wait_for_visible_scan(page)

                pages = await self._capture_visible_pages(page, output_dir)
            finally:
                await context.close()
                await browser.close()

        return BrowserCaptureResult(
            pages=pages,
            warnings=warnings,
            manual_intervention=manual_intervention,
            viewport_width=self.options.viewport_width,
            viewport_height=self.options.viewport_height,
            device_scale_factor=self.options.device_scale_factor,
        )

    async def _wait_for_visible_scan(self, page: Any) -> None:
        deadline = asyncio.get_running_loop().time() + self.options.manual_timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            candidates = await _extract_element_candidates(page)
            if choose_scan_candidate(candidates, self.options) is not None:
                return
            await page.wait_for_timeout(1000)
        raise FetchError(
            "Nessuna scan visibile dopo l'attesa manuale. "
            "Non posso proseguire senza una pagina manga visibile nel browser."
        ) from None

    async def _capture_visible_pages(
        self, page: Any, output_dir: Path
    ) -> list[BrowserCapturedPage]:
        pages: list[BrowserCapturedPage] = []
        seen_hashes: set[str] = set()
        page_progress = parse_page_progress(await _safe_text_content(page))
        total_pages = page_progress[1] if page_progress else None

        for index in range(1, self.options.max_pages + 1):
            captured = await self._capture_current_page(page, output_dir, index)
            if captured.sha256 in seen_hashes:
                captured.local_path.unlink(missing_ok=True)
                break
            seen_hashes.add(captured.sha256)
            pages.append(captured)

            if total_pages is not None and index >= total_pages:
                break
            advanced = await _advance_reader(page)
            if not advanced:
                break
            await page.wait_for_timeout(self.options.page_settle_ms)

        if not pages:
            raise FetchError("Browser capture non ha trovato scan valide nella pagina.")
        return pages

    async def _capture_current_page(
        self,
        page: Any,
        output_dir: Path,
        index: int,
    ) -> BrowserCapturedPage:
        candidates = await _extract_element_candidates(page)
        candidate = choose_scan_candidate(candidates, self.options)
        if candidate is None:
            raise FetchError("Nessun elemento scan valido trovato nel reader.")

        if candidate.url:
            raw = await _try_browser_context_download(page, candidate.url)
            if raw is not None:
                return _write_capture_bytes(
                    raw,
                    output_dir=output_dir,
                    index=index,
                    source_url=candidate.url,
                    capture_mode="browser-raw",
                )

        locator = page.locator("img, canvas").nth(candidate.index)
        screenshot = await locator.screenshot(type="png")
        return _write_capture_bytes(
            screenshot,
            output_dir=output_dir,
            index=index,
            source_url=page.url,
            capture_mode="browser-element-screenshot",
        )


async def _safe_text_content(page: Any) -> str:
    try:
        text = await page.locator("body").inner_text(timeout=3000)
    except Exception:
        return ""
    return str(text)


async def _extract_element_candidates(page: Any) -> list[ElementCandidate]:
    raw: list[dict[str, object]] = await page.evaluate(
        """
        () => Array.from(document.querySelectorAll('img, canvas')).map((el, index) => {
          const rect = el.getBoundingClientRect();
          const dataset = el.dataset || {};
          const url = el.currentSrc || el.src || dataset.src || dataset.original ||
            el.getAttribute('data-src') || el.getAttribute('data-original') || null;
          return {
            index,
            kind: el.tagName.toLowerCase(),
            url,
            x: rect.x + window.scrollX,
            y: rect.y + window.scrollY,
            width: rect.width,
            height: rect.height,
            naturalWidth: el.naturalWidth || el.width || rect.width,
            naturalHeight: el.naturalHeight || el.height || rect.height,
            visible: rect.width > 0 && rect.height > 0 &&
              window.getComputedStyle(el).visibility !== 'hidden' &&
              window.getComputedStyle(el).display !== 'none'
          };
        })
        """
    )
    candidates: list[ElementCandidate] = []
    for item in raw:
        candidates.append(
            ElementCandidate(
                index=_to_int(item.get("index"), default=0),
                kind=str(item.get("kind", "")),
                url=_normalise_candidate_url(page.url, item.get("url")),
                x=_to_float(item.get("x"), default=0.0),
                y=_to_float(item.get("y"), default=0.0),
                width=_to_float(item.get("width"), default=0.0),
                height=_to_float(item.get("height"), default=0.0),
                natural_width=_to_float(item.get("naturalWidth"), default=0.0),
                natural_height=_to_float(item.get("naturalHeight"), default=0.0),
                visible=bool(item.get("visible", False)),
            )
        )
    return candidates


def _to_int(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return default


def _to_float(value: object, *, default: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _normalise_candidate_url(base_url: str, value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    if value.startswith("data:"):
        return None
    return urljoin(base_url, value)


async def _try_browser_context_download(page: Any, url: str) -> bytes | None:
    try:
        response = await page.request.get(url, headers={"Referer": page.url}, timeout=30_000)
        if not response.ok:
            return None
        body = await response.body()
    except Exception:
        return None
    return bytes(body) if image_extension_from_magic(bytes(body)) else None


def _write_capture_bytes(
    body: bytes,
    *,
    output_dir: Path,
    index: int,
    source_url: str,
    capture_mode: str,
) -> BrowserCapturedPage:
    extension = image_extension_from_magic(body)
    if extension is None:
        raise FetchError("Browser capture ha prodotto byte non immagine.")
    digest = hashlib.sha256(body).hexdigest()
    local_path = output_dir / f"{index:03d}{extension}"
    local_path.write_bytes(body)
    return BrowserCapturedPage(
        index=index,
        url=source_url,
        local_path=local_path,
        sha256=f"sha256:{digest}",
        size_bytes=len(body),
        capture_mode=capture_mode,
    )


async def _advance_reader(page: Any) -> bool:
    clicked = await page.evaluate(
        """
        () => {
          const candidates = Array.from(document.querySelectorAll('button, a, [role="button"]'));
          const next = candidates.find((el) => {
            const label = [
              el.getAttribute('aria-label'),
              el.getAttribute('title'),
              el.textContent
            ].filter(Boolean).join(' ').toLowerCase();
            return /next|page\\s*next|\\u203a|\\u00bb|chevron-right|arrow-right/.test(label);
          });
          if (next) {
            next.click();
            return true;
          }
          return false;
        }
        """
    )
    if bool(clicked):
        return True
    try:
        await page.keyboard.press("ArrowRight")
    except Exception:
        return False
    return True
