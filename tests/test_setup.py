"""Tests for the setup wizard building blocks."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from msrt import setup as msrt_setup
from msrt.config import MODEL_ALIASES
from msrt.setup import (
    PROVIDER_CATALOG,
    _apply_env_to_process,
    _format_value,
    load_env,
    provider_alias_lookup,
    run_setup,
    save_env,
)


def test_load_env_returns_empty_when_missing(tmp_path: Path) -> None:
    assert load_env(tmp_path / "missing.env") == {}


def test_load_env_parses_simple_and_quoted_values(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "# comment\nFOO=bar\nBAZ='hello world'\nQUOTED=\"with#hash\"\n",
        encoding="utf-8",
    )
    values = load_env(path)
    assert values["FOO"] == "bar"
    assert values["BAZ"] == "hello world"
    assert values["QUOTED"] == "with#hash"


def test_save_env_preserves_comments_and_other_keys(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "# top comment\nFOO=old\nBAR=keep\n# bottom\n",
        encoding="utf-8",
    )

    save_env(path, {"FOO": "new", "BAZ": "added"})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines == [
        "# top comment",
        "FOO=new",
        "BAR=keep",
        "# bottom",
        "BAZ=added",
    ]


def test_save_env_round_trip_simple(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    payload = {"A": "1", "B": "two", "C": "three-words"}
    save_env(path, payload)
    assert load_env(path) == payload


def test_save_env_round_trip_with_special_chars(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    payload = {
        "WITH_SPACE": "value with spaces",
        "WITH_HASH": "no#comment",
        "WITH_DOLLAR": "raw$dollar",
        "WITH_QUOTE": "she said hello",
    }
    save_env(path, payload)
    assert load_env(path) == payload


def test_format_value_simple_no_quote() -> None:
    assert _format_value("simple") == "simple"
    assert _format_value("/path/to/python") == "/path/to/python"


def test_format_value_with_space_uses_double_quotes() -> None:
    formatted = _format_value("a b c")
    assert formatted.startswith('"') and formatted.endswith('"')
    assert "a b c" in formatted


def test_format_value_escapes_internal_double_quote() -> None:
    formatted = _format_value('he said "hi"')
    assert formatted.startswith('"') and formatted.endswith('"')
    assert '\\"' in formatted


def test_provider_catalog_aliases_match_known_aliases() -> None:
    for choice in PROVIDER_CATALOG:
        assert choice.alias in MODEL_ALIASES, f"alias {choice.alias} non in MODEL_ALIASES"


def test_provider_alias_lookup_helper() -> None:
    lookup = provider_alias_lookup()
    assert set(lookup.keys()) == {p.alias for p in PROVIDER_CATALOG}
    assert lookup["gpt"].env_var == "OPENAI_API_KEY"


def test_run_setup_yes_skips_interactive_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / ".env.example"
    template.write_text(
        "# example\nOPENAI_API_KEY=\nANTHROPIC_API_KEY=\nMITR_BIN_PATH=\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(msrt_setup.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(
        msrt_setup,
        "_maybe_start_server",
        lambda _cons, _root: None,
    )
    monkeypatch.setattr(
        msrt_setup,
        "_maybe_paid_smoke",
        lambda _cons, _alias, *, yes: True,
    )

    code = run_setup(
        project_root=tmp_path,
        yes=True,
        install_mitr=False,
        start_server=False,
        paid_smoke=False,
    )
    assert code == 0
    env_path = tmp_path / ".env"
    assert env_path.exists()
    values = load_env(env_path)
    assert values.get("MSRT_MODEL") == "gpt"
    assert values.get("OPENAI_API_KEY", "") == ""


def test_run_setup_yes_keeps_existing_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "MSRT_MODEL=sonnet\nANTHROPIC_API_KEY=sk-existing\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(msrt_setup.shutil, "which", lambda _: "/usr/bin/uv")

    code = run_setup(
        project_root=tmp_path,
        yes=True,
        install_mitr=False,
        start_server=False,
        paid_smoke=False,
    )

    assert code == 0
    values = load_env(env_path)
    assert values["MSRT_MODEL"] == "sonnet"
    assert values["ANTHROPIC_API_KEY"] == "sk-existing"


def test_apply_env_to_process_exports_non_empty_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MSRT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    _apply_env_to_process({"MSRT_MODEL": "gpt", "OPENAI_API_KEY": "sk-test", "EMPTY": ""})

    assert os.environ["MSRT_MODEL"] == "gpt"
    assert os.environ["OPENAI_API_KEY"] == "sk-test"
    assert "EMPTY" not in os.environ


def test_run_setup_fails_when_paid_smoke_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text(
        "MSRT_MODEL=gpt\nOPENAI_API_KEY=sk-test\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(msrt_setup.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(
        msrt_setup,
        "_maybe_paid_smoke",
        lambda _cons, _alias, *, yes: False,
    )

    code = run_setup(
        project_root=tmp_path,
        yes=True,
        install_mitr=False,
        start_server=False,
        paid_smoke=True,
    )

    assert code == 1


def test_run_setup_fails_when_uv_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(msrt_setup.shutil, "which", lambda _: None)
    code = run_setup(
        project_root=tmp_path,
        yes=True,
        install_mitr=False,
        start_server=False,
        paid_smoke=False,
    )
    assert code == 1
