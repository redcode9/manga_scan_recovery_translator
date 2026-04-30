from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from msrt.scrape.browser_capture import (
    BrowserCaptureOptions,
    ElementCandidate,
    _write_capture_bytes,
    choose_scan_candidate,
    looks_like_human_check,
    parse_page_progress,
)


def _png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_parse_page_progress_from_reader_label() -> None:
    assert parse_page_progress("Chapter 51/63   Page 1/45") == (1, 45)
    assert parse_page_progress("Page 45 / 45") == (45, 45)
    assert parse_page_progress("Page 99/45") is None


def test_looks_like_human_check_detects_challenge_text() -> None:
    assert looks_like_human_check("Checking your browser before accessing MangaFire")
    assert looks_like_human_check("Please complete the Turnstile challenge")
    assert not looks_like_human_check("Page 1/45 Wistoria Wand and Sword")


def test_choose_scan_candidate_prefers_large_visible_manga_page() -> None:
    options = BrowserCaptureOptions(min_width=400, min_height=600)
    candidates = [
        ElementCandidate(
            index=0,
            kind="img",
            url="https://example.com/logo.png",
            x=0,
            y=0,
            width=120,
            height=80,
            natural_width=120,
            natural_height=80,
        ),
        ElementCandidate(
            index=1,
            kind="img",
            url="https://example.com/page.png",
            x=450,
            y=0,
            width=720,
            height=1080,
            natural_width=1440,
            natural_height=2160,
        ),
        ElementCandidate(
            index=2,
            kind="img",
            url="https://example.com/sidebar.png",
            x=1600,
            y=0,
            width=300,
            height=900,
            natural_width=300,
            natural_height=900,
        ),
    ]

    chosen = choose_scan_candidate(candidates, options)

    assert chosen is not None
    assert chosen.index == 1
    assert chosen.url == "https://example.com/page.png"


def test_write_capture_bytes_validates_magic_and_names_pages(tmp_path: Path) -> None:
    page = _write_capture_bytes(
        _png_bytes(),
        output_dir=tmp_path,
        index=3,
        source_url="https://example.com/page.png",
        capture_mode="browser-raw",
    )

    assert page.local_path.name == "003.png"
    assert page.local_path.exists()
    assert page.sha256.startswith("sha256:")
    assert page.capture_mode == "browser-raw"
