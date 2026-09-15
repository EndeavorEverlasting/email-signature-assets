#!/usr/bin/env python3
"""Generate Title_Loading_Ellipsis_Down.gif with sequential fading dots.

Email-safe indexed GIF: dots appear left-to-right, then a down-right arrow
pulses so the cue (left/logo column) aims at the obsolete title on the right.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageSequence

WIDTH = 96
HEIGHT = 56
FRAME_MS = 140

# Fixed palette indices (email-safe, opaque).
# 0=bg, 1=ink full, 2=ink mid, 3=ink dim, 4=ink ghost
PALETTE_RGB = [
    236, 238, 241,  # 0 bg
    107, 116, 181,  # 1 full
    150, 156, 199,  # 2 mid
    193, 197, 217,  # 3 dim
    214, 217, 229,  # 4 ghost
]
while len(PALETTE_RGB) < 768:
    PALETTE_RGB.extend([0, 0, 0])

DOT_RADIUS = 4
DOT_Y = 14
DOT_XS = (22, 42, 62)
# Down-right arrow: stem from mid-left toward lower-right title column.
ARROW_START = (40, 26)
ARROW_END = (78, 50)
ARROW_HEAD = 7

# Named opacity steps mapped to palette indices.
FULL, MID, DIM, GHOST, OFF = 1, 2, 3, 4, 0


def draw_dot(draw: ImageDraw.ImageDraw, x: int, y: int, color_idx: int) -> None:
    if color_idx == OFF:
        return
    draw.ellipse(
        (x - DOT_RADIUS, y - DOT_RADIUS, x + DOT_RADIUS, y + DOT_RADIUS),
        fill=color_idx,
    )


def draw_arrow(draw: ImageDraw.ImageDraw, color_idx: int) -> None:
    """Down-right chevron aiming from the logo column toward the title column."""
    if color_idx == OFF:
        return
    x0, y0 = ARROW_START
    x1, y1 = ARROW_END
    # Thick stem via short perpendicular offsets (indexed palette; no antialias).
    for dx, dy in ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)):
        draw.line((x0 + dx, y0 + dy, x1 + dx, y1 + dy), fill=color_idx, width=1)
    # Arrow head pointing down-right.
    draw.polygon(
        [
            (x1, y1),
            (x1 - ARROW_HEAD, y1 - 2),
            (x1 - 2, y1 - ARROW_HEAD),
        ],
        fill=color_idx,
    )


def make_frame(dot_levels: tuple[int, int, int], arrow_level: int) -> Image.Image:
    img = Image.new("P", (WIDTH, HEIGHT), 0)
    img.putpalette(PALETTE_RGB)
    draw = ImageDraw.Draw(img)
    for x, level in zip(DOT_XS, dot_levels):
        draw_dot(draw, x, DOT_Y, level)
    draw_arrow(draw, arrow_level)
    return img


def build_frames() -> list[Image.Image]:
    """Classic loading ellipsis: ., .., ..., hold, arrow pulse, soft reset."""
    return [
        make_frame((GHOST, OFF, OFF), GHOST),
        make_frame((FULL, OFF, OFF), DIM),
        make_frame((FULL, FULL, OFF), DIM),
        make_frame((FULL, FULL, FULL), MID),
        make_frame((FULL, FULL, FULL), FULL),  # hold + arrow strong
        make_frame((MID, MID, MID), FULL),
        make_frame((DIM, DIM, DIM), FULL),  # arrow still leading
        make_frame((GHOST, GHOST, GHOST), MID),
        make_frame((OFF, OFF, OFF), DIM),
        make_frame((OFF, OFF, OFF), GHOST),
    ]


def assert_sequential(path: Path) -> None:
    with Image.open(path) as im:
        n = getattr(im, "n_frames", 1)
        if n < 6:
            raise SystemExit(f"expected >=6 frames, got {n}")
        samples: list[tuple[int, int, int, int]] = []
        for i, frame in enumerate(ImageSequence.Iterator(im)):
            rgba = frame.convert("RGBA")
            samples.append(
                (
                    i,
                    rgba.getpixel((DOT_XS[0], DOT_Y))[0],
                    rgba.getpixel((DOT_XS[1], DOT_Y))[0],
                    rgba.getpixel((DOT_XS[2], DOT_Y))[0],
                )
            )
        f1 = samples[1]
        f2 = samples[2]
        f3 = samples[3]
        if not (f1[1] < f1[2] and f1[1] < f1[3]):
            raise SystemExit(f"frame1 must light only first dot: {samples}")
        if not (f2[1] <= f2[2] + 5 and f2[2] < f2[3]):
            raise SystemExit(f"frame2 must light first two dots: {samples}")
        if not (abs(f3[1] - f3[2]) < 8 and abs(f3[2] - f3[3]) < 8):
            raise SystemExit(f"frame3 must light all three dots: {samples}")
        if samples[1][1:] == samples[2][1:] == samples[3][1:]:
            raise SystemExit(f"sequential fade collapsed: {samples}")


def write_gif(out: Path) -> dict[str, object]:
    frames = build_frames()
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=False,
        disposal=2,
    )
    assert_sequential(out)
    return {
        "path": str(out),
        "bytes": out.stat().st_size,
        "n_frames": len(frames),
        "duration_ms": FRAME_MS,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "Title_Loading_Ellipsis_Down.gif",
    )
    args = parser.parse_args()
    meta = write_gif(args.output)
    print(
        f"wrote {meta['path']} bytes={meta['bytes']} "
        f"n_frames={meta['n_frames']} duration_ms={meta['duration_ms']}"
    )


if __name__ == "__main__":
    main()
