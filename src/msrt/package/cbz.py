"""CBZ packaging."""

from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile

from msrt.models import Chapter


def write_comic_info(chapter: Chapter) -> bytes:
    root = Element("ComicInfo")
    fields = {
        "Series": chapter.series_title,
        "Number": chapter.chapter_number,
        "Title": chapter.chapter_title or "",
        "LanguageISO": chapter.language_target,
    }
    fields.update(chapter.metadata)
    for key, value in fields.items():
        if value:
            child = SubElement(root, key)
            child.text = value
    xml_bytes = tostring(root, encoding="utf-8", xml_declaration=True)
    if not isinstance(xml_bytes, bytes):
        raise TypeError("ComicInfo.xml serialization returned text unexpectedly")
    return xml_bytes


def package_cbz(files: list[Path], chapter: Chapter, output_file: Path) -> Path:
    """Bundle the given image files into a CBZ + ComicInfo.xml.

    The caller provides the ordered list of pages; we no longer scan a
    directory because that risks pulling in stale files from previous
    chapters.
    """

    if not files:
        raise ValueError("Nessuna immagine da inserire nel CBZ (lista vuota).")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_file, "w", compression=ZIP_DEFLATED) as archive:
        for index, image_path in enumerate(files, start=1):
            archive.write(image_path, f"{index:04d}{image_path.suffix.lower()}")
        archive.writestr("ComicInfo.xml", write_comic_info(chapter))
    return output_file
