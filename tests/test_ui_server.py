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
from msrt.models import ManifestEngine, ManifestInput, ManifestModel, RunManifest
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
    paths don't pollute the user's real ``~/.cache/msrt`` and with
    ``MSRT_HOME`` pointing at tmp so any ``.env`` write the test
    triggers lands in tmp instead of the developer's real repo."""

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MSRT_HOME", str(tmp_path))
    monkeypatch.setenv("MSRT_DISABLE_KEYRING", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
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


def _fake_manifest(output_file: Path) -> RunManifest:
    return RunManifest(
        msrt_version="test",
        command="fake",
        input=ManifestInput(type="local", path="/tmp/pages", page_count=1),
        page_order=["001.png"],
        page_hashes={"001.png": "sha256:test"},
        model=ManifestModel(alias="gpt", resolved_id="gpt-5.5", provider="openai"),
        engine=ManifestEngine(type="subprocess"),
        output_files=[str(output_file)],
        metadata={"series": "Fake", "chapter": "1", "language_target": "it"},
    )


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


def test_setup_save_key_uses_dotenv_without_leaking_value(
    isolated_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    sentinel = "sk-test-SECRET-DO-NOT-LEAK"

    with _client(isolated_settings) as client:
        saved = client.post(
            "/api/setup/save-key",
            json={"name": "OPENAI_API_KEY", "value": sentinel},
        )
        assert saved.status_code == 200, saved.text
        settings_response = client.get("/api/settings")

    assert saved.json()["backend"] == "dotenv"
    assert sentinel not in saved.text
    assert sentinel not in settings_response.text
    assert settings_response.json()["has_openai_key"] is True
    assert "OPENAI_API_KEY=" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_setup_delete_key_removes_presence_flag(
    isolated_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    with _client(isolated_settings) as client:
        client.post(
            "/api/setup/save-key",
            json={"name": "OPENAI_API_KEY", "value": "sk-test-secret"},
        )
        deleted = client.post(
            "/api/setup/delete-key",
            json={"name": "OPENAI_API_KEY"},
        )
        settings_response = client.get("/api/settings")

    assert deleted.status_code == 200, deleted.text
    assert settings_response.json()["has_openai_key"] is False


def test_setup_rejects_unknown_key_name(isolated_settings: Settings) -> None:
    with _client(isolated_settings) as client:
        response = client.post(
            "/api/setup/save-key",
            json={"name": "AWS_SECRET_ACCESS_KEY", "value": "secret"},
        )
    assert response.status_code == 400
    assert "Chiave non riconosciuta" in response.text


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


class _SkipExistingScraper(ChapterScraper):
    name = "fakebatch"

    def matches(self, url: str) -> bool:
        return "fake-batch" in url

    async def list_chapters(self, url: str) -> list[ChapterLink]:
        return [
            ChapterLink(url="https://fake-batch.example/c-50", chapter_number="50", series="Fake")
        ]

    async def fetch(self, url: str, output_dir: Path) -> FetchResult:
        raise AssertionError("skip_existing should avoid fetching an already packaged chapter")


def test_coverage_endpoint_classifies_missing_before_and_after_range(
    isolated_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The coverage view powers the BatchPlanner gap UX. Given a fake
    adapter exposing chapters [1, 50, 51, 52] and an output dir that
    already contains ``fake-1-it.pdf``, with ``range_filter=51-52``:

    - ``missing_before_range`` = ["50"]  (50 is < range, not on disk)
    - ``missing_after_range``  = []      (no chapters after 52)
    - ``on_disk_count``        = 1       (chapter 1 already on disk)
    """

    fake = _MultiChapterScraper()
    monkeypatch.setattr("msrt.ui_server.app.scraper_for_url", lambda _u, site="auto": fake)
    monkeypatch.setattr("msrt.ui_server.commands.scraper_for_url", lambda _u, site="auto": fake)
    out = tmp_path / "out"
    out.mkdir()
    (out / "fake-1-it.pdf").write_bytes(b"%PDF-1.4\n")

    with _client(isolated_settings) as client:
        response = client.post(
            "/api/chapters/coverage",
            json={
                "url": "https://fake-test.example/series/foo",
                "out_dir": str(out),
                "range_filter": "51-52",
                "fmt": "pdf",
                "lang_target": "it",
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["available_count"] == 4
    assert payload["on_disk_count"] == 1
    before_numbers = [row["chapter_number"] for row in payload["missing_before_range"]]
    after_numbers = [row["chapter_number"] for row in payload["missing_after_range"]]
    assert before_numbers == ["50"]
    assert after_numbers == []


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


def test_dry_run_rejects_non_positive_limit(isolated_settings: Settings) -> None:
    with _client(isolated_settings) as client:
        response = client.post(
            "/api/chapters/dry-run",
            json={"url": "https://fake-test.example/series/foo", "limit": 0},
        )
    assert response.status_code == 422


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


def test_url_batch_job_honours_skip_existing(
    isolated_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scraper = _SkipExistingScraper()
    monkeypatch.setattr("msrt.ui_server.commands.scraper_for_url", lambda _u, site="auto": scraper)

    out = tmp_path / "out"
    out.mkdir()
    (out / "fake-50-it.pdf").write_bytes(b"%PDF-1.4\n")

    with _client(isolated_settings) as client:
        create = client.post(
            "/api/jobs",
            json={
                "kind": "url_batch",
                "input_url": "https://fake-batch.example/series/foo",
                "out_dir": str(out),
                "i_own_rights": True,
                "options": {"format": "pdf", "skip_existing": True},
            },
        )
        assert create.status_code == 201, create.text
        job_id = create.json()["id"]
        for _ in range(40):
            final = client.get(f"/api/jobs/{job_id}").json()
            if final["status"] not in {"queued", "running"}:
                break
            asyncio.run(asyncio.sleep(0.05))
        else:
            pytest.fail("Batch job did not finish.")

    assert final["status"] == "succeeded"
    assert final["chapters_total"] == 1
    assert final["chapters_done"] == 1
    assert final["chapters_failed"] == 0
    assert final["warnings"] == ["ch.50: output già presente, capitolo saltato."]


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


def test_default_local_runner_emits_from_worker_thread(
    isolated_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Regression: ``run_local`` executes in ``asyncio.to_thread``.
    The UI bridge must capture the event loop before entering the
    worker thread; ``asyncio.get_event_loop()`` inside the thread raises
    on Python 3.11+ and would fail real UI jobs."""

    def fake_run_local(*_args: object, **kwargs: object) -> RunManifest:
        on_phase = kwargs["on_phase"]
        on_log = kwargs["on_log"]
        assert callable(on_phase)
        assert callable(on_log)
        on_phase("collect")
        on_log("fake log")
        return _fake_manifest(tmp_path / "out" / "fake.pdf")

    monkeypatch.setattr("msrt.ui_server.commands.run_local", fake_run_local)

    with _client(isolated_settings) as client:
        create = client.post(
            "/api/jobs",
            json={
                "kind": "local",
                "input_dir": str(tmp_path / "pages"),
                "out_dir": str(tmp_path / "out"),
            },
        )
        assert create.status_code == 201, create.text
        job_id = create.json()["id"]
        for _ in range(40):
            final = client.get(f"/api/jobs/{job_id}").json()
            if final["status"] not in {"queued", "running"}:
                break
            asyncio.run(asyncio.sleep(0.05))
    assert final["status"] == "succeeded"
    assert final["output_files"] == [str(tmp_path / "out" / "fake.pdf")]


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


def test_cancel_running_job_does_not_stop_worker(
    isolated_settings: Settings,
    tmp_path: Path,
) -> None:
    """A running job can raise ``CancelledError`` without killing the
    FIFO worker. The next queued job must still run."""

    async def runner(ctx: JobContext) -> None:
        if ctx.job.request.input_dir == tmp_path / "cancel-me":
            for _ in range(50):
                if ctx.cancel_requested:
                    raise asyncio.CancelledError("cancelled for test")
                await asyncio.sleep(0.01)
            raise AssertionError("cancel request never reached runner")
        ctx.job.chapters_total = 1
        ctx.job.chapters_done = 1
        ctx.job.output_files.append("out/after-cancel.pdf")

    with _client(isolated_settings, runner) as client:
        first = client.post(
            "/api/jobs",
            json={"kind": "local", "input_dir": str(tmp_path / "cancel-me")},
        ).json()
        for _ in range(40):
            first_state = client.get(f"/api/jobs/{first['id']}").json()
            if first_state["status"] == "running":
                break
            asyncio.run(asyncio.sleep(0.05))
        else:
            pytest.fail("First job did not start.")

        cancel = client.post(f"/api/jobs/{first['id']}/cancel")
        assert cancel.status_code == 200

        second = client.post(
            "/api/jobs",
            json={"kind": "local", "input_dir": str(tmp_path / "after-cancel")},
        ).json()
        for _ in range(80):
            second_state = client.get(f"/api/jobs/{second['id']}").json()
            if second_state["status"] not in {"queued", "running"}:
                break
            asyncio.run(asyncio.sleep(0.05))
        else:
            pytest.fail("Worker stopped after a running-job cancellation.")

        first_final = client.get(f"/api/jobs/{first['id']}").json()

    assert first_final["status"] == "cancelled"
    assert second_state["status"] == "succeeded"
    assert second_state["output_files"] == ["out/after-cancel.pdf"]


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


# ----------------------------------------------------------------------------
# v0.4e — diagnostics + retry-failed
# ----------------------------------------------------------------------------


def test_diagnostics_endpoint_returns_redacted_snapshot(
    isolated_settings: Settings,
) -> None:
    """The diagnostics bundle must be safe to paste in a public bug
    report. We seed a sentinel API key on the Settings object and
    assert it doesn't appear in the response."""

    sentinel = "sk-test-diag-LEAKED-IF-PRESENT"
    object.__setattr__(isolated_settings, "openai_api_key", sentinel)

    with _client(isolated_settings) as client:
        response = client.get("/api/diagnostics")

    assert response.status_code == 200
    assert sentinel not in response.text
    payload = response.json()
    assert payload["msrt_version"]
    assert "settings" in payload
    assert "doctor" in payload
    assert "recent_jobs" in payload
    # Presence flags survive but not values.
    assert payload["settings"]["has_openai_key"] is True


def test_diagnostics_redacts_home_and_keylike_strings(
    isolated_settings: Settings,
) -> None:
    """The redaction layer must mask:

    - the user's HOME prefix in any path-shaped string,
    - URL query string values (?token=, ?api_key=…),
    - obvious API key prefixes (sk-…, AIza…) inside error messages.
    """

    home = str(Path.home())
    object.__setattr__(isolated_settings, "mitr_bin_path", f"{home}/tools/mitr/.venv/bin/python")

    with _client(isolated_settings) as client:
        response = client.get("/api/diagnostics")
        # Seed a job that surfaces a redactable error in the diagnostics
        # ``recent_jobs`` slice.
        manager = client.app.state.manager  # type: ignore[attr-defined]
        from msrt.ui_server.schemas import Job, JobCreate, JobOptions

        seeded = Job(
            id="diag-test-1",
            kind="local",
            status="failed",
            request=JobCreate(kind="local", input_dir=Path("/tmp/x"), options=JobOptions()),
            errors=[
                f"failure at {home}/Desktop/secret.png",
                "leaked sk-ant-DIAG-TEST-ABCDEFGH1234567890",
                "leaked AIzaDIAGTESTABCDEFGH12345678",
                "url=https://example/test?api_key=DIAG-TEST-API-KEY-VALUE",
            ],
        )
        manager._jobs[seeded.id] = seeded  # type: ignore[attr-defined]
        response = client.get("/api/diagnostics")

    assert response.status_code == 200
    body = response.text
    assert home not in body
    assert "sk-ant-DIAG-TEST-ABCDEFGH1234567890" not in body
    assert "AIzaDIAGTESTABCDEFGH12345678" not in body
    assert "DIAG-TEST-API-KEY-VALUE" not in body
    # The HOME-prefix mitr_bin_path is rewritten with ``~``.
    assert "~/tools/mitr/.venv/bin/python" in body


async def _failing_batch_runner(ctx: JobContext) -> None:
    """Simulate a batch where two chapters failed. Used to seed a job
    state the retry-failed endpoint can act on."""

    await ctx.emit(Event(type="phase", job_id=ctx.job.id, phase="fetch"))
    ctx.job.chapters_total = 3
    ctx.job.chapters_done = 1
    ctx.job.chapters_failed = 2
    ctx.job.errors.append("ch.51: fetch failed")
    ctx.job.errors.append("ch.52: fetch failed")


def test_retry_failed_chapters_filters_to_failed_numbers(
    isolated_settings: Settings, tmp_path: Path
) -> None:
    """``POST /api/jobs/{id}/retry-failed`` builds a new url_batch job
    whose ``chapters_filter`` is exactly the chapters reported as
    failed by the original run."""

    with _client(isolated_settings, _failing_batch_runner) as client:
        original = client.post(
            "/api/jobs",
            json={
                "kind": "url_batch",
                "input_url": "https://fake-batch.example/series/foo",
                "out_dir": str(tmp_path / "out"),
                "i_own_rights": True,
                "options": {"format": "pdf"},
            },
        )
        assert original.status_code == 201, original.text
        original_id = original.json()["id"]

        for _ in range(40):
            state = client.get(f"/api/jobs/{original_id}").json()
            if state["status"] not in {"queued", "running"}:
                break
            asyncio.run(asyncio.sleep(0.05))
        assert state["chapters_failed"] == 2
        assert state["status"] == "partial"

        retry = client.post(f"/api/jobs/{original_id}/retry-failed")

    assert retry.status_code == 201, retry.text
    body = retry.json()
    assert body["kind"] == "url_batch"
    assert body["request"]["options"]["chapters_filter"] == "51,52"
    assert body["request"]["options"]["range_filter"] is None
    assert body["request"]["options"]["limit"] is None


def test_retry_failed_rejects_non_batch_jobs(
    isolated_settings: Settings, fast_runner_factory, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    """Local jobs don't have per-chapter errors to filter, so the
    endpoint refuses them with a 409."""

    runner = fast_runner_factory()
    with _client(isolated_settings, runner) as client:
        local = client.post(
            "/api/jobs",
            json={"kind": "local", "input_dir": str(tmp_path / "pages")},
        ).json()
        for _ in range(40):
            final = client.get(f"/api/jobs/{local['id']}").json()
            if final["status"] not in {"queued", "running"}:
                break
            asyncio.run(asyncio.sleep(0.05))

        retry = client.post(f"/api/jobs/{local['id']}/retry-failed")

    assert retry.status_code == 409
    assert "batch" in retry.json()["detail"].lower()


def test_zombie_queued_jobs_are_cancelled_on_restart(
    isolated_settings: Settings, tmp_path: Path
) -> None:
    """If the previous backend process accepted a job but died before
    the worker picked it up, the next process must not leave it
    ``queued`` forever. We simulate that by writing a queued job file
    to the storage dir before booting the app."""

    storage = tmp_path / ".cache" / "msrt" / "ui" / "jobs"
    storage.mkdir(parents=True, exist_ok=True)
    queued_blob = {
        "id": "zombie-queued-1",
        "kind": "local",
        "status": "queued",
        "request": {"kind": "local", "input_dir": str(tmp_path / "x")},
        "current_phase": "queued",
        "chapters_total": 0,
        "chapters_done": 0,
        "chapters_failed": 0,
        "output_files": [],
        "manifest_paths": [],
        "errors": [],
        "warnings": [],
        "created_at": "2026-04-29T22:00:00+00:00",
        "started_at": None,
        "finished_at": None,
    }
    (storage / "zombie-queued-1.json").write_text(json.dumps(queued_blob), encoding="utf-8")

    with _client(isolated_settings) as client:
        body = client.get("/api/jobs/zombie-queued-1").json()

    assert body["status"] == "cancelled"
    assert body["finished_at"] is not None
    assert any("Backend riavviato" in w for w in body["warnings"])


def test_zombie_running_jobs_are_failed_on_restart(
    isolated_settings: Settings, tmp_path: Path
) -> None:
    """Sibling check: ``running`` zombies become ``failed`` (existing
    behaviour, pinned here so neither half regresses silently)."""

    storage = tmp_path / ".cache" / "msrt" / "ui" / "jobs"
    storage.mkdir(parents=True, exist_ok=True)
    running_blob = {
        "id": "zombie-running-1",
        "kind": "url_batch",
        "status": "running",
        "request": {
            "kind": "url_batch",
            "input_url": "https://example.test/x",
            "i_own_rights": True,
        },
        "current_phase": "translate",
        "chapters_total": 1,
        "chapters_done": 0,
        "chapters_failed": 0,
        "output_files": [],
        "manifest_paths": [],
        "errors": [],
        "warnings": [],
        "created_at": "2026-04-29T22:00:00+00:00",
        "started_at": "2026-04-29T22:00:01+00:00",
        "finished_at": None,
    }
    (storage / "zombie-running-1.json").write_text(json.dumps(running_blob), encoding="utf-8")

    with _client(isolated_settings) as client:
        body = client.get("/api/jobs/zombie-running-1").json()

    assert body["status"] == "failed"
    assert any("Backend interrotto" in e for e in body["errors"])


def test_retry_failed_rejects_jobs_without_failed_chapters(
    isolated_settings: Settings, tmp_path: Path
) -> None:
    """If chapters_failed == 0 there's nothing to retry."""

    async def green_runner(ctx: JobContext) -> None:
        await ctx.emit(Event(type="phase", job_id=ctx.job.id, phase="done"))
        ctx.job.chapters_total = 1
        ctx.job.chapters_done = 1

    with _client(isolated_settings, green_runner) as client:
        created = client.post(
            "/api/jobs",
            json={
                "kind": "url_batch",
                "input_url": "https://fake-batch.example/series/foo",
                "out_dir": str(tmp_path / "out"),
                "i_own_rights": True,
                "options": {"format": "pdf"},
            },
        ).json()
        for _ in range(40):
            final = client.get(f"/api/jobs/{created['id']}").json()
            if final["status"] not in {"queued", "running"}:
                break
            asyncio.run(asyncio.sleep(0.05))
        retry = client.post(f"/api/jobs/{created['id']}/retry-failed")

    assert retry.status_code == 409
    assert "fallito" in retry.json()["detail"].lower()
