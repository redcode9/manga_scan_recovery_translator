"""Setup wizard endpoints for the UI.

The CLI has its own interactive setup wizard (``msrt setup``); the UI
needs HTTP-friendly equivalents that are state-less and idempotent.
We keep the surface tiny:

* ``POST /api/setup/save-key``    save / replace one API key
* ``POST /api/setup/delete-key``  delete one API key
* ``POST /api/setup/test-key``    paid-smoke style validation
* ``POST /api/setup/default-model`` change MSRT_MODEL

Everything else (MITR install, Playwright install) keeps using the
existing CLI scripts; the UI documents the steps and links to
``msrt doctor`` for verification.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from msrt.config import Settings
from msrt.setup import save_env
from msrt.translate.litellm_proxy import run_litellm_paid_smoke
from msrt.ui_server.secrets import (
    SecretBackend,
    SecretReport,
    delete_secret,
    known_keys,
    save_secret,
)

_KEY_TO_SETTINGS_ATTR = {
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "OPENAI_API_KEY": "openai_api_key",
    "GEMINI_API_KEY": "gemini_api_key",
}


class SaveKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    value: str = Field(..., min_length=1)


class DeleteKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str


class TestKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str


class DefaultModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(..., min_length=1)


class SecretReportResponse(BaseModel):
    name: str
    backend: SecretBackend
    message: str


class SetupTestResult(BaseModel):
    ok: bool
    message: str
    latency_ms: int | None = None


class DefaultModelResponse(BaseModel):
    default_model: str


def _env_path(settings: Settings) -> Path:
    """Locate the project ``.env``. We resolve it relative to the
    current working directory (where the user typically launches
    ``msrt ui``); if missing, we still return the path so save_env can
    create it on first save."""

    return Path.cwd() / ".env"


def save_api_key(request: SaveKeyRequest, settings: Settings) -> SecretReportResponse:
    if request.name not in known_keys():
        raise ValueError(f"Chiave non riconosciuta: {request.name!r}.")
    report: SecretReport = save_secret(request.name, request.value, env_path=_env_path(settings))
    object.__setattr__(settings, _KEY_TO_SETTINGS_ATTR[request.name], request.value)
    return SecretReportResponse(name=report.name, backend=report.backend, message=report.message)


def remove_api_key(request: DeleteKeyRequest, settings: Settings) -> SecretReportResponse:
    if request.name not in known_keys():
        raise ValueError(f"Chiave non riconosciuta: {request.name!r}.")
    report = delete_secret(request.name, env_path=_env_path(settings))
    object.__setattr__(settings, _KEY_TO_SETTINGS_ATTR[request.name], None)
    return SecretReportResponse(name=report.name, backend=report.backend, message=report.message)


def smoke_test_provider(request: TestKeyRequest, settings: Settings) -> SetupTestResult:
    """Esegue una mini-chiamata reale al provider via LiteLLM proxy.

    Richiede che il proxy sia già up; il caller (UI) può fare il
    check con ``GET /api/server`` prima di esporre il bottone.
    """

    smoke = run_litellm_paid_smoke(settings, model=request.model)
    return SetupTestResult(ok=smoke.ok, message=smoke.message, latency_ms=smoke.latency_ms)


def update_default_model(request: DefaultModelRequest, settings: Settings) -> DefaultModelResponse:
    """Aggiorna ``MSRT_MODEL`` nel file ``.env`` e nell'env corrente."""

    env_path = _env_path(settings)
    from msrt.setup import load_env

    env = load_env(env_path) if env_path.is_file() else {}
    env["MSRT_MODEL"] = request.model
    save_env(env_path, env)

    import os

    os.environ["MSRT_MODEL"] = request.model
    object.__setattr__(settings, "default_model", request.model)
    return DefaultModelResponse(default_model=request.model)
