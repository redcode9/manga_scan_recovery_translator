from __future__ import annotations

import httpx
import pytest

from msrt.config import Settings
from msrt.translate import litellm_proxy


def _settings() -> Settings:
    return Settings(_env_file=None, litellm_port=4000)  # type: ignore[call-arg]


def test_paid_smoke_succeeds_with_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(
        url: str,
        *,
        json: object,
        headers: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        _ = (json, headers, timeout)
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ciao"}}]},
            request=request,
        )

    monkeypatch.setattr(litellm_proxy.httpx, "post", fake_post)

    smoke = litellm_proxy.run_litellm_paid_smoke(_settings(), model="gpt")

    assert smoke.ok is True
    assert "ciao" in smoke.message


def test_paid_smoke_fails_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(
        url: str,
        *,
        json: object,
        headers: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        _ = (json, headers, timeout)
        request = httpx.Request("POST", url)
        return httpx.Response(401, text="invalid api key", request=request)

    monkeypatch.setattr(litellm_proxy.httpx, "post", fake_post)

    smoke = litellm_proxy.run_litellm_paid_smoke(_settings(), model="gpt")

    assert smoke.ok is False
    assert "HTTP 401" in smoke.message
