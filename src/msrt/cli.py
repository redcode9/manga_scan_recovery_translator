"""Entrypoint CLI di msrt — placeholder per v0.0."""

from __future__ import annotations

import typer

from msrt import __version__

app = typer.Typer(
    name="msrt",
    help="Manga Scan Recovery Translator — wrapper EN→IT (v0.0 bootstrap).",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Stampa la versione corrente di msrt."""
    typer.echo(f"msrt {__version__}")


@app.command()
def doctor() -> None:
    """Diagnostica setup (placeholder — implementazione reale in v0.1)."""
    typer.echo(
        "msrt doctor: placeholder. La diagnostica reale (verifica MITR, "
        "LiteLLM, chiavi API, font, GPU) arriva in v0.1."
    )


if __name__ == "__main__":
    app()
