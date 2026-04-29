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
