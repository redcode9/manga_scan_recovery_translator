from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from msrt.config import Settings
from msrt.translate import glossary_builder
from msrt.translate.glossary import load_glossary, load_or_build_glossary
from msrt.translate.glossary_builder import (
    GlossaryBuildError,
    build_glossary_via_llm,
    cached_glossary_path,
    parse_glossary_tsv,
    save_glossary,
    slugify_series,
)


def _settings_with_cache(tmp_path: Path) -> Settings:
    settings = Settings()
    object.__setattr__(settings, "cache_dir", tmp_path / ".cache" / "msrt")
    return settings


def test_slugify_series_handles_punctuation_and_case() -> None:
    assert slugify_series("Wistoria: Wand and Sword") == "wistoria-wand-and-sword"
    assert slugify_series("  ONE PIECE  ") == "one-piece"
    assert slugify_series("@@@") == "untitled"


def test_cached_glossary_path_uses_cache_dir(tmp_path: Path) -> None:
    settings = _settings_with_cache(tmp_path)
    path = cached_glossary_path("Wistoria", settings)
    assert path == tmp_path / ".cache" / "msrt" / "glossaries" / "wistoria.tsv"


def test_parse_glossary_tsv_handles_clean_input() -> None:
    raw = "Emma\tEmma\nWill\tWill\nBelledors\tBelledors\n"
    assert parse_glossary_tsv(raw) == {
        "Emma": "Emma",
        "Will": "Will",
        "Belledors": "Belledors",
    }


def test_parse_glossary_tsv_strips_markdown_fences_and_numbering() -> None:
    raw = "```tsv\n1. Emma\tEmma\n2) Will\tWill\n3.   Sion  \tSion\n```\n"
    assert parse_glossary_tsv(raw) == {"Emma": "Emma", "Will": "Will", "Sion": "Sion"}


def test_parse_glossary_tsv_tolerates_arrow_separator() -> None:
    raw = "Emma => Emma\nWill => Will\n"
    assert parse_glossary_tsv(raw) == {"Emma": "Emma", "Will": "Will"}


def test_parse_glossary_tsv_tolerates_pipe_table() -> None:
    raw = "| Emma | Emma |\n| Will | Will |\n"
    assert parse_glossary_tsv(raw) == {"Emma": "Emma", "Will": "Will"}


def test_parse_glossary_tsv_skips_empty_or_single_column() -> None:
    raw = "JustOneColumn\n\nEmma\tEmma\n"
    assert parse_glossary_tsv(raw) == {"Emma": "Emma"}


def test_parse_glossary_tsv_skips_markdown_table_headers_and_separators() -> None:
    """LLMs sometimes wrap the glossary in a Markdown table. The pipe-table
    branch must not absorb the header (``Source | Target``) or the
    alignment row (``--- | ---``) as glossary entries."""

    raw = "| Source | Target |\n| --- | --- |\n| Emma | Emma |\n| Will | Will |\n"
    assert parse_glossary_tsv(raw) == {"Emma": "Emma", "Will": "Will"}


def test_parse_glossary_tsv_drops_bare_dash_separator_line() -> None:
    raw = "Emma\tEmma\n---\nWill\tWill\n"
    assert parse_glossary_tsv(raw) == {"Emma": "Emma", "Will": "Will"}


def test_parse_glossary_tsv_drops_alternative_header_synonyms() -> None:
    raw = "| English | Italian |\n| Emma | Emma |\n"
    assert parse_glossary_tsv(raw) == {"Emma": "Emma"}


def test_save_glossary_roundtrips(tmp_path: Path) -> None:
    path = tmp_path / "glossaries" / "wistoria.tsv"
    save_glossary(path, {"Emma": "Emma", "Will": "Will"})

    assert path.exists()
    loaded = load_glossary(path)
    assert loaded == {"Emma": "Emma", "Will": "Will"}


def _mock_post(payload: dict, *, status: int = 200) -> object:
    """Build a stand-in for ``httpx.post`` that returns a fixed response.

    Returning ``httpx.Response`` directly is enough — the builder only
    consumes ``status_code``, ``json()``, and ``text``.
    """

    def fake_post(
        url: str,
        json: object | None = None,
        headers: object | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        return httpx.Response(status_code=status, json=payload)

    return fake_post


def test_build_glossary_via_llm_parses_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": "Emma\tEmma\nWill\tWill\n",
                }
            }
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 18},
    }
    monkeypatch.setattr(glossary_builder.httpx, "post", _mock_post(payload))

    result = build_glossary_via_llm(
        "Wistoria", model="gpt", settings=_settings_with_cache(tmp_path)
    )

    assert result.entries == {"Emma": "Emma", "Will": "Will"}
    assert result.tokens_in == 120
    assert result.tokens_out == 18
    assert result.model == "gpt"


def test_build_glossary_via_llm_raises_on_http_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        glossary_builder.httpx,
        "post",
        _mock_post({"error": {"message": "auth failed"}}, status=401),
    )

    with pytest.raises(GlossaryBuildError, match="HTTP 401"):
        build_glossary_via_llm("Wistoria", model="gpt", settings=_settings_with_cache(tmp_path))


def test_build_glossary_via_llm_raises_when_response_unparsable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {"choices": [{"message": {"content": "I have no idea what that is."}}]}
    monkeypatch.setattr(glossary_builder.httpx, "post", _mock_post(payload))

    with pytest.raises(GlossaryBuildError, match="non ha prodotto voci"):
        build_glossary_via_llm("Wistoria", model="gpt", settings=_settings_with_cache(tmp_path))


def test_build_glossary_via_llm_raises_when_proxy_unreachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(glossary_builder.httpx, "post", boom)

    with pytest.raises(GlossaryBuildError, match="non raggiungibile"):
        build_glossary_via_llm("Wistoria", model="gpt", settings=_settings_with_cache(tmp_path))


def test_load_or_build_uses_cache_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings_with_cache(tmp_path)
    cache_path = cached_glossary_path("Wistoria", settings)
    save_glossary(cache_path, {"Emma": "Emma"})

    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("LLM call must not happen on cache hit")

    monkeypatch.setattr(glossary_builder, "build_glossary_via_llm", explode)

    path, entries, result = load_or_build_glossary("Wistoria", model="gpt", settings=settings)

    assert path == cache_path
    assert entries == {"Emma": "Emma"}
    assert result is None


def test_load_or_build_invokes_builder_on_cache_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings_with_cache(tmp_path)
    payload = {
        "choices": [{"message": {"content": "Emma\tEmma\n"}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 5},
    }
    monkeypatch.setattr(glossary_builder.httpx, "post", _mock_post(payload))

    logged: list[str] = []
    path, entries, result = load_or_build_glossary(
        "Wistoria", model="gpt", settings=settings, log=logged.append
    )

    assert entries == {"Emma": "Emma"}
    assert result is not None
    assert result.tokens_in == 50
    assert path.exists()
    assert any("non in cache" in line for line in logged)
    assert any("salvato" in line for line in logged)


def test_load_or_build_force_rebuilds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with_cache(tmp_path)
    cache_path = cached_glossary_path("Wistoria", settings)
    save_glossary(cache_path, {"Stale": "Stale"})

    payload = {"choices": [{"message": {"content": "Fresh\tFresh\n"}}]}
    monkeypatch.setattr(glossary_builder.httpx, "post", _mock_post(payload))

    _path, entries, result = load_or_build_glossary(
        "Wistoria", model="gpt", settings=settings, force_rebuild=True
    )

    assert entries == {"Fresh": "Fresh"}
    assert result is not None
    assert load_glossary(cache_path) == {"Fresh": "Fresh"}
