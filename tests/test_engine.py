from __future__ import annotations

from pathlib import Path

from msrt.config import Settings
from msrt.models import TranslationJob
from msrt.translate.engine import SubprocessEngine


def test_subprocess_engine_uses_job_target_lang(tmp_path: Path) -> None:
    engine = SubprocessEngine(settings=Settings(), prompt_config=Path("prompt.yaml"))
    command = engine._command(
        tmp_path / "in",
        tmp_path / "out",
        tmp_path / "text.json",
        TranslationJob(target_lang="FRA", use_gpu=False),
    )

    target_index = command.index("--target-lang")
    assert command[target_index + 1] == "FRA"
