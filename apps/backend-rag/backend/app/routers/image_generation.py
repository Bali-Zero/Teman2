"""
Image Generation Router - Handles image generation requests
"""

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/api/v1/image", tags=["image"])


class ImageGenerationRequest(BaseModel):
    prompt: str
    number_of_images: int = 1
    aspect_ratio: str = "1:1"
    safety_filter_level: str = "block_some"
    person_generation: str = "allow_adult"


class ImageGenerationResponse(BaseModel):
    images: list[str]
    success: bool
    error: str | None = None


@router.post("/generate", response_model=ImageGenerationResponse)
async def generate_image(request: ImageGenerationRequest):
    """
    Generate images using Google Imagen API

    Args:
        request: Image generation request with prompt and parameters

    Returns:
        ImageGenerationResponse with generated images or error
    """
    # Use dedicated Imagen API key if available, otherwise fallback to google_api_key
    imagen_api_key = getattr(settings, "google_imagen_api_key", None) or getattr(
        settings, "google_api_key", None
    )

    if not imagen_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google Imagen API key not configured. Set GOOGLE_IMAGEN_API_KEY or GOOGLE_API_KEY environment variable.",
        )

    # SECURITY: Use API key in header instead of URL to prevent logging exposure
    url = "https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict"

    payload = {
        "prompt": request.prompt,
        "number_of_images": request.number_of_images,
        "aspect_ratio": request.aspect_ratio,
        "safety_filter_level": request.safety_filter_level,
        "person_generation": request.person_generation,
        "language": "auto",
    }

    # Use API key in header (X-Goog-Api-Key) instead of query parameter
    headers = {
        "X-Goog-Api-Key": imagen_api_key,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Imagen API not enabled or insufficient permissions. Please check Google Cloud console.",
                )

            response.raise_for_status()

            result = response.json()

            # Extract generated images
            images = []
            if "generatedImages" in result:
                for img in result["generatedImages"]:
                    if "bytesBase64Encoded" in img:
                        # Convert base64 to data URL
                        images.append(f"data:image/png;base64,{img['bytesBase64Encoded']}")

            return ImageGenerationResponse(images=images, success=len(images) > 0)

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code, detail=f"Image generation failed: {e.response.text}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during image generation: {str(e)}",
        ) from e
