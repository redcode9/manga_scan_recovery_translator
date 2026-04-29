"""Translation engines for external manga-image-translator integration."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from msrt.config import Settings, resolve_model_alias
from msrt.models import TranslationJob


class TranslationError(RuntimeError):
    """Raised when the external translation engine fails."""


@dataclass(frozen=True)
class TranslationResult:
    output_dir: Path
    text_output_file: Path | None
    stdout: str
    stderr: str


class TranslationEngine(ABC):
    @abstractmethod
    def translate(
        self, input_dir: Path, output_dir: Path, job: TranslationJob
    ) -> TranslationResult:
        """Translate a directory of page images."""


class SubprocessEngine(TranslationEngine):
    def __init__(self, settings: Settings, prompt_config: Path) -> None:
        self.settings = settings
        self.prompt_config = prompt_config

    def translate(
        self, input_dir: Path, output_dir: Path, job: TranslationJob
    ) -> TranslationResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        text_output = output_dir / "mitr-text.json"
        env = self._environment(job)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="msrt-mitr-cfg-"
        ) as cfg_f:
            json.dump(self._mitr_config(job), cfg_f)
            cfg_path = Path(cfg_f.name)
        try:
            command = self._command(input_dir, output_dir, text_output, cfg_path, job)
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    env=env,
                )
            except FileNotFoundError as exc:
                raise TranslationError(f"MITR non trovato: {command[0]}") from exc
        finally:
            cfg_path.unlink(missing_ok=True)

        if completed.returncode != 0:
            raise TranslationError(
                "MITR ha restituito exit code "
                f"{completed.returncode}.\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )

        return TranslationResult(
            output_dir=output_dir,
            text_output_file=text_output if text_output.exists() else None,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _mitr_config(self, job: TranslationJob) -> dict[str, object]:
        """Build the JSON config dict passed to MITR via --config-file.

        MITR expects translator settings nested under a "translator" key.
        custom_openai reads CUSTOM_OPENAI_API_BASE/KEY/MODEL from env.
        gpt_config (YAML) sets temperature=1 required by GPT-5.5.
        Caller can override the gpt_config via job.gpt_config_path; this
        is how the pipeline injects a series glossary.
        """
        if job.gpt_config_path is not None:
            gpt_config_path = job.gpt_config_path
        else:
            gpt_config_path = (
                Path(__file__).parent.parent.parent.parent / "configs" / "mitr-gpt-config.yaml"
            )
        return {
            "translator": {
                "translator": "custom_openai",
                "target_lang": job.target_lang,
                "gpt_config": str(gpt_config_path),
            },
            # Lower thresholds + rotation detection for italic/stylised text.
            # dbconvnext misses angled text at its defaults (0.7/0.5, no rotate).
            "detector": {
                "box_threshold": 0.5,
                "text_threshold": 0.3,
                "det_rotate": True,
                "det_auto_rotate": True,
            },
        }

    def _command(
        self,
        input_dir: Path,
        output_dir: Path,
        text_output: Path,
        cfg_path: Path,
        job: TranslationJob,
    ) -> list[str]:
        base = shlex.split(self.settings.mitr_bin_path or "python -m manga_translator")
        # Top-level flags (shown in manga_translator -h) come before the subcommand.
        # translator/target_lang go in --config-file (not exposed as CLI flags in this build).
        command = [*base]
        if job.use_gpu:
            command.append("--use-gpu")
        if job.font_path is not None:
            command.extend(["--font-path", str(job.font_path)])
        if job.pre_dict_path is not None:
            command.extend(["--pre-dict", str(job.pre_dict_path)])
        command += [
            "local",
            "-i",
            str(input_dir),
            "-o",
            str(output_dir),
            "--config-file",
            str(cfg_path),
            "--save-text-file",
            str(text_output),
            "--overwrite",
        ]
        return command

    def _environment(self, job: TranslationJob) -> dict[str, str]:
        _, resolved_model, _ = resolve_model_alias(job.model)
        env = os.environ.copy()
        # custom_openai translator reads CUSTOM_OPENAI_* vars (not OPENAI_*).
        env["CUSTOM_OPENAI_API_BASE"] = f"{self.settings.litellm_base_url}/v1"
        env["CUSTOM_OPENAI_API_KEY"] = "msrt-local-litellm"
        env["CUSTOM_OPENAI_MODEL"] = job.model
        env["MSRT_RESOLVED_MODEL"] = resolved_model
        return env


class HttpEngine(TranslationEngine):
    def translate(
        self, input_dir: Path, output_dir: Path, job: TranslationJob
    ) -> TranslationResult:
        raise NotImplementedError(
            "HTTP engine previsto per batch futuri, non implementato in v0.1."
        )
