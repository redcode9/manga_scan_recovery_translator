"""High-level local pipeline orchestration."""

from __future__ import annotations

import hashlib
import re
import sys
from collections.abc import Callable
from pathlib import Path

from PIL import Image

from msrt import __version__
from msrt.config import Settings, resolve_model_alias
from msrt.models import (
    Chapter,
    ManifestEngine,
    ManifestInput,
    ManifestModel,
    Page,
    RunManifest,
    TranslationJob,
)
from msrt.package.cbz import package_cbz
from msrt.package.naming import image_files
from msrt.package.pdf import package_pdf
from msrt.translate.engine import SubprocessEngine, TranslationEngine

EngineFactory = Callable[[Settings, Path], TranslationEngine]
PhaseCallback = Callable[[str], None]

PROMPT_CONFIG_PATH = Path("configs/translator-prompt.yaml")


def _default_engine_factory(settings: Settings, prompt_config: Path) -> TranslationEngine:
    return SubprocessEngine(settings=settings, prompt_config=prompt_config)


def _noop_phase(_: str) -> None:
    return None


def collect_local_chapter(
    image_dir: Path,
    *,
    series: str,
    chapter_number: str,
    chapter_title: str | None,
    lang_source: str,
    lang_target: str,
) -> Chapter:
    order = image_files(image_dir)
    if not order.files:
        raise ValueError(f"Nessuna immagine supportata trovata in {image_dir}")

    pages: list[Page] = []
    for index, image_path in enumerate(order.files, start=1):
        with Image.open(image_path) as image:
            width, height = image.size
        pages.append(
            Page(
                index=index,
                local_path=image_path,
                width=width,
                height=height,
                sha256=file_sha256(image_path),
            )
        )

    return Chapter(
        series_title=series,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        language_source=lang_source,
        language_target=lang_target,
        pages=pages,
        metadata={
            "Series": series,
            "Number": chapter_number,
            "Title": chapter_title or "",
            "LanguageISO": lang_target,
        },
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def build_manifest(
    chapter: Chapter,
    *,
    command: str,
    input_path: Path,
    job: TranslationJob,
    engine_binary: str | None,
) -> RunManifest:
    provider, resolved_model, _ = resolve_model_alias(job.model)
    return RunManifest(
        msrt_version=__version__,
        command=command,
        input=ManifestInput(type="local", path=str(input_path), page_count=len(chapter.pages)),
        page_order=[page.local_path.name for page in chapter.pages],
        page_hashes={page.local_path.name: page.sha256 for page in chapter.pages},
        model=ManifestModel(alias=job.model, resolved_id=resolved_model, provider=provider),
        engine=ManifestEngine(type=job.engine, binary=engine_binary),
        font_path=str(job.font_path) if job.font_path else None,
        metadata={
            "series": chapter.series_title,
            "chapter": chapter.chapter_number,
            "title": chapter.chapter_title or "",
            "language_source": chapter.language_source,
            "language_target": chapter.language_target,
        },
    )


def save_manifest(manifest: RunManifest, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "msrt-run.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def translate_only(
    image_dir: Path,
    out_dir: Path,
    *,
    series: str,
    chapter_number: str,
    chapter_title: str | None,
    lang_source: str,
    lang_target: str,
    job: TranslationJob,
    engine_factory: EngineFactory | None = None,
    on_phase: PhaseCallback | None = None,
) -> RunManifest:
    """Run only the MITR translation step. No CBZ/PDF packaging.

    The translated images are written to ``out_dir/translated-pages``. The
    returned ``RunManifest`` lists this directory in ``output_files`` and tags
    ``metadata["mode"] = "translate-only"`` so callers can distinguish it from
    a full ``run_local`` invocation.
    """

    factory = engine_factory or _default_engine_factory
    phase = on_phase or _noop_phase
    settings = Settings()

    phase("collect")
    chapter = collect_local_chapter(
        image_dir,
        series=series,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        lang_source=lang_source,
        lang_target=lang_target,
    )

    translated_dir = out_dir / "translated-pages"
    job = job.model_copy(update={"target_lang": mitr_target_language(lang_target)})
    manifest = build_manifest(
        chapter,
        command=" ".join(sys.argv),
        input_path=image_dir,
        job=job,
        engine_binary=settings.mitr_bin_path,
    )
    manifest.metadata["mode"] = "translate-only"

    phase("translate")
    engine = factory(settings, PROMPT_CONFIG_PATH)
    try:
        result = engine.translate(image_dir, translated_dir, job)
        for page in chapter.pages:
            candidate = translated_dir / page.local_path.name
            if candidate.exists():
                page.translated_path = candidate
        manifest.engine.mitr_version = "unknown"
        manifest.output_files = [str(result.output_dir)]
    except Exception as exc:
        manifest.errors.append(str(exc))
        manifest.finish()
        save_manifest(manifest, out_dir)
        raise

    manifest.finish()
    save_manifest(manifest, out_dir)
    phase("done")
    return manifest


def run_local(
    image_dir: Path,
    out_dir: Path,
    *,
    series: str,
    chapter_number: str,
    chapter_title: str | None,
    lang_source: str,
    lang_target: str,
    fmt: str,
    job: TranslationJob,
    engine_factory: EngineFactory | None = None,
    on_phase: PhaseCallback | None = None,
) -> RunManifest:
    factory = engine_factory or _default_engine_factory
    phase = on_phase or _noop_phase
    settings = Settings()

    phase("collect")
    chapter = collect_local_chapter(
        image_dir,
        series=series,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        lang_source=lang_source,
        lang_target=lang_target,
    )

    translated_dir = out_dir / "translated-pages"
    job = job.model_copy(update={"target_lang": mitr_target_language(lang_target)})
    manifest = build_manifest(
        chapter,
        command=" ".join(sys.argv),
        input_path=image_dir,
        job=job,
        engine_binary=settings.mitr_bin_path,
    )

    phase("translate")
    engine = factory(settings, PROMPT_CONFIG_PATH)
    try:
        result = engine.translate(image_dir, translated_dir, job)
        for page in chapter.pages:
            candidate = translated_dir / page.local_path.name
            if candidate.exists():
                page.translated_path = candidate
        manifest.engine.mitr_version = "unknown"

        phase("package")
        output_files = package_outputs(
            translated_dir if result.output_dir.exists() else image_dir, chapter, out_dir, fmt
        )
        manifest.output_files = [str(path) for path in output_files]
    except Exception as exc:
        manifest.errors.append(str(exc))
        manifest.finish()
        save_manifest(manifest, out_dir)
        raise
    manifest.finish()
    save_manifest(manifest, out_dir)
    phase("done")
    return manifest


def package_outputs(image_dir: Path, chapter: Chapter, out_dir: Path, fmt: str) -> list[Path]:
    slug = _chapter_slug(chapter)
    outputs: list[Path] = []
    if fmt in {"cbz", "both"}:
        outputs.append(package_cbz(image_dir, chapter, out_dir / f"{slug}.cbz"))
    if fmt in {"pdf", "both"}:
        outputs.append(package_pdf(image_dir, out_dir / f"{slug}.pdf"))
    if not outputs:
        raise ValueError(f"Formato non supportato: {fmt}")
    return outputs


def _chapter_slug(chapter: Chapter) -> str:
    series = _slugify(chapter.series_title)
    number = _slugify(chapter.chapter_number)
    return f"{series}-{number}-{chapter.language_target}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return slug.strip("-") or "untitled"


def mitr_target_language(lang_target: str) -> str:
    normalized = lang_target.strip().lower().replace("_", "-")
    aliases = {
        "it": "ITA",
        "ita": "ITA",
        "italian": "ITA",
        "italiano": "ITA",
    }
    if normalized in aliases:
        return aliases[normalized]
    if len(normalized) == 3 and normalized.isalpha():
        return normalized.upper()
    raise ValueError(
        f"Target language non supportata per MITR: {lang_target!r}. Per ora usare 'it'/'ITA'."
    )
