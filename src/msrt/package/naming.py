"""Image ordering helpers for manga pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_NATURAL_RE = re.compile(r"(\d+)")


@dataclass(frozen=True)
class PageOrder:
    files: list[Path]
    warnings: list[str]


def natural_sort_key(path: Path) -> tuple[object, ...]:
    parts: list[object] = []
    for part in _NATURAL_RE.split(path.name.lower()):
        if part.isdigit():
            parts.append(int(part))
        else:
            parts.append(part)
    return tuple(parts)


def image_files(directory: Path, *, natural_sort: bool = True) -> PageOrder:
    files = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    ordered = sorted(
        files, key=natural_sort_key if natural_sort else lambda path: path.name.lower()
    )
    return PageOrder(files=ordered, warnings=_order_warnings(ordered))


def _order_warnings(files: list[Path]) -> list[str]:
    warnings: list[str] = []
    if not files:
        warnings.append("Nessuna immagine supportata trovata.")
        return warnings

    prefixes = {_NATURAL_RE.sub("#", path.stem.lower()) for path in files}
    if len(prefixes) > 3:
        warnings.append("Pattern nomi pagina molto variabile: controllare l'ordine generato.")

    numeric_values: list[int] = []
    for path in files:
        match = _NATURAL_RE.search(path.stem)
        if match:
            numeric_values.append(int(match.group(1)))
    if len(numeric_values) >= 3:
        expected = set(range(min(numeric_values), max(numeric_values) + 1))
        missing = sorted(expected - set(numeric_values))
        if missing:
            preview = ", ".join(str(value) for value in missing[:10])
            warnings.append(f"Sequenza numerica con gap: mancano {preview}.")

    return warnings
