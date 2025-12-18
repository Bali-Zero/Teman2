"""
ZANTARA MEDIA - ImagineArt Integration
AI-powered image and video generation

Features:
- Text to Image generation
- Image to Video conversion
- Background removal
- Image upscaling

Documentation: https://docs.imagine.art/
API Reference: https://reference.imagine.art/
"""

import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import httpx
import base64

logger = logging.getLogger(__name__)


class ImageStyle(Enum):
    """Available image styles for ImagineArt API."""

    REALISTIC = "realistic"
    ANIME = "anime"
    FLUX_SCHNELL = "flux-schnell"  # Fast, high detail
    FLUX_DEV = "flux-dev"  # Versatile, detailed
    FLUX_DEV_FAST = "flux-dev-fast"  # Faster rendering
    SDXL = "sdxl-1.0"  # Hyper-realistic portraits
    TURBO = "imagine-turbo"  # Fast, versatile (default)


class AspectRatio(Enum):
    """Supported aspect ratios."""

    SQUARE = "1:1"  # 1024x1024
    LANDSCAPE = "16:9"  # 1920x1080
    PORTRAIT = "9:16"  # 1080x1920
    WIDE = "21:9"  # Cinematic
    STANDARD = "4:3"  # Traditional
    INSTAGRAM = "4:5"  # Instagram portrait


class VideoModel(Enum):
    """Available video generation models."""

    COGVIDEO_5B = "cogvideox-5b"
    FASTSVD_LCM = "fastsvd-lcm"


@dataclass
class GenerationResult:
    """Result from image/video generation."""

    success: bool
    data: Optional[bytes] = None
    url: Optional[str] = None
    format: str = "png"
    width: int = 0
    height: int = 0
    generation_time_ms: int = 0
    credits_used: int = 0
    error: Optional[str] = None


class ImagineArtClient:
    """
    Client for ImagineArt API.

    Provides text-to-image, image-to-video, and editing capabilities.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.vyro.ai/v2"  # Correct API endpoint
        self._client: Optional[httpx.AsyncClient] = None

        # Stats
        self.total_generations = 0
        self.total_credits_used = 0

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
                timeout=180.0,  # Long timeout for generation
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # =========================================================================
    # TEXT TO IMAGE
    # =========================================================================

    async def generate_image(
        self,
        prompt: str,
        style: ImageStyle = ImageStyle.REALISTIC,
        aspect_ratio: AspectRatio = AspectRatio.SQUARE,
        negative_prompt: Optional[str] = None,
        num_images: int = 1,
        seed: Optional[int] = None,
    ) -> GenerationResult:
        """
        Generate image from text prompt.

        Args:
            prompt: Text description of the image
            style: Art style to use
            aspect_ratio: Image dimensions
            negative_prompt: Things to avoid in the image
            num_images: Number of images to generate (1-4)
            seed: Random seed for reproducibility
        """
        client = await self._get_client()
        start_time = datetime.utcnow()

        # ImagineArt API uses multipart form-data
        form_data = {
            "prompt": (None, prompt),
            "style": (None, style.value),  # Already lowercase in enum
            "aspect_ratio": (None, aspect_ratio.value),
        }

        if negative_prompt:
            form_data["negative_prompt"] = (None, negative_prompt)
        if seed:
            form_data["seed"] = (None, str(seed))

        try:
            response = await client.post("/image/generations", files=form_data)
            response.raise_for_status()

            generation_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            # Response is the image directly or JSON with URL
            content_type = response.headers.get("content-type", "")

            if "image" in content_type:
                # Direct image response
                img_bytes = response.content
            else:
                # JSON response with URL
                data = response.json()
                image_url = data.get("url") or data.get("data", {}).get("url")

                if image_url:
                    img_response = await client.get(image_url)
                    img_bytes = img_response.content
                else:
                    img_bytes = base64.b64decode(
                        data.get("base64", data.get("data", {}).get("base64", ""))
                    )

            self.total_generations += 1
            self.total_credits_used += 1

            logger.info(f"Image generated: {prompt[:50]}... ({generation_time}ms)")

            return GenerationResult(
                success=True,
                data=img_bytes,
                format="png",
                width=1024,
                height=1024,
                generation_time_ms=generation_time,
                credits_used=1,
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"API error: {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg = error_data.get("message", error_msg)
            except:
                pass
            logger.error(f"Image generation failed: {error_msg}")
            return GenerationResult(
                success=False,
                error=error_msg,
            )
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            return GenerationResult(
                success=False,
                error=str(e),
            )

    async def generate_social_image(
        self,
        topic: str,
        platform: str = "instagram",
        style: ImageStyle = ImageStyle.REALISTIC,
    ) -> GenerationResult:
        """
        Generate image optimized for social media.

        Auto-selects aspect ratio based on platform.
        """
        platform_ratios = {
            "instagram": AspectRatio.SQUARE,
            "instagram_story": AspectRatio.PORTRAIT,
            "twitter": AspectRatio.LANDSCAPE,
            "linkedin": AspectRatio.LANDSCAPE,
            "tiktok": AspectRatio.PORTRAIT,
            "youtube": AspectRatio.LANDSCAPE,
        }

        aspect = platform_ratios.get(platform, AspectRatio.SQUARE)

        # Enhance prompt for social media
        enhanced_prompt = f"""Professional {platform} content image.
Topic: {topic}
Style: Clean, modern, eye-catching, high quality.
Perfect for social media engagement."""

        return await self.generate_image(
            prompt=enhanced_prompt,
            style=style,
            aspect_ratio=aspect,
            negative_prompt="text, watermark, logo, blurry, low quality",
        )

    # =========================================================================
    # IMAGE TO VIDEO
    # =========================================================================

    async def generate_video(
        self,
        image_data: bytes,
        prompt: Optional[str] = None,
        duration: int = 4,  # seconds
        model: VideoModel = VideoModel.FASTSVD_LCM,
    ) -> GenerationResult:
        """
        Generate video from a static image.

        Args:
            image_data: Source image bytes
            prompt: Optional motion guidance prompt
            duration: Video duration in seconds
            model: Video generation model to use
        """
        client = await self._get_client()
        start_time = datetime.utcnow()

        # Encode image
        image_b64 = base64.b64encode(image_data).decode("utf-8")

        payload = {
            "image": image_b64,
            "model": model.value,
            "duration": duration,
        }

        if prompt:
            payload["prompt"] = prompt

        try:
            response = await client.post("/generations/image-to-video", json=payload)
            response.raise_for_status()

            data = response.json()
            generation_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            # Get video URL or data
            video_data = data.get("data", {})
            video_url = video_data.get("url")

            # Download video
            video_bytes = None
            if video_url:
                vid_response = await client.get(video_url)
                video_bytes = vid_response.content

            self.total_generations += 1
            self.total_credits_used += data.get("credits_used", 5)

            logger.info(f"Video generated: {duration}s ({generation_time}ms)")

            return GenerationResult(
                success=True,
                data=video_bytes,
                url=video_url,
                format="mp4",
                generation_time_ms=generation_time,
                credits_used=data.get("credits_used", 5),
            )

        except httpx.HTTPStatusError as e:
            return GenerationResult(
                success=False,
                error=f"API error: {e.response.status_code}",
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                error=str(e),
            )

    async def generate_video_from_prompt(
        self,
        prompt: str,
        style: ImageStyle = ImageStyle.REALISTIC,
        duration: int = 4,
    ) -> GenerationResult:
        """
        Generate video from text (image first, then animate).

        Two-step process:
        1. Generate image from prompt
        2. Animate the image into video
        """
        # Step 1: Generate image
        logger.info("Step 1: Generating image for video...")
        image_result = await self.generate_image(
            prompt=prompt,
            style=style,
            aspect_ratio=AspectRatio.LANDSCAPE,
        )

        if not image_result.success or not image_result.data:
            return GenerationResult(
                success=False,
                error=f"Image generation failed: {image_result.error}",
            )

        # Step 2: Generate video from image
        logger.info("Step 2: Animating image into video...")
        video_result = await self.generate_video(
            image_data=image_result.data,
            prompt=prompt,
            duration=duration,
        )

        return video_result

    # =========================================================================
    # IMAGE EDITING
    # =========================================================================

    async def remove_background(
        self,
        image_data: bytes,
    ) -> GenerationResult:
        """Remove background from image."""
        client = await self._get_client()

        image_b64 = base64.b64encode(image_data).decode("utf-8")

        try:
            response = await client.post(
                "/edits/remove-background",
                json={"image": image_b64},
            )
            response.raise_for_status()

            data = response.json()
            result_data = data.get("data", {})

            # Get result image
            result_url = result_data.get("url")
            result_bytes = None

            if result_url:
                img_response = await client.get(result_url)
                result_bytes = img_response.content

            self.total_generations += 1

            return GenerationResult(
                success=True,
                data=result_bytes,
                url=result_url,
                format="png",
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                error=str(e),
            )

    async def upscale_image(
        self,
        image_data: bytes,
        scale: int = 2,  # 2x or 4x
    ) -> GenerationResult:
        """Upscale image resolution."""
        client = await self._get_client()

        image_b64 = base64.b64encode(image_data).decode("utf-8")

        try:
            response = await client.post(
                "/edits/upscale",
                json={
                    "image": image_b64,
                    "scale": min(scale, 4),
                },
            )
            response.raise_for_status()

            data = response.json()
            result_data = data.get("data", {})

            result_url = result_data.get("url")
            result_bytes = None

            if result_url:
                img_response = await client.get(result_url)
                result_bytes = img_response.content

            self.total_generations += 1

            return GenerationResult(
                success=True,
                data=result_bytes,
                url=result_url,
                format="png",
                width=result_data.get("width", 0),
                height=result_data.get("height", 0),
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                error=str(e),
            )

    # =========================================================================
    # CONTENT-SPECIFIC GENERATORS
    # =========================================================================

    async def generate_article_cover(
        self,
        title: str,
        category: str,
    ) -> GenerationResult:
        """Generate cover image for an article."""
        prompt = f"""Professional blog article cover image.
Title: {title}
Category: {category}
Style: Clean, modern, professional, editorial photography style.
No text or typography in the image.
High quality, suitable for business publication."""

        return await self.generate_image(
            prompt=prompt,
            style=ImageStyle.REALISTIC,
            aspect_ratio=AspectRatio.LANDSCAPE,
            negative_prompt="text, words, letters, watermark, logo, amateur",
        )

    async def generate_social_visual(
        self,
        topic: str,
        platform: str,
        mood: str = "professional",
    ) -> GenerationResult:
        """Generate visual for social media post."""
        mood_styles = {
            "professional": ImageStyle.REALISTIC,
            "creative": ImageStyle.FLUX_DEV,
            "fun": ImageStyle.ANIME,
            "dramatic": ImageStyle.SDXL,
        }

        style = mood_styles.get(mood, ImageStyle.REALISTIC)

        prompt = f"""Engaging {platform} visual content.
Topic: {topic}
Mood: {mood}
Requirements: Eye-catching, shareable, modern design.
Perfect for social media engagement and viral potential."""

        platform_ratios = {
            "instagram": AspectRatio.SQUARE,
            "instagram_story": AspectRatio.PORTRAIT,
            "twitter": AspectRatio.LANDSCAPE,
            "linkedin": AspectRatio.LANDSCAPE,
            "tiktok": AspectRatio.PORTRAIT,
            "facebook": AspectRatio.LANDSCAPE,
        }

        return await self.generate_image(
            prompt=prompt,
            style=style,
            aspect_ratio=platform_ratios.get(platform, AspectRatio.SQUARE),
            negative_prompt="text, watermark, low quality, blurry",
        )

    async def generate_thumbnail(
        self,
        title: str,
        style_hint: str = "professional",
    ) -> GenerationResult:
        """Generate YouTube/video thumbnail."""
        prompt = f"""Dramatic YouTube video thumbnail.
Title concept: {title}
Style: {style_hint}, bold, attention-grabbing.
High contrast, vibrant colors, professional quality.
No text - just the visual."""

        return await self.generate_image(
            prompt=prompt,
            style=ImageStyle.FLUX_SCHNELL,
            aspect_ratio=AspectRatio.LANDSCAPE,
            negative_prompt="text, words, low quality, boring, plain",
        )

    # =========================================================================
    # STATS & HEALTH
    # =========================================================================

    def get_stats(self) -> dict:
        """Get usage statistics."""
        return {
            "total_generations": self.total_generations,
            "total_credits_used": self.total_credits_used,
        }

    async def health_check(self) -> dict:
        """Check API health."""
        try:
            # Simple test generation
            result = await self.generate_image(
                prompt="test image, simple blue square",
                style=ImageStyle.REALISTIC,
                aspect_ratio=AspectRatio.SQUARE,
            )

            return {
                "status": "healthy" if result.success else "degraded",
                "generation_time_ms": result.generation_time_ms,
                "error": result.error,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }


# Singleton
_imagine_client: Optional[ImagineArtClient] = None


def get_imagine_client(api_key: str) -> ImagineArtClient:
    """Get or create ImagineArt client singleton."""
    global _imagine_client
    if _imagine_client is None:
        _imagine_client = ImagineArtClient(api_key)
    return _imagine_client


# Create default instance for imports (will be initialized when config loaded)
class _DeferredImagineArt:
    """Deferred ImagineArt client that loads config on first use."""

    def __init__(self):
        self._client: Optional[ImagineArtClient] = None

    def _get_client(self) -> Optional[ImagineArtClient]:
        if self._client is None:
            from app.config import settings

            if settings.imagineart_api_key:
                self._client = get_imagine_client(settings.imagineart_api_key)
            else:
                logger.warning(
                    "IMAGINEART_API_KEY not configured, ImagineArt services unavailable"
                )
                return None
        return self._client

    async def generate_image(
        self,
        prompt: str,
        style: "ImageStyle" = ImageStyle.REALISTIC,
        aspect_ratio: "AspectRatio" = AspectRatio.SQUARE,
        negative_prompt: Optional[str] = None,
        cfg_scale: float = 7.5,
    ) -> "ImageResult":
        """Generate image using ImagineArt."""
        client = self._get_client()
        if not client:
            return ImageResult(success=False, error="ImagineArt not configured")
        return await client.generate_image(
            prompt, style, aspect_ratio, negative_prompt, cfg_scale
        )

    async def generate_article_cover(self, title: str, category: str) -> "ImageResult":
        """Generate cover image for an article."""
        client = self._get_client()
        if not client:
            return ImageResult(success=False, error="ImagineArt not configured")
        return await client.generate_article_cover(title, category)

    async def health_check(self) -> dict:
        """Check API health."""
        try:
            client = self._get_client()
            if not client:
                return {
                    "status": "not_configured",
                    "error": "ImagineArt not configured",
                }
            return await client.health_check()
        except Exception as e:
            return {"status": "error", "error": str(e)}


imagine_art_service = _DeferredImagineArt()
