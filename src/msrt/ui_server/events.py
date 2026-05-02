"""In-memory event broker for the UI's SSE stream.

Each running job has its own :class:`asyncio.Queue`. The job worker
publishes events; SSE consumers subscribe and drain the queue. A
sentinel ``None`` signals "stream closed", letting consumers exit
cleanly without polling.

Designed for single-worker, single-process. Multi-worker deployments
(uvicorn ``--workers N``) would need a Redis-backed broker — out of
scope for the local UI server, which always binds 127.0.0.1.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any


class EventBroker:
    """Per-job pub-sub queue.

    Multiple SSE consumers per job are supported: each ``subscribe``
    call returns its own queue, and ``publish`` fans out the event to
    all of them. Consumers that fall behind don't block the publisher
    — we drop their oldest events to keep memory bounded.
    """

    _MAX_BACKLOG = 256
    _CLOSE_SENTINEL: object = object()

    def __init__(self) -> None:
        # job_id -> set of queues (one per subscriber)
        self._subscribers: dict[str, set[asyncio.Queue[Any]]] = {}
        self._closed: set[str] = set()

    def subscribe(self, job_id: str) -> asyncio.Queue[Any]:
        """Get a fresh queue for ``job_id``. The caller is responsible
        for iterating it (e.g. via :meth:`stream`)."""

        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=self._MAX_BACKLOG)
        self._subscribers.setdefault(job_id, set()).add(queue)
        if job_id in self._closed:
            # Job already finished before subscription — emit terminator
            # so the consumer doesn't hang waiting forever.
            queue.put_nowait(self._CLOSE_SENTINEL)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue[Any]) -> None:
        bucket = self._subscribers.get(job_id)
        if bucket is None:
            return
        bucket.discard(queue)
        if not bucket:
            self._subscribers.pop(job_id, None)

    async def publish(self, job_id: str, payload: dict[str, Any]) -> None:
        """Fan out ``payload`` to every subscriber of ``job_id``.

        Slow subscribers are protected: if a queue is full we drop the
        oldest event rather than blocking the publisher (and therefore
        the pipeline that produced it)."""

        for queue in list(self._subscribers.get(job_id, set())):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(payload)
        # Yield once so consumers have a chance to drain before the
        # next publish; no-op when there are no subscribers.
        await asyncio.sleep(0)

    async def close(self, job_id: str) -> None:
        """Mark ``job_id`` as finished. Pending subscribers receive the
        sentinel and the broker forgets the job."""

        self._closed.add(job_id)
        for queue in list(self._subscribers.get(job_id, set())):
            queue.put_nowait(self._CLOSE_SENTINEL)
        # Don't drop the subscriber set yet: consumers will unsubscribe
        # themselves when they see the sentinel.
        await asyncio.sleep(0)

    async def stream(self, job_id: str) -> AsyncIterator[dict[str, Any]]:
        """Async iterator that yields every payload until the job
        finishes, then exits cleanly. The caller never has to look at
        the close sentinel."""

        queue = self.subscribe(job_id)
        try:
            while True:
                payload = await queue.get()
                if payload is self._CLOSE_SENTINEL:
                    return
                yield payload
        finally:
            self.unsubscribe(job_id, queue)
