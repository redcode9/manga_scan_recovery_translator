"""Test smoke — verifica che il pacchetto si importi e l'entrypoint CLI risponda."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from msrt import __version__
from msrt.cli import app


def test_version_constant_present() -> None:
    assert isinstance(__version__, str)
    assert __version__.count(".") == 2


def test_cli_version_command() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_cli_doctor_placeholder() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in {0, 1}
    assert "python" in result.stdout.lower()


def test_cli_package_uses_slugged_output_name(tmp_path: Path) -> None:
    image_dir = tmp_path / "pages"
    image_dir.mkdir()
    Image.new("RGB", (80, 120), "white").save(image_dir / "1.png")
    out_dir = tmp_path / "out"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "package",
            str(image_dir),
            "--out",
            str(out_dir),
            "--format",
            "cbz",
            "--series",
            "A/B Test",
            "--chapter",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / "a-b-test-1-it.cbz").exists()
    assert not (out_dir / "a").exists()
