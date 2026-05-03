"""Image content extraction via Ollama vision model."""

import asyncio
import base64
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_VISION_MODEL = "qwen2.5vl:7b"
_VISION_PROMPT = (
    "Describe this image in detail for a content management system. "
    "Include: main subjects, setting, mood, colors, any text visible, "
    "and potential use cases for editorial content."
)
_TIMEOUT_S = 60.0


async def extract_image(file_data: bytes, filename: str) -> tuple[str, dict]:
    """Describe an image using Ollama vision model.

    Args:
        file_data: Raw image bytes (any format Ollama accepts).
        filename: Original filename (used for logging).

    Returns:
        Tuple of (description_text, metadata_dict).
        On error/timeout returns ("", {"error": "vision_timeout"}).
    """
    encoded = await asyncio.to_thread(base64.b64encode, file_data)
    b64_image = encoded.decode("ascii")

    payload = {
        "model": _VISION_MODEL,
        "prompt": _VISION_PROMPT,
        "images": [b64_image],
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            response = await client.post(
                f"{_OLLAMA_BASE_URL}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            description: str = data.get("response", "")
            return description, {"model": _VISION_MODEL, "source": "ollama_vision"}
    except httpx.TimeoutException:
        logger.warning("Ollama vision timed out for %s", filename)
        return "", {"error": "vision_timeout"}
    except Exception as exc:
        logger.error("Ollama vision failed for %s: %s", filename, exc)
        return "", {"error": "vision_timeout"}
