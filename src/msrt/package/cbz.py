"""CBZ packaging."""

from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile

from msrt.models import Chapter
from msrt.package.naming import image_files


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


def package_cbz(image_dir: Path, chapter: Chapter, output_file: Path) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    order = image_files(image_dir)
    if not order.files:
        raise ValueError(f"Nessuna immagine da inserire nel CBZ: {image_dir}")

    with ZipFile(output_file, "w", compression=ZIP_DEFLATED) as archive:
        for index, image_path in enumerate(order.files, start=1):
            archive.write(image_path, f"{index:04d}{image_path.suffix.lower()}")
        archive.writestr("ComicInfo.xml", write_comic_info(chapter))
    return output_file
