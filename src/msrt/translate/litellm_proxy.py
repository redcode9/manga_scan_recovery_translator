"""LiteLLM proxy helpers."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from msrt.config import Settings


@dataclass(frozen=True)
class ProxyHealth:
    ok: bool
    message: str


def check_litellm_health(settings: Settings, timeout: float = 2.0) -> ProxyHealth:
    url = f"{settings.litellm_base_url}/health"
    try:
        response = httpx.get(url, timeout=timeout)
    except httpx.HTTPError as exc:
        return ProxyHealth(False, f"LiteLLM non raggiungibile su {url}: {exc}")
    if response.status_code >= 400:
        return ProxyHealth(False, f"LiteLLM risponde HTTP {response.status_code} su {url}")
    return ProxyHealth(True, f"LiteLLM raggiungibile su {url}")
