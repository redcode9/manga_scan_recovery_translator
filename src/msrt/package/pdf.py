"""PDF packaging with img2pdf."""

from __future__ import annotations

from pathlib import Path

import img2pdf

from msrt.package.naming import image_files


def package_pdf(image_dir: Path, output_file: Path) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    order = image_files(image_dir)
    if not order.files:
        raise ValueError(f"Nessuna immagine da inserire nel PDF: {image_dir}")

    with output_file.open("wb") as pdf_file:
        pdf_file.write(img2pdf.convert([str(path) for path in order.files]))
    return output_file
