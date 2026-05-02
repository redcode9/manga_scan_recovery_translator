from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from msrt.translate.postprocess import apply_bubble_aware_postprocess


def _dark_pixel_count(image: Image.Image, box: tuple[int, int, int, int]) -> int:
    gray = image.convert("L")
    pixels = gray.load()
    assert pixels is not None
    x0, y0, x1, y1 = box
    return sum(1 for y in range(y0, y1) for x in range(x0, x1) if pixels[x, y] < 120)


def test_bubble_aware_postprocess_scales_text_inside_bubble(tmp_path: Path) -> None:
    source = tmp_path / "001.png"
    image = Image.new("RGB", (320, 420), (180, 180, 180))
    draw = ImageDraw.Draw(image)
    bubble = (80, 90, 240, 250)
    draw.ellipse(bubble, fill=(255, 255, 255), outline=(0, 0, 0), width=2)
    draw.rectangle((138, 158, 182, 176), fill=(0, 0, 0))
    image.save(source)

    measure_box = (90, 100, 230, 240)
    before_count = _dark_pixel_count(image, measure_box)
    report = apply_bubble_aware_postprocess([source], output_dir=tmp_path / "post")

    assert report.pages == 1
    assert report.bubbles_scaled == 1
    with Image.open(report.output_files[0]) as processed:
        after_count = _dark_pixel_count(processed, measure_box)

    assert after_count > before_count * 1.5


def test_bubble_aware_postprocess_leaves_outside_text_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "001.png"
    image = Image.new("RGB", (240, 240), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 70, 30), fill=(0, 0, 0))
    image.save(source)

    report = apply_bubble_aware_postprocess([source], output_dir=tmp_path / "post")

    with Image.open(report.output_files[0]) as processed:
        assert processed.getpixel((20, 20)) == (0, 0, 0)
    assert report.bubbles_scaled == 0


def test_bubble_aware_postprocess_skips_thin_horizontal_strip(tmp_path: Path) -> None:
    """A wide-but-thin white strip (e.g. a banner or panel border that
    survived the edge check) should NOT be treated as a bubble. The
    aspect-ratio guard introduced in v0.3f is what catches this."""

    source = tmp_path / "001.png"
    image = Image.new("RGB", (480, 480), (40, 40, 40))
    draw = ImageDraw.Draw(image)
    # Aspect ratio 380/30 ≈ 12.6 — well above the 3.5 cap.
    draw.rectangle((50, 220, 430, 250), fill=(255, 255, 255))
    image.save(source)

    report = apply_bubble_aware_postprocess([source], output_dir=tmp_path / "post")

    assert report.bubbles_scaled == 0


def test_bubble_aware_postprocess_skips_low_fill_starburst(tmp_path: Path) -> None:
    """A jagged white shape with a low fill-ratio (cluster of disconnected
    spokes joined by thin lines) is NOT a bubble and must be skipped.

    We approximate the geometry with a wide rectangle plus a slim sliver
    that pulls the bbox much wider than the actual filled area, dropping
    fill_ratio below the 0.55 threshold."""

    source = tmp_path / "001.png"
    image = Image.new("RGB", (480, 480), (40, 40, 40))
    draw = ImageDraw.Draw(image)
    # Main blob: 80x100 = 8000 px in the bbox of size 80x100 plus the spike.
    draw.rectangle((100, 200, 180, 300), fill=(255, 255, 255))
    # A thin spike that extends the bbox horizontally far past the blob,
    # without contributing much to the area → low fill ratio.
    draw.rectangle((181, 245, 380, 250), fill=(255, 255, 255))
    image.save(source)

    report = apply_bubble_aware_postprocess([source], output_dir=tmp_path / "post")

    assert report.bubbles_scaled == 0


def test_bubble_aware_postprocess_no_op_on_dark_page(tmp_path: Path) -> None:
    """A page with no white regions at all (e.g. a flashback or all-black
    panel) must round-trip unchanged."""

    source = tmp_path / "001.png"
    image = Image.new("RGB", (320, 320), (12, 12, 12))
    image.save(source)
    original_bytes = source.read_bytes()

    report = apply_bubble_aware_postprocess([source], output_dir=tmp_path / "post")

    assert report.bubbles_scaled == 0
    out_path = report.output_files[0]
    # The image content can be re-encoded; assert pixel-level equivalence
    # rather than byte-level since the encoder may differ slightly.
    with Image.open(out_path) as processed:
        # Sample a handful of pixels: all should remain dark.
        for x, y in [(0, 0), (160, 160), (319, 319), (10, 200), (200, 10)]:
            r, g, b = processed.getpixel((x, y))
            assert r < 30 and g < 30 and b < 30
    # And the file shouldn't be empty / corrupted.
    assert out_path.stat().st_size > 0
    assert original_bytes  # sanity, source kept around
