from __future__ import annotations

from pathlib import Path

from msrt.translate.glossary import (
    build_gpt_config_with_glossary,
    format_glossary,
    inject_glossary,
    load_glossary,
)


def test_load_glossary_supports_tsv_and_csv(tmp_path: Path) -> None:
    path = tmp_path / "glossary.txt"
    path.write_text(
        "# comment line\nEmma\tEmma\nBelledors,Belledors\n  Iemma\tEmma  \n\n",
        encoding="utf-8",
    )

    entries = load_glossary(path)

    assert entries == {"Emma": "Emma", "Belledors": "Belledors", "Iemma": "Emma"}


def test_load_glossary_returns_empty_when_path_is_none() -> None:
    assert load_glossary(None) == {}


def test_format_glossary_marks_empty_explicitly() -> None:
    assert "(none" in format_glossary({})


def test_inject_glossary_preserves_to_lang_placeholder() -> None:
    template = "Use this glossary:\n{glossary}\nTranslate into {to_lang}."

    rendered = inject_glossary(template, {"Emma": "Emma"})

    assert "{to_lang}" in rendered
    assert "{glossary}" not in rendered
    assert "- Emma => Emma" in rendered


def test_inject_glossary_preserves_block_scalar_indentation() -> None:
    """Regression: substituting a multi-line glossary inside a YAML block
    scalar must keep every line indented to the same column as the
    placeholder, otherwise the YAML parser raises ParserError because
    the dedented line is read as the end of the block."""

    import yaml

    template = (
        "chat_system_template: |\n"
        "  Header line\n"
        "  Glossary:\n"
        "  {glossary}\n"
        "\n"
        "  Footer line {to_lang}\n"
    )
    rendered = inject_glossary(
        template,
        {"Emma": "Emma", "Will": "Will", "Sion": "Sion"},
    )

    # Must parse as valid YAML.
    parsed = yaml.safe_load(rendered)
    assert isinstance(parsed, dict)
    body = parsed["chat_system_template"]
    assert "- Emma => Emma" in body
    assert "- Will => Will" in body
    assert "- Sion => Sion" in body
    # The placeholder must be gone but {to_lang} preserved for MITR.
    assert "{glossary}" not in body
    assert "{to_lang}" in body
    # Every line of the substituted glossary must keep the original two-space
    # indent in the rendered file (raw text check, before YAML parsing strips it).
    for line in rendered.splitlines():
        if line.lstrip().startswith("- "):
            assert line.startswith("  "), f"Lost indent on line: {line!r}"


def test_build_gpt_config_with_glossary_substitutes_placeholder(tmp_path: Path) -> None:
    base = tmp_path / "base.yaml"
    base.write_text(
        "temperature: 1\nchat_system_template: |\n  Glossary:\n  {glossary}\n  Lang: {to_lang}\n",
        encoding="utf-8",
    )

    rendered = build_gpt_config_with_glossary(
        base_config=base,
        entries={"Emma": "Emma"},
        target_dir=tmp_path / "tmp",
    )

    try:
        contents = rendered.read_text(encoding="utf-8")
        assert rendered.suffix == ".yaml"
        assert rendered.parent == tmp_path / "tmp"
        assert "- Emma => Emma" in contents
        assert "{to_lang}" in contents  # untouched, MITR will substitute later
        assert "{glossary}" not in contents
    finally:
        rendered.unlink(missing_ok=True)


def test_build_gpt_config_with_no_entries_inserts_none_marker(tmp_path: Path) -> None:
    base = tmp_path / "base.yaml"
    base.write_text("a: 1\n# {glossary}\n", encoding="utf-8")

    rendered = build_gpt_config_with_glossary(base_config=base, entries={}, target_dir=tmp_path)

    try:
        contents = rendered.read_text(encoding="utf-8")
        assert "(none" in contents
        assert "{glossary}" not in contents
    finally:
        rendered.unlink(missing_ok=True)
