"""Translation engines for external manga-image-translator integration."""

from __future__ import annotations

import os
import shlex
import subprocess
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
        command = self._command(input_dir, output_dir, text_output, job)
        env = self._environment(job)
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

    def _command(
        self,
        input_dir: Path,
        output_dir: Path,
        text_output: Path,
        job: TranslationJob,
    ) -> list[str]:
        base = shlex.split(self.settings.mitr_bin_path or "python -m manga_translator")
        command = [
            *base,
            "local",
            "-i",
            str(input_dir),
            "-o",
            str(output_dir),
            "--translator",
            "custom_openai",
            "--target-lang",
            job.target_lang,
            "--gpt-config",
            str(self.prompt_config),
            "--save-text",
            "--save-text-file",
            str(text_output),
            "--overwrite",
        ]
        if job.renderer == "mitr-manga2eng":
            command.append("--manga2eng")
        if job.font_path is not None:
            command.extend(["--font-path", str(job.font_path)])
        if job.use_gpu:
            command.append("--use-gpu")
        return command

    def _environment(self, job: TranslationJob) -> dict[str, str]:
        _, resolved_model, _ = resolve_model_alias(job.model)
        env = os.environ.copy()
        env.setdefault("OPENAI_API_BASE", f"{self.settings.litellm_base_url}/v1")
        env.setdefault("OPENAI_API_KEY", "msrt-local-litellm")
        env["OPENAI_MODEL"] = job.model
        env["MSRT_RESOLVED_MODEL"] = resolved_model
        return env


class HttpEngine(TranslationEngine):
    def translate(
        self, input_dir: Path, output_dir: Path, job: TranslationJob
    ) -> TranslationResult:
        raise NotImplementedError(
            "HTTP engine previsto per batch futuri, non implementato in v0.1."
        )
