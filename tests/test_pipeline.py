from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from msrt.models import TranslationJob
from msrt.pipeline import run_local
from msrt.translate.engine import TranslationError


def test_run_local_writes_manifest_when_mitr_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_dir = tmp_path / "pages"
    image_dir.mkdir()
    Image.new("RGB", (80, 120), "white").save(image_dir / "1.png")
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
