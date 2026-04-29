from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from msrt.models import Chapter
from msrt.package.cbz import package_cbz
from msrt.package.pdf import package_pdf


def _write_page(path: Path) -> None:
    Image.new("RGB", (80, 120), "white").save(path)


def test_package_cbz_writes_explicit_order_and_comicinfo(tmp_path: Path) -> None:
    image_dir = tmp_path / "pages"
    image_dir.mkdir()
    paths = [image_dir / "1.png", image_dir / "2.png", image_dir / "10.png"]
    for p in paths:
        _write_page(p)
    # Also drop a stale file that previous runs would have leaked.
    _write_page(image_dir / "stale-old.png")
    chapter = Chapter(series_title="Smoke", chapter_number="1", chapter_title="Pilot")

    output = package_cbz(paths, chapter, tmp_path / "out" / "smoke.cbz")

    with ZipFile(output) as archive:
        assert archive.namelist() == ["0001.png", "0002.png", "0003.png", "ComicInfo.xml"]
        comic_info = archive.read("ComicInfo.xml").decode("utf-8")
    assert "<Series>Smoke</Series>" in comic_info
    assert "<LanguageISO>it</LanguageISO>" in comic_info


def test_package_pdf_writes_file(tmp_path: Path) -> None:
    image_dir = tmp_path / "pages"
    image_dir.mkdir()
    page = image_dir / "1.png"
    _write_page(page)

    output = package_pdf([page], tmp_path / "out" / "smoke.pdf")

    assert output.exists()
    assert output.stat().st_size > 0


def test_package_pdf_rejects_empty_list(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="lista vuota"):
        package_pdf([], tmp_path / "out" / "empty.pdf")


def test_package_cbz_rejects_empty_list(tmp_path: Path) -> None:
    chapter = Chapter(series_title="Smoke", chapter_number="1", chapter_title=None)
    with pytest.raises(ValueError, match="lista vuota"):
        package_cbz([], chapter, tmp_path / "out" / "empty.cbz")
