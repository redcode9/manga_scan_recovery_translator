"""Bridge between the UI server's job manager and the existing pipeline.

The UI never re-implements scraping/translation/packaging. It just
hands the pipeline a couple of callbacks (``on_phase``, ``on_log``)
that translate into structured SSE events. Everything else — fetch
staging, atomic promote, selectors, ManifestFetch generation — lives
in the core pipeline modules and stays untouched.
"""

from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path
from typing import Literal

from msrt.models import ManifestFetch, RunManifest, TranslationJob
from msrt.pipeline import run_local, slugify
from msrt.scrape.base import ChapterLink, FetchError, FetchResult
from msrt.scrape.registry import scraper_for_url
from msrt.scrape.selection import (
    parse_chapter_list,
    parse_chapter_range,
    select_chapters,
)
from msrt.ui_server.jobs import JobContext
from msrt.ui_server.schemas import Event, JobOptions

_PIPELINE_PHASE_TO_EVENT = {
    "collect": "collect",
    "translate": "translate",
    "postprocess": "postprocess",
    "package": "package",
    "done": "done",
}


async def run_job(ctx: JobContext) -> None:
    """Job runner wired into ``JobManager``. Picks the right path
    (local / single URL / batch URL) from the request kind."""

    request = ctx.job.request
    if request.kind == "local":
        if request.input_dir is None:
            raise ValueError("Job locale senza input_dir.")
        await _run_local_job(ctx, request.input_dir)
        return

    if request.input_url is None:
        raise ValueError(f"Job {request.kind!r} senza input_url.")
    if not request.i_own_rights:
        raise ValueError("Job URL senza i_own_rights=True; rifiutato come da policy guardrail.")

    if request.kind == "url":
        await _run_url_single_job(ctx, request.input_url)
        return
    await _run_url_batch_job(ctx, request.input_url)


# ----------------------------------------------------------------------------
# local
# ----------------------------------------------------------------------------


async def _run_local_job(ctx: JobContext, input_dir: Path) -> None:
    request = ctx.job.request
    options = request.options
    job_model = _build_translation_job(options)
    out_dir = request.out_dir

    ctx.job.chapters_total = 1
    ctx.save()
    loop = asyncio.get_running_loop()
    manifest = await asyncio.to_thread(
        _invoke_run_local,
        ctx,
        loop=loop,
        input_dir=input_dir,
        out_dir=out_dir,
        series=request.series or "Untitled Series",
        chapter_number=request.chapter_number or "1",
        chapter_title=request.chapter_title,
        options=options,
        job=job_model,
    )
    await _record_manifest(ctx, manifest)
    ctx.job.chapters_done = 1
    ctx.save()


def _invoke_run_local(
    ctx: JobContext,
    *,
    loop: asyncio.AbstractEventLoop,
    input_dir: Path,
    out_dir: Path,
    series: str,
    chapter_number: str,
    chapter_title: str | None,
    options: JobOptions,
    job: TranslationJob,
    fetch_metadata: ManifestFetch | None = None,
    input_type: str = "local",
    input_url: str | None = None,
) -> RunManifest:
    """Synchronous wrapper that converts pipeline callbacks into SSE
    events. Runs in a worker thread (``asyncio.to_thread``) because
    ``run_local`` itself is sync and cannot live on the event loop."""

    def schedule_emit(event: Event) -> None:
        # Cross-thread emit: bounce back to the loop where the broker lives.
        asyncio.run_coroutine_threadsafe(ctx.emit(event), loop)

    def on_phase(phase: str) -> None:
        if ctx.cancel_requested:
            raise asyncio.CancelledError("Job cancelled")
        normalised = _PIPELINE_PHASE_TO_EVENT.get(phase, phase)
        ctx.job.current_phase = normalised  # type: ignore[assignment]
        ctx.save()
        schedule_emit(
            Event(
                type="phase",
                job_id=ctx.job.id,
                phase=normalised,  # type: ignore[arg-type]
                chapter=chapter_number,
            )
        )

    def on_log(message: str) -> None:
        if ctx.cancel_requested:
            raise asyncio.CancelledError("Job cancelled")
        level: Literal["warn", "info"] = "warn" if message.startswith("[warn]") else "info"
        schedule_emit(
            Event(
                type="log",
                job_id=ctx.job.id,
                level=level,
                message=message,
                chapter=chapter_number,
            )
        )

    return run_local(
        input_dir,
        out_dir,
        series=series,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        lang_source=options.lang_source,
        lang_target=options.lang_target,
        fmt=options.format,
        job=job,
        on_phase=on_phase,
        on_log=on_log,
        input_type=input_type,  # type: ignore[arg-type]
        input_url=input_url,
        fetch_metadata=fetch_metadata,
    )


# ----------------------------------------------------------------------------
# single URL
# ----------------------------------------------------------------------------


async def _run_url_single_job(ctx: JobContext, url: str) -> None:
    request = ctx.job.request
    options = request.options

    scraper = scraper_for_url(url, site=options.site)
    fetch_root = request.out_dir / ".msrt-fetch" / scraper.name
    pending_dir = fetch_root / f"_pending-{uuid.uuid4().hex[:8]}"

    ctx.job.chapters_total = 1
    ctx.save()
    await ctx.emit(Event(type="phase", job_id=ctx.job.id, phase="fetch"))

    try:
        result = await scraper.fetch(url, pending_dir)
    except FetchError:
        shutil.rmtree(pending_dir, ignore_errors=True)
        raise

    final_fetch_dir = fetch_root / slugify(result.series) / slugify(result.chapter_number)
    if final_fetch_dir.exists():
        shutil.rmtree(final_fetch_dir)
    final_fetch_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(pending_dir), str(final_fetch_dir))

    fetch_meta = ManifestFetch(
        strategy=result.strategy,
        source_url=result.source_url,
        output_dir=str(final_fetch_dir),
        page_count=len(result.pages),
        warnings=list(result.warnings),
        capture_mode=result.capture_mode,
        viewport=result.viewport,
        device_scale_factor=result.device_scale_factor,
        manual_intervention=result.manual_intervention,
    )

    job_model = _build_translation_job(options)
    loop = asyncio.get_running_loop()
    manifest = await asyncio.to_thread(
        _invoke_run_local,
        ctx,
        loop=loop,
        input_dir=final_fetch_dir,
        out_dir=request.out_dir,
        series=result.series,
        chapter_number=result.chapter_number,
        chapter_title=result.chapter_title,
        options=options,
        job=job_model,
        fetch_metadata=fetch_meta,
        input_type="url",
        input_url=url,
    )
    await _record_manifest(ctx, manifest)
    ctx.job.chapters_done = 1
    ctx.save()


# ----------------------------------------------------------------------------
# URL batch
# ----------------------------------------------------------------------------


async def _run_url_batch_job(ctx: JobContext, url: str) -> None:
    request = ctx.job.request
    options = request.options

    scraper = scraper_for_url(url, site=options.site)
    chapters = await scraper.list_chapters(url)
    chapters = select_chapters(
        chapters,
        range_filter=parse_chapter_range(options.range_filter) if options.range_filter else None,
        chapter_list=parse_chapter_list(options.chapters_filter)
        if options.chapters_filter
        else None,
        limit=options.limit,
    )
    if not chapters:
        raise FetchError("Selettori hanno scartato tutti i capitoli.")

    ctx.job.chapters_total = len(chapters)
    ctx.save()

    for chapter in chapters:
        if ctx.cancel_requested:
            raise asyncio.CancelledError("Batch cancelled by user")
        if options.skip_existing and _chapter_outputs_exist(
            chapter,
            out=request.out_dir,
            fmt=options.format,
            lang_target=options.lang_target,
        ):
            ctx.job.chapters_done += 1
            ctx.job.warnings.append(
                f"ch.{chapter.chapter_number}: output già presente, capitolo saltato."
            )
            await ctx.emit(
                Event(
                    type="warning",
                    job_id=ctx.job.id,
                    chapter=chapter.chapter_number,
                    message="Output già presente: capitolo saltato.",
                )
            )
            ctx.save()
            continue
        try:
            await _run_url_single_chapter(ctx, scraper.name, chapter.url)
            ctx.job.chapters_done += 1
        except Exception as exc:
            ctx.job.chapters_failed += 1
            ctx.job.errors.append(f"ch.{chapter.chapter_number}: {exc}")
            await ctx.emit(
                Event(
                    type="error",
                    job_id=ctx.job.id,
                    chapter=chapter.chapter_number,
                    message=str(exc),
                )
            )
            if not options.continue_on_error:
                raise
        ctx.save()


async def _run_url_single_chapter(ctx: JobContext, site_name: str, url: str) -> None:
    request = ctx.job.request
    options = request.options

    scraper = scraper_for_url(url, site=site_name)
    fetch_root = request.out_dir / ".msrt-fetch" / scraper.name
    pending_dir = fetch_root / f"_pending-{uuid.uuid4().hex[:8]}"

    await ctx.emit(Event(type="phase", job_id=ctx.job.id, phase="fetch"))
    try:
        result: FetchResult = await scraper.fetch(url, pending_dir)
    except FetchError:
        shutil.rmtree(pending_dir, ignore_errors=True)
        raise

    final_fetch_dir = fetch_root / slugify(result.series) / slugify(result.chapter_number)
    if final_fetch_dir.exists():
        shutil.rmtree(final_fetch_dir)
    final_fetch_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(pending_dir), str(final_fetch_dir))

    fetch_meta = ManifestFetch(
        strategy=result.strategy,
        source_url=result.source_url,
        output_dir=str(final_fetch_dir),
        page_count=len(result.pages),
        warnings=list(result.warnings),
        capture_mode=result.capture_mode,
        viewport=result.viewport,
        device_scale_factor=result.device_scale_factor,
        manual_intervention=result.manual_intervention,
    )

    job_model = _build_translation_job(options)
    loop = asyncio.get_running_loop()
    manifest = await asyncio.to_thread(
        _invoke_run_local,
        ctx,
        loop=loop,
        input_dir=final_fetch_dir,
        out_dir=request.out_dir,
        series=result.series,
        chapter_number=result.chapter_number,
        chapter_title=result.chapter_title,
        options=options,
        job=job_model,
        fetch_metadata=fetch_meta,
        input_type="url",
        input_url=url,
    )
    await _record_manifest(ctx, manifest)


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------


def _build_translation_job(options: JobOptions) -> TranslationJob:
    return TranslationJob(
        model=options.model or "gpt",
        font_path=options.font_path,
        glossary_path=options.glossary_path,
        auto_glossary=options.auto_glossary,
        pre_dict_path=options.pre_dict_path,
        renderer=options.renderer,
        use_gpu=not options.no_gpu,
    )


def _chapter_outputs_exist(
    chapter: ChapterLink,
    *,
    out: Path,
    fmt: str,
    lang_target: str,
) -> bool:
    if not chapter.series:
        return False
    base = f"{slugify(chapter.series)}-{slugify(chapter.chapter_number)}-{lang_target}"
    expected: list[Path] = []
    if fmt in {"pdf", "both"}:
        expected.append(out / f"{base}.pdf")
    if fmt in {"cbz", "both"}:
        expected.append(out / f"{base}.cbz")
    return bool(expected) and all(path.exists() for path in expected)


async def _record_manifest(ctx: JobContext, manifest: RunManifest) -> None:
    ctx.job.output_files.extend(manifest.output_files)
    if manifest.errors:
        ctx.job.errors.extend(manifest.errors)
    out_dir = ctx.job.request.out_dir
    manifest_path = (out_dir / "msrt-run.json").resolve()
    if str(manifest_path) not in ctx.job.manifest_paths:
        ctx.job.manifest_paths.append(str(manifest_path))
    for output in manifest.output_files:
        await ctx.emit(
            Event(
                type="output",
                job_id=ctx.job.id,
                path=str(output),
            )
        )
