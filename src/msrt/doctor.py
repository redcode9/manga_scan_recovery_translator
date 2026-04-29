"""Environment diagnostics for msrt."""

from __future__ import annotations

import importlib.util
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from msrt import __version__
from msrt.config import Settings, resolve_model_alias
from msrt.server import find_litellm_binary, litellm_status
from msrt.translate.litellm_proxy import check_litellm_health, run_litellm_paid_smoke


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    message: str


def run_doctor(
    *,
    model: str = "gpt",
    font_path: Path | None = None,
    paid_smoke: bool = False,
    verbose: bool = False,
) -> list[DoctorCheck]:
    settings = Settings()
    checks = [
        _python_check(),
        _disk_check(settings),
        _model_key_check(settings, model),
        _font_check(font_path),
        _hardware_check(),
        _mitr_check(settings),
        _litellm_binary_check(),
        _litellm_check(settings),
        DoctorCheck("msrt", "ok", f"msrt {__version__}"),
    ]
    if paid_smoke:
        checks.append(_paid_smoke_check(settings, model))
    if verbose:
        checks.append(DoctorCheck("config", "info", f"cache_dir={settings.cache_dir}"))
    return checks


def _python_check() -> DoctorCheck:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info < (3, 11) or sys.version_info >= (3, 13):
        return DoctorCheck("python", "fail", f"Python {version}; richiesto >=3.11,<3.13")
    return DoctorCheck("python", "ok", f"Python {version}")


def _disk_check(settings: Settings) -> DoctorCheck:
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(settings.cache_dir)
    free_gb = usage.free / (1024**3)
    if free_gb < 4:
        return DoctorCheck("cache", "fail", f"Spazio libero cache insufficiente: {free_gb:.1f} GB")
    return DoctorCheck("cache", "ok", f"Spazio libero cache: {free_gb:.1f} GB")


def _model_key_check(settings: Settings, model: str) -> DoctorCheck:
    provider, resolved, env_name = resolve_model_alias(model)
    if provider == "local":
        return DoctorCheck("model", "warn", f"{model} è locale; supporto previsto in v0.7.")
    if env_name is None:
        return DoctorCheck("model", "warn", f"Alias custom {model}; chiave API non verificabile.")
    if settings.api_key_for_env_name(env_name):
        return DoctorCheck("model", "ok", f"{model} -> {resolved}; {env_name} presente.")
    return DoctorCheck("model", "fail", f"{model} -> {resolved}; manca {env_name}.")


def _font_check(font_path: Path | None) -> DoctorCheck:
    if font_path is None:
        return DoctorCheck("font", "warn", "--font-path non impostato; MITR userà il font default.")
    if font_path.exists():
        return DoctorCheck("font", "ok", f"Font trovato: {font_path}")
    return DoctorCheck("font", "fail", f"Font non trovato: {font_path}")


def _hardware_check() -> DoctorCheck:
    torch_spec = importlib.util.find_spec("torch")
    if torch_spec is None:
        return DoctorCheck(
            "hardware",
            "warn",
            "torch non installato nel venv msrt; MITR decide CPU/GPU nel suo venv.",
        )
    try:
        import torch  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - defensive around optional dependency
        return DoctorCheck("hardware", "warn", f"torch presente ma non importabile: {exc}")

    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return DoctorCheck("hardware", "ok", "MPS disponibile.")
    if torch.cuda.is_available():
        return DoctorCheck("hardware", "ok", "CUDA disponibile.")
    return DoctorCheck("hardware", "warn", "Solo CPU rilevata.")


def _mitr_check(settings: Settings) -> DoctorCheck:
    command = settings.mitr_bin_path or "python -m manga_translator"
    if command.startswith("http://") or command.startswith("https://"):
        return DoctorCheck(
            "mitr", "warn", f"MITR HTTP configurato ({command}); ping HTTP previsto in fase server."
        )
    try:
        completed = subprocess.run(
            [*shlex.split(command), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        return DoctorCheck("mitr", "fail", f"MITR non trovato: {command}")
    except subprocess.TimeoutExpired:
        return DoctorCheck("mitr", "fail", f"MITR timeout su: {command}")
    if completed.returncode != 0:
        return DoctorCheck(
            "mitr", "fail", f"MITR non disponibile ({command}): {completed.stderr.strip()}"
        )
    first_line = (
        (completed.stdout or completed.stderr).splitlines()[0]
        if (completed.stdout or completed.stderr)
        else command
    )
    return DoctorCheck("mitr", "ok", first_line)


def _litellm_binary_check() -> DoctorCheck:
    binary = find_litellm_binary()
    if binary is None:
        return DoctorCheck(
            "litellm-bin",
            "warn",
            "Binary 'litellm' non trovato; installa l'extra runtime con `uv sync --all-extras`.",
        )
    return DoctorCheck("litellm-bin", "ok", binary)


def _litellm_check(settings: Settings) -> DoctorCheck:
    status = litellm_status(settings)
    if status.running and status.healthy:
        return DoctorCheck("litellm", "ok", f"PID {status.pid}: {status.message}")
    if status.running:
        return DoctorCheck(
            "litellm", "warn", f"PID {status.pid} attivo ma non healthy: {status.message}"
        )
    health = check_litellm_health(settings)
    if health.ok:
        return DoctorCheck("litellm", "ok", health.message)
    return DoctorCheck(
        "litellm",
        "warn",
        f"Proxy non in esecuzione. Avvia con `msrt server up` ({health.message}).",
    )


def _paid_smoke_check(settings: Settings, model: str) -> DoctorCheck:
    smoke = run_litellm_paid_smoke(settings, model=model)
    return DoctorCheck("paid-smoke", "ok" if smoke.ok else "fail", smoke.message)
