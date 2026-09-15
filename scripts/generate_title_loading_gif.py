#!/usr/bin/env python3
"""Generate the accepted Work title-loading cue deterministically.

Contract: work-title-loading-cue-v2
- 128x43 px canvas matching the managed Toga logo column.
- Compact left-side sequential ellipsis.
- Steep down-right arrow accepted against the frozen combined-signature fixture.
- Exact SHA-256 is pinned; drift fails closed.
"""

from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageSequence

CONTRACT_VERSION = "work-title-loading-cue-v2"
WIDTH = 128
HEIGHT = 43
FRAME_MS = 140
FRAME_COUNT = 10
EXPECTED_SHA256 = "e3c950e7d278f285ad5a7be8d9ed0bb219b0aa730ca34e80fd0d0fc371736ee5"

DOT_RADIUS = 2
DOT_Y = 7
DOT_XS = (28, 48, 68)
ARROW_START = (114, 1)
ARROW_END = (125, 40)
ARROW_HEAD = 7
ARROW_WIDTH = 3
ARROW_ANGLE_DEG = math.degrees(
    math.atan2(ARROW_END[1] - ARROW_START[1], ARROW_END[0] - ARROW_START[0])
)

# Indexed, opaque palette for email-client portability.
# 0 background, 1..4 dot levels, 5..7 arrow levels.
PALETTE_RGB = [
    255, 255, 255,
    100, 114, 180,
    145, 154, 199,
    190, 196, 218,
    220, 223, 235,
    190, 196, 218,
    208, 212, 228,
    226, 229, 239,
]
while len(PALETTE_RGB) < 768:
    PALETTE_RGB.extend([0, 0, 0])

DOT_FULL, DOT_MID, DOT_DIM, DOT_GHOST, OFF = 1, 2, 3, 4, 0
ARROW_FULL, ARROW_MID, ARROW_GHOST = 5, 6, 7

FRAME_PLAN = (
    ((DOT_GHOST, OFF, OFF), ARROW_GHOST),
    ((DOT_FULL, OFF, OFF), ARROW_GHOST),
    ((DOT_FULL, DOT_FULL, OFF), ARROW_MID),
    ((DOT_FULL, DOT_FULL, DOT_FULL), ARROW_MID),
    ((DOT_FULL, DOT_FULL, DOT_FULL), ARROW_FULL),
    ((DOT_MID, DOT_MID, DOT_MID), ARROW_FULL),
    ((DOT_DIM, DOT_DIM, DOT_DIM), ARROW_FULL),
    ((DOT_GHOST, DOT_GHOST, DOT_GHOST), ARROW_MID),
    ((OFF, OFF, OFF), ARROW_MID),
    ((OFF, OFF, OFF), ARROW_GHOST),
)


def draw_dot(draw: ImageDraw.ImageDraw, x: int, color_idx: int) -> None:
    if color_idx == OFF:
        return
    draw.ellipse(
        (x - DOT_RADIUS, DOT_Y - DOT_RADIUS, x + DOT_RADIUS, DOT_Y + DOT_RADIUS),
        fill=color_idx,
    )


def draw_arrow(draw: ImageDraw.ImageDraw, color_idx: int) -> None:
    if color_idx == OFF:
        return
    draw.line((*ARROW_START, *ARROW_END), fill=color_idx, width=ARROW_WIDTH)
    shaft_angle = math.atan2(
        ARROW_END[1] - ARROW_START[1], ARROW_END[0] - ARROW_START[0]
    )
    for offset_deg in (28, -28):
        head_angle = shaft_angle + math.pi + math.radians(offset_deg)
        x2 = round(ARROW_END[0] + math.cos(head_angle) * ARROW_HEAD)
        y2 = round(ARROW_END[1] + math.sin(head_angle) * ARROW_HEAD)
        draw.line((*ARROW_END, x2, y2), fill=color_idx, width=ARROW_WIDTH)


def make_frame(dot_levels: tuple[int, int, int], arrow_level: int) -> Image.Image:
    image = Image.new("P", (WIDTH, HEIGHT), 0)
    image.putpalette(PALETTE_RGB)
    draw = ImageDraw.Draw(image)
    for x, level in zip(DOT_XS, dot_levels):
        draw_dot(draw, x, level)
    draw_arrow(draw, arrow_level)
    return image


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_contract(path: Path) -> None:
    digest = sha256_path(path)
    if digest != EXPECTED_SHA256:
        raise SystemExit(
            f"deterministic output drift: expected {EXPECTED_SHA256}, got {digest}"
        )
    with Image.open(path) as image:
        if image.size != (WIDTH, HEIGHT):
            raise SystemExit(f"expected {(WIDTH, HEIGHT)}, got {image.size}")
        if getattr(image, "n_frames", 1) != FRAME_COUNT:
            raise SystemExit(
                f"expected {FRAME_COUNT} frames, got {getattr(image, 'n_frames', 1)}"
            )
        durations = {
            int(frame.info.get("duration", image.info.get("duration", 0)))
            for frame in ImageSequence.Iterator(image)
        }
        if durations != {FRAME_MS}:
            raise SystemExit(f"expected duration {FRAME_MS}ms, got {sorted(durations)}")
        image.seek(2)
        frame = image.convert("RGB")
        dot1 = frame.getpixel((DOT_XS[0], DOT_Y))
        dot2 = frame.getpixel((DOT_XS[1], DOT_Y))
        dot3 = frame.getpixel((DOT_XS[2], DOT_Y))
        if not (
            dot1[2] > dot1[0]
            and dot2[2] > dot2[0]
            and dot3 == (255, 255, 255)
        ):
            raise SystemExit(
                f"frame 2 must show exactly the first two dots: {dot1} {dot2} {dot3}"
            )


def write_gif(output: Path) -> None:
    frames = [make_frame(dots, arrow) for dots, arrow in FRAME_PLAN]
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=False,
        disposal=2,
    )
    assert_contract(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "Title_Loading_Ellipsis_Down.gif",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Validate an existing --output instead of regenerating it.",
    )
    args = parser.parse_args()
    if args.verify_only:
        assert_contract(args.output)
    else:
        write_gif(args.output)
    print(
        f"{CONTRACT_VERSION} path={args.output} sha256={sha256_path(args.output)} "
        f"size={WIDTH}x{HEIGHT} frames={FRAME_COUNT} frame_ms={FRAME_MS} "
        f"arrow_deg={ARROW_ANGLE_DEG:.3f}"
    )


if __name__ == "__main__":
    main()
