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
