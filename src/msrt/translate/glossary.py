"""Glossary loading and prompt injection."""

from __future__ import annotations

from pathlib import Path


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
        return "- No glossary entries."
    return "\n".join(f"- {source} => {target}" for source, target in sorted(entries.items()))


def inject_glossary(template: str, entries: dict[str, str]) -> str:
    return template.replace("{glossary}", format_glossary(entries))
