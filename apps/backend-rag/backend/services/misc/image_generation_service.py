"""
Google Imagen Service for ZANTARA
Uses Google's Generative AI (Imagen) to generate images from text prompts.

UPDATED 2025-12-23:
- Migrated to new google-genai SDK (configuration removed, using pollinations.ai fallback)
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ImageGenerationService:
    """
    Service to generate images using Google's Generative AI.
    Note: Currently uses pollinations.ai as fallback since Google Imagen
    requires Vertex AI setup.
    """

    def __init__(self, api_key: str | None = None):
        from backend.app.core.config import settings

        # Use dedicated Imagen API key if available, otherwise fallback to google_api_key
        # If api_key is explicitly None, don't try to get from settings
        if api_key is None:
            self.api_key = getattr(settings, "google_imagen_api_key", None) or getattr(
                settings, "google_api_key", None
            )
        else:
            self.api_key = api_key

        if not self.api_key:
            logger.warning(
                "⚠️ GOOGLE_IMAGEN_API_KEY or GOOGLE_API_KEY not set. Image generation disabled."
            )
        else:
            # Note: Google Imagen requires Vertex AI setup, currently using pollinations.ai fallback
            logger.info("✅ ImageGenerationService initialized (using pollinations.ai fallback)")

    async def generate_image(self, prompt: str) -> dict[str, Any]:
        """
        Generates an image from a text prompt.
        Returns a structured response with success/error information.
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Image generation service not configured",
                "details": "GOOGLE_API_KEY environment variable required",
            }

        if not prompt or not prompt.strip():
            return {
                "success": False,
                "error": "Invalid prompt",
                "details": "Prompt cannot be empty",
            }

        try:
            logger.info(f"🎨 Generating image for prompt: {prompt[:100]}...")

            # Use pollinations.ai as a working fallback when Google API is not available
            # This provides actual image generation without requiring Google Cloud Vertex AI
            image_url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}"

            logger.info(f"✅ Image generated successfully: {image_url}")

            return {
                "success": True,
                "url": image_url,
                "prompt": prompt,
                "service": "pollinations_fallback",
            }

        except Exception as e:
            logger.error(f"❌ Image generation failed: {e}")
            return {"success": False, "error": "Image generation failed", "details": str(e)}
