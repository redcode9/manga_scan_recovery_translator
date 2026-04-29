from __future__ import annotations

import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from msrt.config import Settings
from msrt.models import TranslationJob
from msrt.pipeline import (
    EngineFactory,
    collect_local_chapter,
    mitr_target_language,
    reset_translated_dir,
    run_local,
    translate_only,
)
from msrt.translate.engine import (
    TranslationEngine,
    TranslationError,
    TranslationResult,
)


class MockEngine(TranslationEngine):
    """Engine che simula MITR copiando le immagini in output."""

    def translate(
        self, input_dir: Path, output_dir: Path, job: TranslationJob
    ) -> TranslationResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        for image_path in input_dir.iterdir():
            if image_path.is_file() and image_path.suffix.lower() in {
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
            }:
                shutil.copy(image_path, output_dir / image_path.name)
        return TranslationResult(
            output_dir=output_dir,
            text_output_file=None,
            stdout="mock",
            stderr="",
        )


def _mock_factory() -> EngineFactory:
    def factory(_settings: Settings, _prompt_config: Path) -> TranslationEngine:
        return MockEngine()

    return factory


def _write_pages(image_dir: Path, indices: list[int]) -> None:
    image_dir.mkdir(parents=True, exist_ok=True)
    for index in indices:
        Image.new("RGB", (80, 120), "white").save(image_dir / f"{index}.png")


def test_run_local_writes_manifest_when_mitr_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_dir = tmp_path / "pages"
    _write_pages(image_dir, [1])
    out_dir = tmp_path / "out"
    monkeypatch.setenv("MITR_BIN_PATH", "definitely-missing-mitr")

    with pytest.raises(TranslationError):
        run_local(
            image_dir,
            out_dir,
            series="Smoke",
            chapter_number="1",
            chapter_title="Pilot",
            lang_source="en",
            lang_target="it",
            fmt="pdf",
            job=TranslationJob(model="sonnet", use_gpu=False),
        )

    manifest = json.loads((out_dir / "msrt-run.json").read_text(encoding="utf-8"))
    assert manifest["input"]["page_count"] == 1
    assert manifest["errors"]


def test_run_local_e2e_with_mock_engine(tmp_path: Path) -> None:
    image_dir = tmp_path / "pages"
    _write_pages(image_dir, [3, 1, 10])
    out_dir = tmp_path / "out"

    phases: list[str] = []

    manifest = run_local(
        image_dir,
        out_dir,
        series="Mock",
        chapter_number="42",
        chapter_title="Test",
        lang_source="en",
        lang_target="it",
        fmt="both",
        job=TranslationJob(model="sonnet", use_gpu=False),
        engine_factory=_mock_factory(),
        on_phase=phases.append,
    )

    assert phases == ["collect", "translate", "package", "done"]
    assert manifest.input.page_count == 3
    assert manifest.errors == []
    assert manifest.metadata["series"] == "Mock"
    assert manifest.metadata["language_target"] == "it"

    cbz_path = out_dir / "mock-42-it.cbz"
    pdf_path = out_dir / "mock-42-it.pdf"
    manifest_path = out_dir / "msrt-run.json"
    assert cbz_path.exists()
    assert pdf_path.exists()
    assert manifest_path.exists()

    with ZipFile(cbz_path) as archive:
        names = archive.namelist()
        comic_info = archive.read("ComicInfo.xml").decode("utf-8")
    page_entries = [name for name in names if name.endswith(".png")]
    assert len(page_entries) == 3
    assert page_entries == sorted(page_entries)
    assert "<LanguageISO>it</LanguageISO>" in comic_info
    assert "<Series>Mock</Series>" in comic_info

    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved["page_order"] == ["1.png", "3.png", "10.png"]
    assert sorted(saved["output_files"]) == sorted([str(cbz_path), str(pdf_path)])


def test_translate_only_raises_when_engine_drops_pages(tmp_path: Path) -> None:
    """``translate_only`` skips packaging but must still validate the
    output: an exit-0 silent failure from MITR has to surface as an error,
    not as a manifest claiming success on an incomplete output dir."""

    image_dir = tmp_path / "pages"
    _write_pages(image_dir, [1, 2, 3])
    out_dir = tmp_path / "out"

    class PartialEngine(TranslationEngine):
        def translate(
            self, input_dir: Path, output_dir: Path, job: TranslationJob
        ) -> TranslationResult:
            output_dir.mkdir(parents=True, exist_ok=True)
            first = next(p for p in sorted(input_dir.iterdir()) if p.suffix == ".png")
            shutil.copy(first, output_dir / first.name)
            return TranslationResult(
                output_dir=output_dir,
                text_output_file=None,
                stdout="some MITR output",
                stderr="WARNING: dropped 2 pages",
            )

    def factory(_settings: Settings, _prompt_config: Path) -> TranslationEngine:
        return PartialEngine()

    with pytest.raises(ValueError, match="MITR non ha prodotto"):
        translate_only(
            image_dir,
            out_dir,
            series="Smoke",
            chapter_number="1",
            chapter_title=None,
            lang_source="en",
            lang_target="it",
            job=TranslationJob(model="sonnet", use_gpu=False, auto_glossary=False),
            engine_factory=factory,
        )

    log_path = out_dir / ".msrt-tmp" / "mitr.log"
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "some MITR output" in log_text
    assert "dropped 2 pages" in log_text


def test_run_local_skips_auto_glossary_for_default_series_title(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bare ``msrt run-local DIR`` with no ``--series`` defaults to
    "Untitled Series", which carries no signal for the LLM. Auto-build
    should NOT fire — otherwise we burn a paid call and leave a useless
    ``untitled-series.tsv`` in the user cache."""

    image_dir = tmp_path / "pages"
    _write_pages(image_dir, [1])
    out_dir = tmp_path / "out"
    monkeypatch.setenv("HOME", str(tmp_path))

    from msrt.translate import glossary_builder as gb

    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Auto-build must not run for default series title")

    monkeypatch.setattr(gb, "build_glossary_via_llm", explode)

    class CapturingEngine(TranslationEngine):
        def translate(
            self, input_dir: Path, output_dir: Path, job: TranslationJob
        ) -> TranslationResult:
            output_dir.mkdir(parents=True, exist_ok=True)
            for image_path in input_dir.iterdir():
                if image_path.suffix == ".png":
                    shutil.copy(image_path, output_dir / image_path.name)
            return TranslationResult(
                output_dir=output_dir, text_output_file=None, stdout="", stderr=""
            )

    def factory(_settings: Settings, _prompt_config: Path) -> TranslationEngine:
        return CapturingEngine()

    logs: list[str] = []
    run_local(
        image_dir,
        out_dir,
        series="Untitled Series",  # CLI default
        chapter_number="1",
        chapter_title=None,
        lang_source="en",
        lang_target="it",
        fmt="pdf",
        job=TranslationJob(model="sonnet", use_gpu=False),
        engine_factory=factory,
        on_log=logs.append,
    )

    cache_file = tmp_path / ".cache" / "msrt" / "glossaries" / "untitled-series.tsv"
    assert not cache_file.exists(), "Default series title leaked into cache"
    assert any("default" in line.lower() or "untitled" in line.lower() for line in logs)


def test_translate_only_skips_packaging(tmp_path: Path) -> None:
    image_dir = tmp_path / "pages"
    _write_pages(image_dir, [1, 2])
    out_dir = tmp_path / "out"

    manifest = translate_only(
        image_dir,
        out_dir,
        series="Smoke",
        chapter_number="1",
        chapter_title=None,
        lang_source="en",
        lang_target="it",
        job=TranslationJob(model="sonnet", use_gpu=False),
        engine_factory=_mock_factory(),
    )

    assert manifest.metadata.get("mode") == "translate-only"
    assert list(out_dir.glob("*.cbz")) == []
    assert list(out_dir.glob("*.pdf")) == []
    translated = out_dir / "translated-pages"
    assert translated.exists()
    assert (translated / "1.png").exists()
    assert (translated / "2.png").exists()
    assert manifest.output_files == [str(translated)]


def test_collect_local_chapter_rejects_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Nessuna immagine"):
        collect_local_chapter(
            tmp_path,
            series="Empty",
            chapter_number="1",
            chapter_title=None,
            lang_source="en",
            lang_target="it",
        )


def test_mitr_target_language_maps_italian_aliases() -> None:
    assert mitr_target_language("it") == "ITA"
    assert mitr_target_language("ITA") == "ITA"
    assert mitr_target_language("italiano") == "ITA"


def test_mitr_target_language_rejects_unsupported_two_letter_code() -> None:
    with pytest.raises(ValueError, match="Target language"):
        mitr_target_language("fr")


def test_reset_translated_dir_removes_stale_files(tmp_path: Path) -> None:
    translated = tmp_path / "translated-pages"
    translated.mkdir()
    (translated / "ch44_1.png").write_bytes(b"old")
    (translated / "ch44_2.png").write_bytes(b"old")

    reset_translated_dir(translated)

    assert translated.exists()
    assert list(translated.iterdir()) == []


def test_reset_translated_dir_creates_when_missing(tmp_path: Path) -> None:
    translated = tmp_path / "translated-pages"
    assert not translated.exists()

    reset_translated_dir(translated)

    assert translated.exists()
    assert translated.is_dir()


def test_run_local_does_not_leak_pages_from_previous_chapter(tmp_path: Path) -> None:
    """Regression for the bug where chapter 50 packaged chapter 44 pages.

    Two consecutive runs sharing the same out_dir must produce a PDF that
    only contains the second run's pages, not leftovers from the first.
    """

    out_dir = tmp_path / "out"

    image_dir_a = tmp_path / "ch44"
    _write_pages(image_dir_a, [1, 2, 3])
    for path in image_dir_a.iterdir():
        path.rename(image_dir_a / path.name.replace(".png", "_44.png"))

    run_local(
        image_dir_a,
        out_dir,
        series="Wistoria",
        chapter_number="44",
        chapter_title=None,
        lang_source="en",
        lang_target="it",
        fmt="pdf",
        job=TranslationJob(model="sonnet", use_gpu=False),
        engine_factory=_mock_factory(),
    )

    image_dir_b = tmp_path / "ch50"
    _write_pages(image_dir_b, [1, 2])
    for path in image_dir_b.iterdir():
        path.rename(image_dir_b / path.name.replace(".png", "_50.png"))

    manifest = run_local(
        image_dir_b,
        out_dir,
        series="Wistoria",
        chapter_number="50",
        chapter_title=None,
        lang_source="en",
        lang_target="it",
        fmt="pdf",
        job=TranslationJob(model="sonnet", use_gpu=False),
        engine_factory=_mock_factory(),
    )

    assert manifest.input.page_count == 2
    translated = out_dir / "translated-pages"
    leftover = [p.name for p in translated.iterdir() if "_44" in p.name]
    assert leftover == [], f"Vecchi file di ch44 leaked: {leftover}"


def test_run_local_raises_when_engine_drops_pages(tmp_path: Path) -> None:
    """If MITR returns success but writes fewer pages than expected, we
    must surface the error instead of packaging a stale or empty output.
    """

    image_dir = tmp_path / "pages"
    _write_pages(image_dir, [1, 2, 3])
    out_dir = tmp_path / "out"

    class PartialEngine(TranslationEngine):
        def translate(
            self, input_dir: Path, output_dir: Path, job: TranslationJob
        ) -> TranslationResult:
            output_dir.mkdir(parents=True, exist_ok=True)
            # Only translate the first page; pages 2 and 3 are silently dropped.
            first = next(p for p in sorted(input_dir.iterdir()) if p.suffix == ".png")
            shutil.copy(first, output_dir / first.name)
            return TranslationResult(
                output_dir=output_dir, text_output_file=None, stdout="", stderr=""
            )

    def factory(_settings: Settings, _prompt_config: Path) -> TranslationEngine:
        return PartialEngine()

    with pytest.raises(ValueError, match="MITR non ha prodotto"):
        run_local(
            image_dir,
            out_dir,
            series="Smoke",
            chapter_number="1",
            chapter_title=None,
            lang_source="en",
            lang_target="it",
            fmt="pdf",
            job=TranslationJob(model="sonnet", use_gpu=False),
            engine_factory=factory,
        )

    manifest = json.loads((out_dir / "msrt-run.json").read_text(encoding="utf-8"))
    assert manifest["errors"]
    assert "MITR non ha prodotto" in manifest["errors"][0]


def test_run_local_auto_builds_glossary_when_cache_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With auto_glossary=True (the default) and no explicit --glossary,
    the pipeline must call the builder once and then inject the result
    into the gpt_config that reaches the engine.
    """

    image_dir = tmp_path / "pages"
    _write_pages(image_dir, [1])
    out_dir = tmp_path / "out"
    cache_root = tmp_path / ".cache"
    monkeypatch.setenv("HOME", str(tmp_path))
    # Pydantic Settings reads cache_dir from default_factory=Path.home()/.cache/msrt.
    # Patching HOME steers the cache under tmp_path so we don't pollute the real one.

    payload = {
        "choices": [{"message": {"content": "Emma\tEmma\nBelledors\tBelledors\n"}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 6},
    }

    def fake_post(
        url: str,
        json: object | None = None,
        headers: object | None = None,
        timeout: float | None = None,
    ) -> object:
        import httpx

        return httpx.Response(status_code=200, json=payload)

    from msrt.translate import glossary_builder as gb

    monkeypatch.setattr(gb.httpx, "post", fake_post)

    captured: dict[str, object] = {}

    class CapturingEngine(TranslationEngine):
        def translate(
            self, input_dir: Path, output_dir: Path, job: TranslationJob
        ) -> TranslationResult:
            captured["gpt_config_path"] = job.gpt_config_path
            cfg_path = job.gpt_config_path
            if cfg_path is not None and cfg_path.exists():
                captured["rendered"] = cfg_path.read_text(encoding="utf-8")
            output_dir.mkdir(parents=True, exist_ok=True)
            for image_path in input_dir.iterdir():
                if image_path.suffix == ".png":
                    shutil.copy(image_path, output_dir / image_path.name)
            return TranslationResult(
                output_dir=output_dir, text_output_file=None, stdout="", stderr=""
            )

    def factory(_settings: Settings, _prompt_config: Path) -> TranslationEngine:
        return CapturingEngine()

    logs: list[str] = []
    run_local(
        image_dir,
        out_dir,
        series="Wistoria",
        chapter_number="1",
        chapter_title=None,
        lang_source="en",
        lang_target="it",
        fmt="pdf",
        job=TranslationJob(model="sonnet", use_gpu=False),
        engine_factory=factory,
        on_log=logs.append,
    )

    rendered = captured.get("rendered")
    assert isinstance(rendered, str)
    assert "Emma => Emma" in rendered
    assert "Belledors => Belledors" in rendered

    cache_file = cache_root / "msrt" / "glossaries" / "wistoria.tsv"
    assert cache_file.exists(), f"Cache file should be saved at {cache_file}"
    assert any("non in cache" in line for line in logs)
    assert any("salvato" in line for line in logs)


def test_run_local_skips_auto_glossary_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_dir = tmp_path / "pages"
    _write_pages(image_dir, [1])
    out_dir = tmp_path / "out"
    monkeypatch.setenv("HOME", str(tmp_path))

    from msrt.translate import glossary_builder as gb

    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Auto-build must not run when auto_glossary=False")

    monkeypatch.setattr(gb, "build_glossary_via_llm", explode)

    captured: dict[str, object] = {}

    class CapturingEngine(TranslationEngine):
        def translate(
            self, input_dir: Path, output_dir: Path, job: TranslationJob
        ) -> TranslationResult:
            cfg_path = job.gpt_config_path
            captured["gpt_config_path"] = cfg_path
            if cfg_path is not None and cfg_path.exists():
                captured["rendered"] = cfg_path.read_text(encoding="utf-8")
            output_dir.mkdir(parents=True, exist_ok=True)
            for image_path in input_dir.iterdir():
                if image_path.suffix == ".png":
                    shutil.copy(image_path, output_dir / image_path.name)
            return TranslationResult(
                output_dir=output_dir, text_output_file=None, stdout="", stderr=""
            )

    def factory(_settings: Settings, _prompt_config: Path) -> TranslationEngine:
        return CapturingEngine()

    run_local(
        image_dir,
        out_dir,
        series="Wistoria",
        chapter_number="1",
        chapter_title=None,
        lang_source="en",
        lang_target="it",
        fmt="pdf",
        job=TranslationJob(model="sonnet", use_gpu=False, auto_glossary=False),
        engine_factory=factory,
    )

    # The pipeline still renders a temp gpt_config (otherwise MITR would
    # crash on the un-substituted ``{glossary}`` placeholder) — but with
    # the glossary block replaced by the explicit "(none)" marker.
    assert captured["gpt_config_path"] is not None
    rendered = captured.get("rendered")
    assert isinstance(rendered, str)
    assert "(none" in rendered
    assert "{glossary}" not in rendered


def test_run_local_falls_through_when_glossary_build_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the LLM build fails (proxy down, hallucination), the run must
    continue without glossary rather than aborting."""

    image_dir = tmp_path / "pages"
    _write_pages(image_dir, [1])
    out_dir = tmp_path / "out"
    monkeypatch.setenv("HOME", str(tmp_path))

    from msrt.translate import glossary_builder as gb

    def boom(*_args: object, **_kwargs: object) -> None:
        raise gb.GlossaryBuildError("LiteLLM down")

    monkeypatch.setattr(gb, "build_glossary_via_llm", boom)

    captured: dict[str, object] = {}

    class CapturingEngine(TranslationEngine):
        def translate(
            self, input_dir: Path, output_dir: Path, job: TranslationJob
        ) -> TranslationResult:
            captured["gpt_config_path"] = job.gpt_config_path
            output_dir.mkdir(parents=True, exist_ok=True)
            for image_path in input_dir.iterdir():
                if image_path.suffix == ".png":
                    shutil.copy(image_path, output_dir / image_path.name)
            return TranslationResult(
                output_dir=output_dir, text_output_file=None, stdout="", stderr=""
            )

    def factory(_settings: Settings, _prompt_config: Path) -> TranslationEngine:
        return CapturingEngine()

    logs: list[str] = []
    run_local(
        image_dir,
        out_dir,
        series="Wistoria",
        chapter_number="1",
        chapter_title=None,
        lang_source="en",
        lang_target="it",
        fmt="pdf",
        job=TranslationJob(model="sonnet", use_gpu=False),
        engine_factory=factory,
        on_log=logs.append,
    )

    # Even on build failure we render a glossary-less temp config so MITR
    # doesn't trip on the un-substituted ``{glossary}`` placeholder.
    assert captured["gpt_config_path"] is not None
    assert any("Auto-glossary fallita" in line for line in logs)


def test_run_local_never_leaves_unsubstituted_glossary_placeholder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: MITR's ``custom_openai`` translator calls
    ``template.format(to_lang=…)`` and crashes with KeyError if the
    template still contains the literal ``{glossary}`` placeholder.

    Whatever path the pipeline takes (auto-glossary on/off, build failure,
    explicit override) the gpt_config that reaches the engine must always
    have ``{glossary}`` already substituted.
    """

    image_dir = tmp_path / "pages"
    _write_pages(image_dir, [1])
    out_dir = tmp_path / "out"
    monkeypatch.setenv("HOME", str(tmp_path))

    captured_paths: list[Path] = []

    class CapturingEngine(TranslationEngine):
        def translate(
            self, input_dir: Path, output_dir: Path, job: TranslationJob
        ) -> TranslationResult:
            cfg = job.gpt_config_path
            assert cfg is not None, "gpt_config_path must always be set"
            text = cfg.read_text(encoding="utf-8")
            assert "{glossary}" not in text, (
                f"Unsubstituted {{glossary}} placeholder leaked to MITR: {text}"
            )
            captured_paths.append(cfg)
            output_dir.mkdir(parents=True, exist_ok=True)
            for image_path in input_dir.iterdir():
                if image_path.suffix == ".png":
                    shutil.copy(image_path, output_dir / image_path.name)
            return TranslationResult(
                output_dir=output_dir, text_output_file=None, stdout="", stderr=""
            )

    def factory(_settings: Settings, _prompt_config: Path) -> TranslationEngine:
        return CapturingEngine()

    # Path 1: auto-glossary disabled (entries empty → "(none)" marker).
    run_local(
        image_dir,
        out_dir,
        series="Wistoria",
        chapter_number="1",
        chapter_title=None,
        lang_source="en",
        lang_target="it",
        fmt="pdf",
        job=TranslationJob(model="sonnet", use_gpu=False, auto_glossary=False),
        engine_factory=factory,
    )

    assert captured_paths, "engine must have been called at least once"


def test_run_local_uses_glossary_path_in_job(tmp_path: Path) -> None:
    """When --glossary is set, the engine should receive a job whose
    gpt_config_path points at a rendered YAML containing the entries.
    """

    image_dir = tmp_path / "pages"
    _write_pages(image_dir, [1])
    out_dir = tmp_path / "out"

    glossary_path = tmp_path / "glossary.tsv"
    glossary_path.write_text("Emma\tEmma\nBelledors\tBelledors\n", encoding="utf-8")

    captured: dict[str, Path | None] = {}

    class CapturingEngine(TranslationEngine):
        def translate(
            self, input_dir: Path, output_dir: Path, job: TranslationJob
        ) -> TranslationResult:
            captured["gpt_config_path"] = job.gpt_config_path
            output_dir.mkdir(parents=True, exist_ok=True)
            for image_path in input_dir.iterdir():
                if image_path.suffix == ".png":
                    shutil.copy(image_path, output_dir / image_path.name)
            # Read the rendered YAML so we can assert on its content even
            # after the pipeline cleans it up.
            cfg = job.gpt_config_path
            if cfg is not None and cfg.exists():
                captured["rendered_text"] = cfg.read_text(encoding="utf-8")  # type: ignore[assignment]
            return TranslationResult(
                output_dir=output_dir, text_output_file=None, stdout="", stderr=""
            )

    def factory(_settings: Settings, _prompt_config: Path) -> TranslationEngine:
        return CapturingEngine()

    run_local(
        image_dir,
        out_dir,
        series="Wistoria",
        chapter_number="44",
        chapter_title=None,
        lang_source="en",
        lang_target="it",
        fmt="pdf",
        job=TranslationJob(model="sonnet", use_gpu=False, glossary_path=glossary_path),
        engine_factory=factory,
    )

    rendered = captured.get("rendered_text")
    assert isinstance(rendered, str)
    assert "Emma => Emma" in rendered
    assert "Belledors => Belledors" in rendered
    # Pipeline must clean up the temp file.
    assert captured["gpt_config_path"] is not None
    assert not captured["gpt_config_path"].exists()
