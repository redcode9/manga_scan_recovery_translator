"""Interactive first-run setup wizard for msrt."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import typer
from dotenv import dotenv_values
from rich.console import Console

from msrt.config import MODEL_ALIASES, Settings
from msrt.server import (
    LiteLLMUnavailableError,
    find_litellm_binary,
    start_litellm,
)
from msrt.translate.litellm_proxy import run_litellm_paid_smoke


@dataclass(frozen=True)
class ProviderChoice:
    provider: str
    label: str
    alias: str
    env_var: str
    signup_url: str


PROVIDER_CATALOG: tuple[ProviderChoice, ...] = (
    ProviderChoice(
        provider="openai",
        label="OpenAI (consigliato per il prossimo E2E)",
        alias="gpt",
        env_var="OPENAI_API_KEY",
        signup_url="https://platform.openai.com/api-keys",
    ),
    ProviderChoice(
        provider="anthropic",
        label="Anthropic Claude",
        alias="sonnet",
        env_var="ANTHROPIC_API_KEY",
        signup_url="https://console.anthropic.com/",
    ),
    ProviderChoice(
        provider="google",
        label="Google Gemini",
        alias="gemini-pro",
        env_var="GEMINI_API_KEY",
        signup_url="https://aistudio.google.com/apikey",
    ),
)


def load_env(path: Path) -> dict[str, str]:
    """Load `.env` values via python-dotenv, returning only non-empty entries."""

    if not path.exists():
        return {}
    return {key: value for key, value in dotenv_values(path).items() if value is not None}


def save_env(path: Path, values: dict[str, str]) -> None:
    """Update `.env` in place, preserving comments and untouched keys.

    New keys are appended at the end. Values containing whitespace, comment
    chars, quotes or shell metacharacters are double-quoted with escapes.
    """

    existing_lines: list[str] = (
        path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    )
    seen: set[str] = set()
    out: list[str] = []
    for raw in existing_lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(raw)
            continue
        key = stripped.partition("=")[0].strip()
        if key in values:
            out.append(f"{key}={_format_value(values[key])}")
            seen.add(key)
        else:
            out.append(raw)
    for key, value in values.items():
        if key not in seen:
            out.append(f"{key}={_format_value(value)}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _format_value(value: str) -> str:
    """Quote `.env` value if it would not survive shell-style parsing."""

    if value == "":
        return value
    needs_quote = any(c in value for c in (" ", "\t", "#", "$", "'", '"', "\n", "\r"))
    if not needs_quote:
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _apply_env_to_process(values: dict[str, str]) -> None:
    for key, value in values.items():
        if value:
            os.environ[key] = value


def run_setup(
    *,
    project_root: Path,
    yes: bool = False,
    install_mitr: bool = True,
    start_server: bool = True,
    paid_smoke: bool = False,
    console: Console | None = None,
) -> int:
    """Drive the interactive setup. Returns exit code (0 success, 1 failure)."""

    cons = console or Console()
    cons.rule("[bold cyan]msrt setup[/bold cyan]")

    env_path = project_root / ".env"
    env_template = project_root / ".env.example"

    if not _check_prereqs(cons):
        return 1

    env_values = _ensure_env_file(cons, env_path, env_template, yes=yes)
    provider = _choose_provider(cons, env_values, yes=yes)
    cons.print(
        f"\n[bold]Provider scelto:[/bold] {provider.label} "
        f"(alias [bold]{provider.alias}[/bold], env [bold]{provider.env_var}[/bold])."
    )

    new_values: dict[str, str] = {}
    if env_values.get("MSRT_MODEL") != provider.alias:
        new_values["MSRT_MODEL"] = provider.alias

    api_key_value = _prompt_for_api_key(cons, provider, env_values, yes=yes)
    if api_key_value is not None:
        new_values[provider.env_var] = api_key_value

    if install_mitr:
        mitr_value = _maybe_install_mitr(cons, project_root, env_values, yes=yes)
        if mitr_value:
            new_values["MITR_BIN_PATH"] = mitr_value

    if new_values:
        merged = {**env_values, **new_values}
        save_env(env_path, merged)
        env_values = merged
        keys = ", ".join(new_values)
        cons.print(f"[green]Salvato[/green] {env_path} ({keys}).")

    _apply_env_to_process(env_values)

    if start_server:
        _maybe_start_server(cons, project_root)

    paid_smoke_ok = True
    if paid_smoke:
        paid_smoke_ok = _maybe_paid_smoke(cons, provider.alias, yes=yes)

    _print_next_steps(cons, provider, completed=paid_smoke_ok)
    return 0 if paid_smoke_ok else 1


def _check_prereqs(cons: Console) -> bool:
    if shutil.which("uv") is None:
        cons.print("[red]✗[/red] uv non trovato. Installa uv: https://docs.astral.sh/uv/")
        return False
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 11) or (major, minor) >= (3, 13):
        cons.print(f"[red]✗[/red] Python {major}.{minor} non supportato; servono 3.11/3.12.")
        return False
    cons.print(f"[green]✓[/green] uv presente, Python {major}.{minor}.")
    return True


def _ensure_env_file(
    cons: Console,
    env_path: Path,
    template_path: Path,
    *,
    yes: bool,
) -> dict[str, str]:
    if env_path.exists():
        cons.print(f"[green]✓[/green] {env_path} già presente.")
        return load_env(env_path)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if template_path.exists() and (
        yes or typer.confirm(f"{env_path} non esiste. Copio da {template_path.name}?", default=True)
    ):
        shutil.copyfile(template_path, env_path)
        cons.print(f"[green]✓[/green] Creato {env_path} dal template.")
        return load_env(env_path)
    env_path.write_text("", encoding="utf-8")
    cons.print(f"[green]✓[/green] Creato {env_path} vuoto.")
    return {}


def _choose_provider(
    cons: Console,
    env_values: dict[str, str],
    *,
    yes: bool,
) -> ProviderChoice:
    existing_provider = _provider_from_env(env_values)
    cons.print("\nProvider LLM disponibili:")
    for index, p in enumerate(PROVIDER_CATALOG, start=1):
        marker = (
            "[green]✓ chiave presente[/green]"
            if env_values.get(p.env_var)
            else "[dim]chiave assente[/dim]"
        )
        configured = " [cyan](MSRT_MODEL)[/cyan]" if p == existing_provider else ""
        cons.print(
            f"  {index}) {p.label}  "
            f"alias [bold]{p.alias}[/bold]  env [bold]{p.env_var}[/bold]  ({marker})"
            f"{configured}"
        )
    if yes:
        return existing_provider or PROVIDER_CATALOG[0]
    default_index = str(PROVIDER_CATALOG.index(existing_provider) + 1) if existing_provider else "1"
    while True:
        raw = typer.prompt("Scegli provider (1-3)", default=default_index)
        try:
            idx = int(raw)
            if 1 <= idx <= len(PROVIDER_CATALOG):
                return PROVIDER_CATALOG[idx - 1]
        except ValueError:
            pass
        cons.print(f"[red]Scelta non valida: {raw}[/red]")


def _provider_from_env(env_values: dict[str, str]) -> ProviderChoice | None:
    model = env_values.get("MSRT_MODEL")
    if not model:
        return None
    return provider_alias_lookup().get(model)


def _prompt_for_api_key(
    cons: Console,
    provider: ProviderChoice,
    env_values: dict[str, str],
    *,
    yes: bool,
) -> str | None:
    existing = env_values.get(provider.env_var, "")
    if existing:
        if yes:
            cons.print(f"[green]✓[/green] {provider.env_var} già presente; mantengo (--yes).")
            return None
        if not typer.confirm(
            f"{provider.env_var} già presente. Sostituire?",
            default=False,
        ):
            cons.print(f"[green]✓[/green] {provider.env_var} mantenuto.")
            return None
    cons.print(f"Crea/recupera la chiave qui: {provider.signup_url}")
    if yes:
        cons.print(
            "[yellow]--yes attivo: chiave non impostata (vuota) finché non la inserisci.[/yellow]"
        )
        return None
    value: str = typer.prompt(
        f"Incolla {provider.env_var}",
        hide_input=True,
        default="",
        show_default=False,
    )
    cleaned: str = value.strip()
    if not cleaned:
        cons.print("[yellow]Nessuna chiave fornita; salto.[/yellow]")
        return None
    return cleaned


def _maybe_install_mitr(
    cons: Console,
    project_root: Path,
    env_values: dict[str, str],
    *,
    yes: bool,
) -> str | None:
    existing = env_values.get("MITR_BIN_PATH", "")
    if existing:
        if yes:
            cons.print(
                f"[green]✓[/green] MITR_BIN_PATH già impostato ({existing}); mantengo (--yes)."
            )
            return None
        if not typer.confirm(
            f"MITR_BIN_PATH già impostato ({existing}). Reinstallare MITR?",
            default=False,
        ):
            return None

    script = project_root / "scripts" / "install-mitr.sh"
    if not script.exists():
        cons.print(f"[red]✗[/red] Script non trovato: {script}")
        return None

    default_prefix = Path.home() / "tools" / "mitr"
    if yes:
        prefix = default_prefix
    else:
        if not typer.confirm(
            f"Eseguo {script.name} per installare MITR (~5 min, scarica torch)?",
            default=True,
        ):
            cons.print("[yellow]Skip install MITR.[/yellow]")
            return None
        raw_prefix = typer.prompt("Prefix MITR", default=str(default_prefix))
        prefix = Path(raw_prefix).expanduser()

    cons.print(f"[bold]Eseguo[/bold] {script} --prefix {prefix}")
    try:
        subprocess.run(
            ["bash", str(script), "--prefix", str(prefix)],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        cons.print(f"[red]✗[/red] Install MITR fallito (exit {exc.returncode}).")
        return None
    except FileNotFoundError:
        cons.print("[red]✗[/red] bash non trovato; impossibile eseguire lo script.")
        return None

    mitr_python = prefix / ".venv" / "bin" / "python"
    if not mitr_python.exists():
        cons.print(f"[red]✗[/red] Python venv MITR non trovato: {mitr_python}")
        return None
    return f"{mitr_python} -m manga_translator"


def _maybe_start_server(cons: Console, project_root: Path) -> None:
    settings = Settings()
    config = project_root / "configs" / "litellm.yaml"
    if find_litellm_binary() is None:
        cons.print("[yellow]![/yellow] Binary 'litellm' assente; esegui `uv sync --all-extras`.")
        return
    try:
        status = start_litellm(settings, config, wait_seconds=45.0)
    except (LiteLLMUnavailableError, FileNotFoundError, RuntimeError) as exc:
        cons.print(f"[red]✗[/red] Avvio LiteLLM fallito: {exc}")
        return
    icon = "[green]✓[/green]" if status.healthy else "[yellow]![/yellow]"
    cons.print(f"{icon} LiteLLM PID {status.pid}: {status.message}")


def _maybe_paid_smoke(cons: Console, alias: str, *, yes: bool) -> bool:
    if not yes:
        cons.print(
            "\n[bold]Paid smoke[/bold]: invia una chiamata reale al provider tramite LiteLLM "
            "(consuma una manciata di token)."
        )
        if not typer.confirm("Procedo con la chiamata paid?", default=False):
            cons.print("[yellow]Paid smoke saltato.[/yellow]")
            return True
    settings = Settings()
    smoke = run_litellm_paid_smoke(settings, model=alias)
    if smoke.ok:
        cons.print(f"[green]✓[/green] {smoke.message}")
        return True
    else:
        cons.print(f"[red]✗[/red] {smoke.message}")
        return False


def _print_next_steps(cons: Console, provider: ProviderChoice, *, completed: bool = True) -> None:
    if completed:
        cons.rule("[bold green]Setup completato[/bold green]")
    else:
        cons.rule("[bold yellow]Setup completato con verifica fallita[/bold yellow]")
        cons.print(
            "[yellow]Correggi la chiave/provider o il proxy LiteLLM, poi rilancia "
            "`msrt doctor --paid-smoke`.[/yellow]"
        )
    cons.print(
        "\nProssimi comandi suggeriti:\n"
        "  [bold]msrt doctor[/bold]  [dim]# usa MSRT_MODEL dal .env[/dim]\n"
        "  [bold]msrt run-local ./pages-test --format pdf "
        "--series 'Esempio' --chapter '1'[/bold]"
    )
    cons.print(
        "\nIl prossimo target è il primo E2E reale; quando funziona possiamo passare "
        "all'adapter MangaDex (v0.2)."
    )


def provider_alias_lookup() -> dict[str, ProviderChoice]:
    """Helper for tests / CLI: alias → ProviderChoice (excludes legacy aliases)."""

    return {choice.alias: choice for choice in PROVIDER_CATALOG}


# Sanity at import time: ogni alias del catalogo deve esistere nel registry config.
for _choice in PROVIDER_CATALOG:
    if _choice.alias not in MODEL_ALIASES:  # pragma: no cover - defensive
        raise RuntimeError(f"Provider alias mismatch: {_choice.alias} non in MODEL_ALIASES")
