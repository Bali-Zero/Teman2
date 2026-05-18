#!/usr/bin/env python3
"""WR3 Chatterbox local TTS — Zantara VO (Symbiosis Law 6 Sovranità locale).

Locked voice params for production Zantara (Emma seed):
  seed             42
  cfg_weight       0.30
  temperature      0.70
  exaggeration     0.32

Output:
  apps/war-room/output/episode/<slug>/audio/vo.wav (LUFS-normalized to -14 ±1)

Cartesia API is BANNED per Symbiosis Law 6 (cloud TTS = sovereignty violation).
Per-episode exception path: Antonello via Telegram P0 reply within 30 min.

Environment:
  WR3_CHATTERBOX_BIN     path to chatterbox-tts CLI (default: chatterbox-tts on PATH)
  WR3_CHATTERBOX_MODEL   model name (default: chatterbox-multilingual)
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

# Production Zantara voice locked params (do not modify without Antonello sign-off)
EMMA_SEED = 42
EMMA_CFG_WEIGHT = 0.30
EMMA_TEMPERATURE = 0.70
EMMA_EXAGGERATION = 0.32
LUFS_TARGET = -14.0
LUFS_TOLERANCE = 1.0


class ChatterboxError(Exception):
    """Base for Chatterbox-layer errors."""


class ChatterboxCrashError(ChatterboxError):
    """Chatterbox crashed mid-run. Episode degrades: no-VO + music + subtitles only."""


@dataclass(frozen=True)
class VOSegment:
    index: int
    start_ms: int
    text: str
    claim_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class VOResult:
    wav_path: Path
    duration_ms: int
    measured_lufs: float | None
    cascade_used: bool = False  # True if Cartesia exception path was taken


async def _run_chatterbox_cli(
    text: str,
    out_path: Path,
    *,
    bin_path: str,
    model: str,
    seed: int,
    cfg_weight: float,
    temperature: float,
    exaggeration: float,
    timeout_s: int,
) -> None:
    """Invoke chatterbox-tts CLI subprocess (Symbiosis Law 1 compliant)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        bin_path,
        "--model", model,
        "--seed", str(seed),
        "--cfg-weight", str(cfg_weight),
        "--temperature", str(temperature),
        "--exaggeration", str(exaggeration),
        "--out", str(out_path),
        "--text", text,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError as e:
        proc.kill()
        raise ChatterboxCrashError(
            f"Chatterbox timeout {timeout_s}s for {out_path.name}"
        ) from e

    if proc.returncode != 0:
        err = stderr.decode("utf-8", "replace")[:400]
        raise ChatterboxCrashError(
            f"Chatterbox exit {proc.returncode}: {err}"
        )


async def _measure_lufs(wav_path: Path) -> float | None:
    """Measure LUFS via ffmpeg loudnorm filter (analyze pass).

    Returns None if ffmpeg or the loudnorm filter is unavailable.
    """
    ffmpeg = os.environ.get("WR3_FFMPEG_BIN", "/tmp/ffmpeg-full/ffmpeg")
    if not Path(ffmpeg).exists():
        ffmpeg = shutil.which("ffmpeg") or ""
    if not ffmpeg:
        return None

    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-hide_banner", "-nostats",
        "-i", str(wav_path),
        "-af", "loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json",
        "-f", "null", "-",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    text = stderr.decode("utf-8", "replace")
    # ffmpeg writes the JSON block to stderr; find {…} block
    start = text.rfind("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        return None
    try:
        block = json.loads(text[start : end + 1])
        return float(block.get("input_i", "nan"))
    except (json.JSONDecodeError, ValueError):
        return None


async def generate_voiceover(
    script_path: Path,
    episode_dir: Path,
    *,
    chatterbox_bin: str | None = None,
    model: str = "chatterbox-multilingual",
    per_segment_timeout_s: int = 60,
) -> VOResult:
    """Generate VO WAV from script.json segments.

    Concatenates per-segment WAV via ffmpeg into vo.wav. LUFS-normalize to -14 ±1.
    """
    bin_path = chatterbox_bin or os.environ.get("WR3_CHATTERBOX_BIN", "chatterbox-tts")
    if not shutil.which(bin_path):
        raise ChatterboxCrashError(
            f"chatterbox-tts CLI not found at {bin_path!r}. "
            "Install: brew install chatterbox-multilingual (or path via WR3_CHATTERBOX_BIN)"
        )

    script = json.loads(script_path.read_text())
    segments_raw = script.get("segments") or []
    if not segments_raw:
        raise ChatterboxError(f"script.json has no segments: {script_path}")

    audio_dir = episode_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    segments_tmp_dir = audio_dir / "_segments"
    segments_tmp_dir.mkdir(exist_ok=True)

    seg_wavs: list[Path] = []
    started = asyncio.get_event_loop().time()
    for i, seg in enumerate(segments_raw):
        seg_text = seg.get("text", "").strip()
        if not seg_text:
            continue
        seg_path = segments_tmp_dir / f"{i:03d}.wav"
        await _run_chatterbox_cli(
            text=seg_text,
            out_path=seg_path,
            bin_path=bin_path,
            model=model,
            seed=EMMA_SEED,
            cfg_weight=EMMA_CFG_WEIGHT,
            temperature=EMMA_TEMPERATURE,
            exaggeration=EMMA_EXAGGERATION,
            timeout_s=per_segment_timeout_s,
        )
        seg_wavs.append(seg_path)

    if not seg_wavs:
        raise ChatterboxError("All segments empty — no VO to render")

    # Concat via ffmpeg
    ffmpeg = os.environ.get("WR3_FFMPEG_BIN", "/tmp/ffmpeg-full/ffmpeg")
    if not Path(ffmpeg).exists():
        ffmpeg = shutil.which("ffmpeg") or ""
    if not ffmpeg:
        raise ChatterboxError("ffmpeg not found for VO concat")

    concat_list = segments_tmp_dir / "_concat.txt"
    concat_list.write_text("\n".join(f"file '{p.name}'" for p in seg_wavs))

    vo_path = audio_dir / "vo.wav"
    proc = await asyncio.create_subprocess_exec(
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(vo_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise ChatterboxError(
            f"ffmpeg concat exit {proc.returncode}: {stderr.decode('utf-8', 'replace')[:200]}"
        )

    measured = await _measure_lufs(vo_path)
    duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)

    if measured is not None and abs(measured - LUFS_TARGET) > LUFS_TOLERANCE:
        # Out of LUFS tolerance — apply loudnorm corrective pass
        normalized = audio_dir / "vo_normalized.wav"
        proc = await asyncio.create_subprocess_exec(
            ffmpeg, "-y",
            "-i", str(vo_path),
            "-af", f"loudnorm=I={LUFS_TARGET}:TP=-1.0:LRA=11",
            str(normalized),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        if normalized.exists():
            vo_path.unlink()
            normalized.rename(vo_path)
            measured = await _measure_lufs(vo_path)

    return VOResult(
        wav_path=vo_path,
        duration_ms=duration_ms,
        measured_lufs=measured,
    )


if __name__ == "__main__":
    import sys
    print(f"chatterbox bin: {os.environ.get('WR3_CHATTERBOX_BIN', 'chatterbox-tts')}", file=sys.stderr)
    print(f"emma seed={EMMA_SEED} cfg={EMMA_CFG_WEIGHT} temp={EMMA_TEMPERATURE} exag={EMMA_EXAGGERATION}", file=sys.stderr)
