"""Runtime configuration for msrt."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from msrt.paths import env_file_path

ProviderName = Literal["anthropic", "openai", "google", "local"]


MODEL_ALIASES: dict[str, tuple[ProviderName, str, str]] = {
    "sonnet": ("anthropic", "claude-sonnet-4-6", "ANTHROPIC_API_KEY"),
    "opus": ("anthropic", "claude-opus-4-7", "ANTHROPIC_API_KEY"),
    "gpt": ("openai", "gpt-5.5", "OPENAI_API_KEY"),
    "gpt-5": ("openai", "gpt-5", "OPENAI_API_KEY"),
    "gpt-mini": ("openai", "gpt-5-mini", "OPENAI_API_KEY"),
    "gemini-pro": ("google", "gemini-2.5-pro", "GEMINI_API_KEY"),
    "gemini-flash": ("google", "gemini-2.5-flash", "GEMINI_API_KEY"),
}


class Settings(BaseSettings):
    """Settings loaded from environment variables and ``.env``.

    The ``.env`` location is resolved by ``msrt.paths.env_file_path``
    *at instantiation time* (not at import time), so the same
    ``Settings()`` call picks up the right file even after a
    ``chdir`` or after ``MSRT_HOME`` has been set programmatically.
    Tests that need full isolation can still pass
    ``_env_file=None`` when instantiating ``Settings`` directly.
    """

    model_config = SettingsConfigDict(
        # Placeholder default; ``__init__`` overrides via ``_env_file``
        # so the resolution is dynamic. Pydantic-settings still expects
        # *something* here for the class config to validate.
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    default_model: str = Field(default="gpt", alias="MSRT_MODEL")
    litellm_port: int = Field(default=4000, alias="LITELLM_PORT")
    mitr_bin_path: str | None = Field(default=None, alias="MITR_BIN_PATH")
    cache_dir: Path = Field(default_factory=lambda: Path.home() / ".cache" / "msrt")
    # Auto cover-art retrieval: when ``True`` (default) the library
    # endpoint walks the resolver chain (MangaDex → AniList → local
    # composite → AI-generated) to surface the best cover available.
    # Setting this to ``False`` skips the chain entirely and the UI
    # falls back to the gradient placeholder.
    auto_cover_enabled: bool = Field(default=True, alias="MSRT_AUTO_COVER")

    def __init__(self, **kwargs: Any) -> None:
        # Resolve the ``.env`` location lazily so that
        # ``MSRT_HOME``, ``chdir`` or test fixtures that set up an
        # alternate project root after import time are honoured.
        if "_env_file" not in kwargs:
            kwargs["_env_file"] = str(env_file_path())
        super().__init__(**kwargs)

    @property
    def litellm_base_url(self) -> str:
        return f"http://localhost:{self.litellm_port}"

    def api_key_for_env_name(self, env_name: str) -> str | None:
        return {
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "OPENAI_API_KEY": self.openai_api_key,
            "GEMINI_API_KEY": self.gemini_api_key,
        }.get(env_name)


def resolve_model_alias(alias: str) -> tuple[ProviderName | None, str, str | None]:
    """Return provider, resolved model ID, and required env key for a model alias."""

    if alias in MODEL_ALIASES:
        provider, model_id, env_name = MODEL_ALIASES[alias]
        return provider, model_id, env_name
    if alias.startswith("local-"):
        return "local", alias, None
    return None, alias, None
