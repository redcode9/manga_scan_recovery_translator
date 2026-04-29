from __future__ import annotations

from pathlib import Path

from msrt.config import Settings
from msrt.models import TranslationJob
from msrt.translate.engine import SubprocessEngine


def test_subprocess_engine_command_structure(tmp_path: Path) -> None:
    """Top-level flags come before the ``local`` subcommand; translator/lang
    settings live in the config-file (not in CLI flags) on this MITR build."""

    engine = SubprocessEngine(settings=Settings(), prompt_config=Path("prompt.yaml"))
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text("{}", encoding="utf-8")
    command = engine._command(
        tmp_path / "in",
        tmp_path / "out",
        tmp_path / "text.json",
        cfg_path,
        TranslationJob(target_lang="FRA", use_gpu=False),
    )

    local_index = command.index("local")
    config_index = command.index("--config-file")
    assert config_index > local_index
    assert command[config_index + 1] == str(cfg_path)
    # MITR no longer accepts --translator/--target-lang as CLI flags.
    assert "--translator" not in command
    assert "--target-lang" not in command


def test_subprocess_engine_use_gpu_top_level(tmp_path: Path) -> None:
    engine = SubprocessEngine(settings=Settings(), prompt_config=Path("prompt.yaml"))
    cfg = tmp_path / "cfg.json"
    cfg.write_text("{}", encoding="utf-8")
    command = engine._command(
        tmp_path / "in",
        tmp_path / "out",
        tmp_path / "text.json",
        cfg,
        TranslationJob(target_lang="ITA", use_gpu=True),
    )

    use_gpu_index = command.index("--use-gpu")
    local_index = command.index("local")
    assert use_gpu_index < local_index, "--use-gpu must precede the 'local' subcommand"


def test_subprocess_engine_pre_dict_top_level(tmp_path: Path) -> None:
    engine = SubprocessEngine(settings=Settings(), prompt_config=Path("prompt.yaml"))
    cfg = tmp_path / "cfg.json"
    cfg.write_text("{}", encoding="utf-8")
    pre_dict = tmp_path / "ocr.tsv"
    pre_dict.write_text("IEMMA\tEMMA\n", encoding="utf-8")
    command = engine._command(
        tmp_path / "in",
        tmp_path / "out",
        tmp_path / "text.json",
        cfg,
        TranslationJob(target_lang="ITA", use_gpu=False, pre_dict_path=pre_dict),
    )

    pre_index = command.index("--pre-dict")
    local_index = command.index("local")
    assert pre_index < local_index
    assert command[pre_index + 1] == str(pre_dict)


def test_subprocess_engine_mitr_config_uses_override(tmp_path: Path) -> None:
    """``job.gpt_config_path`` should override the default config path."""

    engine = SubprocessEngine(settings=Settings(), prompt_config=Path("prompt.yaml"))
    override = tmp_path / "custom-gpt.yaml"
    override.write_text("temperature: 1\n", encoding="utf-8")

    cfg = engine._mitr_config(
        TranslationJob(target_lang="ITA", use_gpu=False, gpt_config_path=override)
    )

    translator_cfg = cfg["translator"]
    assert isinstance(translator_cfg, dict)
    assert translator_cfg["gpt_config"] == str(override)


def test_subprocess_engine_mitr_config_default_path(tmp_path: Path) -> None:
    engine = SubprocessEngine(settings=Settings(), prompt_config=Path("prompt.yaml"))

    cfg = engine._mitr_config(TranslationJob(target_lang="ITA", use_gpu=False))

    translator_cfg = cfg["translator"]
    assert isinstance(translator_cfg, dict)
    assert translator_cfg["gpt_config"].endswith("configs/mitr-gpt-config.yaml")
