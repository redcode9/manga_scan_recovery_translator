"""Tests for the LiteLLM proxy lifecycle helpers."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from msrt import server
from msrt.config import Settings
from msrt.translate.litellm_proxy import ProxyHealth


def _settings_with_cache(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, cache_dir=tmp_path / "cache")  # type: ignore[call-arg]


def test_status_when_no_pid_file(tmp_path: Path) -> None:
    settings = _settings_with_cache(tmp_path)
    status = server.litellm_status(settings)
    assert status.running is False
    assert status.pid is None


def test_status_cleans_stale_pid_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with_cache(tmp_path)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    pid_path = server.pid_file(settings)
    pid_path.write_text("999999", encoding="utf-8")
    monkeypatch.setattr(server, "_is_running", lambda _pid: False)

    status = server.litellm_status(settings)
    assert status.running is False
    assert status.pid == 999999
    assert not pid_path.exists()


def test_start_raises_when_binary_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with_cache(tmp_path)
    monkeypatch.setattr(server, "find_litellm_binary", lambda: None)

    with pytest.raises(server.LiteLLMUnavailableError):
        server.start_litellm(settings, tmp_path / "missing-config.yaml")


def test_start_raises_when_config_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with_cache(tmp_path)
    monkeypatch.setattr(server, "find_litellm_binary", lambda: "/usr/bin/true")

    with pytest.raises(FileNotFoundError):
        server.start_litellm(settings, tmp_path / "missing-config.yaml")


def test_start_returns_existing_status_when_already_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings_with_cache(tmp_path)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    server.pid_file(settings).write_text("12345", encoding="utf-8")
    monkeypatch.setattr(server, "_is_running", lambda _pid: True)
    monkeypatch.setattr(
        server,
        "check_litellm_health",
        lambda _settings, timeout=2.0: ProxyHealth(True, "mocked healthy"),
    )

    status = server.start_litellm(settings, tmp_path / "any-config.yaml")
    assert status.running is True
    assert status.pid == 12345
    assert status.healthy is True


def test_stop_returns_false_when_not_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings_with_cache(tmp_path)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    server.pid_file(settings).write_text("999999", encoding="utf-8")
    monkeypatch.setattr(server, "_is_running", lambda _pid: False)

    assert server.stop_litellm(settings) is False
    assert not server.pid_file(settings).exists()


def test_stop_signals_running_pid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with_cache(tmp_path)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    server.pid_file(settings).write_text("4242", encoding="utf-8")

    running = {4242: True}
    signals: list[int] = []

    def fake_is_running(pid: int) -> bool:
        return running.get(pid, False)

    def fake_kill(pid: int, sig: int) -> None:
        signals.append(sig)
        running[pid] = False

    monkeypatch.setattr(server, "_is_running", fake_is_running)
    monkeypatch.setattr(server.os, "kill", fake_kill)

    assert server.stop_litellm(settings, timeout=0.2, poll_interval=0.05) is True
    assert signals[0] == server.signal.SIGTERM
    assert not server.pid_file(settings).exists()


def test_find_litellm_binary_uses_venv_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    venv_bin = tmp_path / "bin"
    venv_bin.mkdir()
    binary = venv_bin / "litellm"
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)

    fake_executable = venv_bin / "python"
    fake_executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_executable.chmod(0o755)

    monkeypatch.setattr(server.sys, "executable", str(fake_executable))
    # In caso di fallback, non deve risalire a PATH globale
    monkeypatch.setattr(server.shutil, "which", lambda _: "/should/not/be/used")

    assert server.find_litellm_binary() == str(binary)


def test_find_litellm_binary_falls_back_to_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_executable = tmp_path / "python"
    fake_executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_executable.chmod(0o755)
    monkeypatch.setattr(server.sys, "executable", str(fake_executable))
    monkeypatch.setattr(server.shutil, "which", lambda _: "/global/litellm")

    assert server.find_litellm_binary() == "/global/litellm"


def test_find_litellm_binary_returns_none_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_executable = tmp_path / "python"
    fake_executable.write_text("", encoding="utf-8")
    fake_executable.chmod(0o755)
    monkeypatch.setattr(server.sys, "executable", str(fake_executable))
    monkeypatch.setattr(server.shutil, "which", lambda _: None)

    assert server.find_litellm_binary() is None


def test_log_file_path(tmp_path: Path) -> None:
    settings = _settings_with_cache(tmp_path)
    assert server.log_file(settings) == settings.cache_dir / "litellm.log"


def test_pid_file_path(tmp_path: Path) -> None:
    settings = _settings_with_cache(tmp_path)
    assert server.pid_file(settings) == settings.cache_dir / "litellm.pid"


# Sanity: il helper os.kill che usiamo accetta signal=0 per probing — non lo
# testiamo direttamente per evitare side effect, ma documentiamo il contratto.
_ = os.kill
