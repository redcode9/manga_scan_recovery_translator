"""End-to-end tests for the v0.4a backend.

The UI server is exercised via FastAPI's ``TestClient`` (which spins
the lifespan, the job worker and the SSE machinery on a thread). All
external calls — adapters, MITR, LiteLLM — are stubbed. Zero network.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from msrt.config import Settings
from msrt.scrape.base import ChapterLink, ChapterScraper, FetchResult
from msrt.ui_server.app import create_app
from msrt.ui_server.events import EventBroker
from msrt.ui_server.jobs import JobContext
from msrt.ui_server.schemas import Event

# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------


@pytest.fixture
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """A Settings instance with cache_dir routed to tmp so jobs/library
    paths don't pollute the user's real ``~/.cache/msrt``."""

    monkeypatch.setenv("HOME", str(tmp_path))
    settings = Settings()
    object.__setattr__(settings, "cache_dir", tmp_path / ".cache" / "msrt")
    return settings


@pytest.fixture
def fast_runner_factory():  # type: ignore[no-untyped-def]
    """Builds a job runner that just records the job_id and emits a
    couple of canonical events. Used for shape tests where the
    pipeline behaviour itself isn't under test."""

    def factory(*, fail: bool = False, sleep: float = 0.0):  # type: ignore[no-untyped-def]
        async def runner(ctx: JobContext) -> None:
            await ctx.emit(Event(type="phase", job_id=ctx.job.id, phase="translate"))
            if sleep:
                await asyncio.sleep(sleep)
            if fail:
                raise RuntimeError("simulated failure")
            ctx.job.chapters_total = 1
            ctx.job.chapters_done = 1
            ctx.job.output_files.append("out/fake.pdf")

        return runner

    return factory


def _client(
    settings: Settings,
    job_runner=None,  # type: ignore[no-untyped-def]
) -> TestClient:
    app = create_app(settings=settings, job_runner=job_runner)
    return TestClient(app)


# ----------------------------------------------------------------------------
# Health / Settings / Doctor / Library
# ----------------------------------------------------------------------------


def test_health_endpoint(isolated_settings: Settings) -> None:
    with _client(isolated_settings) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload
    assert "server_started_at" in payload


def test_settings_endpoint_does_not_leak_keys(
    isolated_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Settings endpoint must NEVER return raw API key values, only
    ``has_*_key`` booleans. We seed a deliberately recognisable token
    and assert it does not appear in the JSON response."""

    sentinel = "sk-test-LEAKED-IF-PRESENT-1234567890"
    object.__setattr__(isolated_settings, "openai_api_key", sentinel)
    # Zero out the others so the assertion isolates the leak check from
    # whatever happens to be in the developer's environment.
    object.__setattr__(isolated_settings, "anthropic_api_key", None)
    object.__setattr__(isolated_settings, "gemini_api_key", None)

    with _client(isolated_settings) as client:
        response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.text
    assert sentinel not in body
    payload = response.json()
    assert payload["has_openai_key"] is True
    assert payload["has_anthropic_key"] is False
    assert payload["has_gemini_key"] is False
    assert payload["default_model"]


def test_doctor_endpoint_returns_structured_report(isolated_settings: Settings) -> None:
    with _client(isolated_settings) as client:
        response = client.get("/api/doctor")
    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_status"] in {"ok", "warn", "fail"}
    assert isinstance(payload["checks"], list)
    assert payload["checks"], "doctor returned an empty checklist"
    for check in payload["checks"]:
        assert {"name", "status", "message"} <= check.keys()


def test_library_returns_manifest_when_present(isolated_settings: Settings, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    manifest = {
        "msrt_version": "0.0.0",
        "command": "fake",
        "started_at": "2026-04-29T22:00:00+00:00",
        "finished_at": "2026-04-29T22:24:00+00:00",
        "input": {"type": "url", "page_count": 50, "url": "https://x"},
        "page_order": [],
        "page_hashes": {},
        "model": {"alias": "gpt", "resolved_id": "gpt-5.5", "provider": "openai"},
        "engine": {"type": "subprocess"},
        "output_files": [str(out / "wistoria-50-it.pdf")],
        "metadata": {
            "series": "Wistoria",
            "chapter": "50",
            "title": "Capitolo 50",
            "language_target": "it",
        },
        "fetch": {
            "strategy": "mangadex-api",
            "source_url": "https://x",
            "output_dir": str(out / ".msrt-fetch/mangadex/wistoria/50"),
            "page_count": 50,
        },
        "errors": [],
    }
    (out / "msrt-run.json").write_text(json.dumps(manifest), encoding="utf-8")

    with _client(isolated_settings) as client:
        response = client.get(f"/api/library?out={out}")
    assert response.status_code == 200
    entries = response.json()["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["series"] == "Wistoria"
    assert entry["chapter_number"] == "50"
    assert entry["strategy"] == "mangadex-api"
    assert entry["model_alias"] == "gpt"


# ----------------------------------------------------------------------------
# Dry-run
# ----------------------------------------------------------------------------


class _MultiChapterScraper(ChapterScraper):
    name = "fakemd"

    def matches(self, url: str) -> bool:
        return "fake-test" in url

    async def list_chapters(self, url: str) -> list[ChapterLink]:
        return [
            ChapterLink(url=f"https://fake/c-{n}", chapter_number=n, series="Fake")
            for n in ["1", "50", "51", "52"]
        ]

    async def fetch(self, url: str, output_dir: Path) -> FetchResult:  # pragma: no cover
        raise AssertionError("dry-run must not call fetch")


def test_dry_run_returns_filtered_chapters(
    isolated_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _MultiChapterScraper()
    monkeypatch.setattr("msrt.ui_server.app.scraper_for_url", lambda _u, site="auto": fake)

    with _client(isolated_settings) as client:
        response = client.post(
            "/api/chapters/dry-run",
            json={
                "url": "https://fake-test.example/series/foo",
                "site": "auto",
                "range_filter": "50-51",
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["site"] == "fakemd"
    assert payload["total"] == 4
    assert payload["selected"] == 2
    chapters = [c["chapter_number"] for c in payload["chapters"]]
    assert chapters == ["50", "51"]


def test_dry_run_rejects_malformed_range(
    isolated_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _MultiChapterScraper()
    monkeypatch.setattr("msrt.ui_server.app.scraper_for_url", lambda _u, site="auto": fake)

    with _client(isolated_settings) as client:
        response = client.post(
            "/api/chapters/dry-run",
            json={
                "url": "https://fake-test.example/series/foo",
                "range_filter": "51-50",
            },
        )
    assert response.status_code == 400


# ----------------------------------------------------------------------------
# Job lifecycle
# ----------------------------------------------------------------------------


def test_job_validation_rejects_url_kind_without_rights(isolated_settings: Settings) -> None:
    with _client(isolated_settings) as client:
        response = client.post(
            "/api/jobs",
            json={"kind": "url", "input_url": "https://x"},
        )
    assert response.status_code == 400


def test_job_validation_rejects_local_kind_with_url(isolated_settings: Settings) -> None:
    with _client(isolated_settings) as client:
        response = client.post(
            "/api/jobs",
            json={"kind": "local", "input_url": "https://x", "input_dir": "/tmp/x"},
        )
    assert response.status_code == 400


def test_job_lifecycle_succeeded(
    isolated_settings: Settings, fast_runner_factory, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    runner = fast_runner_factory()

    with _client(isolated_settings, runner) as client:
        create = client.post(
            "/api/jobs",
            json={
                "kind": "local",
                "input_dir": str(tmp_path / "pages"),
                "out_dir": str(tmp_path / "out"),
                "options": {"format": "pdf"},
            },
        )
        assert create.status_code == 201, create.text
        job_id = create.json()["id"]

        # Poll until the job is no longer queued/running.
        for _ in range(40):
            status_resp = client.get(f"/api/jobs/{job_id}")
            status = status_resp.json()["status"]
            if status not in {"queued", "running"}:
                break
            asyncio.run(asyncio.sleep(0.05))
        else:
            pytest.fail("Job did not reach a terminal state in time.")

        final = client.get(f"/api/jobs/{job_id}").json()
    assert final["status"] == "succeeded"
    assert final["chapters_done"] == 1
    assert final["output_files"] == ["out/fake.pdf"]


def test_job_lifecycle_failed_records_error(
    isolated_settings: Settings, fast_runner_factory, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    runner = fast_runner_factory(fail=True)

    with _client(isolated_settings, runner) as client:
        create = client.post(
            "/api/jobs",
            json={
                "kind": "local",
                "input_dir": str(tmp_path / "pages"),
                "out_dir": str(tmp_path / "out"),
            },
        )
        job_id = create.json()["id"]
        for _ in range(40):
            final = client.get(f"/api/jobs/{job_id}").json()
            if final["status"] not in {"queued", "running"}:
                break
            asyncio.run(asyncio.sleep(0.05))
    assert final["status"] == "failed"
    assert any("simulated failure" in err for err in final["errors"])


def test_jobs_list_orders_recent_first(
    isolated_settings: Settings, fast_runner_factory, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    runner = fast_runner_factory()
    with _client(isolated_settings, runner) as client:
        first = client.post(
            "/api/jobs",
            json={"kind": "local", "input_dir": str(tmp_path / "a")},
        ).json()
        second = client.post(
            "/api/jobs",
            json={"kind": "local", "input_dir": str(tmp_path / "b")},
        ).json()
        listing = client.get("/api/jobs").json()
    ids = [job["id"] for job in listing["jobs"]]
    assert ids[0] == second["id"]
    assert first["id"] in ids


def test_cancel_queued_job_marks_cancelled(
    isolated_settings: Settings, fast_runner_factory, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    # Slow runner so the worker is still busy with job1 when we cancel job2.
    runner = fast_runner_factory(sleep=0.5)

    with _client(isolated_settings, runner) as client:
        first = client.post(
            "/api/jobs", json={"kind": "local", "input_dir": str(tmp_path / "a")}
        ).json()
        # second job sits in the queue while the first runs.
        second = client.post(
            "/api/jobs", json={"kind": "local", "input_dir": str(tmp_path / "b")}
        ).json()
        cancel = client.post(f"/api/jobs/{second['id']}/cancel")
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "cancelled"

        # Wait for the first job to finish so the test exits cleanly.
        for _ in range(40):
            first_state = client.get(f"/api/jobs/{first['id']}").json()
            if first_state["status"] not in {"queued", "running"}:
                break
            asyncio.run(asyncio.sleep(0.05))


def test_cancel_unknown_job_returns_409(isolated_settings: Settings) -> None:
    with _client(isolated_settings) as client:
        response = client.post("/api/jobs/does-not-exist/cancel")
    assert response.status_code == 409


# ----------------------------------------------------------------------------
# SSE event broker (unit-level — easier to assert than the streaming HTTP)
# ----------------------------------------------------------------------------


def test_event_broker_streams_then_closes() -> None:
    """The broker fans out events to subscribers and sends a sentinel
    on ``close()`` so consumers exit their loops without polling."""

    async def scenario() -> list[dict]:
        broker = EventBroker()
        received: list[dict] = []

        async def consume():  # type: ignore[no-untyped-def]
            async for event in broker.stream("job-1"):
                received.append(event)

        task = asyncio.create_task(consume())
        # give the consumer a moment to subscribe
        await asyncio.sleep(0)
        await broker.publish("job-1", {"type": "phase", "phase": "translate"})
        await broker.publish("job-1", {"type": "log", "message": "ok"})
        await broker.close("job-1")
        await asyncio.wait_for(task, timeout=1.0)
        return received

    received = asyncio.run(scenario())
    assert received == [
        {"type": "phase", "phase": "translate"},
        {"type": "log", "message": "ok"},
    ]


def test_event_broker_late_subscriber_after_close_does_not_hang() -> None:
    """If a consumer subscribes after the job already finished it must
    still exit cleanly — no infinite wait."""

    async def scenario() -> list[dict]:
        broker = EventBroker()
        await broker.close("job-1")
        events: list[dict] = []
        async for event in broker.stream("job-1"):
            events.append(event)
        return events

    assert asyncio.run(scenario()) == []
