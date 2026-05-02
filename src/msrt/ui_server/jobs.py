"""Job queue + lifecycle for the UI server.

Single-worker model: one ``asyncio`` loop processes jobs FIFO.
Multiple jobs can be submitted concurrently — they queue up and run
sequentially. ``cancel`` flips the status to ``cancelled`` and asks
the worker to abort: the runner is expected to check the cancel flag
between phases.

Persistence
-----------
Each job's serialised state is written to
``<cache_dir>/ui/jobs/<job_id>.json`` after every meaningful state
transition. On startup we re-load the index but mark any jobs that
were ``running`` as ``failed`` (the previous worker died with them).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from msrt.ui_server.events import EventBroker
from msrt.ui_server.schemas import (
    Event,
    Job,
    JobCreate,
    JobStatus,
    event_payload_to_dict,
)

_LOG = logging.getLogger(__name__)

JobRunner = Callable[
    ["JobContext"],
    Awaitable[None],
]


class JobContext:
    """Hands a running job the broker, cancel flag, and the snapshot
    of its own ``Job`` model so the runner can mutate counters and
    emit events without depending on the manager directly."""

    def __init__(
        self,
        *,
        job: Job,
        broker: EventBroker,
        cancel_event: asyncio.Event,
        save_callback: Callable[[Job], None],
    ) -> None:
        self.job = job
        self._broker = broker
        self._cancel = cancel_event
        self._save = save_callback

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    async def emit(self, event: Event) -> None:
        await self._broker.publish(self.job.id, event_payload_to_dict(event))

    def save(self) -> None:
        self._save(self.job)


class JobManager:
    """FIFO single-worker manager. Use :meth:`start` once at app
    startup and :meth:`shutdown` on graceful stop."""

    def __init__(
        self,
        *,
        broker: EventBroker,
        runner: JobRunner,
        storage_dir: Path,
    ) -> None:
        self._broker = broker
        self._runner = runner
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, Job] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        # Strong references to fire-and-forget terminal-emit tasks so the
        # GC doesn't reap them mid-flight (asyncio's RUF006 trap).
        self._pending_tasks: set[asyncio.Task[Any]] = set()
        self._stopping = False
        self._load_persisted()

    def _fire(self, coro: Awaitable[Any]) -> None:
        task = asyncio.ensure_future(coro)
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit(self, request: JobCreate) -> Job:
        """Register a new job, persist it, and queue it for the worker.
        The job appears immediately in ``list``/``get`` with status
        ``queued``."""

        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id, kind=request.kind, status="queued", request=request)
        self._jobs[job_id] = job
        self._cancel_events[job_id] = asyncio.Event()
        self._persist(job)
        await self._queue.put(job_id)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        # Most recent first — UIs almost always want this order.
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    async def cancel(self, job_id: str) -> bool:
        """Request cancellation. Returns ``True`` if the job exists and
        was not already terminal."""

        job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.status in {"succeeded", "partial", "failed", "cancelled"}:
            return False
        cancel_event = self._cancel_events.get(job_id)
        if cancel_event is not None:
            cancel_event.set()
        if job.status == "queued":
            # Not running yet — flip directly to cancelled. The worker
            # will skip it when it pops from the queue.
            self._mark_terminal(job, "cancelled")
        return True

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def shutdown(self) -> None:
        self._stopping = True
        # Cancel everything in-flight.
        for cancel in self._cancel_events.values():
            cancel.set()
        if self._worker_task is not None:
            self._worker_task.cancel()
            with _suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    async def _worker_loop(self) -> None:
        while not self._stopping:
            try:
                job_id = await self._queue.get()
            except asyncio.CancelledError:
                return
            job = self._jobs.get(job_id)
            if job is None or job.status != "queued":
                # Cancelled before we got to it, or unknown id.
                continue
            await self._run_one(job)

    async def _run_one(self, job: Job) -> None:
        job.status = "running"
        job.started_at = datetime.now(UTC)
        self._persist(job)
        await self._broker.publish(
            job.id,
            event_payload_to_dict(Event(type="job_started", job_id=job.id)),
        )

        cancel_event = self._cancel_events.get(job.id) or asyncio.Event()
        ctx = JobContext(
            job=job, broker=self._broker, cancel_event=cancel_event, save_callback=self._persist
        )
        terminal: JobStatus
        try:
            await self._runner(ctx)
            if cancel_event.is_set():
                terminal = "cancelled"
            elif job.chapters_failed > 0:
                # Runner came back without raising, but some chapters
                # went into the failed bucket (typical for batches with
                # ``continue_on_error=True``). Surface that as a distinct
                # terminal state so the UI can offer "Retry failed".
                terminal = "partial"
            else:
                terminal = "succeeded"
        except asyncio.CancelledError:
            terminal = "cancelled"
        except Exception as exc:
            _LOG.exception("Job %s failed", job.id)
            job.errors.append(str(exc))
            terminal = "failed"
        finally:
            self._mark_terminal(job, terminal)

    def _mark_terminal(self, job: Job, status: JobStatus) -> None:
        job.status = status
        job.finished_at = datetime.now(UTC)
        self._persist(job)
        # Closing the broker channel is fire-and-forget at this point —
        # but we keep strong refs to the tasks so the GC doesn't drop
        # them before the loop schedules them.
        self._fire(
            self._broker.publish(
                job.id,
                event_payload_to_dict(Event(type="job_finished", job_id=job.id, status=status)),
            )
        )
        self._fire(self._broker.close(job.id))
        self._cancel_events.pop(job.id, None)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _job_path(self, job_id: str) -> Path:
        return self._storage_dir / f"{job_id}.json"

    def _persist(self, job: Job) -> None:
        path = self._job_path(job.id)
        try:
            path.write_text(job.model_dump_json(indent=2), encoding="utf-8")
        except OSError as exc:  # pragma: no cover - disk error
            _LOG.warning("Persist failed for job %s: %s", job.id, exc)

    def _load_persisted(self) -> None:
        for path in self._storage_dir.glob("*.json"):
            try:
                payload: Any = json.loads(path.read_text(encoding="utf-8"))
                job = Job.model_validate(payload)
            except (ValueError, OSError) as exc:
                _LOG.warning("Skipping corrupt job file %s: %s", path, exc)
                continue
            if job.status == "running":
                # Process died mid-job: mark as failed so the user sees
                # something concrete instead of a forever-running entry.
                job.status = "failed"
                job.errors.append(
                    "Backend interrotto durante il job; stato ricostruito al riavvio."
                )
                job.finished_at = datetime.now(UTC)
                self._persist(job)
            elif job.status == "queued":
                # The previous process accepted a queued job but never
                # got to run it. Re-queueing silently would surprise the
                # user (different process, possibly different config);
                # marking it cancelled with an explicit message lets the
                # user decide whether to re-submit, and ``Retry failed``
                # already handles the batch case.
                job.status = "cancelled"
                job.warnings.append(
                    "Backend riavviato prima dell'avvio del job; rilancialo manualmente se serve."
                )
                job.finished_at = datetime.now(UTC)
                self._persist(job)
            self._jobs[job.id] = job


class _suppress:
    """Lightweight contextlib.suppress without importing it just for
    one usage; keeps the module import-light."""

    def __init__(self, *exc_types: type[BaseException]) -> None:
        self._exc_types = exc_types

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> bool:
        return exc_type is not None and issubclass(exc_type, self._exc_types)

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> bool:
        return exc_type is not None and issubclass(exc_type, self._exc_types)
