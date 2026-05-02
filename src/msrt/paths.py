"""Project / app data path resolution.

The CLI and the UI server can be invoked from any working directory.
Without a centralised resolver, each call site falls back to ``cwd``,
which means a user who runs ``msrt ui`` from ``~/Documents`` would
read/write a different ``.env`` and ``configs/litellm.yaml`` than one
who runs it from the repo root.

Resolution order (first match wins):

1. ``MSRT_HOME`` env var, when set and pointing to an existing dir.
2. The first ancestor of ``__file__`` (the installed package
   location) containing a ``configs/litellm.yaml`` — this catches
   editable installs (``uv sync``) where the source tree IS the
   project root.
3. The first ancestor of ``cwd`` containing a ``configs/litellm.yaml``.
4. Same two scans, falling back to a less-specific ``pyproject.toml``
   marker for projects that have been moved/renamed and lost the
   ``configs/`` directory.
5. ``cwd`` as the last-resort fallback so existing behaviour is
   preserved when the user genuinely wants paths relative to where
   they ran the command.
"""

from __future__ import annotations

import os
from pathlib import Path

_MARKER = "configs/litellm.yaml"
_FALLBACK_MARKER = "pyproject.toml"


def _ancestors(path: Path) -> tuple[Path, ...]:
    return (path, *path.parents)


def _search(starts: tuple[Path, ...], marker: str) -> Path | None:
    seen: set[Path] = set()
    for start in starts:
        for candidate in _ancestors(start.resolve()):
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / marker).exists():
                return candidate
    return None


def project_root() -> Path:
    """Resolve the project root deterministically.

    Not cached: we re-resolve every call so a test that swaps
    ``cwd`` via ``monkeypatch.chdir`` gets isolated state.
    """

    override = os.environ.get("MSRT_HOME")
    if override:
        path = Path(override).expanduser()
        if path.is_dir():
            return path

    file_root = Path(__file__).resolve().parent  # src/msrt
    cwd = Path.cwd()
    starts = (file_root, cwd)

    found = _search(starts, _MARKER) or _search(starts, _FALLBACK_MARKER)
    if found is not None:
        return found
    return cwd.resolve()


def env_file_path() -> Path:
    """Absolute path to the ``.env`` file the CLI and UI read/write."""

    return project_root() / ".env"


def litellm_config_path() -> Path:
    """Absolute path to the LiteLLM proxy configuration."""

    return project_root() / "configs" / "litellm.yaml"


def frontend_dist_dir() -> Path:
    """Where the React bundle is built. Caller decides whether to use
    or fall back if the directory does not exist yet."""

    return project_root() / "apps" / "desktop" / "dist"


def frontend_source_dir() -> Path:
    """Source tree for the React app. Used by the staleness check."""

    return project_root() / "apps" / "desktop"
