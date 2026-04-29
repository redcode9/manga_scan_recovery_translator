"""Entrypoint CLI di msrt."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from msrt import __version__
from msrt.doctor import DoctorCheck, run_doctor
from msrt.models import TranslationJob
from msrt.package.cbz import package_cbz
from msrt.package.pdf import package_pdf
from msrt.pipeline import collect_local_chapter, run_local

app = typer.Typer(
    name="msrt",
    help="Manga Scan Recovery Translator — wrapper EN→IT.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Stampa la versione corrente di msrt."""
    typer.echo(f"msrt {__version__}")


@app.command()
def doctor(
    model: Annotated[str, typer.Option("--model", help="Alias modello da verificare.")] = "sonnet",
    font_path: Annotated[
        Path | None, typer.Option("--font-path", help="Font da verificare.")
    ] = None,
    paid_smoke: Annotated[
        bool,
        typer.Option("--paid-smoke", help="Riservato a test provider reale opt-in."),
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Diagnostica setup locale senza chiamate paid di default."""

    checks = run_doctor(model=model, font_path=font_path, paid_smoke=paid_smoke, verbose=verbose)
    for check in checks:
        _print_check(check)
    if any(check.status == "fail" for check in checks):
        raise typer.Exit(code=1)


@app.command()
def package(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, dir_okay=True)],
    out: Annotated[Path, typer.Option("--out", help="Directory output.")] = Path("out"),
    format: Annotated[str, typer.Option("--format", help="cbz|pdf|both")] = "cbz",
    series: Annotated[str, typer.Option("--series")] = "Untitled Series",
    chapter: Annotated[str, typer.Option("--chapter")] = "1",
    title: Annotated[str | None, typer.Option("--title")] = None,
    lang_target: Annotated[str, typer.Option("--lang-target")] = "it",
) -> None:
    """Impacchetta immagini già tradotte in CBZ/PDF."""

    chapter_model = collect_local_chapter(
        directory,
        series=series,
        chapter_number=chapter,
        chapter_title=title,
        lang_source="en",
        lang_target=lang_target,
    )
    out.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    if format in {"cbz", "both"}:
        outputs.append(
            package_cbz(directory, chapter_model, out / f"{series}-{chapter}-{lang_target}.cbz")
        )
    if format in {"pdf", "both"}:
        outputs.append(package_pdf(directory, out / f"{series}-{chapter}-{lang_target}.pdf"))
    if not outputs:
        console.print(f"[red]Formato non supportato: {format}[/red]")
        raise typer.Exit(code=2)
    for path in outputs:
        console.print(f"[green]Creato[/green] {path}")


@app.command("run-local")
def run_local_command(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, dir_okay=True)],
    out: Annotated[Path, typer.Option("--out", help="Directory output.")] = Path("out"),
    format: Annotated[str, typer.Option("--format", help="pdf|cbz|both")] = "pdf",
    model: Annotated[str, typer.Option("--model")] = "sonnet",
    font_path: Annotated[Path | None, typer.Option("--font-path")] = None,
    series: Annotated[str, typer.Option("--series")] = "Untitled Series",
    chapter: Annotated[str, typer.Option("--chapter")] = "1",
    title: Annotated[str | None, typer.Option("--title")] = None,
    lang_source: Annotated[str, typer.Option("--lang-source")] = "en",
    lang_target: Annotated[str, typer.Option("--lang-target")] = "it",
    no_gpu: Annotated[bool, typer.Option("--no-gpu")] = False,
) -> None:
    """Traduci una cartella locale di immagini e produci PDF/CBZ."""

    job = TranslationJob(model=model, font_path=font_path, use_gpu=not no_gpu)
    try:
        manifest = run_local(
            directory,
            out,
            series=series,
            chapter_number=chapter,
            chapter_title=title,
            lang_source=lang_source,
            lang_target=lang_target,
            fmt=format,
            job=job,
        )
    except Exception as exc:
        console.print(f"[red]Errore run-local:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print("[green]Completato[/green]")
    for output_file in manifest.output_files:
        console.print(output_file)


@app.command()
def translate() -> None:
    """Alias previsto per v0.1 avanzato; usare `run-local` per ora."""

    console.print(
        "[yellow]`translate` verrà separato da `run-local` in una patch v0.1 successiva.[/yellow]"
    )


@app.command()
def server(action: Annotated[str, typer.Argument(help="up|down")]) -> None:
    """Gestione LiteLLM proxy (placeholder operativo)."""

    console.print(
        f"[yellow]server {action}: gestione automatica prevista dopo config LiteLLM stabile.[/yellow]"
    )


def _print_check(check: DoctorCheck) -> None:
    styles = {"ok": "green", "warn": "yellow", "fail": "red", "info": "cyan"}
    icons = {"ok": "OK", "warn": "WARN", "fail": "FAIL", "info": "INFO"}
    style = styles.get(check.status, "white")
    icon = icons.get(check.status, check.status.upper())
    console.print(f"[{style}]{icon:>4}[/{style}] {check.name}: {check.message}")


if __name__ == "__main__":
    app()
