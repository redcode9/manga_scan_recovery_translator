from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from msrt.models import Chapter
from msrt.package.cbz import package_cbz
from msrt.package.pdf import package_pdf


def _write_page(path: Path) -> None:
    Image.new("RGB", (80, 120), "white").save(path)


def test_package_cbz_writes_natural_order_and_comicinfo(tmp_path: Path) -> None:
    image_dir = tmp_path / "pages"
    image_dir.mkdir()
    _write_page(image_dir / "10.png")
    _write_page(image_dir / "1.png")
    _write_page(image_dir / "2.png")
    chapter = Chapter(series_title="Smoke", chapter_number="1", chapter_title="Pilot")

    output = package_cbz(image_dir, chapter, tmp_path / "out" / "smoke.cbz")

    with ZipFile(output) as archive:
        assert archive.namelist() == ["0001.png", "0002.png", "0003.png", "ComicInfo.xml"]
        comic_info = archive.read("ComicInfo.xml").decode("utf-8")
    assert "<Series>Smoke</Series>" in comic_info
    assert "<LanguageISO>it</LanguageISO>" in comic_info


def test_package_pdf_writes_file(tmp_path: Path) -> None:
    image_dir = tmp_path / "pages"
    image_dir.mkdir()
    _write_page(image_dir / "1.png")

    output = package_pdf(image_dir, tmp_path / "out" / "smoke.pdf")

    assert output.exists()
    assert output.stat().st_size > 0
