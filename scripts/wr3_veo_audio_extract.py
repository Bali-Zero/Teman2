#!/usr/bin/env python3
"""WR3 Veo audio nativo extractor — primary VO path (override 2026-05-22 Antonello).

Pilot-A `pilot-A-veo-zantara-lipsync.mp4` confirmed Veo 3.1 audio is Emma-grade lipsync.
This script extracts the embedded audio track from each `clips/<n>.mp4`, concatenates to
`audio/vo.wav`, measures LUFS, and deposits a copy in `~/Desktop/Zantara-Voice-Corpus/`
for future voice/avatar cloning (Chatterbox custom training at 50+ wav threshold).

Pipeline:
  1. ffprobe each clip → confirm audio stream present
  2. ffmpeg extract audio → audio/_segments/<n>.wav (PCM s16le 48kHz stereo)
  3. ffmpeg concat → audio/vo.wav
  4. ffmpeg loudnorm analyze → audio/lufs_report.json (per-clip + overall I/LRA/peak)
  5. If overall LUFS outside [-15, -13]: ffmpeg loudnorm corrective pass
  6. Copy audio/vo.wav → ~/Desktop/Zantara-Voice-Corpus/<episode_id>.wav

Exit codes:
  0   OK — Veo audio extracted, LUFS within bounds, corpus updated
  70  EX_SOFTWARE — audio stream missing from one or more clips (caller falls back to Chatterbox)
  75  EX_TEMPFAIL — overall LUFS catastrophic (>±5 from target -14) — caller falls back to Chatterbox

Idempotent: skips when audio/vo.wav + audio/lufs_report.json + corpus entry already exist.

Environment:
  WR3_FFMPEG_BIN          ffmpeg path (default /tmp/ffmpeg-full/ffmpeg, evermeet static)
  WR3_FFPROBE_BIN         ffprobe path (default /opt/homebrew/bin/ffprobe)
  WR3_VOICE_CORPUS_DIR    voice corpus dir (default ~/Desktop/Zantara-Voice-Corpus)
  WR3_VEO_LUFS_TARGET     LUFS target (default -14.0)
  WR3_VEO_LUFS_WINDOW     normalize window half-width (default 1.0 → [-15,-13])
  WR3_VEO_LUFS_FALLBACK   catastrophic threshold (default 5.0 → >±5 from target triggers fallback)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

EX_OK = 0
EX_SOFTWARE = 70
EX_TEMPFAIL = 75

LUFS_TARGET = float(os.environ.get("WR3_VEO_LUFS_TARGET", "-14.0"))
LUFS_WINDOW = float(os.environ.get("WR3_VEO_LUFS_WINDOW", "1.0"))
LUFS_FALLBACK_THRESHOLD = float(os.environ.get("WR3_VEO_LUFS_FALLBACK", "5.0"))


def _resolve_ffmpeg() -> str:
    candidate = os.environ.get("WR3_FFMPEG_BIN", "/tmp/ffmpeg-full/ffmpeg")
    if Path(candidate).exists():
        return candidate
    return shutil.which("ffmpeg") or ""


def _resolve_ffprobe() -> str:
    candidate = os.environ.get("WR3_FFPROBE_BIN", "/opt/homebrew/bin/ffprobe")
    if Path(candidate).exists():
        return candidate
    return shutil.which("ffprobe") or ""


@dataclass
class ClipLufs:
    clip: str
    input_i: float | None
    input_lra: float | None
    input_tp: float | None
    has_audio: bool


@dataclass
class LufsReport:
    target_lufs: float
    overall_input_i: float | None
    overall_input_lra: float | None
    overall_input_tp: float | None
    normalize_applied: bool
    per_clip: list[ClipLufs]
    fallback_required: bool
    reason: str


async def _probe_has_audio(ffprobe: str, mp4: Path) -> bool:
    proc = await asyncio.create_subprocess_exec(
        ffprobe,
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(mp4),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return b"audio" in stdout


async def _extract_audio(ffmpeg: str, mp4: Path, out_wav: Path) -> int:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        ffmpeg, "-y",
        "-i", str(mp4),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "48000",
        "-ac", "2",
        str(out_wav),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        print(f"[veo-audio] ffmpeg extract exit {proc.returncode} on {mp4.name}: "
              f"{err.decode('utf-8', 'replace')[:200]}", file=sys.stderr)
    return proc.returncode


async def _measure_lufs(ffmpeg: str, wav: Path) -> tuple[float | None, float | None, float | None]:
    """Returns (input_i, input_lra, input_tp) or (None, None, None) on parse failure."""
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-hide_banner", "-nostats",
        "-i", str(wav),
        "-af", f"loudnorm=I={LUFS_TARGET}:TP=-1.0:LRA=11:print_format=json",
        "-f", "null", "-",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    text = stderr.decode("utf-8", "replace")
    start = text.rfind("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        return (None, None, None)
    try:
        block = json.loads(text[start:end + 1])
        return (
            float(block.get("input_i", "nan")),
            float(block.get("input_lra", "nan")),
            float(block.get("input_tp", "nan")),
        )
    except (json.JSONDecodeError, ValueError):
        return (None, None, None)


async def _concat_wavs(ffmpeg: str, segments: list[Path], out_wav: Path) -> int:
    concat_list = out_wav.parent / "_segments" / "_concat.txt"
    concat_list.parent.mkdir(parents=True, exist_ok=True)
    concat_list.write_text("\n".join(f"file '{p.name}'" for p in segments))
    proc = await asyncio.create_subprocess_exec(
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(out_wav),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        print(f"[veo-audio] ffmpeg concat exit {proc.returncode}: "
              f"{err.decode('utf-8', 'replace')[:200]}", file=sys.stderr)
    return proc.returncode


async def _loudnorm_correct(ffmpeg: str, in_wav: Path) -> bool:
    """Apply ffmpeg loudnorm corrective pass in-place. Returns True on success."""
    corrected = in_wav.with_suffix(".normalized.wav")
    proc = await asyncio.create_subprocess_exec(
        ffmpeg, "-y",
        "-i", str(in_wav),
        "-af", f"loudnorm=I={LUFS_TARGET}:TP=-1.0:LRA=11",
        "-ar", "48000",
        "-ac", "2",
        str(corrected),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
    if proc.returncode != 0 or not corrected.exists():
        return False
    in_wav.unlink()
    corrected.rename(in_wav)
    return True


async def extract_episode_audio(episode_dir: Path, episode_id: str) -> tuple[int, LufsReport | None]:
    """Main loop: extract Veo audio from clips/, concat, measure LUFS, copy to corpus."""
    ffmpeg = _resolve_ffmpeg()
    ffprobe = _resolve_ffprobe()
    if not ffmpeg or not ffprobe:
        print(f"[veo-audio] missing toolchain: ffmpeg={ffmpeg!r} ffprobe={ffprobe!r}", file=sys.stderr)
        return EX_SOFTWARE, None

    clips_dir = episode_dir / "clips"
    audio_dir = episode_dir / "audio"
    segments_dir = audio_dir / "_segments"
    vo_path = audio_dir / "vo.wav"
    lufs_report_path = audio_dir / "lufs_report.json"
    corpus_dir = Path(os.environ.get(
        "WR3_VOICE_CORPUS_DIR",
        str(Path.home() / "Desktop" / "Zantara-Voice-Corpus"),
    )).expanduser()
    corpus_path = corpus_dir / f"{episode_id}.wav"

    if not clips_dir.exists():
        print(f"[veo-audio] clips/ missing: {clips_dir}", file=sys.stderr)
        return EX_SOFTWARE, None

    clips = sorted(clips_dir.glob("*.mp4"))
    if not clips:
        print(f"[veo-audio] no clips found under {clips_dir}", file=sys.stderr)
        return EX_SOFTWARE, None

    # Idempotence: skip when outputs exist (Symbiosis Law 7 — measure, don't redo)
    if vo_path.exists() and lufs_report_path.exists() and corpus_path.exists():
        print(f"[veo-audio] idempotent skip — outputs present for {episode_id}", file=sys.stderr)
        report_doc = json.loads(lufs_report_path.read_text())
        return EX_OK, LufsReport(**{
            "target_lufs": report_doc.get("target_lufs", LUFS_TARGET),
            "overall_input_i": report_doc.get("overall_input_i"),
            "overall_input_lra": report_doc.get("overall_input_lra"),
            "overall_input_tp": report_doc.get("overall_input_tp"),
            "normalize_applied": report_doc.get("normalize_applied", False),
            "per_clip": [ClipLufs(**c) for c in report_doc.get("per_clip", [])],
            "fallback_required": report_doc.get("fallback_required", False),
            "reason": report_doc.get("reason", "idempotent-skip"),
        })

    audio_dir.mkdir(parents=True, exist_ok=True)
    segments_dir.mkdir(parents=True, exist_ok=True)

    # Step 1+2: probe + extract per clip
    per_clip: list[ClipLufs] = []
    seg_wavs: list[Path] = []
    for idx, mp4 in enumerate(clips):
        has_audio = await _probe_has_audio(ffprobe, mp4)
        if not has_audio:
            per_clip.append(ClipLufs(clip=mp4.name, input_i=None, input_lra=None,
                                    input_tp=None, has_audio=False))
            report = LufsReport(
                target_lufs=LUFS_TARGET,
                overall_input_i=None, overall_input_lra=None, overall_input_tp=None,
                normalize_applied=False,
                per_clip=per_clip,
                fallback_required=True,
                reason=f"audio_missing:{mp4.name}",
            )
            lufs_report_path.write_text(json.dumps(_report_to_dict(report), indent=2))
            print(f"[veo-audio] EX_SOFTWARE: clip {mp4.name} has no audio stream", file=sys.stderr)
            return EX_SOFTWARE, report

        seg_wav = segments_dir / f"{idx:03d}.wav"
        rc = await _extract_audio(ffmpeg, mp4, seg_wav)
        if rc != 0 or not seg_wav.exists():
            report = LufsReport(
                target_lufs=LUFS_TARGET,
                overall_input_i=None, overall_input_lra=None, overall_input_tp=None,
                normalize_applied=False, per_clip=per_clip,
                fallback_required=True, reason=f"ffmpeg_extract_failed:{mp4.name}",
            )
            lufs_report_path.write_text(json.dumps(_report_to_dict(report), indent=2))
            return EX_SOFTWARE, report

        i, lra, tp = await _measure_lufs(ffmpeg, seg_wav)
        per_clip.append(ClipLufs(clip=mp4.name, input_i=i, input_lra=lra,
                                input_tp=tp, has_audio=True))
        seg_wavs.append(seg_wav)

    # Step 3: concat
    rc = await _concat_wavs(ffmpeg, seg_wavs, vo_path)
    if rc != 0 or not vo_path.exists():
        report = LufsReport(
            target_lufs=LUFS_TARGET,
            overall_input_i=None, overall_input_lra=None, overall_input_tp=None,
            normalize_applied=False, per_clip=per_clip,
            fallback_required=True, reason="ffmpeg_concat_failed",
        )
        lufs_report_path.write_text(json.dumps(_report_to_dict(report), indent=2))
        return EX_SOFTWARE, report

    # Step 4: overall LUFS measure
    overall_i, overall_lra, overall_tp = await _measure_lufs(ffmpeg, vo_path)

    # Step 4b: catastrophic LUFS check (>±5 from target) → fallback BEFORE corrective pass
    if overall_i is not None and abs(overall_i - LUFS_TARGET) > LUFS_FALLBACK_THRESHOLD:
        report = LufsReport(
            target_lufs=LUFS_TARGET,
            overall_input_i=overall_i, overall_input_lra=overall_lra, overall_input_tp=overall_tp,
            normalize_applied=False, per_clip=per_clip,
            fallback_required=True,
            reason=f"lufs_catastrophic:{overall_i:.2f}_vs_target_{LUFS_TARGET:.2f}",
        )
        lufs_report_path.write_text(json.dumps(_report_to_dict(report), indent=2))
        print(f"[veo-audio] EX_TEMPFAIL: LUFS {overall_i:.2f} outside ±{LUFS_FALLBACK_THRESHOLD} "
              f"from {LUFS_TARGET}", file=sys.stderr)
        return EX_TEMPFAIL, report

    # Step 5: corrective loudnorm if outside [-15, -13]
    normalize_applied = False
    if overall_i is not None and abs(overall_i - LUFS_TARGET) > LUFS_WINDOW:
        normalize_applied = await _loudnorm_correct(ffmpeg, vo_path)
        if normalize_applied:
            overall_i, overall_lra, overall_tp = await _measure_lufs(ffmpeg, vo_path)

    # Step 6: voice corpus accumulator
    corpus_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(vo_path, corpus_path)

    report = LufsReport(
        target_lufs=LUFS_TARGET,
        overall_input_i=overall_i, overall_input_lra=overall_lra, overall_input_tp=overall_tp,
        normalize_applied=normalize_applied, per_clip=per_clip,
        fallback_required=False,
        reason="ok",
    )
    lufs_report_path.write_text(json.dumps(_report_to_dict(report), indent=2))
    print(f"[veo-audio] OK episode={episode_id} lufs={overall_i} "
          f"corpus={corpus_path}", file=sys.stderr)
    return EX_OK, report


def _report_to_dict(r: LufsReport) -> dict:
    d = asdict(r)
    d["per_clip"] = [asdict(c) for c in r.per_clip]
    return d


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Veo native audio from WR3 clips/ → vo.wav")
    parser.add_argument("--episode-dir", required=True, type=Path,
                        help="apps/war-room/output/episode/<slug>/")
    parser.add_argument("--episode-id", required=True,
                        help="Episode slug for voice corpus filename")
    args = parser.parse_args()

    rc, _report = asyncio.run(extract_episode_audio(args.episode_dir.resolve(), args.episode_id))
    return rc


if __name__ == "__main__":
    sys.exit(main())
