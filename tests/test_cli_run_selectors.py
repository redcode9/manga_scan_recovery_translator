"""CLI tests for the v0.3f chapter selectors on ``msrt run --all-chapters``.

The selectors (``--range``, ``--chapters``, ``--limit``) are pure logic
tested in detail in ``test_scrape_selection.py``. Here we verify that
the CLI wires them correctly: guardrail, dry-run filtering, and clear
errors when the selectors filter everything out.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from msrt.cli import app
from msrt.scrape.base import ChapterLink, ChapterScraper, FetchResult


class _MultiChapterFakeScraper(ChapterScraper):
    name = "fakemd"

    def matches(self, url: str) -> bool:
        return "fake-test" in url

    async def list_chapters(self, url: str) -> list[ChapterLink]:
        return [
            ChapterLink(
                url=f"https://fake/c-{number}",
                chapter_number=number,
                series="Fake Series",
                title=f"Episode {number}",
            )
            for number in ["48", "49", "50", "50.5", "51", "52", "extra"]
        ]

    async def fetch(self, url: str, output_dir: Path) -> FetchResult:  # pragma: no cover - dry-run
        raise AssertionError("dry-run must not call fetch")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_scraper(monkeypatch: pytest.MonkeyPatch) -> _MultiChapterFakeScraper:
    scraper = _MultiChapterFakeScraper()
    monkeypatch.setattr("msrt.cli.scraper_for_url", lambda _url, site="auto": scraper)
    return scraper


def test_run_rejects_range_without_all_chapters(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--range`` outside ``--all-chapters`` is meaningless: refuse it
    so the user doesn't think they did something they didn't."""

    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/series/foo",
            "--out",
            str(tmp_path / "out"),
            "--i-own-rights",
            "--range",
            "50-51",
        ],
    )
    assert result.exit_code == 1
    assert "richiedono --all-chapters" in result.stdout


def test_run_rejects_chapters_without_all_chapters(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/series/foo",
            "--out",
            str(tmp_path / "out"),
            "--i-own-rights",
            "--chapters",
            "50",
        ],
    )
    assert result.exit_code == 1
    assert "richiedono --all-chapters" in result.stdout


def test_run_rejects_limit_without_all_chapters(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/series/foo",
            "--out",
            str(tmp_path / "out"),
            "--i-own-rights",
            "--limit",
            "2",
        ],
    )
    assert result.exit_code == 1
    assert "richiedono --all-chapters" in result.stdout


def test_run_rejects_malformed_range(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    fake_scraper: _MultiChapterFakeScraper,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/series/foo",
            "--out",
            str(tmp_path / "out"),
            "--i-own-rights",
            "--all-chapters",
            "--range",
            "51-50",  # reversed
            "--dry-run",
        ],
    )
    assert result.exit_code == 1
    assert "Errore selettore" in result.stdout


def test_run_dry_run_filters_to_range(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    fake_scraper: _MultiChapterFakeScraper,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/series/foo",
            "--out",
            str(tmp_path / "out"),
            "--i-own-rights",
            "--all-chapters",
            "--dry-run",
            "--range",
            "50-51",
        ],
    )
    assert result.exit_code == 0, result.stdout
    # Only chapters 50, 50.5, 51 should be listed.
    listed = result.stdout
    assert "ch. 50" in listed
    assert "ch. 50.5" in listed
    assert "ch. 51" in listed
    assert "ch. 48" not in listed
    assert "ch. 52" not in listed
    assert "ch. extra" not in listed
    assert "selezionati 3 di 7" in listed


def test_run_dry_run_filters_to_explicit_chapter_list(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    fake_scraper: _MultiChapterFakeScraper,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/series/foo",
            "--out",
            str(tmp_path / "out"),
            "--i-own-rights",
            "--all-chapters",
            "--dry-run",
            "--chapters",
            "50.5,52",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "ch. 50.5" in result.stdout
    assert "ch. 52" in result.stdout
    assert "ch. 50 " not in result.stdout
    assert "ch. 51" not in result.stdout


def test_run_dry_run_limit_takes_first_n(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    fake_scraper: _MultiChapterFakeScraper,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/series/foo",
            "--out",
            str(tmp_path / "out"),
            "--i-own-rights",
            "--all-chapters",
            "--dry-run",
            "--limit",
            "2",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "ch. 48" in result.stdout
    assert "ch. 49" in result.stdout
    assert "ch. 50 " not in result.stdout
    assert "selezionati 2 di 7" in result.stdout


def test_run_dry_run_combines_range_and_limit(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    fake_scraper: _MultiChapterFakeScraper,
) -> None:
    """``--range`` runs first, then ``--limit`` keeps the first N of
    the filtered set."""

    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/series/foo",
            "--out",
            str(tmp_path / "out"),
            "--i-own-rights",
            "--all-chapters",
            "--dry-run",
            "--range",
            "50-52",
            "--limit",
            "2",
        ],
    )
    assert result.exit_code == 0, result.stdout
    # In-range chapters are 50, 50.5, 51, 52; --limit 2 picks the first two.
    assert "ch. 50 " in result.stdout
    assert "ch. 50.5" in result.stdout
    assert "ch. 51" not in result.stdout
    assert "ch. 52" not in result.stdout


def test_run_errors_when_selectors_drop_all_chapters(
    tmp_path: Path,
    runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    fake_scraper: _MultiChapterFakeScraper,
) -> None:
    """Selector that matches nothing exits with a clear message that
    cites which selector criteria the user typed."""

    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "run",
            "https://fake-test.example/series/foo",
            "--out",
            str(tmp_path / "out"),
            "--i-own-rights",
            "--all-chapters",
            "--range",
            "100-200",
        ],
    )
    assert result.exit_code == 1
    assert "non hanno selezionato" in result.stdout
    assert "range=100" in result.stdout
