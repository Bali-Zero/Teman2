"""
Image Generation Router - Handles image generation requests via Pollinations.ai (free)

UPDATED 2026-04-08: Removed Google Imagen (paid). Pollinations-only, zero cost.
"""

import logging
from urllib.parse import quote

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/image", tags=["image"])


class ImageGenerationRequest(BaseModel):
    prompt: str
    number_of_images: int = 1
    aspect_ratio: str = "1:1"


class ImageGenerationResponse(BaseModel):
    images: list[str]
    success: bool
    error: str | None = None


@router.post("/generate", response_model=ImageGenerationResponse)
async def generate_image(request: ImageGenerationRequest) -> ImageGenerationResponse:
    """
    Generate images using Pollinations.ai (free, no API key required).
    """
    if not request.prompt or not request.prompt.strip():
        return ImageGenerationResponse(
            images=[], success=False, error="Prompt cannot be empty",
        )

    try:
        encoded_prompt = quote(request.prompt)

        # Map aspect_ratio to Pollinations width/height params
        aspect_params = {
            "1:1": "width=1024&height=1024",
            "16:9": "width=1024&height=576",
            "9:16": "width=576&height=1024",
            "4:3": "width=1024&height=768",
            "3:4": "width=768&height=1024",
        }
        params = aspect_params.get(request.aspect_ratio, "width=1024&height=1024")

        images = [
            f"https://image.pollinations.ai/prompt/{encoded_prompt}?{params}&seed={i}&nologo=true"
            for i in range(request.number_of_images)
        ]

        logger.info(
            "Image generation via Pollinations: prompt=%s count=%d",
            request.prompt[:80],
            request.number_of_images,
        )

        return ImageGenerationResponse(images=images, success=True)

    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        return ImageGenerationResponse(
            images=[], success=False, error=f"Image generation failed: {e}",
        )
