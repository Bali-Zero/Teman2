"""Video content extraction: frame sampling + Ollama vision description."""

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

from .image_handler import extract_image

logger = logging.getLogger(__name__)

_FRAME_POSITIONS = (0.15, 0.50, 0.85)


async def extract_video(file_data: bytes, filename: str) -> tuple[str, dict]:
    """Extract text description from a video by sampling 3 frames via ffmpeg.

    Frames at 15%, 50%, 85% of the video duration are extracted and described
    using the Ollama vision model via :func:`extract_image`.

    Args:
        file_data: Raw video bytes.
        filename: Original filename (used for logging).

    Returns:
        Tuple of (concatenated_descriptions, metadata_dict).
    """
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        tmp_video = tmp_dir / "input_video"
        await asyncio.to_thread(tmp_video.write_bytes, file_data)

        # --- get duration via ffprobe ---
        duration = await _get_duration(tmp_video, filename)
        if duration is None:
            return "", {"error": "ffprobe_failed"}

        # --- extract frames ---
        timestamps = [duration * pos for pos in _FRAME_POSITIONS]
        frame_paths: list[Path] = []
        for i, ts in enumerate(timestamps):
            frame_path = tmp_dir / f"frame_{i}.jpg"
            await asyncio.to_thread(
                _run_ffmpeg_frame,
                str(tmp_video),
                str(frame_path),
                ts,
            )
            if frame_path.exists():
                frame_paths.append(frame_path)
            else:
                logger.warning("Frame %d extraction failed for %s", i, filename)

        if not frame_paths:
            return "", {"error": "no_frames_extracted"}

        # --- describe each frame ---
        descriptions: list[str] = []
        for frame_path in frame_paths:
            frame_data = await asyncio.to_thread(frame_path.read_bytes)
            desc, _ = await extract_image(frame_data, frame_path.name)
            if desc:
                descriptions.append(desc)

    concatenated = "\n---\n".join(descriptions)
    return concatenated, {
        "frames_extracted": len(frame_paths),
        "duration_s": duration,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_duration(video_path: Path, filename: str) -> float | None:
    """Return video duration in seconds using ffprobe."""
    result = await asyncio.to_thread(
        subprocess.run,
        [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError):
        logger.error("ffprobe could not determine duration for %s: %s", filename, result.stderr)
        return None


def _run_ffmpeg_frame(input_path: str, output_path: str, timestamp: float) -> None:
    """Blocking ffmpeg call to extract a single frame — run inside asyncio.to_thread."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss", str(timestamp),
            "-i", input_path,
            "-frames:v", "1",
            "-q:v", "2",
            output_path,
        ],
        capture_output=True,
        check=False,
    )
