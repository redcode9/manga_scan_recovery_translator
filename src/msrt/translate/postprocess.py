"""Image-level postprocessing for translated pages.

This is a pragmatic bridge until we have a stable structured output from
manga-image-translator. It does not attempt full typesetting. Instead it
detects white, enclosed speech-bubble interiors and scales the already
rendered translated text inside those bubbles so it uses more of the
available space. Text outside bubbles is intentionally left untouched.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from PIL import Image, ImageDraw


@dataclass(frozen=True)
class BubblePostprocessReport:
    pages: int
    bubbles_scaled: int
    output_files: list[Path]


@dataclass(frozen=True)
class _Component:
    bbox: tuple[int, int, int, int]
    area: int
    touches_edge: bool


def apply_bubble_aware_postprocess(
    files: list[Path],
    *,
    output_dir: Path,
    min_scale: float = 1.05,
    max_scale: float = 1.85,
) -> BubblePostprocessReport:
    """Copy ``files`` to ``output_dir`` and enlarge text inside bubbles.

    The input files are never modified. Pages without confident speech-bubble
    candidates are copied as-is.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    for old_file in output_dir.iterdir():
        if old_file.is_file() or old_file.is_symlink():
            old_file.unlink()

    output_files: list[Path] = []
    bubbles_scaled = 0
    for source in files:
        target = output_dir / source.name
        try:
            with Image.open(source) as image:
                processed, count = _process_page(image.convert("RGB"), min_scale, max_scale)
                processed.save(target, quality=95)
                bubbles_scaled += count
        except Exception:
            shutil.copy2(source, target)
        output_files.append(target)
    return BubblePostprocessReport(
        pages=len(output_files),
        bubbles_scaled=bubbles_scaled,
        output_files=output_files,
    )


def _process_page(
    image: Image.Image,
    min_scale: float,
    max_scale: float,
) -> tuple[Image.Image, int]:
    processed = image.copy()
    components = _white_components(processed)
    scaled = 0
    for component in components:
        if _scale_text_in_component(processed, component.bbox, min_scale, max_scale):
            scaled += 1
    return processed, scaled


def _white_components(image: Image.Image, *, downscale: int = 4) -> list[_Component]:
    width, height = image.size
    small_size = (max(1, width // downscale), max(1, height // downscale))
    gray = image.convert("L").resize(small_size, Image.Resampling.BOX)
    sw, sh = gray.size
    pixels = gray.tobytes()
    white = bytearray(1 if value >= 244 else 0 for value in pixels)
    visited = bytearray(sw * sh)
    components: list[_Component] = []

    for start in range(sw * sh):
        if visited[start] or not white[start]:
            continue
        stack = [start]
        visited[start] = 1
        min_x = max_x = start % sw
        min_y = max_y = start // sw
        area = 0
        touches_edge = False

        while stack:
            current = stack.pop()
            area += 1
            x = current % sw
            y = current // sw
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            touches_edge = touches_edge or x == 0 or y == 0 or x == sw - 1 or y == sh - 1

            for neighbor in _neighbors(x, y, sw, sh):
                if not visited[neighbor] and white[neighbor]:
                    visited[neighbor] = 1
                    stack.append(neighbor)

        bbox = (
            max(0, min_x * downscale),
            max(0, min_y * downscale),
            min(width, (max_x + 1) * downscale),
            min(height, (max_y + 1) * downscale),
        )
        # ``area`` and the (max_*-min_*) bbox are both in downscaled
        # space, so the fill ratio is a direct number that doesn't
        # depend on the downscale factor.
        small_w = max_x - min_x + 1
        small_h = max_y - min_y + 1
        fill_ratio = area / max(1, small_w * small_h)
        if _is_bubble_candidate(
            bbox,
            area,
            touches_edge,
            width,
            height,
            fill_ratio=fill_ratio,
        ):
            components.append(_Component(bbox=bbox, area=area, touches_edge=touches_edge))

    return sorted(components, key=lambda comp: comp.area, reverse=True)


def _neighbors(x: int, y: int, width: int, height: int) -> tuple[int, ...]:
    values: list[int] = []
    if x > 0:
        values.append(y * width + x - 1)
    if x < width - 1:
        values.append(y * width + x + 1)
    if y > 0:
        values.append((y - 1) * width + x)
    if y < height - 1:
        values.append((y + 1) * width + x)
    return tuple(values)


_MIN_BUBBLE_ASPECT_RATIO = 0.30
_MAX_BUBBLE_ASPECT_RATIO = 3.50
_MIN_BUBBLE_FILL_RATIO = 0.55


def _is_bubble_candidate(
    bbox: tuple[int, int, int, int],
    area: int,
    touches_edge: bool,
    page_width: int,
    page_height: int,
    *,
    fill_ratio: float = 1.0,
) -> bool:
    """Decide whether a connected white blob looks like a manga bubble.

    Tightened in v0.3f with two extra guards that reduce false positives
    on pages without speech bubbles (full-page panels, dark scenes,
    flashbacks with white frames):

    * **aspect ratio** — speech bubbles are roughly oval/squarish; very
      thin strips (banners, page borders that survived the edge check)
      and very tall slivers (gutters between panels) are rejected.
    * **fill ratio** — bubbles fill most of their own bounding box. A
      complex white shape (e.g. a starburst SFX panel, a sparse cluster
      of white pixels) has a low fill ratio and would be a bad target
      for blind text scaling.
    """

    if touches_edge:
        return False
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0
    if width <= 0 or height <= 0:
        return False
    if width * height < 12_000:
        return False
    if width < max(42, int(page_width * 0.045)):
        return False
    if height < max(34, int(page_height * 0.025)):
        return False
    if width * height > page_width * page_height * 0.25:
        return False
    if area < 80:
        return False

    aspect_ratio = width / height
    if aspect_ratio < _MIN_BUBBLE_ASPECT_RATIO or aspect_ratio > _MAX_BUBBLE_ASPECT_RATIO:
        return False
    return fill_ratio >= _MIN_BUBBLE_FILL_RATIO


def _scale_text_in_component(
    image: Image.Image,
    bubble_bbox: tuple[int, int, int, int],
    min_scale: float,
    max_scale: float,
) -> bool:
    text_bbox = _dark_text_bbox(image, bubble_bbox)
    if text_bbox is None:
        return False

    bx0, by0, bx1, by1 = bubble_bbox
    tx0, ty0, tx1, ty1 = text_bbox
    bubble_w = bx1 - bx0
    bubble_h = by1 - by0
    text_w = tx1 - tx0
    text_h = ty1 - ty0
    if text_w <= 0 or text_h <= 0:
        return False

    scale = min((bubble_w * 0.78) / text_w, (bubble_h * 0.70) / text_h)
    scale = min(scale, max_scale)
    if scale < min_scale:
        return False

    pad = max(4, int(min(bubble_w, bubble_h) * 0.08))
    crop_box = (
        max(tx0 - pad, bx0),
        max(ty0 - pad, by0),
        min(tx1 + pad, bx1),
        min(ty1 + pad, by1),
    )
    crop = image.crop(crop_box)
    scale = min(scale, (bubble_w * 0.96) / crop.width, (bubble_h * 0.86) / crop.height)
    if scale < min_scale:
        return False
    new_size = (max(1, int(crop.width * scale)), max(1, int(crop.height * scale)))
    enlarged = crop.resize(new_size, Image.Resampling.LANCZOS)

    target_x = bx0 + (bubble_w - new_size[0]) // 2
    target_y = by0 + (bubble_h - new_size[1]) // 2
    target_x = max(bx0 + 2, min(target_x, bx1 - new_size[0] - 2))
    target_y = max(by0 + 2, min(target_y, by1 - new_size[1] - 2))
    target_box = (target_x, target_y, target_x + new_size[0], target_y + new_size[1])

    draw = ImageDraw.Draw(image)
    clear_box = _union_boxes(
        _expand_box(crop_box, 4, image.size), _expand_box(target_box, 4, image.size)
    )
    draw.rectangle(clear_box, fill=(255, 255, 255))
    image.paste(enlarged, (target_x, target_y))
    return True


def _dark_text_bbox(
    image: Image.Image,
    bubble_bbox: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    bx0, by0, bx1, by1 = bubble_bbox
    # Keep decorative top/bottom outlines and speed lines out of the text bbox
    # without clipping text that starts close to the left/right bubble edge.
    width = bx1 - bx0
    height = by1 - by0
    margin_x = max(6, int(width * 0.05))
    margin_y = max(7, int(height * 0.20))
    x0 = bx0 + margin_x
    y0 = by0 + margin_y
    x1 = bx1 - margin_x
    y1 = by1 - margin_y
    if x1 <= x0 or y1 <= y0:
        return None

    candidates = _dark_components_inside(image, (x0, y0, x1, y1))
    if not candidates:
        return None
    min_x = min(candidate.bbox[0] for candidate in candidates)
    min_y = min(candidate.bbox[1] for candidate in candidates)
    max_x = max(candidate.bbox[2] for candidate in candidates)
    max_y = max(candidate.bbox[3] for candidate in candidates)
    text_w = max_x - min_x + 1
    text_h = max_y - min_y + 1
    bubble_w = bx1 - bx0
    bubble_h = by1 - by0
    if text_w > bubble_w * 0.92 or text_h > bubble_h * 0.88:
        return None
    return min_x, min_y, max_x + 1, max_y + 1


def _dark_components_inside(
    image: Image.Image,
    region: tuple[int, int, int, int],
) -> list[_Component]:
    x0, y0, x1, y1 = region
    width = x1 - x0
    height = y1 - y0
    gray = image.convert("L")
    pixels = gray.load()
    assert pixels is not None
    visited = bytearray(width * height)
    components: list[_Component] = []

    for start in range(width * height):
        if visited[start]:
            continue
        sx = start % width
        sy = start // width
        if cast(int, pixels[x0 + sx, y0 + sy]) > 120:
            visited[start] = 1
            continue

        stack = [start]
        visited[start] = 1
        min_x = max_x = sx
        min_y = max_y = sy
        area = 0
        touches_edge = False

        while stack:
            current = stack.pop()
            area += 1
            cx = current % width
            cy = current // width
            min_x = min(min_x, cx)
            max_x = max(max_x, cx)
            min_y = min(min_y, cy)
            max_y = max(max_y, cy)
            touches_edge = touches_edge or cx == 0 or cy == 0 or cx == width - 1 or cy == height - 1

            for neighbor in _neighbors(cx, cy, width, height):
                if visited[neighbor]:
                    continue
                nx = neighbor % width
                ny = neighbor // width
                if cast(int, pixels[x0 + nx, y0 + ny]) <= 120:
                    visited[neighbor] = 1
                    stack.append(neighbor)
                else:
                    visited[neighbor] = 1

        if area >= 3 and not touches_edge:
            components.append(
                _Component(
                    bbox=(x0 + min_x, y0 + min_y, x0 + max_x, y0 + max_y),
                    area=area,
                    touches_edge=touches_edge,
                )
            )

    return components


def _expand_box(
    bbox: tuple[int, int, int, int],
    amount: int,
    image_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    width, height = image_size
    x0, y0, x1, y1 = bbox
    return (
        max(0, x0 - amount),
        max(0, y0 - amount),
        min(width, x1 + amount),
        min(height, y1 + amount),
    )


def _union_boxes(
    a: tuple[int, int, int, int], b: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])
