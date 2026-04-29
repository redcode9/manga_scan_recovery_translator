"""Entrypoint CLI di msrt."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from msrt import __version__
from msrt.doctor import DoctorCheck, run_doctor
from msrt.models import TranslationJob
from msrt.pipeline import (
    PhaseCallback,
    collect_local_chapter,
    package_outputs,
    run_local,
    translate_only,
)

app = typer.Typer(
    name="msrt",
    help="Manga Scan Recovery Translator — wrapper EN→IT.",
    no_args_is_help=True,
)
console = Console()

PHASE_DESCRIPTIONS = {
    "collect": "Raccolta pagine",
    "translate": "Traduzione con MITR",
    "package": "Packaging output",
    "done": "Completato",
}


def _make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )


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

    try:
        chapter_model = collect_local_chapter(
            directory,
            series=series,
            chapter_number=chapter,
            chapter_title=title,
            lang_source="en",
            lang_target=lang_target,
        )
        outputs = package_outputs(directory, chapter_model, out, format)
    except Exception as exc:
        console.print(f"[red]Errore package:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    for path in outputs:
        console.print(f"[green]Creato[/green] {path}")


@app.command()
def translate(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, dir_okay=True)],
    out: Annotated[Path, typer.Option("--out", help="Directory output.")] = Path("out"),
    model: Annotated[str, typer.Option("--model")] = "sonnet",
    font_path: Annotated[Path | None, typer.Option("--font-path")] = None,
    glossary: Annotated[Path | None, typer.Option("--glossary")] = None,
    series: Annotated[str, typer.Option("--series")] = "Untitled Series",
    chapter: Annotated[str, typer.Option("--chapter")] = "1",
    title: Annotated[str | None, typer.Option("--title")] = None,
    lang_source: Annotated[str, typer.Option("--lang-source")] = "en",
    lang_target: Annotated[str, typer.Option("--lang-target")] = "it",
    no_gpu: Annotated[bool, typer.Option("--no-gpu")] = False,
) -> None:
    """Traduci una cartella di immagini con MITR; non produce CBZ/PDF."""

    job = TranslationJob(
        model=model,
        font_path=font_path,
        glossary_path=glossary,
        use_gpu=not no_gpu,
    )
    with _make_progress() as progress:
        task_id = progress.add_task("Avvio...", total=2)
        on_phase = _phase_callback(progress, task_id)
        try:
            manifest = translate_only(
                directory,
                out,
                series=series,
                chapter_number=chapter,
                chapter_title=title,
                lang_source=lang_source,
                lang_target=lang_target,
                job=job,
                on_phase=on_phase,
            )
        except Exception as exc:
            console.print(f"[red]Errore translate:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    console.print("[green]Traduzione completata[/green]")
    for output_file in manifest.output_files:
        console.print(output_file)


@app.command("run-local")
def run_local_command(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, dir_okay=True)],
    out: Annotated[Path, typer.Option("--out", help="Directory output.")] = Path("out"),
    format: Annotated[str, typer.Option("--format", help="pdf|cbz|both")] = "pdf",
    model: Annotated[str, typer.Option("--model")] = "sonnet",
    font_path: Annotated[Path | None, typer.Option("--font-path")] = None,
    glossary: Annotated[Path | None, typer.Option("--glossary")] = None,
    series: Annotated[str, typer.Option("--series")] = "Untitled Series",
    chapter: Annotated[str, typer.Option("--chapter")] = "1",
    title: Annotated[str | None, typer.Option("--title")] = None,
    lang_source: Annotated[str, typer.Option("--lang-source")] = "en",
    lang_target: Annotated[str, typer.Option("--lang-target")] = "it",
    no_gpu: Annotated[bool, typer.Option("--no-gpu")] = False,
) -> None:
    """Traduci una cartella locale di immagini e produci PDF/CBZ."""

    job = TranslationJob(
        model=model,
        font_path=font_path,
        glossary_path=glossary,
        use_gpu=not no_gpu,
    )
    with _make_progress() as progress:
        task_id = progress.add_task("Avvio...", total=3)
        on_phase = _phase_callback(progress, task_id)
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
                on_phase=on_phase,
            )
        except Exception as exc:
            console.print(f"[red]Errore run-local:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    console.print("[green]Completato[/green]")
    for output_file in manifest.output_files:
        console.print(output_file)


@app.command()
def server(action: Annotated[str, typer.Argument(help="up|down")]) -> None:
    """Gestione LiteLLM proxy (placeholder operativo)."""

    console.print(
        f"[yellow]server {action}: gestione automatica prevista dopo config LiteLLM stabile.[/yellow]"
    )


def _phase_callback(progress: Progress, task_id: TaskID) -> PhaseCallback:
    """Bind a phase callback that drives a single progress task."""

    def on_phase(phase: str) -> None:
        description = PHASE_DESCRIPTIONS.get(phase, phase)
        if phase == "done":
            progress.update(task_id, description=description)
            return
        progress.update(task_id, advance=1, description=description)

    return on_phase


def _print_check(check: DoctorCheck) -> None:
    styles = {"ok": "green", "warn": "yellow", "fail": "red", "info": "cyan"}
    icons = {"ok": "OK", "warn": "WARN", "fail": "FAIL", "info": "INFO"}
    style = styles.get(check.status, "white")
    icon = icons.get(check.status, check.status.upper())
    console.print(f"[{style}]{icon:>4}[/{style}] {check.name}: {check.message}")


if __name__ == "__main__":
    app()
