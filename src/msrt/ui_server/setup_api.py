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
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from msrt.config import MODEL_ALIASES, Settings
from msrt.paths import env_file_path, litellm_config_path
from msrt.server import (
    LiteLLMUnavailableError,
    litellm_status,
    start_litellm,
    stop_litellm,
)
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


class AutoCoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class AutoCoverResponse(BaseModel):
    auto_cover_enabled: bool


class UiLanguageRequest(BaseModel):
    """Switch the UI language. ``"it"`` (default) keeps Italian copy;
    ``"en"`` flips every page-level string to its English counterpart.

    The backend doesn't render any UI itself — it just persists the
    choice in ``.env`` (``MSRT_UI_LANG``) so subsequent ``/api/settings``
    reads pick it up immediately, including from a fresh tab.
    """

    model_config = ConfigDict(extra="forbid")
    language: Literal["it", "en"]


class UiLanguageResponse(BaseModel):
    ui_language: Literal["it", "en"]


class ProviderModelsRequest(BaseModel):
    """Update the per-provider preferred model alias.

    All fields optional; ``None`` means "leave unchanged". Each alias is
    validated against ``MODEL_ALIASES`` and against the provider it
    must belong to (e.g. ``openai`` rejects ``gemini-flash``).
    """

    model_config = ConfigDict(extra="forbid")
    openai: str | None = Field(default=None, min_length=1)
    anthropic: str | None = Field(default=None, min_length=1)
    google: str | None = Field(default=None, min_length=1)


class ProviderModelsResponse(BaseModel):
    model_openai: str
    model_anthropic: str
    model_google: str
    message: str


def _env_path(settings: Settings) -> Path:
    """Locate the project ``.env`` via ``msrt.paths``. The path is
    absolute and resolved against the project root (or the
    ``MSRT_HOME`` override) so saves land in the same file the rest of
    ``msrt`` reads from, regardless of where ``msrt ui`` was launched.
    """

    del settings  # currently unused; kept for future per-profile envs
    return env_file_path()


def save_api_key(request: SaveKeyRequest, settings: Settings) -> SecretReportResponse:
    if request.name not in known_keys():
        raise ValueError(f"Chiave non riconosciuta: {request.name!r}.")
    report: SecretReport = save_secret(request.name, request.value, env_path=_env_path(settings))
    object.__setattr__(settings, _KEY_TO_SETTINGS_ATTR[request.name], request.value)
    extra = _restart_proxy_if_running(settings)
    message = f"{report.message} {extra}".strip() if extra else report.message
    return SecretReportResponse(name=report.name, backend=report.backend, message=message)


def remove_api_key(request: DeleteKeyRequest, settings: Settings) -> SecretReportResponse:
    if request.name not in known_keys():
        raise ValueError(f"Chiave non riconosciuta: {request.name!r}.")
    report = delete_secret(request.name, env_path=_env_path(settings))
    object.__setattr__(settings, _KEY_TO_SETTINGS_ATTR[request.name], None)
    extra = _restart_proxy_if_running(settings)
    message = f"{report.message} {extra}".strip() if extra else report.message
    return SecretReportResponse(name=report.name, backend=report.backend, message=message)


def _restart_proxy_if_running(settings: Settings) -> str:
    """If LiteLLM is already up, restart it so it picks up the new env.

    The proxy is a separate subprocess: its environment is snapshotted at
    boot from ``_litellm_process_env(settings)``. Without a restart, a
    just-saved ``GEMINI_API_KEY`` (or any other provider key) lands in
    the FastAPI process env but stays invisible to the proxy — and
    "Test" hits ``litellm`` with the stale env, surfacing as a confusing
    auth error.

    Returns a short Italian status string suitable for appending to the
    save/delete message. Empty string if the proxy was not running (no
    restart needed).
    """

    status = litellm_status(settings)
    if not status.running:
        return ""
    stop_litellm(settings)
    try:
        new_status = start_litellm(settings, litellm_config_path())
    except (LiteLLMUnavailableError, FileNotFoundError, RuntimeError) as exc:
        return f"Proxy fermato; restart fallito: {exc}"
    if new_status.healthy:
        return "Proxy LiteLLM riavviato per applicare la nuova chiave."
    return f"Proxy LiteLLM riavviato ma healthcheck KO: {new_status.message}"


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


def update_ui_language(
    request: UiLanguageRequest, settings: Settings
) -> UiLanguageResponse:
    """Persist the UI language preference. The frontend reads the new
    value from ``/api/settings`` and re-renders without a reload."""

    import os

    env_path = _env_path(settings)
    from msrt.setup import load_env

    env = load_env(env_path) if env_path.is_file() else {}
    env["MSRT_UI_LANG"] = request.language
    save_env(env_path, env)
    os.environ["MSRT_UI_LANG"] = request.language
    object.__setattr__(settings, "ui_language", request.language)
    return UiLanguageResponse(ui_language=request.language)


def update_auto_cover(request: AutoCoverRequest, settings: Settings) -> AutoCoverResponse:
    """Toggle automatic cover-art retrieval. Persists ``MSRT_AUTO_COVER``
    in ``.env`` and updates the live ``Settings`` object so the next
    request to ``/api/library/cover`` honours the change immediately."""

    env_path = _env_path(settings)
    from msrt.setup import load_env

    env = load_env(env_path) if env_path.is_file() else {}
    env["MSRT_AUTO_COVER"] = "1" if request.enabled else "0"
    save_env(env_path, env)

    import os

    os.environ["MSRT_AUTO_COVER"] = env["MSRT_AUTO_COVER"]
    object.__setattr__(settings, "auto_cover_enabled", request.enabled)
    return AutoCoverResponse(auto_cover_enabled=request.enabled)


_PROVIDER_TO_ATTR_AND_ENV: dict[str, tuple[str, str]] = {
    "openai": ("model_openai", "MSRT_MODEL_OPENAI"),
    "anthropic": ("model_anthropic", "MSRT_MODEL_ANTHROPIC"),
    "google": ("model_google", "MSRT_MODEL_GOOGLE"),
}


def update_provider_models(
    request: ProviderModelsRequest, settings: Settings
) -> ProviderModelsResponse:
    """Persist per-provider preferred model aliases.

    Each alias is checked against ``MODEL_ALIASES`` so a typo or a
    cross-provider mistake (e.g. ``openai="gemini-pro"``) is rejected
    up-front rather than blowing up later in the fallback chain. Only
    fields the caller sets are touched; ``None`` means "leave as-is".
    """

    import os

    env_path = _env_path(settings)
    from msrt.setup import load_env

    env = load_env(env_path) if env_path.is_file() else {}
    pending: list[tuple[str, str, str]] = []  # (provider, attr, alias)

    for provider, alias in (
        ("openai", request.openai),
        ("anthropic", request.anthropic),
        ("google", request.google),
    ):
        if alias is None:
            continue
        if alias not in MODEL_ALIASES:
            raise ValueError(
                f"Modello '{alias}' non riconosciuto. Disponibili: "
                f"{', '.join(sorted(MODEL_ALIASES))}."
            )
        expected_provider, _, _ = MODEL_ALIASES[alias]
        if expected_provider != provider:
            raise ValueError(
                f"Modello '{alias}' appartiene a {expected_provider!r}, "
                f"non a {provider!r}."
            )
        attr, env_name = _PROVIDER_TO_ATTR_AND_ENV[provider]
        pending.append((provider, attr, alias))
        env[env_name] = alias

    if pending:
        save_env(env_path, env)
        for provider, attr, alias in pending:
            _, env_name = _PROVIDER_TO_ATTR_AND_ENV[provider]
            os.environ[env_name] = alias
            object.__setattr__(settings, attr, alias)

    return ProviderModelsResponse(
        model_openai=settings.model_openai,
        model_anthropic=settings.model_anthropic,
        model_google=settings.model_google,
        message=(
            "Preferenze aggiornate." if pending else "Nessuna modifica richiesta."
        ),
    )
