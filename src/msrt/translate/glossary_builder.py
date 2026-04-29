"""LLM-driven auto-generation of series glossaries.

The flow is intentionally minimal for v0.1.aa:

1. Send a single chat-completion request to the local LiteLLM proxy with a
   structured prompt asking for a TSV of canonical proper nouns.
2. Parse the TSV response into a ``dict[str, str]``.
3. Persist it under the user cache directory so subsequent runs of the
   same series reuse the same glossary without another LLM call.

Hallucinations are an inherent limit of this approach. The glossary file
is plain TSV, so the user can edit it manually after a build to remove
wrong entries or add ones the LLM missed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from msrt.config import Settings

GLOSSARY_SUBDIR = "glossaries"
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_TSV_ROWS = 30

_SYSTEM_PROMPT = (
    "You are a manga reference assistant. Given the title of a manga series, "
    "you output a glossary of proper nouns that should be preserved consistently "
    "when translating from English to Italian.\n\n"
    "Include: main and recurring character names, places, organisations, "
    "magic systems, races, and other recurring terminology that an OCR pipeline "
    "is likely to misread.\n\n"
    "Output strictly as TSV (tab-separated, one entry per line). The first "
    "column is the canonical English form (as it appears in official EN "
    "scanlations or releases). The second column is the Italian translation; "
    "if the term should not be translated (most names usually shouldn't), "
    "repeat the English form unchanged.\n\n"
    f"Output AT MOST {MAX_TSV_ROWS} entries, prioritising terms most likely to "
    "appear in any chapter. Do NOT include headers, explanations, markdown "
    "fences, or any text outside the TSV body. If you do not know the series, "
    "output a single line with two empty fields separated by a tab."
)


class GlossaryBuildError(RuntimeError):
    """Raised when the LLM call or response parsing fails."""


@dataclass(frozen=True)
class GlossaryBuildResult:
    entries: dict[str, str]
    raw_response: str
    model: str
    tokens_in: int | None
    tokens_out: int | None


def slugify_series(series: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", series.strip().lower())
    return slug.strip("-") or "untitled"


def cached_glossary_path(series: str, settings: Settings) -> Path:
    """Return the canonical cache path for a given series title."""

    return settings.cache_dir / GLOSSARY_SUBDIR / f"{slugify_series(series)}.tsv"


def save_glossary(path: Path, entries: dict[str, str]) -> Path:
    """Persist a glossary as TSV. Empty entries are skipped silently."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# msrt auto-generated glossary — edit freely (TSV: source<TAB>target)"]
    for source, target in sorted(entries.items()):
        if not source or not target:
            continue
        lines.append(f"{source}\t{target}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


_MD_TABLE_HEADER_TOKENS = frozenset(
    {
        "source",
        "target",
        "english",
        "italian",
        "en",
        "it",
        "term",
        "translation",
        "name",
        "original",
    }
)
_MD_TABLE_SEPARATOR_RE = re.compile(r"^[\s:|*-]+$")


def parse_glossary_tsv(raw: str) -> dict[str, str]:
    """Best-effort TSV parser for the LLM response.

    Tolerates Markdown code fences, leading "1." numbering, Markdown
    tables (header row + separator row + body rows), and extra
    whitespace. Drops empty rows and rows where either side is blank.
    """

    entries: dict[str, str] = {}
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("```"):
            continue
        if line.startswith("#"):
            continue
        # Markdown table separator rows (``| --- | --- |``) — drop early.
        if _MD_TABLE_SEPARATOR_RE.match(line):
            continue
        # Drop leading numbering like "1." or "12)".
        line = re.sub(r"^\s*\d+[.)]\s*", "", line)
        if "\t" in line:
            source, _, target = line.partition("\t")
        elif "|" in line:
            # Some models emit Markdown tables; tolerate them.
            parts = [piece.strip() for piece in line.split("|") if piece.strip()]
            if len(parts) < 2:
                continue
            source, target = parts[0], parts[1]
        elif "=>" in line:
            source, _, target = line.partition("=>")
        else:
            continue
        source = source.strip().strip("`*")
        target = target.strip().strip("`*")
        if not source or not target:
            continue
        # Skip Markdown table header rows like ``Source | Target``.
        if source.lower() in _MD_TABLE_HEADER_TOKENS and target.lower() in _MD_TABLE_HEADER_TOKENS:
            continue
        entries[source] = target
    return entries


def build_glossary_via_llm(
    series: str,
    *,
    model: str,
    settings: Settings,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> GlossaryBuildResult:
    """Call the local LiteLLM proxy and return the parsed glossary.

    Raises ``GlossaryBuildError`` if the proxy is unreachable, returns an
    HTTP error, or the response cannot be parsed into at least one entry.
    """

    url = f"{settings.litellm_base_url}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Series: {series}\n\nOutput the glossary now:"},
        ],
    }
    headers = {"Authorization": "Bearer msrt-local-litellm"}

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        raise GlossaryBuildError(
            f"LiteLLM non raggiungibile su {url}: {exc}. Avvia 'msrt server up'."
        ) from exc

    if response.status_code >= 400:
        snippet = response.text[:300] if response.text else "(empty body)"
        raise GlossaryBuildError(f"LiteLLM ha risposto HTTP {response.status_code}: {snippet}")

    try:
        data = response.json()
    except ValueError as exc:
        raise GlossaryBuildError("Risposta non JSON dal proxy LiteLLM.") from exc

    raw = _extract_message_content(data)
    entries = parse_glossary_tsv(raw)
    if not entries:
        raise GlossaryBuildError(
            "Il modello non ha prodotto voci di glossario interpretabili. "
            f"Risposta grezza:\n{raw[:500]}"
        )

    usage = data.get("usage") or {}
    return GlossaryBuildResult(
        entries=entries,
        raw_response=raw,
        model=model,
        tokens_in=_int_or_none(usage.get("prompt_tokens")),
        tokens_out=_int_or_none(usage.get("completion_tokens")),
    )


def _extract_message_content(data: dict[str, object]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GlossaryBuildError("Risposta proxy senza 'choices' valido.")
    first = choices[0]
    if not isinstance(first, dict):
        raise GlossaryBuildError("Primo 'choice' non è un oggetto.")
    message = first.get("message")
    if not isinstance(message, dict):
        raise GlossaryBuildError("'choices[0].message' non è un oggetto.")
    content = message.get("content")
    if not isinstance(content, str):
        raise GlossaryBuildError("'choices[0].message.content' non è una stringa.")
    return content


def _int_or_none(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None
