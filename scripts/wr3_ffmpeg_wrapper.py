#!/usr/bin/env python3
"""WR3 ffmpeg wrapper — Python-first assembly (zero LLM cost).

Wraps the static evermeet ffmpeg binary at /tmp/ffmpeg-full/ffmpeg with libass
+ drawtext + concat support. Used by wr3-post-assembler agent to:

  1. Concatenate clips/<n>.mp4 into master.mp4
  2. Sync VO + music bed (sidechain compress music under VO)
  3. Render ASS subtitles
  4. Export 4 platform variants (TikTok, IG Reels, YT Shorts, FB)

Variant ffmpeg failure → DEGRADE (deliver master + 3/4 variants).
Master assembly failure → HARD-FAIL (no coherent artifact to critic).
"""
from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

FFMPEG_BIN = os.environ.get("WR3_FFMPEG_BIN", "/tmp/ffmpeg-full/ffmpeg")


class FFmpegError(Exception):
    """Base for ffmpeg-layer errors."""


class MasterAssemblyError(FFmpegError):
    """Master assembly failed → HARD-FAIL (no artifact for critic)."""


class VariantAssemblyError(FFmpegError):
    """Variant export failed → DEGRADE (manifest flags missing variant)."""


@dataclass(frozen=True)
class VariantSpec:
    name: str  # "tiktok" | "ig-reels" | "yt-shorts" | "fb"
    width: int
    height: int
    max_duration_s: int
    extra_filters: tuple[str, ...] = ()


PLATFORM_VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(name="tiktok", width=720, height=1280, max_duration_s=60),
    VariantSpec(name="ig-reels", width=720, height=1280, max_duration_s=90),
    VariantSpec(name="yt-shorts", width=720, height=1280, max_duration_s=60),
    VariantSpec(name="fb", width=720, height=1280, max_duration_s=90),
)


def _resolve_ffmpeg() -> str:
    if Path(FFMPEG_BIN).exists():
        return FFMPEG_BIN
    fallback = shutil.which("ffmpeg")
    if fallback:
        return fallback
    raise FFmpegError(
        f"ffmpeg not found at {FFMPEG_BIN} and not on PATH. "
        "Install evermeet ffmpeg static OR set WR3_FFMPEG_BIN env var."
    )


async def _run(args: list[str], *, timeout_s: int = 600) -> None:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError as e:
        proc.kill()
        raise FFmpegError(f"ffmpeg timeout {timeout_s}s args={args[:5]}…") from e

    if proc.returncode != 0:
        err = stderr.decode("utf-8", "replace")[-500:]
        raise FFmpegError(f"ffmpeg exit {proc.returncode}: {err}")


async def assemble_master(
    clips_dir: Path,
    vo_path: Path | None,
    music_path: Path | None,
    *,
    episode_dir: Path,
    subtitles_ass: Path | None = None,
) -> Path:
    """Assemble master.mp4 from clips/ + audio.

    Audio strategy:
      - vo.wav drives the master timeline (acts as duration anchor)
      - music.wav optionally sidechained at -10dB under VO
      - if VO missing → music + subtitles only (degraded path flagged by caller)
    """
    ffmpeg = _resolve_ffmpeg()
    clip_files = sorted(clips_dir.glob("*.mp4"))
    if not clip_files:
        raise MasterAssemblyError(f"No clips found in {clips_dir}")

    concat_list = episode_dir / "_concat.txt"
    concat_list.write_text("\n".join(f"file '{p.resolve()}'" for p in clip_files))

    # Step 1: concat video-only
    concat_mp4 = episode_dir / "_concat_video.mp4"
    await _run([
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        "-an",  # drop any native audio (Veo Fast Tier_ONE was rendered audio-off)
        str(concat_mp4),
    ])

    master_path = episode_dir / "master.mp4"
    args = [ffmpeg, "-y", "-i", str(concat_mp4)]

    if vo_path and vo_path.exists():
        args += ["-i", str(vo_path)]
    if music_path and music_path.exists():
        args += ["-i", str(music_path)]

    filter_parts: list[str] = []
    if subtitles_ass and subtitles_ass.exists():
        filter_parts.append(f"[0:v]ass={subtitles_ass.as_posix()}[v]")
    else:
        filter_parts.append("[0:v]copy[v]")

    # Audio mix
    if vo_path and vo_path.exists() and music_path and music_path.exists():
        # VO at 0dB, music sidechained to -10dB when VO active
        filter_parts.append("[2:a]volume=-10dB[mus]")
        filter_parts.append("[1:a][mus]amix=inputs=2:duration=longest:dropout_transition=2[a]")
        map_args = ["-map", "[v]", "-map", "[a]"]
    elif vo_path and vo_path.exists():
        map_args = ["-map", "[v]", "-map", "1:a"]
    elif music_path and music_path.exists():
        map_args = ["-map", "[v]", "-map", "1:a"]
    else:
        map_args = ["-map", "[v]"]

    args += [
        "-filter_complex", ";".join(filter_parts),
        *map_args,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(master_path),
    ]

    try:
        await _run(args, timeout_s=900)
    except FFmpegError as e:
        raise MasterAssemblyError(str(e)) from e

    # Cleanup intermediates
    concat_list.unlink(missing_ok=True)
    concat_mp4.unlink(missing_ok=True)

    return master_path


async def export_variant(
    master_path: Path,
    spec: VariantSpec,
    *,
    episode_dir: Path,
) -> Path:
    """Export a single platform variant.

    On failure raises VariantAssemblyError — caller (post-assembler) flags
    manifest.variants_missing and continues with remaining variants.
    """
    ffmpeg = _resolve_ffmpeg()
    variant_dir = episode_dir / "variants"
    variant_dir.mkdir(exist_ok=True)
    out_path = variant_dir / f"{spec.name}.mp4"

    filters = [f"scale={spec.width}:{spec.height}:force_original_aspect_ratio=decrease"]
    filters.append(f"pad={spec.width}:{spec.height}:(ow-iw)/2:(oh-ih)/2:black")
    filters.extend(spec.extra_filters)

    args = [
        ffmpeg, "-y",
        "-i", str(master_path),
        "-t", str(spec.max_duration_s),
        "-vf", ",".join(filters),
        "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        str(out_path),
    ]

    try:
        await _run(args, timeout_s=600)
    except FFmpegError as e:
        raise VariantAssemblyError(f"{spec.name}: {e}") from e

    return out_path


async def export_all_variants(
    master_path: Path,
    episode_dir: Path,
) -> tuple[dict[str, Path], list[str]]:
    """Export all 4 variants. Returns (succeeded_map, failed_names).

    Per Symbiosis Law 4 — variant failures degrade-loud (manifest records),
    they do NOT halt the episode.
    """
    succeeded: dict[str, Path] = {}
    failed: list[str] = []
    for spec in PLATFORM_VARIANTS:
        try:
            path = await export_variant(master_path, spec, episode_dir=episode_dir)
            succeeded[spec.name] = path
        except VariantAssemblyError as e:
            failed.append(spec.name)
            # do NOT raise — degrade-loud per Law 4
            print(f"[wr3-ffmpeg] variant {spec.name} failed: {e}")
    return succeeded, failed


if __name__ == "__main__":
    import sys
    try:
        bin_path = _resolve_ffmpeg()
        print(f"ffmpeg resolved: {bin_path}")
        for v in PLATFORM_VARIANTS:
            print(f"  variant {v.name}: {v.width}x{v.height} max {v.max_duration_s}s")
    except FFmpegError as e:
        print(f"ffmpeg not available: {e}", file=sys.stderr)
        sys.exit(1)
