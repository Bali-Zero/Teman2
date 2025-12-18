"""
ZANTARA MEDIA - Media Generation Router
AI-powered image and video generation using Google Gemini + ImagineArt

Endpoints:
- /media/image/generate - Generate images from text
- /media/image/social - Generate social media images
- /media/video/generate - Generate videos from images
- /media/analyze - Analyze images with Gemini vision
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.config import settings
from app.services.google_ai import get_google_client, GoogleAIClient
from app.services.imagine_art import (
    get_imagine_client,
    ImagineArtClient,
    ImageStyle,
    AspectRatio,
    VideoModel,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# Request/Response Models
class ImageGenerateRequest(BaseModel):
    prompt: str
    style: str = "REALISTIC"
    aspect_ratio: str = "1:1"
    negative_prompt: Optional[str] = None


class SocialImageRequest(BaseModel):
    topic: str
    platform: str = "instagram"
    mood: str = "professional"


class VideoGenerateRequest(BaseModel):
    prompt: str
    duration: int = 4
    style: str = "REALISTIC"


class ImageAnalyzeRequest(BaseModel):
    prompt: str = "Describe this image in detail"


class GenerationResponse(BaseModel):
    success: bool
    url: Optional[str] = None
    format: str = "png"
    width: int = 0
    height: int = 0
    generation_time_ms: int = 0
    credits_used: int = 0
    error: Optional[str] = None


def _get_imagine() -> ImagineArtClient:
    """Get ImagineArt client."""
    if not settings.imagineart_api_key:
        raise HTTPException(status_code=500, detail="ImagineArt API key not configured")
    return get_imagine_client(settings.imagineart_api_key)


def _get_google() -> GoogleAIClient:
    """Get Google AI client."""
    if not settings.google_api_key:
        raise HTTPException(status_code=500, detail="Google API key not configured")
    return get_google_client(settings.google_api_key)


# =============================================================================
# IMAGE GENERATION
# =============================================================================


@router.post("/image/generate", response_model=GenerationResponse)
async def generate_image(request: ImageGenerateRequest):
    """
    Generate image from text prompt.

    Styles: REALISTIC, ANIME, DISNEY, COMIC, PHOTOGRAPHY, RENDER_3D, PAINTING, ILLUSTRATION
    Aspect ratios: 1:1, 16:9, 9:16, 21:9, 4:3, 4:5
    """
    try:
        client = _get_imagine()

        # Parse style
        try:
            style = ImageStyle[request.style.upper()]
        except KeyError:
            style = ImageStyle.REALISTIC

        # Parse aspect ratio
        ratio_map = {
            "1:1": AspectRatio.SQUARE,
            "16:9": AspectRatio.LANDSCAPE,
            "9:16": AspectRatio.PORTRAIT,
            "21:9": AspectRatio.WIDE,
            "4:3": AspectRatio.STANDARD,
            "4:5": AspectRatio.INSTAGRAM,
        }
        aspect = ratio_map.get(request.aspect_ratio, AspectRatio.SQUARE)

        result = await client.generate_image(
            prompt=request.prompt,
            style=style,
            aspect_ratio=aspect,
            negative_prompt=request.negative_prompt,
        )

        return GenerationResponse(
            success=result.success,
            url=result.url,
            format=result.format,
            width=result.width,
            height=result.height,
            generation_time_ms=result.generation_time_ms,
            credits_used=result.credits_used,
            error=result.error,
        )

    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        return GenerationResponse(success=False, error=str(e))


@router.post("/image/social", response_model=GenerationResponse)
async def generate_social_image(request: SocialImageRequest):
    """
    Generate image optimized for social media platform.

    Platforms: instagram, instagram_story, twitter, linkedin, tiktok, youtube, facebook
    Moods: professional, creative, fun, dramatic
    """
    try:
        client = _get_imagine()

        result = await client.generate_social_visual(
            topic=request.topic,
            platform=request.platform,
            mood=request.mood,
        )

        return GenerationResponse(
            success=result.success,
            url=result.url,
            format=result.format,
            width=result.width,
            height=result.height,
            generation_time_ms=result.generation_time_ms,
            credits_used=result.credits_used,
            error=result.error,
        )

    except Exception as e:
        logger.error(f"Social image generation failed: {e}")
        return GenerationResponse(success=False, error=str(e))


@router.post("/image/article-cover", response_model=GenerationResponse)
async def generate_article_cover(
    title: str,
    category: str = "business",
):
    """Generate cover image for an article."""
    try:
        client = _get_imagine()

        result = await client.generate_article_cover(
            title=title,
            category=category,
        )

        return GenerationResponse(
            success=result.success,
            url=result.url,
            format=result.format,
            width=result.width,
            height=result.height,
            generation_time_ms=result.generation_time_ms,
            credits_used=result.credits_used,
            error=result.error,
        )

    except Exception as e:
        logger.error(f"Article cover generation failed: {e}")
        return GenerationResponse(success=False, error=str(e))


@router.post("/image/thumbnail", response_model=GenerationResponse)
async def generate_thumbnail(
    title: str,
    style: str = "professional",
):
    """Generate YouTube/video thumbnail."""
    try:
        client = _get_imagine()

        result = await client.generate_thumbnail(
            title=title,
            style_hint=style,
        )

        return GenerationResponse(
            success=result.success,
            url=result.url,
            format=result.format,
            width=result.width,
            height=result.height,
            generation_time_ms=result.generation_time_ms,
            credits_used=result.credits_used,
            error=result.error,
        )

    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
        return GenerationResponse(success=False, error=str(e))


# =============================================================================
# VIDEO GENERATION
# =============================================================================


@router.post("/video/from-prompt", response_model=GenerationResponse)
async def generate_video_from_prompt(request: VideoGenerateRequest):
    """
    Generate video from text prompt.

    Two-step process:
    1. Generates image from prompt
    2. Animates image into video

    Duration: 2-8 seconds
    """
    try:
        client = _get_imagine()

        try:
            style = ImageStyle[request.style.upper()]
        except KeyError:
            style = ImageStyle.REALISTIC

        result = await client.generate_video_from_prompt(
            prompt=request.prompt,
            style=style,
            duration=min(max(request.duration, 2), 8),
        )

        return GenerationResponse(
            success=result.success,
            url=result.url,
            format=result.format,
            generation_time_ms=result.generation_time_ms,
            credits_used=result.credits_used,
            error=result.error,
        )

    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        return GenerationResponse(success=False, error=str(e))


@router.post("/video/from-image", response_model=GenerationResponse)
async def generate_video_from_image(
    image: UploadFile = File(...),
    prompt: Optional[str] = Form(None),
    duration: int = Form(4),
):
    """
    Generate video from uploaded image.

    Upload an image and get an animated video.
    Optional prompt guides the motion/animation style.
    """
    try:
        client = _get_imagine()

        image_data = await image.read()

        result = await client.generate_video(
            image_data=image_data,
            prompt=prompt,
            duration=min(max(duration, 2), 8),
        )

        return GenerationResponse(
            success=result.success,
            url=result.url,
            format=result.format,
            generation_time_ms=result.generation_time_ms,
            credits_used=result.credits_used,
            error=result.error,
        )

    except Exception as e:
        logger.error(f"Video from image failed: {e}")
        return GenerationResponse(success=False, error=str(e))


# =============================================================================
# IMAGE EDITING
# =============================================================================


@router.post("/edit/remove-background", response_model=GenerationResponse)
async def remove_background(
    image: UploadFile = File(...),
):
    """Remove background from uploaded image."""
    try:
        client = _get_imagine()
        image_data = await image.read()

        result = await client.remove_background(image_data)

        return GenerationResponse(
            success=result.success,
            url=result.url,
            format=result.format,
            error=result.error,
        )

    except Exception as e:
        logger.error(f"Background removal failed: {e}")
        return GenerationResponse(success=False, error=str(e))


@router.post("/edit/upscale", response_model=GenerationResponse)
async def upscale_image(
    image: UploadFile = File(...),
    scale: int = Form(2),
):
    """
    Upscale image resolution.

    Scale: 2 (2x) or 4 (4x)
    """
    try:
        client = _get_imagine()
        image_data = await image.read()

        result = await client.upscale_image(
            image_data=image_data,
            scale=min(scale, 4),
        )

        return GenerationResponse(
            success=result.success,
            url=result.url,
            format=result.format,
            width=result.width,
            height=result.height,
            error=result.error,
        )

    except Exception as e:
        logger.error(f"Upscale failed: {e}")
        return GenerationResponse(success=False, error=str(e))


# =============================================================================
# IMAGE ANALYSIS (Gemini Vision)
# =============================================================================


@router.post("/analyze/image")
async def analyze_image(
    image: UploadFile = File(...),
    prompt: str = Form("Describe this image in detail"),
):
    """
    Analyze image using Google Gemini vision.

    Upload an image and get AI analysis/description.
    """
    try:
        client = _get_google()
        image_data = await image.read()

        # Determine MIME type
        mime_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }
        ext = image.filename.split(".")[-1].lower() if image.filename else "jpeg"
        mime = mime_types.get(ext, "image/jpeg")

        result = await client.analyze_image(
            image_data=image_data,
            prompt=prompt,
            image_mime=mime,
        )

        return {
            "success": True,
            "analysis": result,
        }

    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/analyze/extract-text")
async def extract_text_from_image(
    image: UploadFile = File(...),
):
    """
    Extract text from image (OCR) using Gemini vision.
    """
    try:
        client = _get_google()
        image_data = await image.read()

        ext = image.filename.split(".")[-1].lower() if image.filename else "jpeg"
        mime = (
            f"image/{ext}"
            if ext in ["jpeg", "jpg", "png", "gif", "webp"]
            else "image/jpeg"
        )

        result = await client.extract_text_from_image(
            image_data=image_data,
            image_mime=mime,
        )

        return {
            "success": True,
            "text": result,
        }

    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


# =============================================================================
# GOOGLE GEMINI TEXT GENERATION
# =============================================================================


@router.post("/gemini/generate")
async def gemini_generate(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    model: str = "gemini-2.0-flash",
):
    """
    Direct text generation using Google Gemini.

    Models: gemini-2.0-flash, gemini-2.0-flash-lite, gemini-1.5-flash, gemini-1.5-pro
    """
    try:
        client = _get_google()

        content, metadata = await client.generate(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return {
            "success": True,
            "content": content,
            "model": metadata["model"],
            "input_tokens": metadata["input_tokens"],
            "output_tokens": metadata["output_tokens"],
            "latency_ms": metadata["latency_ms"],
        }

    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/gemini/summarize")
async def gemini_summarize(
    content: str,
    length: str = "medium",
):
    """
    Summarize text using Gemini.

    Lengths: short, medium, long
    """
    try:
        client = _get_google()
        summary = await client.summarize(content, length)

        return {
            "success": True,
            "summary": summary,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/gemini/translate")
async def gemini_translate(
    content: str,
    source_lang: str = "en",
    target_lang: str = "id",
):
    """
    Translate text using Gemini.
    """
    try:
        client = _get_google()
        translation = await client.translate(content, source_lang, target_lang)

        return {
            "success": True,
            "translation": translation,
            "source_lang": source_lang,
            "target_lang": target_lang,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# =============================================================================
# HEALTH & STATS
# =============================================================================


@router.get("/health")
async def media_health_check():
    """Check health of media generation services."""
    results = {}

    # Check Google
    try:
        client = _get_google()
        results["google_gemini"] = await client.health_check()
    except Exception as e:
        results["google_gemini"] = {"status": "error", "error": str(e)}

    # Check ImagineArt
    try:
        client = _get_imagine()
        # Just check if client initializes (full health check costs credits)
        results["imagineart"] = {"status": "configured"}
    except Exception as e:
        results["imagineart"] = {"status": "error", "error": str(e)}

    overall = (
        "healthy"
        if all(
            r.get("status") in ["healthy", "configured", "ok"] for r in results.values()
        )
        else "degraded"
    )

    return {
        "overall": overall,
        "services": results,
    }


@router.get("/stats")
async def media_stats():
    """Get usage statistics for media services."""
    stats = {}

    try:
        google = _get_google()
        stats["google_gemini"] = google.get_stats()
    except:
        stats["google_gemini"] = {}

    try:
        imagine = _get_imagine()
        stats["imagineart"] = imagine.get_stats()
    except:
        stats["imagineart"] = {}

    return stats


@router.get("/styles")
async def list_available_styles():
    """List all available image styles."""
    return {
        "styles": [s.value for s in ImageStyle],
        "aspect_ratios": {
            "1:1": "Square (1024x1024)",
            "16:9": "Landscape (1920x1080)",
            "9:16": "Portrait (1080x1920)",
            "21:9": "Cinematic Wide",
            "4:3": "Standard",
            "4:5": "Instagram Portrait",
        },
        "video_models": [v.value for v in VideoModel],
    }
