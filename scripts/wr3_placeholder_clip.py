#!/usr/bin/env python3
"""WR3 zero-spend placeholder clip generator.

Renders a deterministic 8s, 720x1280 (9:16 portrait) H.264/yuv420p MP4 so the
WR3 pipeline (gatekeeper -> audio -> assembler -> critic) can run end-to-end
with ZERO Veo/Flow credits. This module never opens a network socket and
never talks to FlowKit — it is pure local ffmpeg + PIL rendering.

Visual: ffmpeg `smptebars` colour bars as the base plate, composited with a
PIL-rendered burned-in label (episode_id, shot_index, PLACEHOLDER, NO VEO
SPEND) via ffmpeg's `overlay` filter. `drawtext` is deliberately NOT used —
this ffmpeg build (8.1, Homebrew) has no libfreetype and
`ffmpeg -h filter=drawtext` reports `Unknown filter 'drawtext'`. Do not
reintroduce it without re-verifying the build.

Determinism: rendering the same (episode_id, shot_index, duration, size)
twice is required to produce byte-identical (or at minimum frame-identical)
output — see `render_placeholder_clip` docstring for exactly what is
guaranteed and how, and `scripts/tests/test_wr3_zero_spend.py` for the
empirical proof.

CLI:
    python3 scripts/wr3_placeholder_clip.py --episode-id EP01 --shot-index 3 \
        --dest /tmp/out.mp4
"""
from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

DEFAULT_WIDTH: Final[int] = 720
DEFAULT_HEIGHT: Final[int] = 1280
DEFAULT_DURATION_S: Final[int] = 8
FRAME_RATE: Final[int] = 25

# Fixed stream-metadata tag so the "encoder" tag libavformat writes into the
# output does not vary across ffmpeg builds/versions — part of the
# determinism contract (see module docstring).
_ENCODER_TAG: Final[str] = "wr3-placeholder-clip"

# Deterministic font search order. Tried in sequence; falls back to PIL's
# bundled default font (scaled up) if none is found on this machine. The
# choice matters only for legibility, not correctness — any font that
# resolves the same way twice on the SAME machine keeps determinism.
_FONT_CANDIDATES: Final[tuple[str, ...]] = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


class PlaceholderRenderError(RuntimeError):
    """Raised when the placeholder clip cannot be rendered.

    Never swallow this to produce a 0-byte or missing file — a downstream
    WR3 stage (gatekeeper/audio/assembler/critic) must see a hard failure,
    not silently proceed on a placeholder that doesn't exist.
    """


def _resolve_ffmpeg(ffmpeg_bin: str | None) -> str:
    candidate = ffmpeg_bin or "ffmpeg"
    resolved = shutil.which(candidate) if not Path(candidate).is_absolute() else (
        candidate if Path(candidate).exists() else None
    )
    if resolved is None:
        raise PlaceholderRenderError(
            f"ffmpeg binary not found (looked for {candidate!r}) — cannot render placeholder clip"
        )
    return resolved


def _load_font(size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size_px)
            except OSError:
                logger.warning("font candidate %s exists but failed to load, trying next", candidate)
                continue
    logger.warning("no system font found among %s — falling back to PIL default font", _FONT_CANDIDATES)
    # Pillow >=10.1 supports a `size` kwarg on load_default(); it stays
    # deterministic across runs on the same Pillow install.
    return ImageFont.load_default(size=size_px)


def _render_label_png(
    *,
    episode_id: str,
    shot_index: int,
    width: int,
    height: int,
    dest: Path,
) -> Path:
    """Render the burned-in label to a transparent RGBA PNG via PIL.

    No `drawtext` filter is used (unavailable in this ffmpeg build — see
    module docstring). No timestamp/metadata is embedded: Pillow's default
    PNG writer does not add a tIME chunk unless explicitly asked, so two
    renders of identical text/font/size produce byte-identical PNG bytes.
    """
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    title_size = max(24, width // 14)
    body_size = max(18, width // 22)
    title_font = _load_font(title_size)
    body_font = _load_font(body_size)

    lines = [
        (str(episode_id), title_font),
        (f"SHOT {shot_index:03d}", body_font),
        ("PLACEHOLDER", body_font),
        ("NO VEO SPEND", body_font),
    ]

    # Measure the text block to size a legibility backdrop behind it.
    line_metrics: list[tuple[str, ImageFont.FreeTypeFont | ImageFont.ImageFont, int, int]] = []
    max_line_w = 0
    total_h = 0
    line_gap = max(4, body_size // 4)
    for text, font in lines:
        bbox = draw.textbbox((0, 0), text, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]
        line_metrics.append((text, font, line_w, line_h))
        max_line_w = max(max_line_w, line_w)
        total_h += line_h + line_gap
    total_h -= line_gap

    pad_x, pad_y = 28, 24
    block_w = max_line_w + 2 * pad_x
    block_h = total_h + 2 * pad_y
    block_x0 = (width - block_w) // 2
    block_y0 = (height - block_h) // 2
    draw.rectangle(
        [block_x0, block_y0, block_x0 + block_w, block_y0 + block_h],
        fill=(0, 0, 0, 200),
    )

    y = block_y0 + pad_y
    for text, font, line_w, line_h in line_metrics:
        x = (width - line_w) // 2
        draw.text((x, y), text, font=font, fill=(255, 221, 0, 255))
        y += line_h + line_gap

    # optimize=False, compress_level fixed: keep PNG bytes deterministic and
    # independent of any ambient zlib tuning.
    image.save(dest, format="PNG", optimize=False, compress_level=6)
    return dest


def render_placeholder_clip(
    *,
    episode_id: str,
    shot_index: int,
    dest: Path,
    duration_s: int = DEFAULT_DURATION_S,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    ffmpeg_bin: str | None = None,
) -> Path:
    """Render a deterministic zero-spend placeholder clip.

    Video: `duration_s` seconds at `width`x`height` (9:16 portrait by
    default), H.264 (libx264) + yuv420p so every downstream ffmpeg/critic
    step can read it. Base plate is ffmpeg `smptebars`; a PIL-rendered label
    (episode_id, zero-padded shot_index, PLACEHOLDER, NO VEO SPEND) is
    composited on top via ffmpeg `overlay`.

    Determinism: two calls with identical (episode_id, shot_index,
    duration_s, width, height) on the SAME ffmpeg build are made
    byte-identical (identical sha256 of the output MP4) via:
      - `-fflags +bitexact -flags:v +bitexact` (removes the libx264 version
        SEI + any lavf timestamp banners from the bitstream/container —
        this is the same incantation ffmpeg's own FATE regression suite
        uses for reproducible encodes);
      - `-map_metadata -1` (drop all source/container metadata) plus a
        fixed `-metadata:s:v:0 encoder=` tag (overrides the
        Lavc<version>/libx264<build> string lavf would otherwise stamp,
        which would vary across ffmpeg installs though not across runs on
        THIS one);
      - a fixed `-r`/output frame rate and `-fps_mode cfr`;
      - `-threads 1` + `x264-params threads=1:sliced_threads=0` and
        `-filter_threads 1` (removes frame/slice-parallel encode ordering
        as a theoretical nondeterminism source — smptebars + overlay have
        no cross-frame state, but the encoder's bitstream packing can
        depend on thread interleaving without this);
      - a PIL-rendered label PNG that embeds no timestamp (see
        `_render_label_png`).
    This was verified empirically (not assumed) by rendering twice and
    comparing `shasum -a 256` — see the test suite for the exact command
    and the measured result, and do not trust this docstring over a fresh
    measurement if the ffmpeg build changes.

    Raises PlaceholderRenderError (never leaves a 0-byte/partial file at
    `dest`) if ffmpeg is missing or the render fails.
    """
    if duration_s <= 0:
        raise PlaceholderRenderError(f"duration_s must be positive, got {duration_s}")
    if width <= 0 or height <= 0:
        raise PlaceholderRenderError(f"width/height must be positive, got {width}x{height}")

    ffmpeg = _resolve_ffmpeg(ffmpeg_bin)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="wr3-placeholder-") as tmp_dir:
        label_png = Path(tmp_dir) / "label.png"
        try:
            _render_label_png(
                episode_id=episode_id,
                shot_index=shot_index,
                width=width,
                height=height,
                dest=label_png,
            )
        except Exception as exc:  # noqa: BLE001 — re-raise as our named error
            raise PlaceholderRenderError(f"failed to render label overlay PNG: {exc}") from exc

        tmp_dest = Path(tmp_dir) / "render.mp4"
        cmd = [
            ffmpeg,
            "-y",
            "-fflags",
            "+bitexact",
            "-f",
            "lavfi",
            "-i",
            f"smptebars=size={width}x{height}:rate={FRAME_RATE}:duration={duration_s}",
            "-i",
            str(label_png),
            "-filter_complex",
            "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p",
            "-filter_threads",
            "1",
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-metadata:s:v:0",
            f"encoder={_ENCODER_TAG}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-threads",
            "1",
            "-x264-params",
            "threads=1:sliced_threads=0",
            "-flags:v",
            "+bitexact",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FRAME_RATE),
            "-fps_mode",
            "cfr",
            "-t",
            str(duration_s),
            "-an",
            "-movflags",
            "+faststart",
            str(tmp_dest),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0 or not tmp_dest.exists() or tmp_dest.stat().st_size == 0:
            raise PlaceholderRenderError(
                "ffmpeg placeholder render failed "
                f"(returncode={result.returncode}): {result.stderr[-4000:]}"
            )

        # Atomic-ish move into place so a partially-written dest is never
        # observable by a concurrent reader (assembler/gatekeeper).
        shutil.move(str(tmp_dest), str(dest))

    if not dest.exists() or dest.stat().st_size == 0:
        raise PlaceholderRenderError(f"placeholder render reported success but {dest} is missing/empty")

    logger.info(
        "rendered zero-spend placeholder clip: episode=%s shot=%d dest=%s (%d bytes)",
        episode_id,
        shot_index,
        dest,
        dest.stat().st_size,
    )
    return dest


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-id", required=True, help="episode id, e.g. EP01")
    parser.add_argument("--shot-index", required=True, type=int, help="shot index, zero-padded in the label")
    parser.add_argument("--dest", required=True, type=Path, help="output .mp4 path")
    parser.add_argument("--duration-s", type=int, default=DEFAULT_DURATION_S)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--ffmpeg-bin", default=None, help="override ffmpeg binary path")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        out = render_placeholder_clip(
            episode_id=args.episode_id,
            shot_index=args.shot_index,
            dest=args.dest,
            duration_s=args.duration_s,
            width=args.width,
            height=args.height,
            ffmpeg_bin=args.ffmpeg_bin,
        )
    except PlaceholderRenderError as exc:
        logger.error("placeholder render failed: %s", exc)
        return 1
    print(str(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
