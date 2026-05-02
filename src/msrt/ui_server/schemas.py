"""Pydantic schemas for the UI server.

Three families of types:

* **Job** — state and lifecycle of a translation job (single or batch).
* **Event** — what the SSE stream emits while a job runs.
* **Misc** — everything else: dry-run, library entries, doctor reports,
  settings views, etc.

Models intentionally mirror the existing core dataclasses (``Chapter``,
``ChapterLink``, ``RunManifest``) without subclassing them: the API
layer can evolve independently of the pipeline's internal types.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ----------------------------------------------------------------------------
# Job lifecycle
# ----------------------------------------------------------------------------

JobKind = Literal["local", "url", "url_batch"]
# ``partial`` is a terminal state distinct from ``succeeded`` and
# ``failed``: the runner finished without raising but at least one
# chapter went into ``chapters_failed``. Surfacing it lets the UI
# offer "Retry failed" without misrepresenting the run as a clean
# success or as a total failure.
JobStatus = Literal["queued", "running", "succeeded", "partial", "failed", "cancelled"]
JobPhase = Literal[
    "queued",
    "preflight",
    "fetch",
    "auto_glossary",
    "collect",
    "translate",
    "postprocess",
    "package",
    "done",
    "error",
]


class JobOptions(BaseModel):
    """User-controllable knobs for a job. Mirrors a subset of the CLI flags."""

    model_config = ConfigDict(extra="forbid")

    format: Literal["pdf", "cbz", "both"] = "pdf"
    model: str | None = None
    renderer: Literal["mitr-default", "mitr-manga2eng", "custom-postprocess"] = "custom-postprocess"
    lang_source: str = "en"
    lang_target: str = "it"
    no_gpu: bool = False
    auto_glossary: bool = True
    glossary_path: Path | None = None
    pre_dict_path: Path | None = None
    font_path: Path | None = None
    site: str = "auto"
    skip_existing: bool = True
    continue_on_error: bool = True
    range_filter: str | None = None
    chapters_filter: str | None = None
    limit: int | None = Field(default=None, ge=1)


class JobCreate(BaseModel):
    """Request body for ``POST /api/jobs``.

    Exactly one of ``input_url`` / ``input_dir`` must be set. The
    server validates this in the route handler so the user gets a
    400 with a clear message rather than a silent fallback.
    """

    model_config = ConfigDict(extra="forbid")

    kind: JobKind
    input_url: str | None = None
    input_dir: Path | None = None
    out_dir: Path = Path("out")
    series: str | None = None
    chapter_number: str | None = None
    chapter_title: str | None = None
    options: JobOptions = Field(default_factory=JobOptions)
    i_own_rights: bool = False


class Job(BaseModel):
    """Server-side view of a job. Fields populate as the lifecycle
    progresses; ``running`` jobs may have ``current_phase`` updated
    asynchronously via the event stream."""

    id: str
    kind: JobKind
    status: JobStatus
    request: JobCreate
    current_phase: JobPhase = "queued"
    chapters_total: int = 0
    chapters_done: int = 0
    chapters_failed: int = 0
    output_files: list[str] = Field(default_factory=list)
    manifest_paths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobList(BaseModel):
    jobs: list[Job]


# ----------------------------------------------------------------------------
# SSE events
# ----------------------------------------------------------------------------

EventType = Literal[
    "job_started",
    "phase",
    "progress",
    "log",
    "output",
    "warning",
    "error",
    "job_finished",
]
LogLevel = Literal["debug", "info", "warn", "error"]


class Event(BaseModel):
    """One SSE event payload.

    ``model_dump_json()`` produces the JSON wire format. The SSE writer
    formats each line as ``data: <json>\\n\\n``; the broker is unaware
    of the framing.
    """

    model_config = ConfigDict(extra="forbid")

    type: EventType
    job_id: str
    chapter: str | None = None
    phase: JobPhase | None = None
    message: str | None = None
    level: LogLevel | None = None
    current: int | None = None
    total: int | None = None
    unit: str | None = None
    path: str | None = None
    status: JobStatus | None = None


# ----------------------------------------------------------------------------
# Dry-run, library, doctor, settings
# ----------------------------------------------------------------------------


class DryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    site: str = "auto"
    range_filter: str | None = None
    chapters_filter: str | None = None
    limit: int | None = Field(default=None, ge=1)


class DryRunChapter(BaseModel):
    url: str
    chapter_number: str
    title: str | None = None
    series: str | None = None
    output_exists: bool = False


class DryRunResponse(BaseModel):
    site: str
    total: int
    selected: int
    chapters: list[DryRunChapter]


class LibraryEntry(BaseModel):
    """One row of the local library, sourced from a ``msrt-run.json``."""

    manifest_id: str
    manifest_path: str
    series: str | None = None
    chapter_number: str | None = None
    chapter_title: str | None = None
    language_target: str | None = None
    output_files: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    model_alias: str | None = None
    provider: str | None = None
    strategy: str | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LibraryResponse(BaseModel):
    entries: list[LibraryEntry]


class DoctorCheckView(BaseModel):
    name: str
    status: str
    message: str
    detail: str | None = None


class DoctorReport(BaseModel):
    checks: list[DoctorCheckView]
    overall_status: Literal["ok", "warn", "fail"]


class SettingsView(BaseModel):
    """Public-safe view of msrt settings.

    API keys are NEVER returned. Only ``has_key`` flags so the UI can
    show "OpenAI key: present" without ever shipping the secret to the
    frontend.
    """

    default_model: str
    litellm_port: int
    litellm_base_url: str
    cache_dir: str
    mitr_bin_path: str | None
    has_anthropic_key: bool
    has_openai_key: bool
    has_gemini_key: bool


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    server_started_at: datetime


class OpenPathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Path


class ServerActionResponse(BaseModel):
    action: Literal["up", "down", "status"]
    running: bool
    healthy: bool
    pid: int | None
    message: str
    log_path: str


# ----------------------------------------------------------------------------
# Internal helper: convert anything event-shaped into an Event
# ----------------------------------------------------------------------------


def event_payload_to_dict(event: Event | dict[str, Any]) -> dict[str, Any]:
    """Normalise an event so it can be JSON-encoded for SSE."""

    if isinstance(event, Event):
        return event.model_dump(exclude_none=True)
    return {k: v for k, v in event.items() if v is not None}
