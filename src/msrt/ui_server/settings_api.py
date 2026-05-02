"""Read-only views over user-facing configuration.

The contract is strict: **API key values never leave this module**.
The UI only ever sees ``has_*_key`` booleans, so a screenshot of the
Settings page is safe to share publicly.
"""

from __future__ import annotations

from msrt.config import Settings
from msrt.ui_server.schemas import SettingsView


def settings_view(settings: Settings | None = None) -> SettingsView:
    """Build the public-safe ``SettingsView``. Pass ``settings`` for
    tests; production code can call without args and a fresh
    ``Settings()`` (which reads ``.env``) is materialised."""

    s = settings or Settings()
    return SettingsView(
        default_model=s.default_model,
        litellm_port=s.litellm_port,
        litellm_base_url=s.litellm_base_url,
        cache_dir=str(s.cache_dir),
        mitr_bin_path=s.mitr_bin_path,
        has_anthropic_key=bool(s.anthropic_api_key),
        has_openai_key=bool(s.openai_api_key),
        has_gemini_key=bool(s.gemini_api_key),
    )
