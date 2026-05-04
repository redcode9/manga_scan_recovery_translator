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

from msrt.config import ProviderName, Settings, resolve_model_alias
from msrt.models import ManifestFetch, RunManifest, TranslationJob
from msrt.pipeline import QuotaExhaustedError, run_local, slugify
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
    manifest_name: str | None = None,
) -> RunManifest:
    """Synchronous wrapper that converts pipeline callbacks into SSE
    events. Runs in a worker thread (``asyncio.to_thread``) because
    ``run_local`` itself is sync and cannot live on the event loop.

    Spawns a background watcher thread that emits per-page progress
    events while MITR is rendering, so the UI's per-chapter bar moves
    instead of going silent for 30 minutes. The watcher polls the
    ``translated-pages/`` directory; one file = one page rendered.
    """

    import threading
    import time

    expected_pages = sum(
        1 for _ in input_dir.glob("*") if _.is_file() and _.suffix.lower() in _IMAGE_SUFFIXES
    )

    def schedule_emit(event: Event) -> None:
        # Cross-thread emit: bounce back to the loop where the broker lives.
        asyncio.run_coroutine_threadsafe(ctx.emit(event), loop)

    watcher_stop = threading.Event()
    translated_dir = out_dir / "translated-pages"

    def watch_translated_pages() -> None:
        last_count = -1
        last_change_at = time.monotonic()
        # Stall threshold: emit one warning if no new page lands for
        # this many seconds. Keeps the user from staring at a frozen
        # progress bar without context.
        stall_threshold_s = _STALL_THRESHOLD_SECONDS
        warned_about_stall = False
        while not watcher_stop.wait(2.0):
            try:
                count = sum(
                    1
                    for entry in translated_dir.iterdir()
                    if entry.is_file() and entry.suffix.lower() in _IMAGE_SUFFIXES
                )
            except FileNotFoundError:
                continue
            now = time.monotonic()
            if count != last_count:
                last_count = count
                last_change_at = now
                warned_about_stall = False
                schedule_emit(
                    Event(
                        type="progress",
                        job_id=ctx.job.id,
                        chapter=chapter_number,
                        current=count,
                        total=max(expected_pages, count),
                        unit="pages",
                    )
                )
            elif (
                not warned_about_stall
                and now - last_change_at > stall_threshold_s
                and count < expected_pages
            ):
                warned_about_stall = True
                schedule_emit(
                    Event(
                        type="warning",
                        job_id=ctx.job.id,
                        chapter=chapter_number,
                        level="warn",
                        message=(
                            f"ch.{chapter_number}: nessuna pagina tradotta da "
                            f"{int((now - last_change_at) / 60)} min "
                            f"(ferma a {count}/{expected_pages}). "
                            "Verifica che MITR non sia bloccato."
                        ),
                    )
                )

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
        # Phase transitions gate the watcher: only watch during translate
        # / postprocess, stop at package / done so we don't double-count
        # files left behind by the previous chapter.
        if phase == "translate" and not watcher_thread.is_alive():
            watcher_thread.start()
        elif phase in {"package", "done"}:
            watcher_stop.set()

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

    watcher_thread = threading.Thread(
        target=watch_translated_pages, name="msrt-page-watcher", daemon=True
    )

    try:
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
            manifest_name=manifest_name,
        )
    finally:
        watcher_stop.set()
        if watcher_thread.is_alive():
            watcher_thread.join(timeout=2.0)


_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
# Per-chapter stall threshold for the page watcher. 15 minutes is
# longer than any normal MITR pass (worst seen ~1 page/min on dense
# 50-page chapters) but short enough to surface a real freeze.
_STALL_THRESHOLD_SECONDS = 15 * 60


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

    settings = Settings()
    fallback_chain = _build_provider_fallback_chain(
        primary=options.model or settings.default_model, settings=settings
    )
    loop = asyncio.get_running_loop()
    last_quota: QuotaExhaustedError | None = None
    manifest: RunManifest | None = None
    for index, alias in enumerate(fallback_chain):
        options.model = alias
        if index > 0:
            await ctx.emit(
                Event(
                    type="warning",
                    job_id=ctx.job.id,
                    chapter=result.chapter_number,
                    level="warn",
                    message=(
                        f"Fallback a {alias}: il provider precedente ha "
                        "esaurito la quota."
                    ),
                )
            )
        job_model = _build_translation_job(options)
        try:
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
            break
        except QuotaExhaustedError as exc:
            last_quota = exc
            continue

    if manifest is None:
        assert last_quota is not None
        raise QuotaExhaustedError(
            "Tutti i provider configurati hanno quota esaurita. "
            f"Ultimo errore: {last_quota}"
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

    settings = Settings()
    fallback_chain = _build_provider_fallback_chain(
        primary=options.model or settings.default_model, settings=settings
    )

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
            await _run_chapter_through_providers(
                ctx,
                scraper.name,
                chapter.url,
                chapter_number=chapter.chapter_number,
                fallback_chain=fallback_chain,
            )
            ctx.job.chapters_done += 1
        except QuotaExhaustedError as exc:
            # All providers in the fallback chain were exhausted, so
            # every remaining chapter would fail identically until the
            # user tops up at least one plan. Abort the whole batch
            # even if the user opted into ``continue_on_error`` — that
            # flag is meant for per-chapter fetch/parse hiccups, not for
            # "every LLM I have a key for has stopped answering".
            # skip_existing on the retry will pick up exactly where this
            # run left off.
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
            ctx.save()
            raise
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


# Provider order used when expanding the fallback chain past the
# primary model. Conservative: OpenAI first because it's the most common
# default, then Anthropic, then Google. The user's per-provider model
# preference (Settings.model_<provider>) overrides the alias picked.
_FALLBACK_PROVIDER_ORDER: tuple[ProviderName, ...] = ("openai", "anthropic", "google")


def _build_provider_fallback_chain(*, primary: str, settings: Settings) -> list[str]:
    """Return an ordered list of model aliases to try for one chapter.

    The first entry is always ``primary`` (the model the user actually
    asked for, even if its key is missing — we don't silently rewrite
    user intent on the happy path; ``run_local`` will surface the
    auth error if the key is gone). Subsequent entries are the
    user-preferred model for each *other* provider that has a key
    configured, in ``_FALLBACK_PROVIDER_ORDER``.

    Why not just "rotate through every provider with a key": because
    when the user explicitly picked, say, ``gemini-pro`` for a series,
    we should still honour it as the first attempt rather than
    silently substituting ``gemini-flash``.
    """

    chain: list[str] = [primary]
    primary_provider, _, _ = resolve_model_alias(primary)

    for provider in _FALLBACK_PROVIDER_ORDER:
        if provider == primary_provider:
            continue
        candidate = settings.model_for_provider(provider)
        if candidate is None or candidate == primary:
            continue
        _, _, env_name = resolve_model_alias(candidate)
        if env_name is None:
            continue
        if not settings.api_key_for_env_name(env_name):
            continue
        chain.append(candidate)
    return chain


async def _run_chapter_through_providers(
    ctx: JobContext,
    site_name: str,
    chapter_url: str,
    *,
    chapter_number: str,
    fallback_chain: list[str],
) -> None:
    """Run one chapter, falling back to the next provider when the
    current one returns ``insufficient_quota``.

    We mutate ``ctx.job.request.options.model`` in place because
    ``_run_url_single_chapter`` reads ``options`` fresh on each call —
    so the next attempt sees the new model alias. Fetch retries
    (``_run_chapter_with_retry``) still happen *within* a given
    provider; only quota exhaustion triggers the provider switch.
    """

    if not fallback_chain:
        raise QuotaExhaustedError(
            "Nessun provider configurato: aggiungi almeno una API key e ri-esegui."
        )

    options = ctx.job.request.options
    last_error: QuotaExhaustedError | None = None
    for index, model_alias in enumerate(fallback_chain):
        if index > 0:
            await ctx.emit(
                Event(
                    type="warning",
                    job_id=ctx.job.id,
                    chapter=chapter_number,
                    level="warn",
                    message=(
                        f"ch.{chapter_number} fallback a {model_alias} "
                        f"(provider precedente esaurito)."
                    ),
                )
            )
        options.model = model_alias
        try:
            await _run_chapter_with_retry(
                ctx,
                site_name,
                chapter_url,
                chapter_number=chapter_number,
            )
            return
        except QuotaExhaustedError as exc:
            last_error = exc
            continue

    assert last_error is not None  # we entered the loop at least once
    raise QuotaExhaustedError(
        "Tutti i provider configurati hanno quota esaurita. "
        f"Ultimo errore: {last_error}"
    )


async def _run_chapter_with_retry(
    ctx: JobContext,
    site_name: str,
    url: str,
    *,
    chapter_number: str,
    max_attempts: int = 3,
) -> None:
    """Run one chapter as part of a batch, retrying transient failures.

    A transient failure is anything that raises ``FetchError`` /
    ``DownloadError`` whose message looks like a network/CDN/race
    condition we've seen flip green on retry (Cloudflare 5xx,
    ``Network.getResponseBody`` race, generic timeouts). Per the
    failure pattern of the overnight Wistoria run, just two extra
    attempts with exponential backoff would have rescued chapters 8
    and 15 (CDN 520) and very likely 1 / 8.1 (race) too.
    """

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        if ctx.cancel_requested:
            raise asyncio.CancelledError("Batch cancelled by user")
        try:
            await _run_url_single_chapter(ctx, site_name, url, batch=True)
            return
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts or not _is_retryable_chapter_error(exc):
                raise
            backoff = min(60.0, 5.0 * (2 ** (attempt - 1)))
            await ctx.emit(
                Event(
                    type="warning",
                    job_id=ctx.job.id,
                    chapter=chapter_number,
                    level="warn",
                    message=(
                        f"ch.{chapter_number} retry {attempt}/{max_attempts - 1} "
                        f"dopo {backoff:.0f}s: {exc}"
                    ),
                )
            )
            await asyncio.sleep(backoff)
    if last_exc is not None:
        raise last_exc


_RETRYABLE_HINTS = (
    "Network.getResponseBody",
    "No resource with given identifier",
    "HTTP 408",
    "HTTP 425",
    "HTTP 429",
    "HTTP 5",  # 500-504 + 520-524
    "timeout",
    "Timeout",
    "Reader-network",
)


def _is_retryable_chapter_error(exc: Exception) -> bool:
    """Heuristic: retry on signs of network / browser race, never on
    parsing or 4xx-style client errors. Conservative by design — we'd
    rather skip a retry than burn an MITR pass on a 404."""

    # Quota exhaustion is global: retrying the same chapter just burns
    # three more API calls before the same 429 comes back. The literal
    # message contains "HTTP 429" (intentional, for user clarity), so
    # check the type *before* falling through to the substring match.
    if isinstance(exc, QuotaExhaustedError):
        return False
    msg = str(exc)
    return any(hint in msg for hint in _RETRYABLE_HINTS)


async def _run_url_single_chapter(
    ctx: JobContext, site_name: str, url: str, *, batch: bool = False
) -> None:
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

    # Per-chapter manifest filename for batches so the next chapter
    # doesn't overwrite this one's ``msrt-run.json``.
    manifest_name: str | None = None
    if batch:
        manifest_name = (
            f"msrt-run-{slugify(result.series)}-{slugify(result.chapter_number)}-"
            f"{options.lang_target}.json"
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
        manifest_name=manifest_name,
    )
    await _record_manifest(ctx, manifest, manifest_name=manifest_name)


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


async def _record_manifest(
    ctx: JobContext, manifest: RunManifest, *, manifest_name: str | None = None
) -> None:
    ctx.job.output_files.extend(manifest.output_files)
    if manifest.errors:
        ctx.job.errors.extend(manifest.errors)
    out_dir = ctx.job.request.out_dir
    name = manifest_name or "msrt-run.json"
    manifest_path = (out_dir / name).resolve()
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
