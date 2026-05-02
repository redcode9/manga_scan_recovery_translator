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
import subprocess
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from sse_starlette.sse import EventSourceResponse

from msrt import __version__
from msrt.config import Settings
from msrt.scrape.base import FetchError
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
from msrt.ui_server.schemas import (
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
from msrt.ui_server.settings_api import settings_view

_LOG = logging.getLogger(__name__)

LITELLM_CONFIG_PATH = Path("configs/litellm.yaml")


def create_app(
    *,
    settings: Settings | None = None,
    job_runner: Callable[..., Awaitable[None]] | None = None,
) -> FastAPI:
    """Build the FastAPI app.

    ``settings`` and ``job_runner`` are injected for tests; production
    callers leave them ``None``.
    """

    resolved_settings = settings or Settings()
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
            status = start_litellm(resolved_settings, LITELLM_CONFIG_PATH)
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

    return app


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------


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
