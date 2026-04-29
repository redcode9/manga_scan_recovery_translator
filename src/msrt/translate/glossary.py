"""Glossary loading and prompt injection."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from msrt.config import Settings
from msrt.translate.glossary_builder import (
    GlossaryBuildResult,
    build_glossary_via_llm,
    cached_glossary_path,
    save_glossary,
)


def load_glossary(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    entries: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            source, target = line.split("\t", 1)
        elif "," in line:
            source, target = line.split(",", 1)
        else:
            continue
        entries[source.strip()] = target.strip()
    return entries


def format_glossary(entries: dict[str, str]) -> str:
    if not entries:
        return "(none — no series-specific terminology)"
    return "\n".join(f"- {source} => {target}" for source, target in sorted(entries.items()))


def inject_glossary(template: str, entries: dict[str, str]) -> str:
    """Replace the literal ``{glossary}`` placeholder with the formatted entries.

    The substitution preserves the indentation of the line that contains
    the placeholder. This matters for YAML block scalars (``|``): if a
    multi-line replacement starts at column 0 while the surrounding text
    is indented at column 2, the YAML parser treats the dedented line as
    the end of the block and raises ``ParserError``.

    ``str.replace`` is used (rather than ``str.format``) so that other
    braces — notably ``{to_lang}``, which MITR substitutes later via
    ``str.format`` — survive untouched.
    """

    formatted = format_glossary(entries)
    if "{glossary}" not in template:
        return template

    out_lines: list[str] = []
    for raw_line in template.splitlines(keepends=True):
        if "{glossary}" not in raw_line:
            out_lines.append(raw_line)
            continue
        prefix_idx = raw_line.index("{glossary}")
        indent = raw_line[:prefix_idx]
        # Only re-indent when the prefix is pure whitespace; if it isn't
        # (e.g. ``Glossary: {glossary}`` inline), don't add indent — the
        # surrounding context isn't a YAML block scalar.
        if indent.strip():
            out_lines.append(raw_line.replace("{glossary}", formatted))
            continue
        first, *rest = formatted.split("\n")
        indented = first + ("\n" + "\n".join(indent + line for line in rest) if rest else "")
        out_lines.append(raw_line.replace("{glossary}", indented))
    return "".join(out_lines)


BuildLogger = Callable[[str], None]


def _noop_log(_: str) -> None:
    return None


def load_or_build_glossary(
    series: str,
    *,
    model: str,
    settings: Settings,
    force_rebuild: bool = False,
    log: BuildLogger | None = None,
) -> tuple[Path, dict[str, str], GlossaryBuildResult | None]:
    """Return the cached glossary path and entries for a series, building
    via the LLM if the cache is missing.

    The third tuple element is the raw build result if a fresh build was
    performed, otherwise ``None`` (cache hit). Callers can use it to
    surface token usage to the user.

    Build failures are not silenced: ``GlossaryBuildError`` propagates so
    the pipeline can decide whether to abort or proceed without glossary.
    """

    log_fn = log or _noop_log
    cache_path = cached_glossary_path(series, settings)
    if cache_path.exists() and not force_rebuild:
        log_fn(f"Uso glossario in cache: {cache_path}")
        return cache_path, load_glossary(cache_path), None

    log_fn(
        f"Glossario per '{series}' non in cache. Lo costruisco con il modello "
        f"'{model}' (1 chiamata LLM)..."
    )
    result = build_glossary_via_llm(series, model=model, settings=settings)
    save_glossary(cache_path, result.entries)
    log_fn(
        f"Glossario salvato in {cache_path} ({len(result.entries)} voci, "
        f"{result.tokens_in or '?'} token in / {result.tokens_out or '?'} token out)."
    )
    return cache_path, result.entries, result


def build_gpt_config_with_glossary(
    base_config: Path, entries: dict[str, str], target_dir: Path | None = None
) -> Path:
    """Materialise a gpt_config YAML with glossary substituted in.

    Reads ``base_config`` as text (no YAML parse — we only swap a literal
    placeholder), substitutes ``{glossary}`` with formatted entries, and
    writes the result to a temp ``.yaml`` file under ``target_dir`` (or
    the system temp dir). Returns the temp file path; the caller owns
    its lifetime and is expected to ``unlink`` it when done.

    The base file must already include a ``{glossary}`` token in its
    ``chat_system_template`` section. If the placeholder is absent the
    function still copies the base file verbatim so behaviour degrades
    safely.
    """

    raw = base_config.read_text(encoding="utf-8")
    rendered = inject_glossary(raw, entries)
    target_dir_resolved = target_dir if target_dir is not None else Path(tempfile.gettempdir())
    target_dir_resolved.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        prefix="msrt-gpt-config-", suffix=".yaml", dir=str(target_dir_resolved)
    )
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)
