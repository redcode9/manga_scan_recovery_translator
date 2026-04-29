"""High-level local pipeline orchestration."""

from __future__ import annotations

import hashlib
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from PIL import Image

from msrt import __version__
from msrt.config import Settings, resolve_model_alias
from msrt.models import (
    Chapter,
    ManifestEngine,
    ManifestFetch,
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
from msrt.translate.glossary import (
    build_gpt_config_with_glossary,
    load_glossary,
    load_or_build_glossary,
)
from msrt.translate.glossary_builder import GlossaryBuildError

EngineFactory = Callable[[Settings, Path], TranslationEngine]
PhaseCallback = Callable[[str], None]
LogCallback = Callable[[str], None]

PROMPT_CONFIG_PATH = Path("configs/translator-prompt.yaml")
DEFAULT_GPT_CONFIG_PATH = Path("configs/mitr-gpt-config.yaml")

# Series titles that should NOT trigger an auto-glossary build, because they
# carry no useful signal for the LLM and would just burn a paid call and
# pollute the cache (e.g. ``untitled-series.tsv``).
_PLACEHOLDER_SERIES_TITLES = frozenset({"untitled series", "untitled", ""})


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
    input_type: Literal["local", "url"] = "local",
    input_url: str | None = None,
    fetch_metadata: ManifestFetch | None = None,
) -> RunManifest:
    """Build the canonical ``RunManifest`` for one pipeline invocation.

    ``input_type``/``input_url``/``fetch_metadata`` are populated only by
    ``msrt run`` (URL pipeline). ``msrt run-local`` leaves them at their
    defaults so the manifest schema reflects "this run came from a
    user-provided folder".
    """

    provider, resolved_model, _ = resolve_model_alias(job.model)
    return RunManifest(
        msrt_version=__version__,
        command=command,
        input=ManifestInput(
            type=input_type,
            path=str(input_path) if input_type == "local" else None,
            url=input_url,
            page_count=len(chapter.pages),
        ),
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
        fetch=fetch_metadata,
    )


def save_manifest(manifest: RunManifest, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "msrt-run.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


def _series_is_meaningful(series: str) -> bool:
    """Reject empty / default-placeholder series titles.

    Auto-glossary should not fire on the CLI-default ``"Untitled Series"``
    or an empty string: there is no signal for the LLM, the call would
    just cost tokens, and the resulting cache file would clutter
    ``~/.cache/msrt/glossaries/`` with a useless ``untitled-series.tsv``.
    """

    return series.strip().lower() not in _PLACEHOLDER_SERIES_TITLES


def reset_translated_dir(translated_dir: Path) -> None:
    """Remove all *files* in ``translated_dir`` so that a new run cannot
    accidentally pick up images left over from a previous chapter.

    Subdirectories are left in place to be conservative; MITR's flat layout
    only writes files at the root, so this is enough for our purposes.
    """

    if not translated_dir.exists():
        translated_dir.mkdir(parents=True, exist_ok=True)
        return
    for entry in translated_dir.iterdir():
        if entry.is_file() or entry.is_symlink():
            entry.unlink()


def _prepare_gpt_config(
    job: TranslationJob,
    *,
    out_dir: Path,
    base_config: Path,
    series: str,
    settings: Settings,
    log: Callable[[str], None] | None = None,
) -> tuple[TranslationJob, Path | None]:
    """Build a temporary gpt_config YAML with the series glossary injected.

    Sources for the glossary entries, in order of priority:

    1. ``job.glossary_path`` set by the caller (explicit override).
    2. Cached glossary at ``settings.cache_dir/glossaries/<slug>.tsv``.
    3. Fresh build via the configured LLM, persisted to the cache for
       future runs.

    If the LLM build fails (proxy down, hallucination produced no rows,
    etc.) we log a warning and fall through to a glossary-less config
    rather than aborting the whole translation.

    Returns the updated job and the temp file path so the caller can
    ``unlink`` it once the engine has finished. ``None`` for the path
    means no temp file was rendered (e.g. nothing to inject and no
    auto-build configured).
    """

    log_fn = log or _noop_phase  # signature matches; we just want a sink
    entries: dict[str, str] = {}

    if job.glossary_path is not None:
        entries = load_glossary(job.glossary_path)
    elif job.auto_glossary and _series_is_meaningful(series):
        try:
            _path, entries, _result = load_or_build_glossary(
                series, model=job.model, settings=settings, log=log_fn
            )
        except GlossaryBuildError as exc:
            log_fn(f"[warn] Auto-glossary fallita ({exc}); proseguo senza glossary.")
            entries = {}
    elif job.auto_glossary and not _series_is_meaningful(series):
        log_fn(
            "[info] Auto-glossary saltata: --series è vuoto o il default "
            "('Untitled Series'). Passa un titolo reale per attivarla."
        )

    # Always render the gpt_config to a temp file with the {glossary} placeholder
    # substituted — even when entries is empty. Otherwise MITR receives the raw
    # config file, calls ``template.format(to_lang=…)`` on a string that still
    # contains ``{glossary}``, and crashes with ``KeyError: 'glossary'`` on
    # every page (silently, since exit code stays 0).
    target_dir = out_dir / ".msrt-tmp"
    rendered = build_gpt_config_with_glossary(
        base_config=base_config, entries=entries, target_dir=target_dir
    )
    return job.model_copy(update={"gpt_config_path": rendered}), rendered


def _collect_translated_files(
    chapter: Chapter, translated_dir: Path, *, log_dir: Path | None = None
) -> list[Path]:
    """Return the translated image for each page, in chapter order.

    Raises ``ValueError`` if any page is missing from ``translated_dir``,
    so we never silently package a stale file from a previous run. The
    error message points at the captured MITR log when one is available.
    """

    files: list[Path] = []
    missing: list[str] = []
    for page in chapter.pages:
        candidate = translated_dir / page.local_path.name
        if candidate.exists():
            files.append(candidate)
        else:
            missing.append(page.local_path.name)
    if missing:
        sample = ", ".join(missing[:3])
        more = "" if len(missing) <= 3 else f" (+{len(missing) - 3} altre)"
        log_hint = f" Vedi il log MITR in {log_dir}/mitr.log." if log_dir else ""
        raise ValueError(
            f"MITR non ha prodotto {len(missing)} pagine attese su {len(chapter.pages)}: "
            f"{sample}{more}.{log_hint}"
        )
    return files


def _write_mitr_log(log_dir: Path, stdout: str, stderr: str) -> Path:
    """Persist MITR's stdout+stderr for post-mortem debugging.

    MITR sometimes exits with code 0 even when every page errored
    (logged as WARNING/ERROR but not propagated). Writing the captured
    output to disk lets the user (and the test suite) inspect what went
    wrong without re-running the translation.
    """

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "mitr.log"
    payload_parts = []
    if stdout:
        payload_parts.append("=== STDOUT ===\n" + stdout)
    if stderr:
        payload_parts.append("=== STDERR ===\n" + stderr)
    log_path.write_text(
        "\n\n".join(payload_parts) if payload_parts else "(no output)\n",
        encoding="utf-8",
    )
    return log_path


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
    on_log: LogCallback | None = None,
) -> RunManifest:
    """Run only the MITR translation step. No CBZ/PDF packaging.

    The translated images are written to ``out_dir/translated-pages``. The
    returned ``RunManifest`` lists this directory in ``output_files`` and tags
    ``metadata["mode"] = "translate-only"`` so callers can distinguish it from
    a full ``run_local`` invocation.
    """

    factory = engine_factory or _default_engine_factory
    phase = on_phase or _noop_phase
    log = on_log or _noop_phase
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
    reset_translated_dir(translated_dir)

    job = job.model_copy(update={"target_lang": mitr_target_language(lang_target)})
    job, gpt_config_temp = _prepare_gpt_config(
        job,
        out_dir=out_dir,
        base_config=DEFAULT_GPT_CONFIG_PATH,
        series=series,
        settings=settings,
        log=log,
    )
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
    log_dir = out_dir / ".msrt-tmp"
    try:
        result = engine.translate(image_dir, translated_dir, job)
        _write_mitr_log(log_dir, result.stdout, result.stderr)
        for page in chapter.pages:
            candidate = translated_dir / page.local_path.name
            if candidate.exists():
                page.translated_path = candidate
        manifest.engine.mitr_version = "unknown"
        # Validate that MITR actually produced every expected page. ``run_local``
        # does this before packaging; ``translate_only`` skips packaging but the
        # check is just as important here — otherwise an exit-0 silent failure
        # leaves the user with an incomplete output dir and no surfaced error.
        _collect_translated_files(chapter, translated_dir, log_dir=log_dir)
        manifest.output_files = [str(result.output_dir)]
    except Exception as exc:
        manifest.errors.append(str(exc))
        manifest.finish()
        save_manifest(manifest, out_dir)
        raise
    finally:
        if gpt_config_temp is not None:
            gpt_config_temp.unlink(missing_ok=True)

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
    on_log: LogCallback | None = None,
    input_type: Literal["local", "url"] = "local",
    input_url: str | None = None,
    fetch_metadata: ManifestFetch | None = None,
) -> RunManifest:
    factory = engine_factory or _default_engine_factory
    phase = on_phase or _noop_phase
    log = on_log or _noop_phase
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
    reset_translated_dir(translated_dir)

    job = job.model_copy(update={"target_lang": mitr_target_language(lang_target)})
    job, gpt_config_temp = _prepare_gpt_config(
        job,
        out_dir=out_dir,
        base_config=DEFAULT_GPT_CONFIG_PATH,
        series=series,
        settings=settings,
        log=log,
    )
    manifest = build_manifest(
        chapter,
        command=" ".join(sys.argv),
        input_path=image_dir,
        job=job,
        engine_binary=settings.mitr_bin_path,
        input_type=input_type,
        input_url=input_url,
        fetch_metadata=fetch_metadata,
    )

    phase("translate")
    engine = factory(settings, PROMPT_CONFIG_PATH)
    log_dir = out_dir / ".msrt-tmp"
    try:
        result = engine.translate(image_dir, translated_dir, job)
        _write_mitr_log(log_dir, result.stdout, result.stderr)
        for page in chapter.pages:
            candidate = translated_dir / page.local_path.name
            if candidate.exists():
                page.translated_path = candidate
        manifest.engine.mitr_version = "unknown"

        translated_files = _collect_translated_files(chapter, translated_dir, log_dir=log_dir)

        phase("package")
        output_files = package_outputs(translated_files, chapter, out_dir, fmt)
        manifest.output_files = [str(path) for path in output_files]
    except Exception as exc:
        manifest.errors.append(str(exc))
        manifest.finish()
        save_manifest(manifest, out_dir)
        raise
    finally:
        if gpt_config_temp is not None:
            gpt_config_temp.unlink(missing_ok=True)
    manifest.finish()
    save_manifest(manifest, out_dir)
    phase("done")
    return manifest


def package_outputs(files: list[Path], chapter: Chapter, out_dir: Path, fmt: str) -> list[Path]:
    """Package the given (already-ordered) list of translated files.

    Unlike a directory scan, this never picks up stragglers from previous
    runs: the caller is responsible for providing the exact set of pages
    in the right order.
    """

    if not files:
        raise ValueError("Nessun file tradotto da pacchettizzare.")
    slug = _chapter_slug(chapter)
    outputs: list[Path] = []
    if fmt in {"cbz", "both"}:
        outputs.append(package_cbz(files, chapter, out_dir / f"{slug}.cbz"))
    if fmt in {"pdf", "both"}:
        outputs.append(package_pdf(files, out_dir / f"{slug}.pdf"))
    if not outputs:
        raise ValueError(f"Formato non supportato: {fmt}")
    return outputs


def _chapter_slug(chapter: Chapter) -> str:
    series = _slugify(chapter.series_title)
    number = _slugify(chapter.chapter_number)
    return f"{series}-{number}-{chapter.language_target}"


def _slugify(value: str) -> str:
    return slugify(value)


def slugify(value: str) -> str:
    """Public path-safe slugifier. Used by ``msrt run`` to build the
    fetch staging path under ``out/.msrt-fetch/<site>/<series>/<chapter>``."""

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
