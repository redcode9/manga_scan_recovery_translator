"""Library reader: scans the output directory for ``msrt-run.json``
manifests and turns them into UI-friendly entries.

The manifest format is the source of truth (it's what the pipeline
emits). We never re-derive series/chapter from the file system —
that would diverge from what the run actually thought it produced.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from msrt.ui_server.schemas import LibraryEntry

_LOG = logging.getLogger(__name__)
_EPOCH = datetime.fromtimestamp(0, tz=UTC)


def scan_library(out_dir: Path) -> list[LibraryEntry]:
    """Return every translated chapter known to ``out_dir``.

    Looks for ``msrt-run.json`` files at the top level (single-job
    layout used by ``run-local`` / single-URL ``run``). Batch runs
    write per-chapter manifests inside subdirs that the user can also
    surface — but per v0.4a we only handle the canonical case to keep
    the contract simple. v0.4b will extend this when batch jobs land
    a per-chapter manifest folder.
    """

    entries: list[LibraryEntry] = []
    if not out_dir.exists():
        return entries

    for manifest_path in _iter_manifests(out_dir):
        entry = _load_manifest(manifest_path)
        if entry is not None:
            entries.append(entry)

    entries.sort(
        key=lambda e: e.finished_at or e.started_at or _EPOCH,
        reverse=True,
    )
    return entries


def load_entry(manifest_id: str, *, out_dir: Path) -> LibraryEntry | None:
    """Look up a single library entry by its deterministic manifest_id."""

    for entry in scan_library(out_dir):
        if entry.manifest_id == manifest_id:
            return entry
    return None


def _iter_manifests(out_dir: Path) -> list[Path]:
    """Find candidate manifest files. Limited depth to avoid sweeping
    in caches like ``.msrt-fetch`` and ``.msrt-tmp``."""

    candidates: list[Path] = []
    direct = out_dir / "msrt-run.json"
    if direct.is_file():
        candidates.append(direct)
    # One level deeper is enough for the single-chapter layout that
    # ``run-local`` produces. Subdirs starting with "." (cache, staging,
    # tmp) are skipped on purpose.
    for child in out_dir.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        manifest = child / "msrt-run.json"
        if manifest.is_file():
            candidates.append(manifest)
    return candidates


def _load_manifest(path: Path) -> LibraryEntry | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _LOG.warning("Cannot read manifest %s: %s", path, exc)
        return None
    if not isinstance(payload, dict):
        return None

    metadata = payload.get("metadata") or {}
    model = payload.get("model") or {}
    fetch = payload.get("fetch") or {}

    return LibraryEntry(
        manifest_id=_manifest_id(path),
        manifest_path=str(path.resolve()),
        series=metadata.get("series") or None,
        chapter_number=metadata.get("chapter") or None,
        chapter_title=metadata.get("title") or None,
        language_target=metadata.get("language_target") or None,
        output_files=list(payload.get("output_files") or []),
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        model_alias=model.get("alias") if isinstance(model, dict) else None,
        provider=model.get("provider") if isinstance(model, dict) else None,
        strategy=fetch.get("strategy") if isinstance(fetch, dict) else None,
        errors=list(payload.get("errors") or []),
        warnings=list(payload.get("warnings") or []),
    )


def _manifest_id(path: Path) -> str:
    """Stable, short id derived from the absolute manifest path so the
    UI can address an entry without exposing filesystem layout."""

    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()
    return digest[:12]
