#!/usr/bin/env python3
"""Generate the accepted Work title-loading cue from its tracked JSON contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageSequence

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts" / "title-loading-cue.v2.json"

# Rendering policy intentionally code-owned. Every contract-exposed identity,
# dimension, timing, and geometry value is loaded from CONTRACT_PATH.
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


def load_contract() -> dict[str, object]:
    """Load and self-consistency-check the canonical JSON contract."""
    contract = json.loads(CONTRACT_PATH.read_text())
    required = {
        "contractId",
        "output",
        "sha256",
        "canvas",
        "animation",
        "ellipsis",
        "arrow",
        "toolchain",
    }
    missing = sorted(required - contract.keys())
    if missing:
        raise SystemExit(f"contract missing keys: {missing}")

    canvas = contract["canvas"]
    animation = contract["animation"]
    ellipsis = contract["ellipsis"]
    arrow = contract["arrow"]

    if len(ellipsis["dotCentersPx"]) != 3:
        raise SystemExit("contract must define exactly three ellipsis dot centers")
    if int(animation["frameCount"]) != len(FRAME_PLAN):
        raise SystemExit(
            "contract frameCount does not match renderer FRAME_PLAN: "
            f"{animation['frameCount']} != {len(FRAME_PLAN)}"
        )
    if ellipsis["side"] != "left":
        raise SystemExit("accepted cue requires ellipsis side=left")
    if arrow["direction"] != "down-right":
        raise SystemExit("accepted cue requires arrow direction=down-right")

    start = tuple(int(v) for v in arrow["startPx"])
    end = tuple(int(v) for v in arrow["endPx"])
    derived_angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
    if abs(derived_angle - float(arrow["angleDeg"])) > 0.001:
        raise SystemExit(
            f"contract arrow angle mismatch: declared {arrow['angleDeg']} "
            f"derived {derived_angle:.6f}"
        )

    width = int(canvas["widthPx"])
    height = int(canvas["heightPx"])
    for x, y in [*ellipsis["dotCentersPx"], start, end]:
        if not (0 <= int(x) < width and 0 <= int(y) < height):
            raise SystemExit(f"contract geometry outside {width}x{height}: {(x, y)}")
    return contract


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_frame(
    contract: dict[str, object],
    dot_levels: tuple[int, int, int],
    arrow_level: int,
) -> Image.Image:
    canvas = contract["canvas"]
    ellipsis = contract["ellipsis"]
    arrow = contract["arrow"]
    width = int(canvas["widthPx"])
    height = int(canvas["heightPx"])
    background = tuple(int(v) for v in canvas["backgroundRgb"])
    if background != (255, 255, 255):
        raise SystemExit("renderer currently supports the accepted white background only")

    image = Image.new("P", (width, height), 0)
    image.putpalette(PALETTE_RGB)
    draw = ImageDraw.Draw(image)

    radius = int(ellipsis["radiusPx"])
    for (x, y), level in zip(ellipsis["dotCentersPx"], dot_levels):
        if level != OFF:
            x, y = int(x), int(y)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=level)

    if arrow_level != OFF:
        start = tuple(int(v) for v in arrow["startPx"])
        end = tuple(int(v) for v in arrow["endPx"])
        width_px = int(arrow["widthPx"])
        head_length = int(arrow["headLengthPx"])
        draw.line((*start, *end), fill=arrow_level, width=width_px)
        shaft_angle = math.atan2(end[1] - start[1], end[0] - start[0])
        for offset_deg in (28, -28):
            head_angle = shaft_angle + math.pi + math.radians(offset_deg)
            x2 = round(end[0] + math.cos(head_angle) * head_length)
            y2 = round(end[1] + math.sin(head_angle) * head_length)
            draw.line((*end, x2, y2), fill=arrow_level, width=width_px)

    return image


def assert_contract(path: Path, contract: dict[str, object]) -> None:
    """Fail closed unless bytes and decoded behavior match the JSON contract."""
    canvas = contract["canvas"]
    animation = contract["animation"]
    ellipsis = contract["ellipsis"]

    digest = sha256_path(path)
    if digest != contract["sha256"]:
        raise SystemExit(
            f"deterministic output drift: expected {contract['sha256']}, got {digest}"
        )

    with Image.open(path) as image:
        expected_size = (int(canvas["widthPx"]), int(canvas["heightPx"]))
        if image.size != expected_size:
            raise SystemExit(f"expected {expected_size}, got {image.size}")

        expected_frames = int(animation["frameCount"])
        if getattr(image, "n_frames", 1) != expected_frames:
            raise SystemExit(
                f"expected {expected_frames} frames, got {getattr(image, 'n_frames', 1)}"
            )

        frame_ms = int(animation["frameDurationMs"])
        durations = {
            int(frame.info.get("duration", image.info.get("duration", 0)))
            for frame in ImageSequence.Iterator(image)
        }
        if durations != {frame_ms}:
            raise SystemExit(f"expected duration {frame_ms}ms, got {sorted(durations)}")

        representative = int(ellipsis["representativeFrame"])
        image.seek(representative)
        frame = image.convert("RGB")
        centers = [tuple(int(v) for v in p) for p in ellipsis["dotCentersPx"]]
        pixels = [frame.getpixel(p) for p in centers]
        visible = [pixel != (255, 255, 255) for pixel in pixels]
        expected_visible = int(ellipsis["representativeFrameVisibleDots"])
        if visible != [i < expected_visible for i in range(len(centers))]:
            raise SystemExit(
                f"representative frame {representative} dot state drift: {visible}"
            )


def write_gif(output: Path, contract: dict[str, object]) -> None:
    """Generate to a sibling temp file; replace canonical output only after PASS."""
    animation = contract["animation"]
    output.parent.mkdir(parents=True, exist_ok=True)
    frames = [make_frame(contract, dots, arrow) for dots, arrow in FRAME_PLAN]

    pending_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as pending:
            pending_path = Path(pending.name)

        frames[0].save(
            pending_path,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=int(animation["frameDurationMs"]),
            loop=int(animation["loop"]),
            optimize=False,
            disposal=2,
        )
        assert_contract(pending_path, contract)
        os.replace(pending_path, output)
        pending_path = None
    finally:
        if pending_path is not None:
            pending_path.unlink(missing_ok=True)


def main() -> None:
    contract = load_contract()
    default_output = ROOT / str(contract["output"])

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=default_output)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Validate an existing --output instead of regenerating it.",
    )
    args = parser.parse_args()

    if args.verify_only:
        assert_contract(args.output, contract)
    else:
        write_gif(args.output, contract)

    canvas = contract["canvas"]
    animation = contract["animation"]
    arrow = contract["arrow"]
    print(
        f"{contract['contractId']} path={args.output} sha256={sha256_path(args.output)} "
        f"size={canvas['widthPx']}x{canvas['heightPx']} "
        f"frames={animation['frameCount']} frame_ms={animation['frameDurationMs']} "
        f"arrow_deg={float(arrow['angleDeg']):.3f}"
    )


if __name__ == "__main__":
    main()
