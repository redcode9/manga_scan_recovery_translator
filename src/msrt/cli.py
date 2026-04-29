"""Entrypoint CLI di msrt."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
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
from msrt.scrape.base import FetchError
from msrt.scrape.registry import scraper_for_url
from msrt.server import (
    LiteLLMUnavailableError,
    ServerStatus,
    litellm_status,
    log_file,
    start_litellm,
    stop_litellm,
)
from msrt.setup import run_setup
from msrt.translate.glossary import load_glossary
from msrt.translate.glossary_builder import (
    GLOSSARY_SUBDIR,
    GlossaryBuildError,
    build_glossary_via_llm,
    cached_glossary_path,
    save_glossary,
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
    model: Annotated[
        str | None,
        typer.Option("--model", help="Alias modello da verificare. Default: MSRT_MODEL."),
    ] = None,
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

    checks = run_doctor(
        model=_effective_model(model),
        font_path=font_path,
        paid_smoke=paid_smoke,
        verbose=verbose,
    )
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
        files = [page.local_path for page in chapter_model.pages]
        outputs = package_outputs(files, chapter_model, out, format)
    except Exception as exc:
        console.print(f"[red]Errore package:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    for path in outputs:
        console.print(f"[green]Creato[/green] {path}")


@app.command()
def translate(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, dir_okay=True)],
    out: Annotated[Path, typer.Option("--out", help="Directory output.")] = Path("out"),
    model: Annotated[str | None, typer.Option("--model", help="Default: MSRT_MODEL.")] = None,
    font_path: Annotated[Path | None, typer.Option("--font-path")] = None,
    glossary: Annotated[
        Path | None,
        typer.Option(
            "--glossary",
            help="Override del glossario. Se omesso uso quello in cache (auto-build).",
        ),
    ] = None,
    auto_glossary: Annotated[
        bool,
        typer.Option(
            "--auto-glossary/--no-auto-glossary",
            help="Genera/usa automaticamente un glossario di serie via LLM.",
        ),
    ] = True,
    pre_dict: Annotated[
        Path | None,
        typer.Option("--pre-dict", help="File TSV correzioni OCR (passato a MITR --pre-dict)."),
    ] = None,
    series: Annotated[str, typer.Option("--series")] = "Untitled Series",
    chapter: Annotated[str, typer.Option("--chapter")] = "1",
    title: Annotated[str | None, typer.Option("--title")] = None,
    lang_source: Annotated[str, typer.Option("--lang-source")] = "en",
    lang_target: Annotated[str, typer.Option("--lang-target")] = "it",
    no_gpu: Annotated[bool, typer.Option("--no-gpu")] = False,
) -> None:
    """Traduci una cartella di immagini con MITR; non produce CBZ/PDF."""

    job = TranslationJob(
        model=_effective_model(model),
        font_path=font_path,
        glossary_path=glossary,
        auto_glossary=auto_glossary,
        pre_dict_path=pre_dict,
        use_gpu=not no_gpu,
    )
    with _make_progress() as progress:
        task_id = progress.add_task("Avvio...", total=2)
        on_phase = _phase_callback(progress, task_id)
        on_log = _log_callback(progress)
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
                on_log=on_log,
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
    model: Annotated[str | None, typer.Option("--model", help="Default: MSRT_MODEL.")] = None,
    font_path: Annotated[Path | None, typer.Option("--font-path")] = None,
    glossary: Annotated[
        Path | None,
        typer.Option(
            "--glossary",
            help="Override del glossario. Se omesso uso quello in cache (auto-build).",
        ),
    ] = None,
    auto_glossary: Annotated[
        bool,
        typer.Option(
            "--auto-glossary/--no-auto-glossary",
            help="Genera/usa automaticamente un glossario di serie via LLM.",
        ),
    ] = True,
    pre_dict: Annotated[
        Path | None,
        typer.Option("--pre-dict", help="File TSV correzioni OCR (passato a MITR --pre-dict)."),
    ] = None,
    series: Annotated[str, typer.Option("--series")] = "Untitled Series",
    chapter: Annotated[str, typer.Option("--chapter")] = "1",
    title: Annotated[str | None, typer.Option("--title")] = None,
    lang_source: Annotated[str, typer.Option("--lang-source")] = "en",
    lang_target: Annotated[str, typer.Option("--lang-target")] = "it",
    no_gpu: Annotated[bool, typer.Option("--no-gpu")] = False,
) -> None:
    """Traduci una cartella locale di immagini e produci PDF/CBZ."""

    job = TranslationJob(
        model=_effective_model(model),
        font_path=font_path,
        glossary_path=glossary,
        auto_glossary=auto_glossary,
        pre_dict_path=pre_dict,
        use_gpu=not no_gpu,
    )
    with _make_progress() as progress:
        task_id = progress.add_task("Avvio...", total=3)
        on_phase = _phase_callback(progress, task_id)
        on_log = _log_callback(progress)
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
                on_log=on_log,
            )
        except Exception as exc:
            console.print(f"[red]Errore run-local:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    console.print("[green]Completato[/green]")
    for output_file in manifest.output_files:
        console.print(output_file)


@app.command()
def fetch(
    url: Annotated[str, typer.Argument(help="URL del capitolo manga da scaricare.")],
    out: Annotated[
        Path,
        typer.Option("--out", help="Cartella di output. Verrà creata se non esiste."),
    ] = Path("out") / "fetch",
    site: Annotated[
        str,
        typer.Option(
            "--site",
            help="Adapter da usare. 'auto' (default) sceglie in base al dominio.",
        ),
    ] = "auto",
    i_own_rights: Annotated[
        bool,
        typer.Option(
            "--i-own-rights",
            help=(
                "Conferma esplicita che hai il diritto di scaricare il contenuto. "
                "Guardrail UX, non tutela legale: la responsabilità resta tua."
            ),
        ),
    ] = False,
) -> None:
    """Scarica un capitolo da URL in una cartella locale di immagini.

    Non chiama MITR né LLM — produce solo la cartella di pagine, pronta
    per essere passata a ``msrt run-local``. Lo step ``fetch + run-local``
    sarà unificato in ``msrt run`` dalla v0.2c.
    """

    if not i_own_rights:
        console.print(
            "[red]Errore:[/red] msrt fetch scarica contenuti da Internet. "
            "Aggiungi [bold]--i-own-rights[/bold] solo se hai il diritto di "
            "scaricare il contenuto (es. tuo, pubblico dominio, o licenza che "
            "lo consente). È un guardrail UX, non tutela legale: la responsabilità "
            "resta tua."
        )
        raise typer.Exit(code=1)

    try:
        scraper = scraper_for_url(url, site=site)
    except FetchError as exc:
        console.print(f"[red]Errore:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"Adapter scelto: [bold]{scraper.name}[/bold]. Scarico in [bold]{out}[/bold]…")
    try:
        result = asyncio.run(scraper.fetch(url, out))
    except NotImplementedError as exc:
        console.print(f"[yellow]Adapter '{scraper.name}' non ancora implementato:[/yellow] {exc}")
        raise typer.Exit(code=2) from exc
    except FetchError as exc:
        console.print(f"[red]Errore fetch:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    for warn in result.warnings:
        console.print(f"[yellow]warn:[/yellow] {warn}")
    console.print(
        f"[green]✓[/green] {len(result.pages)} pagine scaricate in {result.output_dir}\n"
        f"[dim]Series:[/dim] {result.series}\n"
        f"[dim]Chapter:[/dim] {result.chapter_number}"
        + (f"  [dim]Title:[/dim] {result.chapter_title}" if result.chapter_title else "")
    )
    console.print(
        "\nProssimo passo: [bold]msrt run-local "
        f"{result.output_dir} --series {result.series!r} "
        f"--chapter {result.chapter_number!r} --format pdf[/bold]"
    )


@app.command()
def setup(
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Accetta default in tutti gli step interattivi."),
    ] = False,
    no_install_mitr: Annotated[
        bool,
        typer.Option("--no-install-mitr", help="Salta l'installazione di MITR."),
    ] = False,
    no_server: Annotated[
        bool,
        typer.Option("--no-server", help="Non avviare LiteLLM al termine."),
    ] = False,
    paid_smoke: Annotated[
        bool,
        typer.Option("--paid-smoke", help="Esegui smoke paid alla fine (chiede conferma)."),
    ] = False,
    project_root: Annotated[
        Path,
        typer.Option("--project-root", help="Override radice progetto (per test)."),
    ] = Path("."),
) -> None:
    """Wizard di primo setup: env, provider, MITR, LiteLLM."""

    code = run_setup(
        project_root=project_root.resolve(),
        yes=yes,
        install_mitr=not no_install_mitr,
        start_server=not no_server,
        paid_smoke=paid_smoke,
    )
    if code != 0:
        raise typer.Exit(code=code)


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


def _log_callback(progress: Progress) -> Callable[[str], None]:
    """Bind a log callback that prints above the progress bar.

    Rich's ``progress.console.print`` reflows around the live progress
    rendering so messages from the pipeline (auto-glossary build, etc.)
    don't get mangled by the spinner.
    """

    def on_log(message: str) -> None:
        progress.console.print(message)

    return on_log


def _print_check(check: DoctorCheck) -> None:
    styles = {"ok": "green", "warn": "yellow", "fail": "red", "info": "cyan"}
    icons = {"ok": "OK", "warn": "WARN", "fail": "FAIL", "info": "INFO"}
    style = styles.get(check.status, "white")
    icon = icons.get(check.status, check.status.upper())
    console.print(f"[{style}]{icon:>4}[/{style}] {check.name}: {check.message}")


def _effective_model(model: str | None) -> str:
    return model or Settings().default_model


glossary_app = typer.Typer(
    name="glossary",
    help="Gestione del glossario di serie (auto-generato via LLM).",
    no_args_is_help=True,
)
app.add_typer(glossary_app, name="glossary")


@glossary_app.command("build")
def glossary_build(
    series: Annotated[str, typer.Argument(help="Titolo della serie (es. 'Wistoria').")],
    model: Annotated[
        str | None,
        typer.Option("--model", help="Alias modello LLM. Default: MSRT_MODEL."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Rigenera anche se la cache contiene già il glossario."),
    ] = False,
) -> None:
    """Costruisce (o rigenera con --force) il glossario per la serie via LLM."""

    settings = Settings()
    cache_path = cached_glossary_path(series, settings)
    if cache_path.exists() and not force:
        console.print(
            f"[yellow]Glossario già presente:[/yellow] {cache_path}\n"
            "[dim]Usa --force per rigenerarlo.[/dim]"
        )
        raise typer.Exit(code=0)

    effective_model = _effective_model(model)
    console.print(
        f"Costruisco glossario per [bold]{series}[/bold] con modello "
        f"[bold]{effective_model}[/bold]..."
    )
    try:
        result = build_glossary_via_llm(series, model=effective_model, settings=settings)
    except GlossaryBuildError as exc:
        console.print(f"[red]Build fallita:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    save_glossary(cache_path, result.entries)
    console.print(
        f"[green]✓[/green] {len(result.entries)} voci salvate in {cache_path} "
        f"(token in/out: {result.tokens_in or '?'} / {result.tokens_out or '?'})."
    )


@glossary_app.command("show")
def glossary_show(
    series: Annotated[str, typer.Argument(help="Titolo della serie.")],
) -> None:
    """Stampa il glossario in cache per la serie."""

    settings = Settings()
    cache_path = cached_glossary_path(series, settings)
    if not cache_path.exists():
        console.print(
            f"[yellow]Nessun glossario per[/yellow] '{series}' in {cache_path.parent}.\n"
            f"[dim]Esegui[/dim] [bold]msrt glossary build {series!r}[/bold]"
        )
        raise typer.Exit(code=1)
    entries = load_glossary(cache_path)
    console.print(f"[bold]{cache_path}[/bold] — {len(entries)} voci\n")
    for source, target in sorted(entries.items()):
        console.print(f"  {source}\t→ {target}")


@glossary_app.command("list")
def glossary_list() -> None:
    """Lista tutti i glossari in cache."""

    settings = Settings()
    cache_root = settings.cache_dir / GLOSSARY_SUBDIR
    if not cache_root.exists():
        console.print(f"[yellow]Cache vuota:[/yellow] {cache_root} non esiste ancora.")
        return
    items = sorted(cache_root.glob("*.tsv"))
    if not items:
        console.print(f"[yellow]Nessun glossario in[/yellow] {cache_root}.")
        return
    console.print(f"[bold]{cache_root}[/bold] — {len(items)} glossari\n")
    for path in items:
        try:
            entries = load_glossary(path)
        except OSError:
            console.print(f"  [red]✗[/red] {path.stem} (errore lettura)")
            continue
        console.print(f"  [green]●[/green] {path.stem}  [dim]({len(entries)} voci)[/dim]")


@glossary_app.command("path")
def glossary_path_cmd(
    series: Annotated[str, typer.Argument(help="Titolo della serie.")],
) -> None:
    """Stampa il path del glossario in cache (anche se non esiste)."""

    settings = Settings()
    cache_path = cached_glossary_path(series, settings)
    console.print(str(cache_path))


@glossary_app.command("forget")
def glossary_forget(
    series: Annotated[str, typer.Argument(help="Titolo della serie.")],
) -> None:
    """Cancella il glossario in cache per la serie."""

    settings = Settings()
    cache_path = cached_glossary_path(series, settings)
    if not cache_path.exists():
        console.print(f"[yellow]Niente da cancellare:[/yellow] {cache_path} non esiste.")
        return
    cache_path.unlink()
    console.print(f"[green]✓[/green] Cancellato {cache_path}.")


if __name__ == "__main__":
    app()
