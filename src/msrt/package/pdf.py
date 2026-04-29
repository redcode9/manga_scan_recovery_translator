"""PDF packaging with img2pdf."""

from __future__ import annotations

from pathlib import Path

import img2pdf


def package_pdf(files: list[Path], output_file: Path) -> Path:
    """Bundle the given image files into a PDF, in the order provided.

    The caller is responsible for ordering and for ensuring that every
    entry exists; we no longer scan the parent directory because that
    would let stale files from a previous chapter leak into the output.
    """

    if not files:
        raise ValueError("Nessuna immagine da inserire nel PDF (lista vuota).")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("wb") as pdf_file:
        pdf_file.write(img2pdf.convert([str(path) for path in files]))
    return output_file
