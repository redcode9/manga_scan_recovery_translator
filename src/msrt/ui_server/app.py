"""FastAPI application factory for the UI backend.

Surfaces every endpoint listed in ``docs/DESKTOP_UI_PLAN.md`` for v0.4a:

* ``/api/health``                — liveness + version + boot time
* ``/api/doctor``                — structured ``DoctorReport``
* ``/api/settings``              — public-safe view (no key values)
* ``/api/server/{up,down}``      — LiteLLM lifecycle
* ``/api/chapters/dry-run``      — adapter list_chapters + selectors
* ``/api/jobs`` (POST/GET)       — submit + list
* ``/api/jobs/{id}``             — single job state
* ``/api/jobs/{id}/cancel``      — request cancellation
* ``/api/jobs/{id}/events``      — SSE stream of pipeline events
* ``/api/library``               — output manifests
* ``/api/library/{manifest_id}`` — single manifest
* ``/api/open-path``             — best-effort native open

Everything binds 127.0.0.1: this server is meant to be embedded by a
Tauri shell or used by a local browser tab, not exposed to a LAN.
"""

from __future__ import annotations

import logging
import platform
import re
import subprocess
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from msrt import __version__
from msrt.config import Settings
from msrt.paths import env_file_path, litellm_config_path
from msrt.paths import frontend_dist_dir as resolve_frontend_dist
from msrt.scrape.base import FetchError
from msrt.scrape.cover import resolve_cover
from msrt.scrape.registry import scraper_for_url
from msrt.scrape.selection import (
    parse_chapter_list,
    parse_chapter_range,
    select_chapters,
)
from msrt.server import (
    LiteLLMUnavailableError,
    litellm_status,
    log_file,
    start_litellm,
    stop_litellm,
)
from msrt.ui_server.commands import run_job
from msrt.ui_server.doctor_api import build_doctor_report
from msrt.ui_server.events import EventBroker
from msrt.ui_server.jobs import JobManager
from msrt.ui_server.library import load_entry, scan_library
from msrt.ui_server.redact import redact_value
from msrt.ui_server.schemas import (
    CoverageChapter,
    CoverageRequest,
    CoverageResponse,
    DoctorReport,
    DryRunChapter,
    DryRunRequest,
    DryRunResponse,
    HealthResponse,
    Job,
    JobCreate,
    JobList,
    LibraryEntry,
    LibraryResponse,
    OpenPathRequest,
    ServerActionResponse,
    SettingsView,
)
from msrt.ui_server.secrets import hydrate_process_env
from msrt.ui_server.settings_api import settings_view
from msrt.ui_server.setup_api import (
    DefaultModelRequest,
    DefaultModelResponse,
    DeleteKeyRequest,
    SaveKeyRequest,
    SecretReportResponse,
    SetupTestResult,
    TestKeyRequest,
    remove_api_key,
    save_api_key,
    smoke_test_provider,
    update_default_model,
)

_LOG = logging.getLogger(__name__)


def create_app(
    *,
    settings: Settings | None = None,
    job_runner: Callable[..., Awaitable[None]] | None = None,
) -> FastAPI:
    """Build the FastAPI app.

    ``settings`` and ``job_runner`` are injected for tests; production
    callers leave them ``None``.
    """

    if settings is None:
        hydrate_process_env(env_path=env_file_path())
        resolved_settings = Settings()
    else:
        resolved_settings = settings
    boot_at = datetime.now(UTC)

    broker = EventBroker()
    storage_dir = Path(resolved_settings.cache_dir) / "ui" / "jobs"
    manager = JobManager(
        broker=broker,
        runner=job_runner or run_job,
        storage_dir=storage_dir,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
        await manager.start()
        try:
            yield
        finally:
            await manager.shutdown()

    app = FastAPI(title="msrt UI server", version=__version__, lifespan=lifespan)

    # Stash the dependencies on the app so tests / shutdown hooks can
    # reach them without a global.
    app.state.settings = resolved_settings
    app.state.broker = broker
    app.state.manager = manager

    # ------------------------------------------------------------------
    # Health / Settings / Doctor
    # ------------------------------------------------------------------

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__, server_started_at=boot_at)

    @app.get("/api/settings", response_model=SettingsView)
    def get_settings() -> SettingsView:
        return settings_view(resolved_settings)

    @app.get("/api/doctor", response_model=DoctorReport)
    def doctor(model: str | None = None) -> DoctorReport:
        return build_doctor_report(model=model)

    # ------------------------------------------------------------------
    # LiteLLM lifecycle
    # ------------------------------------------------------------------

    @app.get("/api/server", response_model=ServerActionResponse)
    def server_status() -> ServerActionResponse:
        status = litellm_status(resolved_settings)
        return ServerActionResponse(
            action="status",
            running=status.running,
            healthy=status.healthy,
            pid=status.pid,
            message=status.message,
            log_path=str(log_file(resolved_settings)),
        )

    @app.post("/api/server/up", response_model=ServerActionResponse)
    def server_up() -> ServerActionResponse:
        try:
            status = start_litellm(resolved_settings, litellm_config_path())
        except (LiteLLMUnavailableError, FileNotFoundError, RuntimeError) as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return ServerActionResponse(
            action="up",
            running=status.running,
            healthy=status.healthy,
            pid=status.pid,
            message=status.message,
            log_path=str(log_file(resolved_settings)),
        )

    @app.post("/api/setup/save-key", response_model=SecretReportResponse)
    def setup_save_key(request: SaveKeyRequest) -> SecretReportResponse:
        try:
            return save_api_key(request, resolved_settings)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/setup/delete-key", response_model=SecretReportResponse)
    def setup_delete_key(request: DeleteKeyRequest) -> SecretReportResponse:
        try:
            return remove_api_key(request, resolved_settings)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/setup/test-key", response_model=SetupTestResult)
    def setup_test_key(request: TestKeyRequest) -> SetupTestResult:
        return smoke_test_provider(request, resolved_settings)

    @app.post("/api/setup/default-model", response_model=DefaultModelResponse)
    def setup_default_model(request: DefaultModelRequest) -> DefaultModelResponse:
        return update_default_model(request, resolved_settings)

    @app.post("/api/server/down", response_model=ServerActionResponse)
    def server_down() -> ServerActionResponse:
        stopped = stop_litellm(resolved_settings)
        return ServerActionResponse(
            action="down",
            running=False,
            healthy=False,
            pid=None,
            message="Stopped." if stopped else "Was not running.",
            log_path=str(log_file(resolved_settings)),
        )

    # ------------------------------------------------------------------
    # Dry-run chapter listing
    # ------------------------------------------------------------------

    @app.post("/api/chapters/dry-run", response_model=DryRunResponse)
    async def dry_run(request: DryRunRequest) -> DryRunResponse:
        try:
            scraper = scraper_for_url(request.url, site=request.site)
        except FetchError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            chapters = await scraper.list_chapters(request.url)
        except FetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        try:
            range_filter = (
                parse_chapter_range(request.range_filter) if request.range_filter else None
            )
            chapter_list = (
                parse_chapter_list(request.chapters_filter) if request.chapters_filter else None
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        total = len(chapters)
        filtered = select_chapters(
            chapters,
            range_filter=range_filter,
            chapter_list=chapter_list,
            limit=request.limit,
        )
        items = [
            DryRunChapter(
                url=ch.url,
                chapter_number=ch.chapter_number,
                title=ch.title,
                series=ch.series,
            )
            for ch in filtered
        ]
        return DryRunResponse(site=scraper.name, total=total, selected=len(items), chapters=items)

    @app.post("/api/chapters/coverage", response_model=CoverageResponse)
    async def chapters_coverage(request: CoverageRequest) -> CoverageResponse:
        """Return what's available on the source, what's on disk, and
        what falls before/after the user's planned range. Powers the
        BatchPlanner gap detection and the manga-level progress bar."""

        try:
            scraper = scraper_for_url(request.url, site=request.site)
        except FetchError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            chapters = await scraper.list_chapters(request.url)
        except FetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        try:
            range_filter = (
                parse_chapter_range(request.range_filter) if request.range_filter else None
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        from msrt.ui_server.commands import _chapter_outputs_exist

        all_rows: list[CoverageChapter] = []
        on_disk_count = 0
        before_gap: list[CoverageChapter] = []
        after_gap: list[CoverageChapter] = []
        in_range_seen = False
        for chapter in chapters:
            on_disk = _chapter_outputs_exist(
                chapter,
                out=request.out_dir,
                fmt=request.fmt,
                lang_target=request.lang_target,
            )
            if on_disk:
                on_disk_count += 1
            in_range = True
            if range_filter is not None:
                low, high = range_filter
                try:
                    num = float(chapter.chapter_number)
                    in_range = low <= num <= high
                except ValueError:
                    in_range = False
            row = CoverageChapter(
                chapter_number=chapter.chapter_number,
                url=chapter.url,
                title=chapter.title,
                series=chapter.series,
                on_disk=on_disk,
                in_range=in_range,
            )
            all_rows.append(row)
            if not on_disk:
                if in_range:
                    in_range_seen = True
                elif not in_range_seen:
                    before_gap.append(row)
                else:
                    after_gap.append(row)

        return CoverageResponse(
            site=scraper.name,
            available=all_rows,
            available_count=len(all_rows),
            on_disk_count=on_disk_count,
            missing_before_range=before_gap,
            missing_after_range=after_gap,
        )

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    @app.post("/api/jobs", response_model=Job, status_code=201)
    async def create_job(request: JobCreate) -> Job:
        _validate_job_request(request)
        return await manager.submit(request)

    @app.get("/api/jobs", response_model=JobList)
    def list_jobs() -> JobList:
        return JobList(jobs=manager.list_jobs())

    @app.get("/api/jobs/{job_id}", response_model=Job)
    def get_job(job_id: str) -> Job:
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} non trovato.")
        return job

    @app.post("/api/jobs/{job_id}/cancel", response_model=Job)
    async def cancel_job(job_id: str) -> Job:
        cancelled = await manager.cancel(job_id)
        if not cancelled:
            raise HTTPException(
                status_code=409,
                detail=f"Job {job_id} non cancellabile (assente o già terminale).",
            )
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} non trovato.")
        return job

    @app.post("/api/jobs/{job_id}/retry-failed", response_model=Job, status_code=201)
    async def retry_failed_chapters(job_id: str) -> Job:
        original = manager.get(job_id)
        if original is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} non trovato.")
        if original.kind != "url_batch":
            raise HTTPException(
                status_code=409,
                detail="Retry-failed disponibile solo su batch URL.",
            )
        failed_numbers = _extract_failed_chapter_numbers(original.errors)
        if not failed_numbers:
            raise HTTPException(
                status_code=409,
                detail="Nessun capitolo fallito da rilanciare.",
            )

        new_request = original.request.model_copy(
            update={
                "options": original.request.options.model_copy(
                    update={
                        "chapters_filter": ",".join(failed_numbers),
                        "range_filter": None,
                        "limit": None,
                    }
                ),
            }
        )
        return await manager.submit(new_request)

    @app.get("/api/jobs/{job_id}/events")
    async def job_events(job_id: str) -> EventSourceResponse:
        job = manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} non trovato.")

        async def event_generator() -> AsyncIterator[dict[str, str]]:
            async for event in broker.stream(job_id):
                yield {"data": _json_dumps(event)}

        return EventSourceResponse(event_generator())

    # ------------------------------------------------------------------
    # Library
    # ------------------------------------------------------------------

    @app.get("/api/library", response_model=LibraryResponse)
    def library(out: str = "out") -> LibraryResponse:
        return LibraryResponse(entries=scan_library(Path(out)))

    @app.get("/api/library/{manifest_id}", response_model=LibraryEntry)
    def library_entry(manifest_id: str, out: str = "out") -> LibraryEntry:
        entry = load_entry(manifest_id, out_dir=Path(out))
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail=f"Manifest {manifest_id} non trovato in {out}.",
            )
        return entry

    # ------------------------------------------------------------------
    # Diagnostics — redacted bundle for bug reports
    # ------------------------------------------------------------------

    @app.get("/api/diagnostics")
    def diagnostics() -> dict[str, Any]:
        """Snapshot for issue reports: doctor + presence flags +
        recent jobs + platform info.

        Redaction passes over the entire payload before it leaves the
        process: ``$HOME`` is replaced with ``~``, URL query strings
        are masked, and known API key prefixes (``sk-…``, ``AIza…``,
        ``Bearer …``) are blanked. The response is therefore safe to
        attach to a public issue, even though the raw values would
        otherwise include ``/Users/<name>/...`` paths and full URLs.
        """

        view = settings_view(resolved_settings)
        recent = manager.list_jobs()[:20]
        payload: dict[str, Any] = {
            "msrt_version": __version__,
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "python": platform.python_version(),
            },
            "settings": view.model_dump(),
            "doctor": build_doctor_report().model_dump(),
            "litellm_log_path": str(log_file(resolved_settings)),
            "recent_jobs": [
                {
                    "id": j.id,
                    "kind": j.kind,
                    "status": j.status,
                    "current_phase": j.current_phase,
                    "chapters_total": j.chapters_total,
                    "chapters_done": j.chapters_done,
                    "chapters_failed": j.chapters_failed,
                    "errors": j.errors,
                    "warnings": j.warnings,
                    "created_at": j.created_at.isoformat(),
                    "finished_at": j.finished_at.isoformat() if j.finished_at else None,
                }
                for j in recent
            ],
        }
        return redact_value(payload)  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Cover art (best-effort, cached on disk)
    # ------------------------------------------------------------------

    @app.get("/api/library/cover", response_class=Response)
    async def library_cover(
        series: str,
        source_url: str | None = None,
        out_dir: str | None = None,
    ) -> Response:
        """Resolve and serve a manga cover image.

        Tries MangaDex first when ``source_url`` points at a title
        UUID, then AniList by name, then a local composite generated
        from the on-disk scans (``out_dir/.msrt-fetch``). Cached
        under ``cache_dir/covers`` so a second hit is local-only.
        ``Cache-Control`` lets the browser keep the image around for
        the rest of the session.
        """

        cover = await resolve_cover(
            series,
            cache_dir=Path(resolved_settings.cache_dir),
            source_url=source_url,
            out_dir=Path(out_dir) if out_dir else None,
        )
        if cover is None:
            raise HTTPException(status_code=404, detail="Cover non trovata.")
        return Response(
            content=cover.content,
            media_type=cover.content_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Cover-Source": cover.source,
            },
        )

    # ------------------------------------------------------------------
    # Open path (native)
    # ------------------------------------------------------------------

    @app.post("/api/open-path", status_code=204)
    def open_path(request: OpenPathRequest) -> None:
        path = request.path
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Path inesistente: {path}.")
        opener = _native_opener_command()
        if opener is None:
            raise HTTPException(
                status_code=501, detail="Apertura nativa non supportata su questa piattaforma."
            )
        try:
            subprocess.Popen([*opener, str(path)])
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Impossibile aprire: {exc}") from exc

    # ------------------------------------------------------------------
    # Static UI: serve apps/desktop/dist when present so a single
    # ``msrt ui`` command boots both API and UI. The UI build is opt-in
    # — if the dist isn't there yet, we skip the mount and the API
    # remains available for dev mode (Vite proxies on 5173).
    # ------------------------------------------------------------------
    dist = _frontend_dist_dir()
    if dist is not None:
        # Mount /assets as static (immutable, hashed file names) and
        # then route the SPA: every non-API path returns index.html so
        # client-side routing works after a deep reload.
        assets_dir = dist / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=assets_dir, html=False),
                name="assets",
            )

        index_path = dist / "index.html"

        @app.get("/", include_in_schema=False)
        def root_index() -> FileResponse:
            return FileResponse(index_path)

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str) -> FileResponse:
            # /api/* is already handled by the API routes above; this
            # catch-all only fires for client-side routes (Dashboard,
            # Library, /jobs/:id, …). Static assets like .ico/.svg
            # served from dist root are returned directly.
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404)
            candidate = dist / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index_path)

    return app


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------


_FAILED_CHAPTER_PATTERN = re.compile(r"^ch\.([^:]+):", re.IGNORECASE)


def _extract_failed_chapter_numbers(errors: list[str]) -> list[str]:
    """Pull chapter numbers from batch errors of the form
    ``ch.<number>: <message>``. The UI builds a retry job that
    re-runs only those chapters via ``options.chapters_filter``."""

    seen: list[str] = []
    for line in errors:
        match = _FAILED_CHAPTER_PATTERN.match(line.strip())
        if match is None:
            continue
        number = match.group(1).strip()
        if number and number not in seen:
            seen.append(number)
    return seen


def _validate_job_request(request: JobCreate) -> None:
    """Reject jobs with inconsistent inputs before they hit the queue."""

    if request.kind == "local":
        if request.input_dir is None:
            raise HTTPException(status_code=400, detail="Job 'local' richiede input_dir.")
        if request.input_url is not None:
            raise HTTPException(
                status_code=400,
                detail="Job 'local' non accetta input_url.",
            )
    else:  # url / url_batch
        if request.input_url is None:
            raise HTTPException(status_code=400, detail=f"Job '{request.kind}' richiede input_url.")
        if not request.i_own_rights:
            raise HTTPException(
                status_code=400,
                detail="Manca i_own_rights=True; guardrail UX per scaricare contenuti.",
            )


def _frontend_dist_dir() -> Path | None:
    """Return the absolute path to ``apps/desktop/dist`` if it has
    been built, otherwise ``None``.

    Search order: env var ``MSRT_UI_DIST`` (override for packaged
    deployments), then the project root resolved by ``msrt.paths``.
    """

    import os

    override = os.environ.get("MSRT_UI_DIST")
    if override:
        candidate = Path(override).expanduser().resolve()
        if (candidate / "index.html").is_file():
            return candidate

    candidate = resolve_frontend_dist()
    if (candidate / "index.html").is_file():
        return candidate
    return None


def _native_opener_command() -> list[str] | None:
    system = platform.system()
    if system == "Darwin":
        return ["open"]
    if system == "Linux":
        return ["xdg-open"]
    if system == "Windows":  # pragma: no cover - non-target platform
        return ["cmd", "/c", "start", ""]
    return None


def _json_dumps(payload: object) -> str:
    import json

    return json.dumps(payload, default=str)
