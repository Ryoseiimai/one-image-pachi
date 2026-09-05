#!/usr/bin/env python3
"""Extract gold pachinko pin heads and machine geometry from a frame image.

The detector deliberately uses only Pillow and NumPy.  It thresholds warm/gold,
bright pixels, labels four-connected components, scores compact components by
the characteristic bright-top/dark-bottom appearance of a pin head, and uses
their centroids as pin positions.  Machine furniture is kept per skin because
those large shapes are not reliably recoverable from decorative artwork.

Usage:
    python3 extract_pins.py kaeru_real_frame.png
    python3 extract_pins.py neko_real_frame.png --output pins_neko.json
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw


@dataclass(frozen=True)
class SkinGeometry:
    lcd: tuple[int, int, int, int]
    windmills: tuple[tuple[int, int, int], ...]
    heso: tuple[int, int, int, int]
    rail: tuple[tuple[int, int], ...]  # top to bottom
    out: tuple[int, int]
    bounds: tuple[int, int, int, int]
    target_count: int | None = None


def cubic_bezier(
    p0: tuple[int, int],
    p1: tuple[int, int],
    p2: tuple[int, int],
    p3: tuple[int, int],
    samples: int = 17,
) -> tuple[tuple[int, int], ...]:
    """Return integer points from p0 to p3, inclusive."""
    points: list[tuple[int, int]] = []
    for t in np.linspace(0.0, 1.0, samples):
        u = 1.0 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        points.append((round(x), round(y)))
    return tuple(points)


GEOMETRY: dict[str, SkinGeometry] = {
    "kaeru": SkinGeometry(
        lcd=(356, 451, 312, 286),
        windmills=((318, 758, 58), (704, 758, 58)),
        heso=(440, 786, 144, 144),
        # Same cubic curve as real.html, sampled in the requested top-to-bottom order.
        rail=cubic_bezier((246, 153), (103, 278), (111, 747), (191, 979)),
        out=(512, 1029),
        bounds=(120, 120, 930, 1035),
        target_count=180,
    ),
    "neko": SkinGeometry(
        lcd=(395, 478, 270, 258),
        windmills=((271, 747, 58), (774, 753, 58)),
        heso=(444, 740, 166, 176),
        rail=((284, 145), (238, 200), (197, 285), (165, 390), (144, 515),
              (135, 650), (140, 790), (160, 925), (205, 1045)),
        out=(521, 1108),
        bounds=(125, 125, 925, 1090),
        target_count=245,
    ),
    "inu": SkinGeometry(
        lcd=(383, 515, 285, 250),
        windmills=((297, 799, 66), (759, 803, 66)),
        heso=(458, 800, 142, 225),
        rail=((354, 277), (295, 314), (239, 382), (196, 477), (167, 590),
              (153, 720), (164, 850), (211, 963), (302, 1035), (430, 1074)),
        out=(523, 1108),
        bounds=(115, 250, 930, 1090),
        target_count=230,
    ),
}


def skin_name(path: Path) -> str:
    stem = path.stem.lower()
    for name in GEOMETRY:
        if name in stem:
            return name
    raise ValueError(
        f"Cannot infer skin from {path.name!r}; expected a filename containing "
        f"one of: {', '.join(GEOMETRY)}"
    )


def inside_rect(x: float, y: float, rect: tuple[int, int, int, int], margin: int = 0) -> bool:
    rx, ry, rw, rh = rect
    return rx - margin <= x <= rx + rw + margin and ry - margin <= y <= ry + rh + margin


def inside_circle(x: float, y: float, circle: tuple[int, int, int], margin: int = 0) -> bool:
    cx, cy, radius = circle
    return (x - cx) ** 2 + (y - cy) ** 2 <= (radius + margin) ** 2


def connected_components(mask: np.ndarray) -> Iterable[tuple[int, float, float, int, int]]:
    """Yield area, centroid x/y, width and height for 4-connected foreground."""
    height, width = mask.shape
    seen = np.zeros(mask.shape, dtype=bool)
    for start_y, start_x in np.argwhere(mask):
        if seen[start_y, start_x]:
            continue
        stack = [(int(start_y), int(start_x))]
        seen[start_y, start_x] = True
        area = sum_x = sum_y = 0
        min_x = max_x = int(start_x)
        min_y = max_y = int(start_y)
        while stack:
            y, x = stack.pop()
            area += 1
            sum_x += x
            sum_y += y
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        yield area, sum_x / area, sum_y / area, max_x - min_x + 1, max_y - min_y + 1


def excluded_by_furniture(x: float, y: float, geometry: SkinGeometry) -> bool:
    if inside_rect(x, y, geometry.lcd, margin=10):
        return True
    if inside_rect(x, y, geometry.heso, margin=8):
        return True
    return any(inside_circle(x, y, circle, margin=13) for circle in geometry.windmills)


def detect_pins(image: Image.Image, geometry: SkinGeometry) -> list[list[int]]:
    hsv = np.asarray(image.convert("HSV"))
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    # PIL hue 10..50 is approximately 14..71 degrees: brass/gold through pale gold.
    mask = (
        (hue >= 10)
        & (hue <= 50)
        & (saturation >= 20)
        & (value >= 170)
    )
    x0, y0, x1, y1 = geometry.bounds
    in_bounds = np.zeros(mask.shape, dtype=bool)
    in_bounds[y0:y1, x0:x1] = True
    mask &= in_bounds

    candidates: list[tuple[float, float, float]] = []
    height, width = mask.shape
    for area, component_x, component_y, component_w, component_h in connected_components(mask):
        # A nail's illuminated cap is normally a 4-10 px horizontal component.
        if not (8 <= area <= 55 and 4 <= component_w <= 14 and 2 <= component_h <= 12):
            continue
        ix, iy = round(component_x), round(component_y)
        if ix < 8 or iy < 8 or ix >= width - 8 or iy >= height - 12:
            continue

        patch = value[iy - 3 : iy + 12, ix - 7 : ix + 8].astype(np.float32)
        below = float(value[iy + 5, ix])
        top_bottom_contrast = float(patch[:6].mean() - patch[7:].mean())
        local_range = float(patch.max() - patch.min())
        local_std = float(patch.std())
        center_saturation = float(saturation[iy, ix])
        normal_pin = (
            below < 145
            and top_bottom_contrast > 8
            and local_range > 125
            and local_std > 25
            and center_saturation < 150
        )
        # The top row in the frog frame lies on a dark red panel. Its lower
        # shadow has less contrast, although the compact metallic highlight is
        # still unambiguous.
        frog_upper_pin = (
            geometry.target_count == 180
            and component_y + 4 < 230
            and below < 155
            and top_bottom_contrast > -5
            and local_range > 160
            and local_std > 30
            and center_saturation < 120
        )
        if not (normal_pin or frog_upper_pin):
            continue

        # The gold component is the highlight on the upper half of the domed head;
        # shift four pixels down to the physical center (as in real.html's centers).
        pin_x = component_x
        pin_y = component_y + 4.0
        if excluded_by_furniture(pin_x, pin_y, geometry):
            continue
        # On the frog photograph the upper playfield narrows sharply; bright
        # chrome in the two corners otherwise has the same colour as brass.
        if geometry.target_count == 180 and pin_y < 230 and not (300 < pin_x < 720):
            continue
        shape_score = max(
            0.0,
            30.0
            - abs(area - 20) * 1.5
            - abs(component_w - 7) * 5.0
            - abs(component_h - 4) * 7.0,
        )
        score = (
            (145 - below) * 0.40
            + top_bottom_contrast * 0.70
            + (local_range - 125) * 0.15
            + (local_std - 25) * 0.50
            + (150 - center_saturation) * 0.08
            + shape_score
        )
        if geometry.target_count == 180 and pin_y < 230:
            score += 45.0
        candidates.append((pin_x, pin_y, score))

    # A real head can occasionally split into two bright components. Keep the
    # stronger one in each 10 px neighbourhood.
    candidates.sort(key=lambda item: item[2], reverse=True)
    selected: list[tuple[float, float, float]] = []
    for candidate in candidates:
        x, y, _ = candidate
        if all((x - old_x) ** 2 + (y - old_y) ** 2 > 10**2 for old_x, old_y, _ in selected):
            selected.append(candidate)

    if geometry.target_count is not None and len(selected) > geometry.target_count:
        selected = selected[: geometry.target_count]

    pins = [[round(x), round(y)] for x, y, _ in selected]
    pins.sort(key=lambda point: (point[1], point[0]))
    return pins


def make_overlay(
    image: Image.Image,
    pins: list[list[int]],
    geometry: SkinGeometry,
) -> Image.Image:
    overlay = image.convert("RGB").copy()
    draw = ImageDraw.Draw(overlay)

    # High-contrast outlines remain readable without hiding the original photo.
    for x, y in pins:
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), outline=(74, 232, 255), width=3)
    draw.line(geometry.rail, fill=(60, 255, 90), width=5, joint="curve")
    x, y, w, h = geometry.lcd
    draw.rectangle((x, y, x + w, y + h), outline=(255, 224, 64), width=5)
    x, y, w, h = geometry.heso
    draw.rectangle((x, y, x + w, y + h), outline=(255, 80, 220), width=5)
    for x, y, radius in geometry.windmills:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=(255, 145, 45), width=5)
    ox, oy = geometry.out
    draw.line((ox - 10, oy, ox + 10, oy), fill=(255, 70, 70), width=4)
    draw.line((ox, oy - 10, ox, oy + 10), fill=(255, 70, 70), width=4)
    return overlay


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="1024x1536 pachinko frame PNG")
    parser.add_argument("--output", "-o", type=Path, help="JSON output path")
    parser.add_argument("--overlay", type=Path, help="verification overlay PNG path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    name = skin_name(args.image)
    geometry = GEOMETRY[name]
    output = args.output or Path(f"pins_{name}.json")
    overlay_path = args.overlay or Path(f"overlay_{name}.png")

    image = Image.open(args.image).convert("RGB")
    if image.size != (1024, 1536):
        raise ValueError(f"Expected a 1024x1536 image, got {image.size[0]}x{image.size[1]}")
    pins = detect_pins(image, geometry)
    payload = {
        "pins": pins,
        "lcd": list(geometry.lcd),
        "windmills": [list(item) for item in geometry.windmills],
        "heso": list(geometry.heso),
        "rail": [list(item) for item in geometry.rail],
        "out": list(geometry.out),
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    make_overlay(image, pins, geometry).save(overlay_path)
    print(f"{name}: {len(pins)} pins -> {output}; overlay -> {overlay_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
