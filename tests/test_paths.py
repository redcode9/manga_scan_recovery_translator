"""Project root resolution must not depend on cwd at import time.

The ``msrt.paths`` module is consulted by every Python entrypoint
(CLI, UI server, setup, secrets). If it returned the wrong root, the
user would silently read/write a different ``.env`` than the one the
rest of ``msrt`` operates on. These tests pin the resolution rules.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from msrt.paths import (
    env_file_path,
    litellm_config_path,
    project_root,
)


def test_msrt_home_override_takes_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MSRT_HOME", str(tmp_path))
    assert project_root() == tmp_path
    assert env_file_path() == tmp_path / ".env"
    assert litellm_config_path() == tmp_path / "configs" / "litellm.yaml"


def test_msrt_home_ignored_when_path_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bogus ``MSRT_HOME`` falls through to the file-based search
    instead of crashing with a non-existent dir."""

    monkeypatch.setenv("MSRT_HOME", str(tmp_path / "does-not-exist"))
    # Falls back to __file__ ancestors → the actual repo, which has
    # ``configs/litellm.yaml``. Not pinning the absolute path here so
    # the test stays portable.
    root = project_root()
    assert (root / "configs" / "litellm.yaml").exists()


def test_resolves_from_file_when_cwd_unrelated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``cwd`` has no marker (e.g. user runs ``msrt`` from
    ``/tmp``), the resolver should still find the editable-install
    project root via ``__file__``'s ancestors."""

    monkeypatch.delenv("MSRT_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    root = project_root()
    # The resolved root must contain the litellm config; that's the
    # marker the resolver looks for.
    assert (root / "configs" / "litellm.yaml").exists()
    # And it must NOT be the unrelated ``cwd`` we chdir'd into.
    assert root != tmp_path.resolve()
