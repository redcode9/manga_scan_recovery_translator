"""Read-only views over user-facing configuration.

The contract is strict: **API key values never leave this module**.
The UI only ever sees ``has_*_key`` booleans, so a screenshot of the
Settings page is safe to share publicly.
"""

from __future__ import annotations

from typing import Any

from msrt.config import Settings
from msrt.ui_server.schemas import SettingsView
from msrt.ui_server.secrets import _try_import_keyring


def _keychain_has(name: str) -> bool:
    """True if the OS keychain has a non-empty entry for ``name`` under
    the msrt service. Returns False on any error or when the keyring
    backend is unavailable / explicitly disabled.

    We avoid ``get_secret`` here because that helper also consults
    ``.env`` and the process environment — but pydantic-settings has
    already loaded both into the ``Settings`` object, so re-reading
    them would be redundant *and* would leak the developer's real
    keys into test runs that pass an ``isolated_settings``.
    """

    keyring_module: Any = _try_import_keyring()
    if keyring_module is None:
        return False
    try:
        return bool(keyring_module.get_password("msrt", name))
    except Exception:
        return False


def settings_view(settings: Settings | None = None) -> SettingsView:
    """Build the public-safe ``SettingsView``. Pass ``settings`` for
    tests; production code can call without args and a fresh
    ``Settings()`` (which reads ``.env``) is materialised."""

    s = settings or Settings()
    return SettingsView(
        default_model=s.default_model,
        model_openai=s.model_openai,
        model_anthropic=s.model_anthropic,
        model_google=s.model_google,
        litellm_port=s.litellm_port,
        litellm_base_url=s.litellm_base_url,
        cache_dir=str(s.cache_dir),
        mitr_bin_path=s.mitr_bin_path,
        has_anthropic_key=bool(s.anthropic_api_key) or _keychain_has("ANTHROPIC_API_KEY"),
        has_openai_key=bool(s.openai_api_key) or _keychain_has("OPENAI_API_KEY"),
        has_gemini_key=bool(s.gemini_api_key) or _keychain_has("GEMINI_API_KEY"),
        auto_cover_enabled=s.auto_cover_enabled,
        ui_language=s.ui_language,
    )
