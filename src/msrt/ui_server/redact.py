"""Redaction helpers for the diagnostics endpoint.

The diagnostics bundle is meant to be attached to a public bug
report. Even when no API key value is present, raw paths
(``/Users/<name>/...``), URL query strings and ad-hoc tokens leak
context the user might not want to share. This module masks all
three before the JSON is serialised.

The redaction is conservative: when in doubt, replace. False
positives (e.g. a long base64 chunk in a log line) are acceptable
because the resulting bundle is still useful for triage; under-
redaction is not, because the file becomes the user's
responsibility once it leaves the local machine.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_KEY_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{20,}"),
    # Bearer tokens / Authorization-style values
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{12,}"),
)

_QUERY_STRING = re.compile(r"(\?|&)([A-Za-z0-9_\-]+)=([^&\s\"']+)")


def redact_text(value: str | None) -> str | None:
    """Redact a single string. Returns ``None`` on ``None`` input.

    Pipeline:
    1. Replace the user's home prefix with ``~`` (handles paths
       embedded in error messages, not just bare paths).
    2. Mask values inside URL query strings (``?token=…`` → ``?token=…``).
    3. Mask known API key prefixes (``sk-…``, ``AIza…``, etc).
    """

    if value is None:
        return None
    redacted = value
    # ``Path.home()`` is resolved per-call so test fixtures that swap
    # ``HOME`` via ``monkeypatch.setenv`` get the right substitution.
    home = str(Path.home())
    if home and home in redacted:
        redacted = redacted.replace(home, "~")
    redacted = _QUERY_STRING.sub(lambda m: f"{m.group(1)}{m.group(2)}=***", redacted)
    for pattern in _KEY_PATTERNS:
        redacted = pattern.sub("***REDACTED***", redacted)
    return redacted


def redact_value(value: Any) -> Any:
    """Recursively redact strings inside dicts / lists. Non-string
    leaves (ints, bools, None) pass through unchanged."""

    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_value(v) for v in value)
    return value
