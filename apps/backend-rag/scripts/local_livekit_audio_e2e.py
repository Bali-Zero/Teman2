#!/usr/bin/env python3
"""End-to-end local audio smoke through a real LiveKit room.

The script can record a short microphone sample or use an existing WAV file.
It publishes the input audio into a local LiveKit room, runs the local STT/VAD
and Chatterbox TTS providers, then publishes the generated TTS WAV back into
the same room. Raw audio is written only to the requested local output dir.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import math
import os
import socket
import sys
import tempfile
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.app.core.config import settings
from backend.app.services.local_audio.chatterbox import ChatterboxTTSProvider
from backend.app.services.local_audio.runtime_checks import is_approved_voice_runtime_host
from backend.app.services.local_audio.silero_vad import SileroVADProvider
from backend.app.services.local_audio.whisper_cpp import WhisperCppSTTProvider

LOCAL_LIVEKIT_HOSTS = {"localhost", "127.0.0.1", "::1", "0:0:0:0:0:0:0:1"}
OFFLINE_ENV_GUARDS = {
    "DO_NOT_TRACK": "1",
    "HF_DATASETS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
}


@dataclass(frozen=True)
class WavInfo:
    sample_rate: int
    channels: int
    sample_width: int
    frames: int
    duration_seconds: float


class E2EPreflightError(RuntimeError):
    """Raised when the local E2E smoke must fail closed."""


def validate_runtime_host() -> None:
    if not is_approved_voice_runtime_host(socket.gethostname()):
        raise E2EPreflightError("local LiveKit audio E2E is allowed only on Pro/Mini")


def validate_offline_env() -> None:
    missing_or_wrong = [
        key for key, expected in OFFLINE_ENV_GUARDS.items() if os.environ.get(key) != expected
    ]
    if missing_or_wrong:
        raise E2EPreflightError("offline guard env missing or mismatched: " + ", ".join(missing_or_wrong))


def validate_livekit_env() -> tuple[str, str, str]:
    livekit_url = os.environ.get("LIVEKIT_URL", "").strip()
    api_key = os.environ.get("LIVEKIT_API_KEY", "").strip()
    api_secret = os.environ.get("LIVEKIT_API_SECRET", "").strip()
    if not livekit_url or not api_key or not api_secret:
        raise E2EPreflightError("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are required")

    parsed = urlparse(livekit_url)
    if parsed.scheme not in {"ws", "wss"} or parsed.hostname is None:
        raise E2EPreflightError("LIVEKIT_URL must be ws:// or wss://")
    if parsed.hostname.lower() not in LOCAL_LIVEKIT_HOSTS:
        raise E2EPreflightError("LIVEKIT_URL must point at loopback for this local E2E smoke")
    return livekit_url, api_key, api_secret


def ensure_livekit_sdk() -> tuple[Any, Any]:
    try:
        from livekit import api, rtc
    except ImportError as exc:
        raise E2EPreflightError(
            "LiveKit Python SDK is missing; install requirements-livekit-worker.txt "
            "into the local E2E virtualenv",
        ) from exc
    return api, rtc


def wav_info(path: Path) -> WavInfo:
    with wave.open(str(path), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        frames = wav_file.getnframes()
    if sample_width != 2:
        raise E2EPreflightError("E2E WAV input/output must be 16-bit PCM")
    if channels < 1:
        raise E2EPreflightError("E2E WAV must have at least one channel")
    return WavInfo(
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        frames=frames,
        duration_seconds=frames / sample_rate if sample_rate else 0.0,
    )


def record_microphone_wav(path: Path, *, seconds: float, sample_rate: int = 16_000) -> None:
    try:
        import sounddevice as sd  # type: ignore[import-not-found]
    except ImportError as exc:
        raise E2EPreflightError("sounddevice is required for --mic-seconds") from exc

    frame_count = max(1, int(seconds * sample_rate))
    recording = sd.rec(frame_count, samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(recording.tobytes())


def play_wav_output(path: Path) -> None:
    try:
        import sounddevice as sd  # type: ignore[import-not-found]
    except ImportError as exc:
        raise E2EPreflightError("sounddevice is required for --play-output") from exc

    info = wav_info(path)
    with wave.open(str(path), "rb") as wav_file:
        with sd.RawOutputStream(
            samplerate=info.sample_rate,
            channels=info.channels,
            dtype="int16",
        ) as stream:
            while True:
                chunk = wav_file.readframes(max(1, int(info.sample_rate * 0.02)))
                if not chunk:
                    break
                stream.write(chunk)


def write_synthetic_wav(path: Path, *, seconds: float = 1.0, sample_rate: int = 16_000) -> None:
    frame_count = max(1, int(seconds * sample_rate))
    amplitude = 1200
    frequency = 440.0
    frames = bytearray()
    for index in range(frame_count):
        sample = int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
        frames.extend(sample.to_bytes(2, byteorder="little", signed=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(frames))


@contextlib.contextmanager
def _redirect_stdout_to_stderr() -> Any:
    """Redirect Python and child-process stdout while preserving final JSON stdout."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved_stdout_fd = os.dup(1)
    try:
        os.dup2(2, 1)
        with contextlib.redirect_stdout(sys.stderr):
            yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(saved_stdout_fd, 1)
        os.close(saved_stdout_fd)


def build_access_token(
    *,
    api_module: Any,
    api_key: str,
    api_secret: str,
    room_name: str,
    identity: str,
) -> str:
    return (
        api_module.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(
            api_module.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            ),
        )
        .to_jwt()
    )


async def publish_wav_to_room(
    *,
    rtc_module: Any,
    room: Any,
    wav_path: Path,
    track_name: str,
    frame_ms: int = 20,
) -> WavInfo:
    info = wav_info(wav_path)
    source = rtc_module.AudioSource(info.sample_rate, info.channels)
    track = rtc_module.LocalAudioTrack.create_audio_track(track_name, source)
    await room.local_participant.publish_track(track)

    frames_per_chunk = max(1, int(info.sample_rate * frame_ms / 1000))
    with wave.open(str(wav_path), "rb") as wav_file:
        while True:
            chunk = wav_file.readframes(frames_per_chunk)
            if not chunk:
                break
            samples_per_channel = len(chunk) // (info.sample_width * info.channels)
            frame = rtc_module.AudioFrame(
                data=chunk,
                sample_rate=info.sample_rate,
                num_channels=info.channels,
                samples_per_channel=samples_per_channel,
            )
            await source.capture_frame(frame)
    await source.wait_for_playout()
    await source.aclose()
    return info


async def run_local_audio_roundtrip(input_wav: Path, output_dir: Path, *, tts_text: str) -> dict[str, Any]:
    whisper_binary = settings.voice_concierge_whisper_binary
    whisper_model = settings.voice_concierge_whisper_model
    if not whisper_binary or not whisper_model:
        raise E2EPreflightError("Whisper binary/model not configured")

    stt = WhisperCppSTTProvider(
        binary_path=Path(whisper_binary),
        model_path=Path(whisper_model),
        timeout_seconds=settings.voice_concierge_whisper_timeout_seconds,
    )
    vad = SileroVADProvider(
        module_name=settings.voice_concierge_silero_module,
        sampling_rate=settings.voice_concierge_silero_sampling_rate,
        threshold=settings.voice_concierge_silero_threshold,
        timeout_seconds=settings.voice_concierge_silero_timeout_seconds,
    )
    tts = ChatterboxTTSProvider(
        module_name=settings.voice_concierge_chatterbox_module,
        model_path=Path(settings.voice_concierge_chatterbox_model_path)
        if settings.voice_concierge_chatterbox_model_path
        else None,
        t3_model=settings.voice_concierge_chatterbox_t3_model,
        language_id=settings.voice_concierge_chatterbox_language,
        timeout_seconds=settings.voice_concierge_chatterbox_timeout_seconds,
    )

    segments = await vad.detect_segments(input_wav)
    transcript = await stt.transcribe(input_wav, language="en")
    tts_path = output_dir / "voice-concierge-e2e-tts.wav"
    tts_result = await tts.synthesize(tts_text, output_path=tts_path)
    return {
        "vad_segments": [asdict(segment) for segment in segments],
        "transcript": transcript.text,
        "transcript_provider": transcript.provider,
        "tts_path": str(tts_result.audio_path),
        "tts_provider": tts_result.provider,
    }


async def run_e2e(args: argparse.Namespace) -> dict[str, Any]:
    validate_runtime_host()
    validate_offline_env()
    livekit_url, api_key, api_secret = validate_livekit_env()
    api_module, rtc_module = ensure_livekit_sdk()

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    input_mode_count = sum(
        1
        for enabled in (
            bool(args.input_wav),
            args.mic_seconds is not None,
            bool(args.synthetic_input),
        )
        if enabled
    )
    if input_mode_count > 1:
        raise E2EPreflightError("choose only one input source: --input-wav, --mic-seconds, or --synthetic-input")
    if args.mic_seconds is not None and args.mic_seconds <= 0:
        raise E2EPreflightError("--mic-seconds must be positive")

    input_wav = Path(args.input_wav).expanduser() if args.input_wav else output_dir / "voice-concierge-e2e-input.wav"
    if args.mic_seconds is not None:
        await asyncio.to_thread(record_microphone_wav, input_wav, seconds=args.mic_seconds)
    elif args.synthetic_input:
        await asyncio.to_thread(write_synthetic_wav, input_wav)
    elif not input_wav.exists():
        raise E2EPreflightError("--input-wav must exist unless --mic-seconds or --synthetic-input is used")

    room_name = args.room or f"voice-local-e2e-{int(time.time())}"
    identity = args.identity or "voice-e2e-probe"
    token = build_access_token(
        api_module=api_module,
        api_key=api_key,
        api_secret=api_secret,
        room_name=room_name,
        identity=identity,
    )

    room = rtc_module.Room()
    await room.connect(livekit_url, token)
    try:
        input_info = await publish_wav_to_room(
            rtc_module=rtc_module,
            room=room,
            wav_path=input_wav,
            track_name="voice-e2e-input",
        )
        audio_result = await run_local_audio_roundtrip(
            input_wav,
            output_dir,
            tts_text=args.tts_text,
        )
        tts_info = await publish_wav_to_room(
            rtc_module=rtc_module,
            room=room,
            wav_path=Path(audio_result["tts_path"]),
            track_name="voice-e2e-tts",
        )
        played_output = False
        if args.play_output:
            await asyncio.to_thread(play_wav_output, Path(audio_result["tts_path"]))
            played_output = True
    finally:
        await room.disconnect()

    return {
        "ok": True,
        "room": room_name,
        "identity": identity,
        "input_wav": str(input_wav),
        "input_audio": asdict(input_info),
        "tts_audio": asdict(tts_info),
        "played_output": played_output,
        **audio_result,
        "constraints": [
            "local_only_audio",
            "no_cloud_fallback",
            "loopback_livekit_only",
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local LiveKit room audio E2E smoke")
    parser.add_argument("--input-wav")
    parser.add_argument("--mic-seconds", type=float)
    parser.add_argument("--synthetic-input", action="store_true")
    parser.add_argument("--output-dir", default=str(Path(tempfile.gettempdir()) / "nuz-local-audio-e2e"))
    parser.add_argument("--room")
    parser.add_argument("--identity")
    parser.add_argument("--tts-text", default="Local voice concierge audio path is ready.")
    parser.add_argument("--play-output", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.json:
            with _redirect_stdout_to_stderr():
                payload = asyncio.run(run_e2e(args))
        else:
            payload = asyncio.run(run_e2e(args))
    except Exception as exc:
        payload = {
            "ok": False,
            "error": type(exc).__name__,
            "detail": str(exc),
        }
    if args.json or not payload["ok"]:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("local LiveKit audio E2E: OK")
        print(f"room: {payload['room']}")
        print(f"input_wav: {payload['input_wav']}")
        print(f"tts_path: {payload['tts_path']}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
