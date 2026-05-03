"""
Image Generation Service for ZANTARA
Uses Pollinations.ai (free, no API key required) for image generation.

UPDATED 2026-04-08:
- Removed Google Imagen dependency (paid API). Pollinations-only, zero cost.
"""

import logging
from urllib.parse import quote

from typing import Any

logger = logging.getLogger(__name__)


class ImageGenerationService:
    """
    Service to generate images using Pollinations.ai (free, no API key).
    """

    def __init__(self, api_key: str | None = None) -> None:
        # api_key param kept for backward compatibility but ignored.
        logger.info("ImageGenerationService initialized (Pollinations.ai, free)")

    async def generate_image(self, prompt: str) -> dict[str, Any]:
        """
        Generates an image from a text prompt via Pollinations.ai.
        Returns a structured response with success/error information.
        """
        if not prompt or not prompt.strip():
            return {
                "success": False,
                "error": "Invalid prompt",
                "details": "Prompt cannot be empty",
            }

        try:
            logger.info(f"Generating image for prompt: {prompt[:100]}...")

            image_url = f"https://image.pollinations.ai/prompt/{quote(prompt)}"

            logger.info(f"Image generated successfully: {image_url}")

            return {
                "success": True,
                "url": image_url,
                "prompt": prompt,
                "service": "pollinations",
            }

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {"success": False, "error": "Image generation failed", "details": str(e)}
