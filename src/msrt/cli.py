"""Entrypoint CLI di msrt."""

from __future__ import annotations

import asyncio
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal, cast

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
from msrt.models import ManifestFetch, RunManifest, TranslationJob
from msrt.paths import litellm_config_path
from msrt.pipeline import (
    PhaseCallback,
    QuotaExhaustedError,
    collect_local_chapter,
    package_outputs,
    run_local,
    slugify,
    translate_only,
)
from msrt.scrape.base import ChapterLink, FetchError, FetchResult
from msrt.scrape.registry import scraper_for_url
from msrt.scrape.selection import (
    parse_chapter_list,
    parse_chapter_range,
    select_chapters,
)
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

# Resolved per-call via ``litellm_config_path()`` so a user who runs
# ``msrt`` from outside the repo gets the right file. Typer defaults
# are evaluated at import time, so the ``server`` command uses
# ``None`` as the default and resolves dynamically inside the body.

app = typer.Typer(
    name="msrt",
    help="Manga Scan Recovery Translator — wrapper EN→IT.",
    no_args_is_help=True,
)
console = Console()

PHASE_DESCRIPTIONS = {
    "collect": "Raccolta pagine",
    "translate": "Traduzione con MITR",
    "postprocess": "Postprocess bubble-aware",
    "package": "Packaging output",
    "done": "Completato",
}

RendererOption = Annotated[
    str,
    typer.Option(
        "--renderer",
        help="mitr-manga2eng|custom-postprocess. Default: custom-postprocess.",
    ),
]


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
    renderer: RendererOption = "custom-postprocess",
    series: Annotated[str, typer.Option("--series")] = "Untitled Series",
    chapter: Annotated[str, typer.Option("--chapter")] = "1",
    title: Annotated[str | None, typer.Option("--title")] = None,
    lang_source: Annotated[str, typer.Option("--lang-source")] = "en",
    lang_target: Annotated[str, typer.Option("--lang-target")] = "it",
    no_gpu: Annotated[bool, typer.Option("--no-gpu")] = False,
) -> None:
    """Traduci una cartella di immagini con MITR; non produce CBZ/PDF."""

    renderer_choice = _renderer(renderer)
    job = TranslationJob(
        model=_effective_model(model),
        font_path=font_path,
        glossary_path=glossary,
        auto_glossary=auto_glossary,
        pre_dict_path=pre_dict,
        renderer=renderer_choice,
        use_gpu=not no_gpu,
    )
    with _make_progress() as progress:
        task_id = progress.add_task(
            "Avvio...", total=_phase_total(renderer_choice, includes_package=False)
        )
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
    renderer: RendererOption = "custom-postprocess",
    series: Annotated[str, typer.Option("--series")] = "Untitled Series",
    chapter: Annotated[str, typer.Option("--chapter")] = "1",
    title: Annotated[str | None, typer.Option("--title")] = None,
    lang_source: Annotated[str, typer.Option("--lang-source")] = "en",
    lang_target: Annotated[str, typer.Option("--lang-target")] = "it",
    no_gpu: Annotated[bool, typer.Option("--no-gpu")] = False,
) -> None:
    """Traduci una cartella locale di immagini e produci PDF/CBZ."""

    renderer_choice = _renderer(renderer)
    job = TranslationJob(
        model=_effective_model(model),
        font_path=font_path,
        glossary_path=glossary,
        auto_glossary=auto_glossary,
        pre_dict_path=pre_dict,
        renderer=renderer_choice,
        use_gpu=not no_gpu,
    )
    with _make_progress() as progress:
        task_id = progress.add_task(
            "Avvio...", total=_phase_total(renderer_choice, includes_package=True)
        )
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
def run(
    url: Annotated[str, typer.Argument(help="URL del capitolo manga da tradurre.")],
    out: Annotated[
        Path,
        typer.Option("--out", help="Cartella output finale (PDF/CBZ + manifest)."),
    ] = Path("out"),
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
    renderer: RendererOption = "custom-postprocess",
    lang_source: Annotated[str, typer.Option("--lang-source")] = "en",
    lang_target: Annotated[str, typer.Option("--lang-target")] = "it",
    no_gpu: Annotated[bool, typer.Option("--no-gpu")] = False,
    site: Annotated[
        str,
        typer.Option(
            "--site",
            help="Adapter da usare. 'auto' (default) sceglie in base al dominio.",
        ),
    ] = "auto",
    all_chapters: Annotated[
        bool,
        typer.Option(
            "--all-chapters",
            help="Scarica/traduce tutti i capitoli esposti dalla serie del reader URL.",
        ),
    ] = False,
    skip_existing: Annotated[
        bool,
        typer.Option(
            "--skip-existing/--no-skip-existing",
            help="In --all-chapters salta i capitoli con output già presente.",
        ),
    ] = True,
    continue_on_error: Annotated[
        bool,
        typer.Option(
            "--continue-on-error/--stop-on-error",
            help="In --all-chapters prosegue sugli altri capitoli se uno fallisce.",
        ),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="In --all-chapters lista i capitoli che verrebbero processati senza scaricare/tradurre.",
        ),
    ] = False,
    range_filter: Annotated[
        str | None,
        typer.Option(
            "--range",
            help="Solo capitoli nel range numerico inclusivo, es. '50-51'. Richiede --all-chapters.",
        ),
    ] = None,
    chapters_filter: Annotated[
        str | None,
        typer.Option(
            "--chapters",
            help="Lista esplicita di capitoli, es. '50,51,51.1'. Richiede --all-chapters.",
        ),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            help="Processa solo i primi N capitoli, dopo --range/--chapters. Richiede --all-chapters.",
        ),
    ] = None,
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
    """Scarica + traduce un capitolo da URL in un solo comando.

    È solo orchestrazione: ``fetch`` produce le pagine in
    ``out/.msrt-fetch/<site>/<series>/<chapter>/`` e ``run-local``
    prosegue da lì verso ``out/<series>-<chapter>-<lang>.{pdf,cbz}``.
    Il fetch resta su disco anche in caso di errore di traduzione, così
    si può riprendere/debuggare senza riscaricare le pagine.
    """

    if not i_own_rights:
        console.print(
            "[red]Errore:[/red] msrt run scarica contenuti da Internet. "
            "Aggiungi [bold]--i-own-rights[/bold] solo se hai il diritto di "
            "scaricare il contenuto (es. tuo, pubblico dominio, o licenza che "
            "lo consente). È un guardrail UX, non tutela legale: la responsabilità "
            "resta tua."
        )
        raise typer.Exit(code=1)

    renderer_choice = _renderer(renderer)

    # Selectors only make sense with --all-chapters; reject otherwise so the
    # user doesn't think they did something they didn't.
    selectors_used = (range_filter, chapters_filter, limit)
    if any(value is not None for value in selectors_used) and not all_chapters:
        console.print("[red]Errore:[/red] --range/--chapters/--limit richiedono --all-chapters.")
        raise typer.Exit(code=1)

    if all_chapters:
        try:
            range_parsed = parse_chapter_range(range_filter) if range_filter else None
            chapters_parsed = parse_chapter_list(chapters_filter) if chapters_filter else None
            limit_parsed = _validated_limit(limit)
        except ValueError as exc:
            console.print(f"[red]Errore selettore capitoli:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        _run_all_chapters(
            url=url,
            out=out,
            fmt=format,
            model=model,
            font_path=font_path,
            glossary=glossary,
            auto_glossary=auto_glossary,
            pre_dict=pre_dict,
            renderer=renderer_choice,
            lang_source=lang_source,
            lang_target=lang_target,
            no_gpu=no_gpu,
            site=site,
            skip_existing=skip_existing,
            continue_on_error=continue_on_error,
            dry_run=dry_run,
            range_filter=range_parsed,
            chapter_list=chapters_parsed,
            limit=limit_parsed,
        )
        return

    try:
        manifest = _run_url_once(
            url=url,
            out=out,
            fmt=format,
            model=model,
            font_path=font_path,
            glossary=glossary,
            auto_glossary=auto_glossary,
            pre_dict=pre_dict,
            renderer=renderer_choice,
            lang_source=lang_source,
            lang_target=lang_target,
            no_gpu=no_gpu,
            site=site,
        )
    except NotImplementedError as exc:
        console.print(f"[yellow]Adapter non implementato:[/yellow] {exc}")
        raise typer.Exit(code=2) from exc
    except FetchError as exc:
        console.print(f"[red]Errore fetch:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]Errore run:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print("[green]Completato[/green]")
    for output_file in manifest.output_files:
        console.print(output_file)


def _run_url_once(
    *,
    url: str,
    out: Path,
    fmt: str,
    model: str | None,
    font_path: Path | None,
    glossary: Path | None,
    auto_glossary: bool,
    pre_dict: Path | None,
    renderer: str,
    lang_source: str,
    lang_target: str,
    no_gpu: bool,
    site: str,
    manifest_name: str | None = None,
) -> RunManifest:
    try:
        scraper = scraper_for_url(url, site=site)
    except FetchError:
        raise

    fetch_root = out / ".msrt-fetch" / scraper.name
    pending_dir = fetch_root / f"_pending-{uuid.uuid4().hex[:8]}"
    console.print(f"Adapter [bold]{scraper.name}[/bold]: scarico in [dim]{pending_dir}[/dim]…")

    try:
        fetch_result: FetchResult = asyncio.run(scraper.fetch(url, pending_dir))
    except (NotImplementedError, FetchError):
        shutil.rmtree(pending_dir, ignore_errors=True)
        raise
    except Exception as exc:
        console.print(f"[red]Errore fetch inatteso:[/red] {exc}")
        shutil.rmtree(pending_dir, ignore_errors=True)
        raise

    # Promote pending → canonical fetch dir based on resolved metadata.
    final_fetch_dir = (
        fetch_root / slugify(fetch_result.series) / slugify(fetch_result.chapter_number)
    )
    if final_fetch_dir.exists():
        shutil.rmtree(final_fetch_dir)
    final_fetch_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(pending_dir), str(final_fetch_dir))
    console.print(
        f"[green]✓ fetch[/green] {len(fetch_result.pages)} pagine in [bold]{final_fetch_dir}[/bold]\n"
        f"[dim]Series:[/dim] {fetch_result.series}  "
        f"[dim]Chapter:[/dim] {fetch_result.chapter_number}"
    )
    for warn in fetch_result.warnings:
        console.print(f"[yellow]warn:[/yellow] {warn}")

    fetch_meta = ManifestFetch(
        strategy=fetch_result.strategy,
        source_url=fetch_result.source_url,
        output_dir=str(final_fetch_dir),
        page_count=len(fetch_result.pages),
        warnings=list(fetch_result.warnings),
        capture_mode=fetch_result.capture_mode,
        viewport=fetch_result.viewport,
        device_scale_factor=fetch_result.device_scale_factor,
        manual_intervention=fetch_result.manual_intervention,
    )

    renderer_choice = _renderer(renderer)
    job = TranslationJob(
        model=_effective_model(model),
        font_path=font_path,
        glossary_path=glossary,
        auto_glossary=auto_glossary,
        pre_dict_path=pre_dict,
        renderer=renderer_choice,
        use_gpu=not no_gpu,
    )
    with _make_progress() as progress:
        task_id = progress.add_task(
            "Avvio…", total=_phase_total(renderer_choice, includes_package=True)
        )
        on_phase = _phase_callback(progress, task_id)
        on_log = _log_callback(progress)
        try:
            return run_local(
                final_fetch_dir,
                out,
                series=fetch_result.series,
                chapter_number=fetch_result.chapter_number,
                chapter_title=fetch_result.chapter_title,
                lang_source=lang_source,
                lang_target=lang_target,
                fmt=fmt,
                job=job,
                on_phase=on_phase,
                on_log=on_log,
                input_type="url",
                input_url=url,
                fetch_metadata=fetch_meta,
                manifest_name=manifest_name,
            )
        except Exception as exc:
            console.print(f"[red]Errore run-local:[/red] {exc}")
            console.print(f"[dim]Le pagine fetch restano in {final_fetch_dir} per debug.[/dim]")
            raise


def _run_all_chapters(
    *,
    url: str,
    out: Path,
    fmt: str,
    model: str | None,
    font_path: Path | None,
    glossary: Path | None,
    auto_glossary: bool,
    pre_dict: Path | None,
    renderer: str,
    lang_source: str,
    lang_target: str,
    no_gpu: bool,
    site: str,
    skip_existing: bool,
    continue_on_error: bool,
    dry_run: bool,
    range_filter: tuple[float, float] | None = None,
    chapter_list: set[str] | None = None,
    limit: int | None = None,
) -> None:
    try:
        scraper = scraper_for_url(url, site=site)
        chapters = asyncio.run(scraper.list_chapters(url))
    except FetchError as exc:
        console.print(f"[red]Errore lista capitoli:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not chapters:
        console.print("[red]Errore:[/red] nessun capitolo trovato.")
        raise typer.Exit(code=1)

    total_found = len(chapters)
    chapters = select_chapters(
        chapters,
        range_filter=range_filter,
        chapter_list=chapter_list,
        limit=limit,
    )
    if not chapters:
        criteria_parts: list[str] = []
        if range_filter is not None:
            criteria_parts.append(f"range={range_filter[0]}-{range_filter[1]}")
        if chapter_list is not None:
            criteria_parts.append(f"chapters={sorted(chapter_list)}")
        if limit is not None:
            criteria_parts.append(f"limit={limit}")
        criteria = ", ".join(criteria_parts) or "(nessuno)"
        console.print(
            f"[red]Errore:[/red] i selettori ({criteria}) non hanno selezionato "
            f"alcun capitolo dei {total_found} trovati."
        )
        raise typer.Exit(code=1)

    suffix = (
        f" (selezionati {len(chapters)} di {total_found})" if len(chapters) != total_found else ""
    )
    console.print(
        f"[green]✓[/green] Trovati [bold]{total_found}[/bold] capitoli con "
        f"adapter [bold]{scraper.name}[/bold]{suffix}."
    )
    if dry_run:
        console.print(
            "[yellow]DRY RUN[/yellow] nessun download, nessuna traduzione, nessun file scritto."
        )
        for index, chapter in enumerate(chapters, start=1):
            marker = (
                "skip"
                if skip_existing
                and _chapter_outputs_exist(
                    chapter,
                    out=out,
                    fmt=fmt,
                    lang_target=lang_target,
                )
                else "todo"
            )
            title = f" — {chapter.title}" if chapter.title else ""
            console.print(
                f"{index:>3}. [{marker}] ch. {chapter.chapter_number}{title}\n     {chapter.url}"
            )
        return

    failures: list[tuple[ChapterLink, str]] = []
    completed = 0
    skipped = 0

    for index, chapter in enumerate(chapters, start=1):
        label = f"{chapter.chapter_number}"
        console.rule(f"[bold]Capitolo {label}[/bold] ({index}/{len(chapters)})")
        if skip_existing and _chapter_outputs_exist(
            chapter,
            out=out,
            fmt=fmt,
            lang_target=lang_target,
        ):
            skipped += 1
            console.print(f"[yellow]skip[/yellow] output già presente per capitolo {label}.")
            continue

        # Per-chapter manifest filename so each chapter in a CLI batch
        # gets its own ``msrt-run-<series>-<chapter>-<lang>.json`` instead
        # of overwriting a shared ``msrt-run.json``.
        series_for_manifest = chapter.series or "unknown-series"
        manifest_name = (
            f"msrt-run-{slugify(series_for_manifest)}-"
            f"{slugify(chapter.chapter_number)}-{lang_target}.json"
        )

        try:
            manifest = _run_url_once(
                url=chapter.url,
                out=out,
                fmt=fmt,
                model=model,
                font_path=font_path,
                glossary=glossary,
                auto_glossary=auto_glossary,
                pre_dict=pre_dict,
                renderer=renderer,
                lang_source=lang_source,
                lang_target=lang_target,
                no_gpu=no_gpu,
                site=site,
                manifest_name=manifest_name,
            )
        except QuotaExhaustedError as exc:
            # Provider quota is global: every remaining chapter would
            # fail identically. Abort the batch even with
            # ``--continue-on-error``; skip_existing on the retry will
            # resume from this chapter once the user tops up.
            failures.append((chapter, str(exc)))
            console.print(f"[red]Errore capitolo {label}:[/red] {exc}")
            console.print("[red]Batch interrotto:[/red] quota esaurita, niente da continuare.")
            raise typer.Exit(code=1) from exc
        except Exception as exc:
            failures.append((chapter, str(exc)))
            console.print(f"[red]Errore capitolo {label}:[/red] {exc}")
            if not continue_on_error:
                raise typer.Exit(code=1) from exc
            continue

        completed += 1
        for output_file in manifest.output_files:
            console.print(output_file)

    console.rule("[bold]Batch completato[/bold]")
    console.print(
        f"[green]completati[/green]: {completed}  "
        f"[yellow]saltati[/yellow]: {skipped}  "
        f"[red]falliti[/red]: {len(failures)}"
    )
    if failures:
        for chapter, error in failures:
            console.print(f"[red]fail[/red] ch. {chapter.chapter_number}: {error}")
        raise typer.Exit(code=1)


def _chapter_outputs_exist(
    chapter: ChapterLink,
    *,
    out: Path,
    fmt: str,
    lang_target: str,
) -> bool:
    if not chapter.series:
        return False
    base = f"{slugify(chapter.series)}-{slugify(chapter.chapter_number)}-{lang_target}"
    expected: list[Path] = []
    if fmt in {"pdf", "both"}:
        expected.append(out / f"{base}.pdf")
    if fmt in {"cbz", "both"}:
        expected.append(out / f"{base}.cbz")
    return bool(expected) and all(path.exists() for path in expected)


@app.command()
def ui(
    host: Annotated[
        str,
        typer.Option("--host", help="Bind host. Default 127.0.0.1 (no LAN exposure)."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", help="Porta TCP del backend UI."),
    ] = 4001,
    reload: Annotated[
        bool,
        typer.Option("--reload", help="Auto-reload del backend durante lo sviluppo."),
    ] = False,
    build: Annotated[
        bool,
        typer.Option(
            "--build/--no-build",
            help=(
                "Builda apps/desktop con npm run build se la dist non c'è "
                "(default attivo). Disabilita se preferisci servire solo l'API e usare 'npm run dev'."
            ),
        ),
    ] = True,
    open_browser: Annotated[
        bool,
        typer.Option(
            "--open/--no-open",
            help="Apre il browser di sistema sulla UI dopo l'avvio.",
        ),
    ] = True,
) -> None:
    """Avvia la UI desktop/web in un singolo comando.

    Quando ``apps/desktop/dist`` è presente, il backend FastAPI serve
    sia ``/api`` sia la SPA — un solo URL, un solo processo. Senza la
    dist, parte il backend "headless" e lo sviluppatore può
    affiancare ``npm run dev`` per l'HMR.

    Bind di default su 127.0.0.1 — non esporre questa porta in rete.
    """

    try:
        import uvicorn
    except ImportError as exc:
        console.print(
            "[red]Errore:[/red] dipendenze UI non installate. "
            "Esegui [bold]uv sync --extra ui[/bold] o [bold]uv sync --all-extras[/bold]."
        )
        raise typer.Exit(code=1) from exc

    from msrt.paths import frontend_source_dir

    desktop_dir = frontend_source_dir()
    dist_dir = desktop_dir / "dist"

    if build:
        if not desktop_dir.is_dir():
            console.print(
                f"[yellow]apps/desktop non trovato in {desktop_dir}. "
                "Salto la build e avvio solo l'API.[/yellow]"
            )
        elif not dist_dir.is_dir() or _frontend_is_stale(desktop_dir, dist_dir):
            _build_frontend(desktop_dir)

    if dist_dir.is_dir():
        console.print(
            f"[bold]msrt[/bold] UI + API → http://{host}:{port}\n"
            f"[dim]API docs:[/dim] http://{host}:{port}/docs"
        )
    else:
        console.print(
            f"[bold]msrt[/bold] API → http://{host}:{port}  "
            f"[dim](UI non buildata; usa 'npm run dev' o riprova con --build)[/dim]"
        )

    if open_browser and dist_dir.is_dir():
        import threading
        import webbrowser

        url = f"http://{host}:{port}/"
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        "msrt.ui_server:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


def _build_frontend(desktop_dir: Path) -> None:
    """Run ``npm install`` + ``npm run build`` in ``apps/desktop`` so
    ``msrt ui`` can serve a fresh production bundle. Best-effort: if
    npm isn't installed we tell the user how to do the build manually
    and continue with API-only mode."""

    import shutil
    import subprocess

    npm = shutil.which("npm")
    if npm is None:
        console.print(
            "[yellow]npm non trovato. Salto la build della UI: "
            "installa Node 18+ e rilancia, oppure builda a mano con "
            "[bold]cd apps/desktop && npm install && npm run build[/bold].[/yellow]"
        )
        return

    if not (desktop_dir / "node_modules").is_dir():
        console.print("[bold]apps/desktop:[/bold] npm install…")
        result = subprocess.run([npm, "install"], cwd=desktop_dir, check=False)
        if result.returncode != 0:
            console.print("[red]npm install fallito; salto la build.[/red]")
            return

    console.print("[bold]apps/desktop:[/bold] npm run build…")
    result = subprocess.run([npm, "run", "build"], cwd=desktop_dir, check=False)
    if result.returncode != 0:
        console.print("[red]npm run build fallito; avvio solo l'API.[/red]")


def _frontend_is_stale(desktop_dir: Path, dist_dir: Path) -> bool:
    """Return True when sources are newer than the built bundle.

    Compares the mtime of every relevant source file (``src/**``,
    ``index.html``, ``package*.json``, ``vite.config.*``,
    ``tsconfig*.json``, ``tailwind.config.*``) against
    ``dist/index.html``. After a ``git pull`` this catches the
    typical case where the backend bumped along with the UI but the
    user still has yesterday's bundle on disk.
    """

    index = dist_dir / "index.html"
    if not index.is_file():
        return True
    dist_mtime = index.stat().st_mtime

    candidates: list[Path] = []
    src_dir = desktop_dir / "src"
    if src_dir.is_dir():
        candidates.extend(src_dir.rglob("*"))
    for name in (
        "index.html",
        "package.json",
        "package-lock.json",
        "vite.config.ts",
        "vite.config.js",
        "tsconfig.json",
        "tsconfig.app.json",
        "tailwind.config.ts",
        "tailwind.config.js",
    ):
        candidate = desktop_dir / name
        if candidate.is_file():
            candidates.append(candidate)

    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.stat().st_mtime > dist_mtime:
                return True
        except OSError:
            continue
    return False


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
        Path | None,
        typer.Option("--project-root", help="Override radice progetto (per test)."),
    ] = None,
) -> None:
    """Wizard di primo setup: env, provider, MITR, LiteLLM."""

    from msrt.paths import project_root as resolve_root

    root = project_root.resolve() if project_root else resolve_root()
    code = run_setup(
        project_root=root,
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
        Path | None, typer.Option("--config", help="Config LiteLLM da usare.")
    ] = None,
    wait_seconds: Annotated[
        float,
        typer.Option("--wait", help="Secondi di attesa per healthcheck dopo l'avvio."),
    ] = 15.0,
) -> None:
    """Gestione del proxy LiteLLM locale (subprocess; no Docker richiesto)."""

    settings = Settings()
    resolved_config = config or litellm_config_path()
    if action == "up":
        try:
            status = start_litellm(settings, resolved_config, wait_seconds=wait_seconds)
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


def _renderer(value: str) -> Literal["mitr-default", "mitr-manga2eng", "custom-postprocess"]:
    normalized = value.strip().lower()
    allowed = {"mitr-default", "mitr-manga2eng", "custom-postprocess"}
    if normalized not in allowed:
        raise typer.BadParameter(
            f"renderer non supportato: {value!r}. Usa: {', '.join(sorted(allowed))}."
        )
    return cast(Literal["mitr-default", "mitr-manga2eng", "custom-postprocess"], normalized)


def _validated_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    if limit < 1:
        raise ValueError(f"--limit deve essere >= 1, ricevuto {limit}.")
    return limit


def _phase_total(
    renderer: Literal["mitr-default", "mitr-manga2eng", "custom-postprocess"],
    *,
    includes_package: bool,
) -> int:
    total = 2  # collect + translate
    if renderer == "custom-postprocess":
        total += 1
    if includes_package:
        total += 1
    return total


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
