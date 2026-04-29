"""LiteLLM proxy lifecycle helpers (start/stop/status as a local subprocess)."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from msrt.config import Settings
from msrt.translate.litellm_proxy import check_litellm_health


class LiteLLMUnavailableError(RuntimeError):
    """Raised when the litellm binary is not found or fails to spawn."""


@dataclass(frozen=True)
class ServerStatus:
    running: bool
    pid: int | None
    healthy: bool
    message: str


def pid_file(settings: Settings) -> Path:
    return settings.cache_dir / "litellm.pid"


def log_file(settings: Settings) -> Path:
    return settings.cache_dir / "litellm.log"


def find_litellm_binary() -> str | None:
    """Locate the litellm CLI, preferring the venv next to the running Python."""

    venv_candidate = Path(sys.executable).parent / "litellm"
    if venv_candidate.exists() and os.access(venv_candidate, os.X_OK):
        return str(venv_candidate)
    return shutil.which("litellm")


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_pid(settings: Settings) -> int | None:
    pid_path = pid_file(settings)
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def litellm_status(settings: Settings) -> ServerStatus:
    pid = _read_pid(settings)
    if pid is None:
        return ServerStatus(
            running=False,
            pid=None,
            healthy=False,
            message=f"LiteLLM non in esecuzione (no {pid_file(settings)}).",
        )
    if not _is_running(pid):
        pid_file(settings).unlink(missing_ok=True)
        return ServerStatus(
            running=False,
            pid=pid,
            healthy=False,
            message=f"PID {pid} non più attivo (PID file rimosso).",
        )
    health = check_litellm_health(settings)
    return ServerStatus(running=True, pid=pid, healthy=health.ok, message=health.message)


def start_litellm(
    settings: Settings,
    config_path: Path,
    *,
    wait_seconds: float = 15.0,
    poll_interval: float = 0.5,
) -> ServerStatus:
    """Start the LiteLLM proxy as a background subprocess.

    Idempotent: if a healthy instance is already running according to the PID
    file, return its status without spawning a new process.
    """

    existing = litellm_status(settings)
    if existing.running:
        return existing

    binary = find_litellm_binary()
    if binary is None:
        raise LiteLLMUnavailableError(
            "Binary 'litellm' non trovato. Installa l'extra runtime con "
            "`uv sync --all-extras` (oppure `uv sync --extra runtime`)."
        )
    if not config_path.exists():
        raise FileNotFoundError(f"Config LiteLLM non trovato: {config_path}")

    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_file(settings)
    log_handle = log_path.open("a", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [binary, "--config", str(config_path), "--port", str(settings.litellm_port)],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
            start_new_session=True,
        )
    except OSError as exc:
        log_handle.close()
        raise LiteLLMUnavailableError(f"Impossibile avviare litellm: {exc}") from exc

    pid_file(settings).write_text(str(process.pid), encoding="utf-8")

    deadline = time.monotonic() + wait_seconds
    last_message = "LiteLLM avviato; healthcheck in attesa."
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_handle.close()
            pid_file(settings).unlink(missing_ok=True)
            raise RuntimeError(
                "LiteLLM è terminato durante l'avvio "
                f"(exit {process.returncode}). Vedi log: {log_path}"
            )
        health = check_litellm_health(settings, timeout=1.0)
        if health.ok:
            return ServerStatus(
                running=True,
                pid=process.pid,
                healthy=True,
                message=health.message,
            )
        last_message = health.message
        time.sleep(poll_interval)

    return ServerStatus(
        running=True,
        pid=process.pid,
        healthy=False,
        message=(
            f"LiteLLM avviato (PID {process.pid}) ma healthcheck non risponde "
            f"entro {wait_seconds:.0f}s: {last_message}. Log: {log_path}"
        ),
    )


def stop_litellm(
    settings: Settings,
    *,
    timeout: float = 5.0,
    poll_interval: float = 0.2,
) -> bool:
    """Stop the LiteLLM proxy. Returns True if a running process was stopped."""

    pid_path = pid_file(settings)
    pid = _read_pid(settings)
    if pid is None:
        pid_path.unlink(missing_ok=True)
        return False
    if not _is_running(pid):
        pid_path.unlink(missing_ok=True)
        return False

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pid_path.unlink(missing_ok=True)
        return False

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_running(pid):
            pid_path.unlink(missing_ok=True)
            return True
        time.sleep(poll_interval)

    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)
    pid_path.unlink(missing_ok=True)
    return True
