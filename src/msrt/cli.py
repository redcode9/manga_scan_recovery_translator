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
from msrt.config import Settings
from msrt.doctor import DoctorCheck, run_doctor
from msrt.models import TranslationJob
from msrt.pipeline import (
    PhaseCallback,
    collect_local_chapter,
    package_outputs,
    run_local,
    translate_only,
)
from msrt.server import (
    LiteLLMUnavailableError,
    ServerStatus,
    litellm_status,
    log_file,
    start_litellm,
    stop_litellm,
)

LITELLM_CONFIG_PATH = Path("configs/litellm.yaml")

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
def server(
    action: Annotated[str, typer.Argument(help="up|down|status")],
    config: Annotated[
        Path, typer.Option("--config", help="Config LiteLLM da usare.")
    ] = LITELLM_CONFIG_PATH,
    wait_seconds: Annotated[
        float,
        typer.Option("--wait", help="Secondi di attesa per healthcheck dopo l'avvio."),
    ] = 15.0,
) -> None:
    """Gestione del proxy LiteLLM locale (subprocess; no Docker richiesto)."""

    settings = Settings()
    if action == "up":
        try:
            status = start_litellm(settings, config, wait_seconds=wait_seconds)
        except LiteLLMUnavailableError as exc:
            console.print(f"[red]LiteLLM non disponibile:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        except FileNotFoundError as exc:
            console.print(f"[red]Config mancante:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        except RuntimeError as exc:
            console.print(f"[red]Errore avvio LiteLLM:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        _print_server_status(status, log_path=log_file(settings))
        if not status.healthy:
            raise typer.Exit(code=1)
    elif action == "down":
        if stop_litellm(settings):
            console.print("[green]LiteLLM fermato.[/green]")
        else:
            console.print("[yellow]LiteLLM non era in esecuzione.[/yellow]")
    elif action == "status":
        status = litellm_status(settings)
        _print_server_status(status, log_path=log_file(settings))
        if not status.healthy:
            raise typer.Exit(code=1)
    else:
        console.print(f"[red]Azione non supportata: {action}[/red] (usare up|down|status)")
        raise typer.Exit(code=2)


def _print_server_status(status: ServerStatus, *, log_path: Path) -> None:
    if status.running and status.healthy:
        console.print(f"[green]LiteLLM up & healthy[/green] PID {status.pid}: {status.message}")
    elif status.running:
        console.print(
            f"[yellow]LiteLLM up ma non healthy[/yellow] PID {status.pid}: {status.message}"
        )
        console.print(f"[dim]Log: {log_path}[/dim]")
    else:
        console.print(f"[yellow]{status.message}[/yellow]")


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
