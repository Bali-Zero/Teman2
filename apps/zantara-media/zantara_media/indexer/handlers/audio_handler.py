"""Audio transcription handler using local Whisper CLI."""

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_WHISPER_MODEL = "medium"
_WHISPER_TIMEOUT_S = 300


async def extract_audio(file_data: bytes, filename: str) -> tuple[str, dict]:
    """Transcribe audio using the local Whisper CLI.

    Args:
        file_data: Raw audio bytes (any format Whisper/ffmpeg accepts).
        filename: Original filename, used to determine the output .txt stem.

    Returns:
        Tuple of (transcript_text, metadata_dict).
        On error/timeout returns ("", {"error": "whisper_failed"}).
    """
    suffix = Path(filename).suffix or ".audio"

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        audio_file = tmp_dir / f"audio_input{suffix}"
        await asyncio.to_thread(audio_file.write_bytes, file_data)

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    subprocess.run,
                    [
                        "whisper",
                        str(audio_file),
                        "--model", _WHISPER_MODEL,
                        "--output_format", "txt",
                        "--output_dir", str(tmp_dir),
                    ],
                    capture_output=True,
                    text=True,
                ),
                timeout=_WHISPER_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.error("Whisper timed out after %ds for %s", _WHISPER_TIMEOUT_S, filename)
            return "", {"error": "whisper_failed"}
        except Exception as exc:
            logger.error("Whisper subprocess error for %s: %s", filename, exc)
            return "", {"error": "whisper_failed"}

        if result.returncode != 0:
            logger.warning(
                "Whisper exited %d for %s: %s",
                result.returncode, filename, result.stderr
            )

        # Whisper writes <stem>.txt — match against the audio input stem
        txt_stem = audio_file.stem
        txt_path = tmp_dir / f"{txt_stem}.txt"
        if not txt_path.exists():
            # Try any .txt in the dir as fallback
            txt_files = list(tmp_dir.glob("*.txt"))
            if txt_files:
                txt_path = txt_files[0]
            else:
                logger.error("Whisper output .txt not found for %s", filename)
                return "", {"error": "whisper_failed"}

        try:
            transcript = await asyncio.to_thread(txt_path.read_text, "utf-8")
        except Exception as exc:
            logger.error("Could not read Whisper output for %s: %s", filename, exc)
            return "", {"error": "whisper_failed"}

    return transcript, {"model": f"whisper-{_WHISPER_MODEL}", "source": "local_whisper"}
