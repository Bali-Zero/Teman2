"""
ZANTARA MEDIA - Google AI Integration
Complete access to Google's AI suite:
- Gemini (text generation, vision, reasoning)
- Imagen 3 (image generation)
- Veo 2 (video generation)

All via generativelanguage.googleapis.com API
"""

import logging
import base64
import asyncio
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import httpx

logger = logging.getLogger(__name__)


class ImagenAspectRatio(Enum):
    """Supported aspect ratios for Imagen."""

    SQUARE = "1:1"
    PORTRAIT_3_4 = "3:4"
    LANDSCAPE_4_3 = "4:3"
    PORTRAIT_9_16 = "9:16"
    LANDSCAPE_16_9 = "16:9"


class VeoAspectRatio(Enum):
    """Supported aspect ratios for Veo videos."""

    SQUARE = "1:1"
    PORTRAIT_9_16 = "9:16"
    LANDSCAPE_16_9 = "16:9"


@dataclass
class GeminiModel:
    """Configuration for a Gemini model."""

    id: str
    name: str
    context_length: int
    input_price_per_1m: float
    output_price_per_1m: float
    strengths: list[str]
    speed: str = "fast"


@dataclass
class ImageResult:
    """Result from image generation."""

    success: bool
    images: list[bytes] = None  # List of image bytes
    mime_type: str = "image/png"
    error: Optional[str] = None
    generation_time_ms: int = 0


@dataclass
class VideoResult:
    """Result from video generation."""

    success: bool
    video_data: Optional[bytes] = None
    video_url: Optional[str] = None
    mime_type: str = "video/mp4"
    duration_seconds: int = 8
    error: Optional[str] = None
    generation_time_ms: int = 0
    operation_name: Optional[str] = None  # For polling


# Available Gemini Models
GEMINI_MODELS = {
    "gemini-2.0-flash": GeminiModel(
        id="gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        context_length=1_048_576,
        input_price_per_1m=0.10,
        output_price_per_1m=0.40,
        strengths=["speed", "1M context", "multimodal", "code"],
        speed="fast",
    ),
    "gemini-2.0-flash-lite": GeminiModel(
        id="gemini-2.0-flash-lite",
        name="Gemini 2.0 Flash Lite",
        context_length=1_048_576,
        input_price_per_1m=0.02,
        output_price_per_1m=0.10,
        strengths=["ultra-fast", "cheap", "simple tasks"],
        speed="very-fast",
    ),
    "gemini-1.5-flash": GeminiModel(
        id="gemini-1.5-flash",
        name="Gemini 1.5 Flash",
        context_length=1_048_576,
        input_price_per_1m=0.075,
        output_price_per_1m=0.30,
        strengths=["balanced", "reliable", "multimodal"],
        speed="fast",
    ),
    "gemini-1.5-pro": GeminiModel(
        id="gemini-1.5-pro",
        name="Gemini 1.5 Pro",
        context_length=2_097_152,
        input_price_per_1m=1.25,
        output_price_per_1m=5.00,
        strengths=["2M context", "complex reasoning", "quality"],
        speed="medium",
    ),
}

# Imagen Models (as of Dec 2025)
IMAGEN_MODELS = {
    "imagen-4": "imagen-4.0-generate-001",
    "imagen-4-ultra": "imagen-4.0-ultra-generate-001",
    "imagen-4-fast": "imagen-4.0-fast-generate-001",
}

# Veo Models (as of Dec 2025)
VEO_MODELS = {
    "veo-2": "veo-2.0-generate-001",
    "veo-3": "veo-3.0-generate-001",
    "veo-3-fast": "veo-3.0-fast-generate-001",
    "veo-3.1": "veo-3.1-generate-preview",
}

# Gemini with native image generation
GEMINI_IMAGE_MODELS = {
    "gemini-2.0-flash-image": "gemini-2.0-flash-exp-image-generation",
    "gemini-2.5-flash-image": "gemini-2.5-flash-image",
    "gemini-3-pro-image": "gemini-3-pro-image-preview",
}


class GoogleAIClient:
    """
    Complete Google AI client supporting:
    - Gemini (text, vision, reasoning)
    - Imagen 3 (image generation)
    - Veo 2 (video generation)
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self._client: Optional[httpx.AsyncClient] = None

        # Stats
        self.total_requests = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_images_generated = 0
        self.total_videos_generated = 0

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=300.0,  # Long timeout for media generation
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # =========================================================================
    # GEMINI TEXT GENERATION
    # =========================================================================

    async def generate(
        self,
        prompt: str,
        model: str = "gemini-2.0-flash",
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> tuple[str, dict]:
        """Generate content using Gemini."""
        client = await self._get_client()

        contents = []
        if system_prompt:
            contents.append(
                {
                    "role": "user",
                    "parts": [{"text": f"System instruction: {system_prompt}"}],
                }
            )
            contents.append(
                {
                    "role": "model",
                    "parts": [
                        {"text": "Understood. I will follow these instructions."}
                    ],
                }
            )

        contents.append({"role": "user", "parts": [{"text": prompt}]})

        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }

        start_time = datetime.utcnow()
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        content = ""
        if "candidates" in data and len(data["candidates"]) > 0:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                content = candidate["content"]["parts"][0].get("text", "")

        usage = data.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)

        self.total_requests += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        metadata = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": round(latency_ms),
        }

        logger.info(
            f"Gemini {model}: {input_tokens}+{output_tokens} tokens, {latency_ms:.0f}ms"
        )
        return content, metadata

    async def generate_with_image(
        self,
        prompt: str,
        image_data: bytes,
        image_mime: str = "image/jpeg",
        model: str = "gemini-2.0-flash",
        max_tokens: int = 1024,
    ) -> tuple[str, dict]:
        """Generate content with image input (vision)."""
        client = await self._get_client()

        image_b64 = base64.b64encode(image_data).decode("utf-8")

        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": image_mime,
                                "data": image_b64,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
            },
        }

        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

        content = ""
        if "candidates" in data and len(data["candidates"]) > 0:
            content = data["candidates"][0]["content"]["parts"][0].get("text", "")

        usage = data.get("usageMetadata", {})

        return content, {
            "model": model,
            "input_tokens": usage.get("promptTokenCount", 0),
            "output_tokens": usage.get("candidatesTokenCount", 0),
        }

    # =========================================================================
    # IMAGEN 4 - IMAGE GENERATION
    # =========================================================================

    async def generate_image(
        self,
        prompt: str,
        num_images: int = 1,
        aspect_ratio: ImagenAspectRatio = ImagenAspectRatio.SQUARE,
        model: str = "imagen-4",
        negative_prompt: Optional[str] = None,
    ) -> ImageResult:
        """
        Generate images using Imagen 4.

        Args:
            prompt: Text description (max 480 tokens, English only)
            num_images: Number of images (1-4)
            aspect_ratio: Image aspect ratio
            model: "imagen-4", "imagen-4-ultra", or "imagen-4-fast"
            negative_prompt: Things to avoid

        Returns:
            ImageResult with list of image bytes

        Pricing: ~$0.03-0.08 per image depending on model
        """
        client = await self._get_client()
        start_time = datetime.utcnow()

        model_id = IMAGEN_MODELS.get(model, IMAGEN_MODELS["imagen-4"])
        url = f"{self.base_url}/models/{model_id}:predict?key={self.api_key}"

        # Build instance
        instance = {"prompt": prompt}
        if negative_prompt:
            instance["negativePrompt"] = negative_prompt

        payload = {
            "instances": [instance],
            "parameters": {
                "sampleCount": min(max(num_images, 1), 4),
                "aspectRatio": aspect_ratio.value,
                "personGeneration": "allow_adult",
            },
        }

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            generation_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            # Extract images
            images = []
            predictions = data.get("predictions", [])

            for pred in predictions:
                if "bytesBase64Encoded" in pred:
                    img_bytes = base64.b64decode(pred["bytesBase64Encoded"])
                    images.append(img_bytes)

            self.total_images_generated += len(images)

            logger.info(f"Imagen generated {len(images)} images ({generation_time}ms)")

            return ImageResult(
                success=True,
                images=images,
                mime_type=predictions[0].get("mimeType", "image/png")
                if predictions
                else "image/png",
                generation_time_ms=generation_time,
            )

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("error", {}).get("message", str(e))
            except:
                error_detail = str(e)

            logger.error(f"Imagen generation failed: {error_detail}")
            return ImageResult(
                success=False,
                error=error_detail,
            )
        except Exception as e:
            logger.error(f"Imagen error: {e}")
            return ImageResult(success=False, error=str(e))

    async def generate_social_image(
        self,
        topic: str,
        platform: str = "instagram",
        style: str = "professional photography",
    ) -> ImageResult:
        """Generate image optimized for social media."""
        platform_ratios = {
            "instagram": ImagenAspectRatio.SQUARE,
            "instagram_story": ImagenAspectRatio.PORTRAIT_9_16,
            "twitter": ImagenAspectRatio.LANDSCAPE_16_9,
            "linkedin": ImagenAspectRatio.LANDSCAPE_16_9,
            "tiktok": ImagenAspectRatio.PORTRAIT_9_16,
            "youtube": ImagenAspectRatio.LANDSCAPE_16_9,
        }

        prompt = f"""Professional {platform} content image.
Topic: {topic}
Style: {style}, clean, modern, high quality, eye-catching.
No text or watermarks."""

        return await self.generate_image(
            prompt=prompt,
            aspect_ratio=platform_ratios.get(platform, ImagenAspectRatio.SQUARE),
            negative_prompt="text, words, letters, watermark, logo, blurry, low quality",
        )

    async def generate_article_cover(
        self,
        title: str,
        category: str,
    ) -> ImageResult:
        """Generate cover image for an article."""
        prompt = f"""Professional editorial cover image for business article.
Title concept: {title}
Category: {category}
Style: Clean, modern, professional photography, suitable for business publication.
No text in image."""

        return await self.generate_image(
            prompt=prompt,
            aspect_ratio=ImagenAspectRatio.LANDSCAPE_16_9,
            negative_prompt="text, watermark, amateur, blurry",
        )

    # =========================================================================
    # GEMINI IMAGE GENERATION (FREE)
    # =========================================================================

    async def generate_image_gemini(
        self,
        prompt: str,
        model: str = "gemini-2.0-flash-image",
    ) -> ImageResult:
        """
        Generate images using Gemini's native image generation.

        This is FREE (included in Gemini API) but may be lower quality than Imagen.

        Args:
            prompt: Image description
            model: "gemini-2.0-flash-image", "gemini-2.5-flash-image", or "gemini-3-pro-image"

        Returns:
            ImageResult with generated image
        """
        client = await self._get_client()
        start_time = datetime.utcnow()

        model_id = GEMINI_IMAGE_MODELS.get(
            model, GEMINI_IMAGE_MODELS["gemini-2.0-flash-image"]
        )
        url = f"{self.base_url}/models/{model_id}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{"parts": [{"text": f"Generate an image: {prompt}"}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
            },
        }

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            generation_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            images = []
            if "candidates" in data and len(data["candidates"]) > 0:
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        inline = part["inlineData"]
                        img_bytes = base64.b64decode(inline["data"])
                        images.append(img_bytes)

            if images:
                self.total_images_generated += len(images)
                logger.info(
                    f"Gemini generated {len(images)} images ({generation_time}ms)"
                )

                return ImageResult(
                    success=True,
                    images=images,
                    mime_type="image/png",
                    generation_time_ms=generation_time,
                )
            else:
                return ImageResult(
                    success=False,
                    error="No images in response",
                )

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("error", {}).get("message", str(e))
            except:
                error_detail = str(e)
            return ImageResult(success=False, error=error_detail)
        except Exception as e:
            return ImageResult(success=False, error=str(e))

    # =========================================================================
    # VEO 2/3 - VIDEO GENERATION
    # =========================================================================

    async def generate_video(
        self,
        prompt: str,
        aspect_ratio: VeoAspectRatio = VeoAspectRatio.LANDSCAPE_16_9,
        duration_seconds: int = 8,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> VideoResult:
        """
        Generate video using Veo 2.

        Args:
            prompt: Text description of the video
            aspect_ratio: Video aspect ratio
            duration_seconds: 5-8 seconds (default 8)
            negative_prompt: Things to avoid
            seed: For reproducibility

        Returns:
            VideoResult (may need polling for completion)

        Note: Video generation is async - may need to poll for results.
        """
        client = await self._get_client()
        start_time = datetime.utcnow()

        model_id = VEO_MODELS["veo-2"]
        url = f"{self.base_url}/models/{model_id}:predictLongRunning?key={self.api_key}"

        # Build instance
        instance = {"prompt": prompt}
        if negative_prompt:
            instance["negativePrompt"] = negative_prompt

        parameters = {
            "aspectRatio": aspect_ratio.value,
            "personGeneration": "allow_adult",
            "sampleCount": 1,
        }

        if seed:
            parameters["seed"] = seed

        payload = {
            "instances": [instance],
            "parameters": parameters,
        }

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            generation_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            # Check if operation is returned (async generation)
            if "name" in data:
                # Long-running operation - need to poll
                operation_name = data["name"]
                logger.info(f"Veo video generation started: {operation_name}")

                return VideoResult(
                    success=True,
                    operation_name=operation_name,
                    generation_time_ms=generation_time,
                    error="Video generation in progress. Use poll_video_operation() to check status.",
                )

            # Direct response (if available)
            predictions = data.get("predictions", [])
            if predictions:
                video_data = None
                video_url = None

                pred = predictions[0]
                if "bytesBase64Encoded" in pred:
                    video_data = base64.b64decode(pred["bytesBase64Encoded"])
                elif "uri" in pred:
                    video_url = pred["uri"]

                self.total_videos_generated += 1

                return VideoResult(
                    success=True,
                    video_data=video_data,
                    video_url=video_url,
                    duration_seconds=duration_seconds,
                    generation_time_ms=generation_time,
                )

            return VideoResult(
                success=False,
                error="No video generated",
            )

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("error", {}).get("message", str(e))
            except:
                error_detail = str(e)

            logger.error(f"Veo generation failed: {error_detail}")
            return VideoResult(success=False, error=error_detail)
        except Exception as e:
            logger.error(f"Veo error: {e}")
            return VideoResult(success=False, error=str(e))

    async def poll_video_operation(
        self,
        operation_name: str,
        max_wait_seconds: int = 300,
        poll_interval: int = 10,
    ) -> VideoResult:
        """
        Poll for video generation completion.

        Args:
            operation_name: Operation name from generate_video()
            max_wait_seconds: Maximum time to wait
            poll_interval: Seconds between polls
        """
        client = await self._get_client()
        start_time = datetime.utcnow()

        url = f"{self.base_url}/{operation_name}?key={self.api_key}"

        elapsed = 0
        while elapsed < max_wait_seconds:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                if data.get("done", False):
                    # Operation complete
                    result = data.get("response", {})
                    predictions = result.get("predictions", [])

                    if predictions:
                        pred = predictions[0]
                        video_data = None
                        video_url = None

                        if "bytesBase64Encoded" in pred:
                            video_data = base64.b64decode(pred["bytesBase64Encoded"])
                        elif "uri" in pred:
                            video_url = pred["uri"]

                        self.total_videos_generated += 1
                        generation_time = int(
                            (datetime.utcnow() - start_time).total_seconds() * 1000
                        )

                        return VideoResult(
                            success=True,
                            video_data=video_data,
                            video_url=video_url,
                            generation_time_ms=generation_time,
                        )

                    # Check for error
                    if "error" in data:
                        return VideoResult(
                            success=False,
                            error=data["error"].get("message", "Unknown error"),
                        )

                # Not done yet, wait and poll again
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            except Exception as e:
                logger.error(f"Poll error: {e}")
                return VideoResult(success=False, error=str(e))

        return VideoResult(
            success=False,
            error=f"Video generation timed out after {max_wait_seconds}s",
        )

    async def generate_video_from_image(
        self,
        image_data: bytes,
        prompt: Optional[str] = None,
        duration_seconds: int = 8,
    ) -> VideoResult:
        """
        Generate video from an image (image-to-video).

        Args:
            image_data: Source image bytes
            prompt: Optional motion guidance
            duration_seconds: Video duration
        """
        client = await self._get_client()
        start_time = datetime.utcnow()

        model_id = VEO_MODELS["veo-2"]
        url = f"{self.base_url}/models/{model_id}:predictLongRunning?key={self.api_key}"

        image_b64 = base64.b64encode(image_data).decode("utf-8")

        instance = {
            "image": {
                "bytesBase64Encoded": image_b64,
            }
        }
        if prompt:
            instance["prompt"] = prompt

        payload = {
            "instances": [instance],
            "parameters": {
                "sampleCount": 1,
            },
        }

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            generation_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            if "name" in data:
                return VideoResult(
                    success=True,
                    operation_name=data["name"],
                    generation_time_ms=generation_time,
                )

            return VideoResult(success=False, error="No operation returned")

        except httpx.HTTPStatusError as e:
            error_detail = str(e)
            try:
                error_detail = e.response.json().get("error", {}).get("message", str(e))
            except:
                pass
            return VideoResult(success=False, error=error_detail)
        except Exception as e:
            return VideoResult(success=False, error=str(e))

    # =========================================================================
    # TEXT UTILITIES
    # =========================================================================

    async def summarize(self, content: str, length: str = "medium") -> str:
        """Summarize content using Gemini Flash."""
        length_instructions = {
            "short": "in 2-3 sentences",
            "medium": "in a paragraph (5-7 sentences)",
            "long": "in 2-3 paragraphs with key details",
        }

        prompt = f"""Summarize the following content {length_instructions.get(length, "concisely")}:

{content}

Focus on key points and actionable information."""

        result, _ = await self.generate(prompt, max_tokens=500, temperature=0.3)
        return result

    async def translate(self, content: str, source_lang: str, target_lang: str) -> str:
        """Translate content using Gemini."""
        prompt = f"""Translate the following from {source_lang} to {target_lang}.
Maintain the original tone, style, and formatting.

Content:
{content}

Translation:"""

        result, _ = await self.generate(
            prompt, max_tokens=len(content.split()) * 3, temperature=0.2
        )
        return result

    async def analyze_image(
        self,
        image_data: bytes,
        prompt: str = "Describe this image in detail.",
        image_mime: str = "image/jpeg",
    ) -> str:
        """Analyze an image using Gemini vision."""
        result, _ = await self.generate_with_image(prompt, image_data, image_mime)
        return result

    async def extract_text_from_image(
        self, image_data: bytes, image_mime: str = "image/jpeg"
    ) -> str:
        """OCR - Extract text from image."""
        result, _ = await self.generate_with_image(
            "Extract all text from this image. Return only the extracted text, no descriptions.",
            image_data,
            image_mime,
        )
        return result

    # =========================================================================
    # STATS & HEALTH
    # =========================================================================

    def get_stats(self) -> dict:
        """Get usage statistics."""
        return {
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_images_generated": self.total_images_generated,
            "total_videos_generated": self.total_videos_generated,
            "estimated_text_cost_usd": self._estimate_text_cost(),
            "estimated_image_cost_usd": self.total_images_generated * 0.03,
        }

    def _estimate_text_cost(self) -> float:
        """Estimate text generation cost."""
        input_cost = (self.total_input_tokens / 1_000_000) * 0.10
        output_cost = (self.total_output_tokens / 1_000_000) * 0.40
        return round(input_cost + output_cost, 4)

    async def health_check(self) -> dict:
        """Check if APIs are working."""
        results = {}

        # Test Gemini
        try:
            start = datetime.utcnow()
            await self.generate("Say OK", max_tokens=10)
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            results["gemini"] = {"status": "healthy", "latency_ms": round(latency)}
        except Exception as e:
            results["gemini"] = {"status": "error", "error": str(e)}

        # Note: Don't test Imagen/Veo in health check to avoid costs

        return {
            "overall": "healthy"
            if results.get("gemini", {}).get("status") == "healthy"
            else "degraded",
            "services": results,
        }


# Singleton
_google_client: Optional[GoogleAIClient] = None


def get_google_client(api_key: str) -> GoogleAIClient:
    """Get or create Google AI client singleton."""
    global _google_client
    if _google_client is None:
        _google_client = GoogleAIClient(api_key)
    return _google_client


# Create default instance for imports (will be initialized when config loaded)
class _DeferredGoogleAI:
    """Deferred Google AI client that loads config on first use."""

    def __init__(self):
        self._client: Optional[GoogleAIClient] = None

    def _get_client(self) -> Optional[GoogleAIClient]:
        if self._client is None:
            from app.config import settings

            if settings.google_api_key:
                self._client = get_google_client(settings.google_api_key)
            else:
                logger.warning(
                    "GOOGLE_API_KEY not configured, Google AI services unavailable"
                )
                return None
        return self._client

    async def generate_social_image(
        self,
        topic: str,
        platform: str = "instagram",
        style: str = "professional photography",
    ) -> ImageResult:
        """Generate image optimized for social media."""
        client = self._get_client()
        if not client:
            return ImageResult(success=False, error="Google AI not configured")
        return await client.generate_social_image(topic, platform, style)

    async def generate_article_cover(self, title: str, category: str) -> ImageResult:
        """Generate cover image for an article."""
        client = self._get_client()
        if not client:
            return ImageResult(success=False, error="Google AI not configured")
        return await client.generate_article_cover(title, category)

    async def generate_image(
        self,
        prompt: str,
        num_images: int = 1,
        aspect_ratio: ImagenAspectRatio = ImagenAspectRatio.SQUARE,
        model: str = "imagen-4",
        negative_prompt: Optional[str] = None,
    ) -> ImageResult:
        """Generate images using Imagen."""
        client = self._get_client()
        if not client:
            return ImageResult(success=False, error="Google AI not configured")
        return await client.generate_image(
            prompt, num_images, aspect_ratio, model, negative_prompt
        )

    async def health_check(self) -> dict:
        """Check API health."""
        try:
            client = self._get_client()
            if not client:
                return {
                    "overall": "not_configured",
                    "error": "Google AI not configured",
                }
            return await client.health_check()
        except Exception as e:
            return {"overall": "error", "error": str(e)}


google_ai_service = _DeferredGoogleAI()
