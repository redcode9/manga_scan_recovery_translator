"""Chapter selectors for ``msrt run --all-chapters``.

The CLI surfaces three selectors that constrain which entries from
``ChapterScraper.list_chapters()`` end up being processed:

* ``--range "50-51"`` keeps every chapter whose ``chapter_number`` falls
  inside the inclusive numeric interval. Non-numeric chapter numbers
  (``"extra"``, ``"omake"``, …) are dropped from the range filter.
* ``--chapters "50,51,51.1"`` keeps the listed chapters by exact string
  match (whitespace-trimmed). This is the only way to pick something
  like ``"51.1"`` precisely without sweeping in neighbours.
* ``--limit N`` keeps the first ``N`` entries *after* the previous two
  filters apply. Useful for "process the first 2 chapters of this series
  to validate the pipeline before the long batch".

All three are composable. Functions are kept pure (no I/O, no asyncio)
so they can be unit-tested without the CLI in the loop.
"""

from __future__ import annotations

import math

from msrt.scrape.base import ChapterLink


def parse_chapter_range(raw: str) -> tuple[float, float]:
    """Parse a ``"50-51"`` style range into ``(start, end)`` inclusive.

    Negative numbers, decimals and reversed ranges are rejected with
    a ``ValueError`` carrying a user-readable message.
    """

    text = raw.strip()
    if not text:
        raise ValueError("--range vuoto: atteso 'start-end' (es. '50-51').")
    parts = text.split("-")
    if len(parts) != 2:
        raise ValueError(
            f"--range non valido: {raw!r}. Atteso esattamente uno '-' (es. '50-51' o '50.5-51.0')."
        )
    try:
        start = float(parts[0])
        end = float(parts[1])
    except ValueError as exc:
        raise ValueError(
            f"--range con estremi non numerici: {raw!r}. Atteso numeri tipo '50-51' o '50.5-51.0'."
        ) from exc
    if not math.isfinite(start) or not math.isfinite(end):
        raise ValueError(f"--range con estremi non finiti: {raw!r}. Usa numeri reali tipo '50-51'.")
    if start > end:
        raise ValueError(f"--range invertito: {raw!r}. start={start} > end={end}.")
    return start, end


def parse_chapter_list(raw: str) -> set[str]:
    """Parse ``"50, 51, 51.1"`` into a set of canonical chapter strings.

    Empty entries (from trailing commas or doubles) are silently ignored.
    A completely-empty list raises ``ValueError`` so the user notices
    that ``--chapters ","`` is meaningless.
    """

    items = {item.strip() for item in raw.split(",")}
    items.discard("")
    if not items:
        raise ValueError(f"--chapters senza valori: {raw!r}.")
    return items


def select_chapters(
    chapters: list[ChapterLink],
    *,
    range_filter: tuple[float, float] | None = None,
    chapter_list: set[str] | None = None,
    limit: int | None = None,
) -> list[ChapterLink]:
    """Apply the selectors in the documented order.

    Order matters: ``--limit`` is applied **after** range/chapters so
    "first 2 chapters of range 50-100" works the way the user expects.
    Original order from ``list_chapters`` is preserved within each
    selection — adapters are responsible for sorting.
    """

    selected = list(chapters)
    if range_filter is not None:
        start, end = range_filter
        kept: list[ChapterLink] = []
        for chapter in selected:
            number = _chapter_number_as_float(chapter.chapter_number)
            if number is None:
                # Non-numeric chapter (e.g. "extra"): skipped by --range.
                continue
            if start <= number <= end:
                kept.append(chapter)
        selected = kept
    if chapter_list is not None:
        # Whitespace-trim both sides; case-sensitive to mirror the
        # source-of-truth chapter numbers, which are usually plain digits.
        wanted = {item.strip() for item in chapter_list}
        selected = [chapter for chapter in selected if chapter.chapter_number.strip() in wanted]
    if limit is not None:
        if limit < 1:
            raise ValueError(f"--limit deve essere >= 1, ricevuto {limit}.")
        selected = selected[:limit]
    return selected


def _chapter_number_as_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
