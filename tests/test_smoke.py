"""Test smoke — verifica che il pacchetto si importi e l'entrypoint CLI risponda."""

from __future__ import annotations

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
    assert result.exit_code == 0
    assert "placeholder" in result.stdout.lower()
