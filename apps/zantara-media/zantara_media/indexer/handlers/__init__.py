"""Content extraction dispatcher for zantara-media indexer.

Dispatches to the appropriate handler based on MIME type.
"""

import logging

from .audio_handler import extract_audio
from .image_handler import extract_image
from .pdf_handler import extract_pdf
from .video_handler import extract_video

logger = logging.getLogger(__name__)

__all__ = [
    "extract_content",
    "extract_pdf",
    "extract_image",
    "extract_video",
    "extract_audio",
]


async def extract_content(
    file_data: bytes,
    mime_type: str,
    filename: str,
) -> tuple[str, dict]:
    """Dispatch to the right handler based on *mime_type*.

    Args:
        file_data: Raw file bytes.
        mime_type: MIME type string (e.g. ``"application/pdf"``).
        filename: Original filename (used for logging and heuristics).

    Returns:
        Tuple of ``(text, metadata)`` where *text* is extracted content
        (may be empty on failure) and *metadata* is a dict of handler details.
    """
    if mime_type == "application/pdf":
        return await extract_pdf(file_data, filename)
    elif mime_type.startswith("image/"):
        return await extract_image(file_data, filename)
    elif mime_type.startswith("video/"):
        return await extract_video(file_data, filename)
    elif mime_type.startswith("audio/"):
        return await extract_audio(file_data, filename)
    else:
        # Fallback: try to decode as UTF-8 text
        logger.debug("No specific handler for mime_type=%s, trying UTF-8 decode", mime_type)
        try:
            return file_data.decode("utf-8", errors="replace")[:50000], {}
        except Exception:
            return "", {"error": "unsupported_mime"}
