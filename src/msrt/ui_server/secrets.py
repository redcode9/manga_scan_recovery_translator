"""Secret store abstraction for API keys.

Two backends, in priority order:

1. **macOS Keychain** (and equivalents on Linux/Windows) via the
   ``keyring`` library. This is the preferred path because the
   secret never lives in plaintext on disk and is scoped to the
   user account.
2. **Plain `.env`** in the project root, the legacy CLI behaviour.
   Used when ``keyring`` is unavailable or the user explicitly
   opts out.

The store is intentionally minimal: ``set``/``get``/``delete`` per
named secret. Higher-level "save my OpenAI key" logic lives in
``setup_api.py``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from msrt.setup import load_env, save_env

_LOG = logging.getLogger(__name__)
_SERVICE = "msrt"

SecretBackend = Literal["keychain", "dotenv"]

_KEY_NAMES = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
)


@dataclass(frozen=True)
class SecretReport:
    """Result of a save attempt — the API tells the UI whether the
    secret ended up in the OS keychain or had to fall back to .env."""

    name: str
    backend: SecretBackend
    message: str


def known_keys() -> tuple[str, ...]:
    return _KEY_NAMES


def hydrate_process_env(*, env_path: Path) -> None:
    """Load known secrets from keychain / .env into ``os.environ``.

    This is called when the UI backend starts. It makes keys saved in
    Keychain available to the existing LiteLLM/MITR code paths, which
    already read provider keys from environment variables.
    """

    import os

    for name in _KEY_NAMES:
        value = get_secret(name, env_path=env_path)
        if value:
            os.environ[name] = value


def save_secret(name: str, value: str, *, env_path: Path) -> SecretReport:
    """Persist ``value`` under ``name`` in the most secure backend
    available. Always mirrors the value into the in-process
    environment so the rest of the app picks it up without a restart.

    The function never returns the value back, only a report.
    """

    _validate_name(name)
    if not value:
        raise ValueError(f"Secret {name!r} non può essere vuoto.")

    import os

    backend: SecretBackend = "dotenv"
    message = "Salvato nel file .env."

    keyring_module: Any = _try_import_keyring()
    if keyring_module is not None:
        try:
            keyring_module.set_password(_SERVICE, name, value)
            backend = "keychain"
            message = "Salvato nel portachiavi di sistema."
            # Mirror to .env strip removing the line if present —
            # otherwise the .env keeps shadowing the keychain.
            _wipe_env_entry(env_path, name)
        except Exception as exc:
            _LOG.warning("Keyring backend non disponibile (%s); fallback .env", exc)
            backend = "dotenv"
            message = f"Keyring fallito ({exc}); salvato nel file .env."
            _save_to_env(env_path, name, value)
    else:
        _save_to_env(env_path, name, value)

    os.environ[name] = value
    return SecretReport(name=name, backend=backend, message=message)


def get_secret(name: str, *, env_path: Path) -> str | None:
    """Resolve ``name`` from keychain → .env → process env, in that
    order. Returns ``None`` when nothing is found."""

    _validate_name(name)
    keyring_module: Any = _try_import_keyring()
    if keyring_module is not None:
        try:
            stored: Any = keyring_module.get_password(_SERVICE, name)
            if stored:
                return str(stored)
        except Exception as exc:
            _LOG.debug("Keyring lookup failed for %s: %s", name, exc)

    if env_path.is_file():
        env = load_env(env_path)
        if env.get(name):
            return env[name]

    import os

    return os.environ.get(name) or None


def delete_secret(name: str, *, env_path: Path) -> SecretReport:
    """Remove the key from every backend we know about."""

    _validate_name(name)
    backend: SecretBackend = "dotenv"
    message = "Rimosso da .env."

    keyring_module: Any = _try_import_keyring()
    if keyring_module is not None:
        try:
            keyring_module.delete_password(_SERVICE, name)
            backend = "keychain"
            message = "Rimosso dal portachiavi di sistema."
        except Exception:
            pass

    _wipe_env_entry(env_path, name)
    import os

    os.environ.pop(name, None)
    return SecretReport(name=name, backend=backend, message=message)


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------


def _validate_name(name: str) -> None:
    if name not in _KEY_NAMES:
        raise ValueError(f"Chiave non riconosciuta: {name!r}. Atteso uno di {_KEY_NAMES}.")


def _try_import_keyring() -> object | None:
    """Lazy import: ``keyring`` is an optional UI extra, so the module
    must keep working even when it isn't installed.

    Returned as ``object`` because the keyring module is treated as a
    duck-typed namespace (set_password / get_password / delete_password)
    — the static type isn't worth dragging in just for this."""

    import os

    if os.environ.get("MSRT_DISABLE_KEYRING") == "1":
        return None

    try:
        import keyring
    except ImportError:
        return None
    return keyring


def _save_to_env(env_path: Path, name: str, value: str) -> None:
    env = load_env(env_path) if env_path.is_file() else {}
    env[name] = value
    save_env(env_path, env)


def _wipe_env_entry(env_path: Path, name: str) -> None:
    if not env_path.is_file():
        return
    env = load_env(env_path)
    if name in env:
        env[name] = ""
        save_env(env_path, env)
