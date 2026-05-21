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


# Lazy-loaded Chatterbox model (heavy: torch + transformers + tokenizers +
# ~10GB weights downloaded on first run from Resemble AI HuggingFace).
# Re-used across segments within an episode — model load is the dominant cost.
_CHATTERBOX_MODEL = None  # type: ignore[var-annotated]


def _get_chatterbox_model():
    """Load ChatterboxMultilingualTTS once per process, cache on module."""
    global _CHATTERBOX_MODEL
    if _CHATTERBOX_MODEL is not None:
        return _CHATTERBOX_MODEL

    try:
        import torch  # type: ignore
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # type: ignore
    except ImportError as e:
        raise ChatterboxCrashError(
            "chatterbox-tts not installed in active venv. "
            "pip install chatterbox-tts. "
            f"Underlying: {e}"
        ) from e

    # Device selection: prefer MPS on Mac, CUDA on NVIDIA, else CPU.
    # NOTE: Chatterbox 0.1.7 checkpoints reference cuda storage tensors —
    # `from_pretrained(device="mps")` actually passes map_location="mps" but
    # the unpickler still hits cuda location strings and crashes. The only
    # safe load path right now is CPU.
    # Override via WR3_CHATTERBOX_DEVICE="mps"|"cuda"|"cpu" if a future
    # Chatterbox release fixes the checkpoint encoding.
    requested = os.environ.get("WR3_CHATTERBOX_DEVICE", "cpu").lower()
    if requested == "mps" and torch.backends.mps.is_available():
        device = torch.device("mps")
    elif requested == "cuda" and torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    # Defense in depth: patch torch.load to inject map_location even when
    # mtl_tts.from_local() calls it. Required for cross-device weight load.
    _orig_torch_load = torch.load

    def _patched_load(*args, **kwargs):
        kwargs["map_location"] = device  # always force, overriding any caller value
        return _orig_torch_load(*args, **kwargs)

    torch.load = _patched_load
    try:
        _CHATTERBOX_MODEL = ChatterboxMultilingualTTS.from_pretrained(device=device)
    finally:
        torch.load = _orig_torch_load
    return _CHATTERBOX_MODEL


async def _generate_segment_in_thread(
    text: str,
    out_path: Path,
    *,
    language_id: str,
    seed: int,
    cfg_weight: float,
    temperature: float,
    exaggeration: float,
    timeout_s: int,
) -> None:
    """Generate one segment WAV via ChatterboxMultilingualTTS Python API.

    Runs the CPU/MPS-bound generate() in a worker thread so the asyncio
    event loop doesn't block. Symbiosis Law 1 compliant: model is local
    (Resemble AI MIT, no cloud TTS).

    Indonesian (`id`) NOT in SUPPORTED_LANGUAGES — caller must pre-select
    `en` for English scripts or fall back to MiniMax for Indonesian VO.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _do_generate() -> None:
        import soundfile as sf  # type: ignore
        import torch  # type: ignore

        model = _get_chatterbox_model()
        # Pin seed for deterministic output
        torch.manual_seed(seed)
        if torch.backends.mps.is_available():
            torch.mps.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        wav = model.generate(
            text=text,
            language_id=language_id,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            temperature=temperature,
        )
        # ChatterboxMultilingualTTS returns a torch.Tensor [1, samples] at S3_SR (24000)
        from chatterbox.mtl_tts import S3GEN_SR  # type: ignore
        if hasattr(wav, "cpu"):
            wav = wav.cpu().numpy().squeeze()
        sf.write(str(out_path), wav, samplerate=S3GEN_SR, subtype="PCM_16")

    try:
        await asyncio.wait_for(asyncio.to_thread(_do_generate), timeout=timeout_s)
    except asyncio.TimeoutError as e:
        raise ChatterboxCrashError(
            f"Chatterbox generate timeout {timeout_s}s for {out_path.name}"
        ) from e
    except Exception as e:
        raise ChatterboxCrashError(
            f"Chatterbox generate failed for {out_path.name}: {e}"
        ) from e


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
    chatterbox_bin: str | None = None,  # legacy, unused (kept for caller compat)
    model: str = "chatterbox-multilingual",  # legacy
    per_segment_timeout_s: int = 120,
    language_id: str = "en",  # Indonesian not in SUPPORTED_LANGUAGES — see Voice-Clone-Pilot-2026-05-16
) -> VOResult:
    """Generate VO WAV from script.json segments via Chatterbox Python API.

    Concatenates per-segment WAV via ffmpeg into vo.wav. LUFS-normalize to -14 ±1.

    The Chatterbox model (~10GB) is loaded once per process and reused across
    segments via `_get_chatterbox_model()`. First call may take 30-60s for
    HuggingFace download + warmup; subsequent generates are 3-8s each.
    """
    # chatterbox_bin / model kwargs preserved for backward-compat with the
    # WR3_CHATTERBOX_BIN env var contract documented in __doc__ above —
    # they are not used by the Python API path. CLI path is removed.
    del chatterbox_bin, model  # explicit "intentionally unused"

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
        await _generate_segment_in_thread(
            text=seg_text,
            out_path=seg_path,
            language_id=language_id,
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
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="WR3 Chatterbox runner — local Emma-seed TTS fallback path"
    )
    parser.add_argument(
        "--mode",
        choices=("primary", "fallback"),
        default=os.environ.get("WR3_CHATTERBOX_MODE", "fallback"),
        help=(
            "Operational mode (default 'fallback' per override 2026-05-22 — Veo audio nativo "
            "is the primary path; Chatterbox engages only on LUFS catastrophe or missing audio). "
            "Mode is informational/logging only; voice params remain Emma-locked."
        ),
    )
    args, _ = parser.parse_known_args()

    print(f"chatterbox bin: {os.environ.get('WR3_CHATTERBOX_BIN', 'chatterbox-tts')}", file=sys.stderr)
    print(
        f"emma seed={EMMA_SEED} cfg={EMMA_CFG_WEIGHT} temp={EMMA_TEMPERATURE} exag={EMMA_EXAGGERATION}",
        file=sys.stderr,
    )
    print(f"mode={args.mode} (Veo native primary path, Chatterbox fallback role)", file=sys.stderr)
