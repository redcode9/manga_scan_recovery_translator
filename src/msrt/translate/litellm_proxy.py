"""LiteLLM proxy helpers."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import httpx

from msrt.config import Settings


@dataclass(frozen=True)
class ProxyHealth:
    ok: bool
    message: str


@dataclass(frozen=True)
class ProxySmoke:
    ok: bool
    message: str
    latency_ms: int | None = None


def check_litellm_health(settings: Settings, timeout: float = 2.0) -> ProxyHealth:
    url = f"{settings.litellm_base_url}/health"
    try:
        response = httpx.get(url, timeout=timeout)
    except httpx.HTTPError as exc:
        return ProxyHealth(False, f"LiteLLM non raggiungibile su {url}: {exc}")
    if response.status_code >= 400:
        return ProxyHealth(False, f"LiteLLM risponde HTTP {response.status_code} su {url}")
    return ProxyHealth(True, f"LiteLLM raggiungibile su {url}")


def run_litellm_paid_smoke(
    settings: Settings,
    *,
    model: str,
    timeout: float = 30.0,
) -> ProxySmoke:
    """Run a tiny real provider call through LiteLLM.

    This is opt-in because it can consume provider credits. The call uses the
    same Chat Completions-compatible path that MITR's custom_openai translator
    will use in the real E2E.
    """

    url = f"{settings.litellm_base_url}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Translate exactly to Italian, lowercase only: hello",
            }
        ],
    }
    headers = {"Authorization": "Bearer msrt-local-litellm"}
    started = perf_counter()
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        return ProxySmoke(False, f"Paid smoke non riuscito su {url}: {exc}")

    latency_ms = int((perf_counter() - started) * 1000)
    if response.status_code >= 400:
        return ProxySmoke(
            False,
            f"Paid smoke HTTP {response.status_code}: {_short_response_text(response)}",
            latency_ms,
        )

    try:
        data = response.json()
    except ValueError:
        return ProxySmoke(False, "Paid smoke: risposta non JSON dal proxy.", latency_ms)

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ProxySmoke(False, "Paid smoke: risposta senza choices.", latency_ms)

    content = choices[0].get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        return ProxySmoke(False, "Paid smoke: contenuto risposta vuoto.", latency_ms)
    preview = " ".join(content.strip().split())[:80]
    return ProxySmoke(True, f"Paid smoke OK ({latency_ms} ms): {preview!r}", latency_ms)


def _short_response_text(response: httpx.Response) -> str:
    text = response.text.strip()
    if not text:
        return "<empty response>"
    return " ".join(text.split())[:300]
