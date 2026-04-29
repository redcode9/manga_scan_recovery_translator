"""End-to-end tests for ``msrt run`` URL pipeline orchestration.

The command stitches ``fetch`` and ``run-local`` together; the actual
adapter and the actual MITR engine are both replaced by lightweight
fakes so the tests stay fully offline and deterministic.
"""

from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from msrt.cli import app
from msrt.scrape.base import ChapterScraper, FetchedPage, FetchError, FetchResult


def _real_png_bytes(seed: int = 0x10) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (16, 16), (seed, seed, seed)).save(buf, format="PNG")
    return buf.getvalue()


class _FakeMangaDexLikeScraper(ChapterScraper):
    """Drops two real PNGs into ``output_dir`` and reports plausible
    MangaDex metadata. Tests can override ``raise_in_fetch`` to simulate
    fetch failures."""

    name = "fakemd"
    raise_in_fetch: type[BaseException] | None = None

    def matches(self, url: str) -> bool:
        return "fake-test" in url

    async def fetch(self, url: str, output_dir: Path) -> FetchResult:
        if self.raise_in_fetch is not None:
            raise self.raise_in_fetch("simulated fetch failure")
        output_dir.mkdir(parents=True, exist_ok=True)
        pages = []
        for index in (1, 2):
            page_path = output_dir / f"{index:03d}.png"
            page_path.write_bytes(_real_png_bytes(seed=index * 0x20))
            pages.append(
                FetchedPage(
                    index=index,
                    url=f"{url}#page-{index}",
                    local_path=page_path,
                    sha256=f"sha256:fake-{index}",
                    content_type="image/png",
                    size_bytes=page_path.stat().st_size,
                )
            )
        return FetchResult(
            series="Fake Series",
            chapter_number="42",
            chapter_title="Pilot",
            source_url=url,
            strategy="fake-md",
            pages=pages,
            output_dir=output_dir,
        )


def _patch_fake_scraper(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fetch_raises: type[BaseException] | None = None,
) -> _FakeMangaDexLikeScraper:
    fake = _FakeMangaDexLikeScraper()
    fake.raise_in_fetch = fetch_raises  # type: ignore[assignment]
    monkeypatch.setattr(
        "msrt.cli.scraper_for_url",
        lambda _url, site="auto": fake,
    )
    return fake


def _patch_run_local(
    monkeypatch: pytest.MonkeyPatch,
    captured: dict[str, object],
    *,
    raise_exc: type[BaseException] | None = None,
):  # type: ignore[no-untyped-def]
    """Replace ``msrt.cli.run_local`` with a stub that records its kwargs.

    Returns nothing; the test inspects ``captured`` after invoking the
    CLI to assert on metadata propagation."""

    from msrt.models import RunManifest

    def stub(image_dir, out_dir, **kwargs):  # type: ignore[no-untyped-def]
        captured["image_dir"] = image_dir
        captured["out_dir"] = out_dir
        captured.update(kwargs)
        if raise_exc is not None:
            raise raise_exc("simulated translation failure")
        # Return a minimal-but-valid manifest so the CLI's success path runs.
        return RunManifest.model_validate(
            {
                "msrt_version": "0.0.0",
                "command": "stub",
                "input": {"type": "url", "page_count": 2, "url": "http://x"},
                "page_order": ["001.png", "002.png"],
                "page_hashes": {"001.png": "sha256:a", "002.png": "sha256:b"},
                "model": {"alias": "gpt", "resolved_id": "gpt-5.5", "provider": "openai"},
                "engine": {"type": "subprocess"},
                "output_files": [str(out_dir / "fake.pdf")],
                "fetch": kwargs.get("fetch_metadata"),
            }
        )

    monkeypatch.setattr("msrt.cli.run_local", stub)


def test_run_url_without_rights_flag_exits_one(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "https://fake-test.example/chapter/abc", "--out", str(tmp_path / "out")],
    )
    assert result.exit_code == 1
    assert "--i-own-rights" in result.stdout


def test_run_unsupported_url_exits_one(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """No registered adapter claims the URL → exit 1, MITR doesn't start."""

    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "https://example.com/random",
            "--out",
            str(tmp_path / "out"),
            "--i-own-rights",
        ],
    )
    assert result.exit_code == 1
    assert "Nessun adapter supporta" in result.stdout


def test_run_orchestrates_fetch_then_local_pipeline(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Fake adapter populates the staging dir → CLI moves it under the
    canonical ``<site>/<series>/<chapter>/`` path → run_local is called
    with the metadata from FetchResult and a populated ManifestFetch."""

    monkeypatch.setenv("HOME", str(tmp_path))
    _patch_fake_scraper(monkeypatch)
    captured: dict[str, object] = {}
    _patch_run_local(monkeypatch, captured)

    runner = CliRunner()
    out_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/chapter/abc",
            "--out",
            str(out_dir),
            "--i-own-rights",
            "--no-gpu",
        ],
    )

    assert result.exit_code == 0, result.stdout
    # run_local got the metadata from FetchResult, not user-provided defaults.
    assert captured["series"] == "Fake Series"
    assert captured["chapter_number"] == "42"
    assert captured["chapter_title"] == "Pilot"
    assert captured["input_type"] == "url"
    assert captured["input_url"] == "https://fake-test.example/chapter/abc"
    fetch_meta = captured["fetch_metadata"]
    assert fetch_meta is not None
    assert fetch_meta.strategy == "fake-md"  # type: ignore[union-attr]
    assert fetch_meta.page_count == 2  # type: ignore[union-attr]
    # Final fetch dir is under <out>/.msrt-fetch/<site>/<series-slug>/<chapter-slug>/
    expected_dir = out_dir / ".msrt-fetch" / "fakemd" / "fake-series" / "42"
    assert captured["image_dir"] == expected_dir
    assert (expected_dir / "001.png").exists()
    assert (expected_dir / "002.png").exists()
    # No leftover _pending- staging dir.
    pending = list((out_dir / ".msrt-fetch" / "fakemd").glob("_pending-*"))
    assert pending == []


def test_run_aborts_when_fetch_fails(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """If the adapter raises FetchError, MITR / run_local must not be
    invoked at all."""

    monkeypatch.setenv("HOME", str(tmp_path))
    _patch_fake_scraper(monkeypatch, fetch_raises=FetchError)
    captured: dict[str, object] = {}

    def explode(image_dir, out_dir, **kwargs):  # type: ignore[no-untyped-def]
        captured["called"] = True
        raise AssertionError("run_local must not be called when fetch fails")

    monkeypatch.setattr("msrt.cli.run_local", explode)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/chapter/abc",
            "--out",
            str(tmp_path / "out"),
            "--i-own-rights",
        ],
    )

    assert result.exit_code == 1
    assert "Errore fetch" in result.stdout
    assert "called" not in captured


def test_run_keeps_fetch_dir_when_translation_fails(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Fetch succeeds, run_local fails — the canonical fetch dir must
    survive so the user can re-try without redownloading."""

    monkeypatch.setenv("HOME", str(tmp_path))
    _patch_fake_scraper(monkeypatch)
    captured: dict[str, object] = {}
    _patch_run_local(monkeypatch, captured, raise_exc=RuntimeError)

    runner = CliRunner()
    out_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/chapter/abc",
            "--out",
            str(out_dir),
            "--i-own-rights",
            "--no-gpu",
        ],
    )

    assert result.exit_code == 1
    assert "Errore run-local" in result.stdout
    expected_dir = out_dir / ".msrt-fetch" / "fakemd" / "fake-series" / "42"
    assert expected_dir.exists()
    assert (expected_dir / "001.png").exists()
    assert (expected_dir / "002.png").exists()


def test_run_cleans_pending_dir_when_fetch_raises_not_implemented(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    """A NotImplementedError from a skeleton adapter exits with code 2
    and removes the empty staging dir to keep the workspace clean."""

    monkeypatch.setenv("HOME", str(tmp_path))
    _patch_fake_scraper(monkeypatch, fetch_raises=NotImplementedError)

    runner = CliRunner()
    out_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/chapter/abc",
            "--out",
            str(out_dir),
            "--i-own-rights",
        ],
    )

    assert result.exit_code == 2
    pending = list((out_dir / ".msrt-fetch" / "fakemd").glob("_pending-*"))
    assert pending == [], f"Staging dir not cleaned up: {pending}"


def test_run_help_lists_url_orchestration_flags() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    for flag in ("--site", "--i-own-rights", "--format", "--model"):
        assert flag in result.stdout


@pytest.fixture(autouse=True)
def _cleanup_fake_dirs(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Make sure leftover fake fetch dirs from one test don't interfere
    with the next, even though tmp_path already isolates per-test."""

    yield
    shutil.rmtree(tmp_path / "out", ignore_errors=True)
