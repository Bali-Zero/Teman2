#!/usr/bin/env python3
"""
GEMINI API IMAGE GENERATOR - Direct API Integration
====================================================
Generates cover images using Google AI Studio API (Imagen 4).
Replaces browser automation with direct HTTP API calls.

Benefits:
- No browser dependency (Playwright not needed)
- Faster generation (~5-10 seconds vs ~60 seconds)
- More reliable (no UI changes breaking automation)
- Direct base64 image output

Requires: GOOGLE_API_KEY environment variable
"""

import os
import re
import base64
import asyncio
import httpx
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class ImageAspectRatio(Enum):
    """Supported aspect ratios for Imagen."""
    SQUARE = "1:1"
    PORTRAIT_3_4 = "3:4"
    LANDSCAPE_4_3 = "4:3"
    PORTRAIT_9_16 = "9:16"
    LANDSCAPE_16_9 = "16:9"


@dataclass
class ImageResult:
    """Result from image generation."""
    success: bool
    image_bytes: Optional[bytes] = None
    image_path: Optional[str] = None
    mime_type: str = "image/png"
    error: Optional[str] = None
    generation_time_ms: int = 0
    prompt_used: Optional[str] = None


# Imagen models available
IMAGEN_MODELS = {
    "imagen-4": "imagen-4.0-generate-001",
    "imagen-4-fast": "imagen-4.0-fast-generate-001",
    "gemini-image": "gemini-2.0-flash-exp-image-generation",  # Free alternative
}


class GeminiAPIImageGenerator:
    """
    Generate cover images via Google AI Studio API.

    Uses Imagen 4 for high-quality professional images.
    Falls back to Gemini native image generation if Imagen fails.
    """

    def __init__(
        self,
        output_dir: str = "data/images",
        api_key: Optional[str] = None
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not set - image generation will fail")

        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self._client: Optional[httpx.AsyncClient] = None

        # Stats
        self.total_generated = 0
        self.total_failures = 0

        logger.info(f"🎨 GeminiAPIImageGenerator initialized (output: {output_dir})")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=120.0,  # 2 minutes for image generation
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_editorial_prompt(
        self,
        title: str,
        category: str,
        summary: str = "",
        key_details: list = None
    ) -> str:
        """
        Build a professional editorial image prompt.

        Philosophy: "Il lettore deve capire il tema in 2 secondi"
        """
        # Category-specific style hints
        category_styles = {
            "immigration": "immigration office setting, visa documents, professional consultation",
            "tax": "tax office, laptop with tax portal, financial documents, professional environment",
            "business": "modern Bali coworking space, entrepreneur, tropical business setting",
            "property": "Bali villa, property viewing, tropical architecture, lush gardens",
            "lifestyle": "daily life in Bali, authentic local scene, cafe or beach",
            "legal": "law office in Indonesia, consultation, professional batik attire",
            "tech": "digital nomad, laptop with Bali view, remote work paradise",
        }

        style_hint = category_styles.get(category.lower(), "professional Bali setting")

        details_text = ""
        if key_details:
            details_text = f"\nKey elements to include: {', '.join(key_details[:3])}"

        prompt = f"""Create a stunning magazine-quality photograph for a business article.

TOPIC: {title}

SCENE: {style_hint}{details_text}

STYLE REQUIREMENTS:
- Ultra-realistic photography (NOT illustration, NOT AI-looking)
- Bali/Indonesia setting with warm, natural lighting
- 8K resolution, sharp details, cinematic composition
- 16:9 landscape format
- Leave space in upper third for potential text overlay
- No text, watermarks, or logos in the image
- Real people in realistic situations if people included

THE 2-SECOND TEST:
- Viewer must immediately understand the topic
- Beautiful but CLEAR - no cryptic metaphors
- Professional editorial quality

DO NOT INCLUDE:
- Stock photo aesthetic (posed, fake smiles)
- Graphs, charts, arrows
- Text or readable documents
- Western corporate imagery
- Tourist clichés"""

        return prompt

    async def generate_image_imagen(
        self,
        prompt: str,
        aspect_ratio: ImageAspectRatio = ImageAspectRatio.LANDSCAPE_16_9,
        model: str = "imagen-4-fast",
        negative_prompt: Optional[str] = None,
    ) -> ImageResult:
        """
        Generate image using Imagen 4 API.

        Pricing: ~$0.03-0.08 per image
        """
        if not self.api_key:
            return ImageResult(success=False, error="GOOGLE_API_KEY not configured")

        client = await self._get_client()
        start_time = datetime.utcnow()

        model_id = IMAGEN_MODELS.get(model, IMAGEN_MODELS["imagen-4-fast"])
        url = f"{self.base_url}/models/{model_id}:predict?key={self.api_key}"

        # Build instance
        instance = {"prompt": prompt}
        if negative_prompt:
            instance["negativePrompt"] = negative_prompt

        payload = {
            "instances": [instance],
            "parameters": {
                "sampleCount": 1,
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

            # Extract image
            predictions = data.get("predictions", [])

            if predictions and "bytesBase64Encoded" in predictions[0]:
                img_bytes = base64.b64decode(predictions[0]["bytesBase64Encoded"])
                self.total_generated += 1

                logger.info(f"✅ Imagen generated image ({generation_time}ms)")

                return ImageResult(
                    success=True,
                    image_bytes=img_bytes,
                    mime_type=predictions[0].get("mimeType", "image/png"),
                    generation_time_ms=generation_time,
                    prompt_used=prompt,
                )

            return ImageResult(
                success=False,
                error="No image in response",
                generation_time_ms=generation_time,
            )

        except httpx.HTTPStatusError as e:
            error_detail = str(e)
            try:
                error_json = e.response.json()
                error_detail = error_json.get("error", {}).get("message", str(e))
            except:
                pass

            self.total_failures += 1
            logger.error(f"❌ Imagen API error: {error_detail}")
            return ImageResult(success=False, error=error_detail)

        except Exception as e:
            self.total_failures += 1
            logger.error(f"❌ Imagen generation failed: {e}")
            return ImageResult(success=False, error=str(e))

    async def generate_image_gemini(
        self,
        prompt: str,
    ) -> ImageResult:
        """
        Generate image using Gemini's native image generation (FREE).

        Falls back option when Imagen fails or for cost savings.
        """
        if not self.api_key:
            return ImageResult(success=False, error="GOOGLE_API_KEY not configured")

        client = await self._get_client()
        start_time = datetime.utcnow()

        model_id = "gemini-2.0-flash-exp-image-generation"
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

            # Extract image from response
            if "candidates" in data and len(data["candidates"]) > 0:
                parts = data["candidates"][0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        inline = part["inlineData"]
                        img_bytes = base64.b64decode(inline["data"])
                        self.total_generated += 1

                        logger.info(f"✅ Gemini generated image ({generation_time}ms)")

                        return ImageResult(
                            success=True,
                            image_bytes=img_bytes,
                            mime_type="image/png",
                            generation_time_ms=generation_time,
                            prompt_used=prompt,
                        )

            return ImageResult(
                success=False,
                error="No image in Gemini response",
                generation_time_ms=generation_time,
            )

        except httpx.HTTPStatusError as e:
            error_detail = str(e)
            try:
                error_json = e.response.json()
                error_detail = error_json.get("error", {}).get("message", str(e))
            except:
                pass

            self.total_failures += 1
            logger.error(f"❌ Gemini image error: {error_detail}")
            return ImageResult(success=False, error=error_detail)

        except Exception as e:
            self.total_failures += 1
            logger.error(f"❌ Gemini image failed: {e}")
            return ImageResult(success=False, error=str(e))

    async def generate_cover_image(
        self,
        title: str,
        category: str,
        summary: str = "",
        article_id: Optional[str] = None,
        key_details: list = None,
        use_gemini_free: bool = False,
    ) -> ImageResult:
        """
        Generate a cover image for an article.

        Args:
            title: Article title
            category: Article category (immigration, tax, business, etc.)
            summary: Article summary for context
            article_id: Optional ID for filename
            key_details: Optional list of key visual elements
            use_gemini_free: Use free Gemini instead of Imagen

        Returns:
            ImageResult with image bytes and path
        """
        # Build editorial prompt
        prompt = self._build_editorial_prompt(
            title=title,
            category=category,
            summary=summary,
            key_details=key_details,
        )

        # Standard negative prompt for all editorial images
        negative_prompt = (
            "text, words, letters, watermark, logo, blurry, low quality, "
            "stock photo aesthetic, graphs, charts, arrows, illustration, "
            "cartoon, anime, fake, posed, generic corporate"
        )

        # Try Imagen first (unless user requested free tier)
        if use_gemini_free:
            result = await self.generate_image_gemini(prompt)
        else:
            result = await self.generate_image_imagen(
                prompt=prompt,
                aspect_ratio=ImageAspectRatio.LANDSCAPE_16_9,
                model="imagen-4-fast",
                negative_prompt=negative_prompt,
            )

            # Fallback to Gemini free if Imagen fails
            if not result.success:
                logger.warning("Imagen failed, falling back to Gemini free tier...")
                result = await self.generate_image_gemini(prompt)

        # Save to disk if successful
        if result.success and result.image_bytes:
            output_path = self._get_output_path(title, article_id)

            try:
                with open(output_path, "wb") as f:
                    f.write(result.image_bytes)
                result.image_path = output_path
                logger.info(f"💾 Saved image: {output_path}")
            except Exception as e:
                logger.error(f"Failed to save image: {e}")

        return result

    def _get_output_path(self, title: str, article_id: Optional[str] = None) -> str:
        """Generate output path for image."""
        if article_id:
            filename = f"cover_{article_id}.png"
        else:
            slug = re.sub(r"[^a-z0-9]+", "_", title.lower())[:50]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cover_{timestamp}_{slug}.png"

        return str(self.output_dir / filename)

    def get_stats(self) -> Dict:
        """Get generation statistics."""
        total = self.total_generated + self.total_failures
        success_rate = (self.total_generated / total * 100) if total > 0 else 0

        return {
            "total_generated": self.total_generated,
            "total_failures": self.total_failures,
            "success_rate": f"{success_rate:.1f}%",
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def generate_article_cover(
    title: str,
    category: str,
    summary: str = "",
    article_id: Optional[str] = None,
    output_dir: str = "data/images",
) -> Tuple[Optional[str], Optional[str]]:
    """
    Convenience function to generate a cover image.

    Returns:
        (image_path, prompt_used) or (None, error_message)
    """
    generator = GeminiAPIImageGenerator(output_dir=output_dir)

    try:
        result = await generator.generate_cover_image(
            title=title,
            category=category,
            summary=summary,
            article_id=article_id,
        )

        if result.success:
            return result.image_path, result.prompt_used
        else:
            return None, result.error
    finally:
        await generator.close()


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    async def test():
        print("=" * 70)
        print("GEMINI API IMAGE GENERATOR - Test")
        print("=" * 70)

        generator = GeminiAPIImageGenerator(output_dir="data/images")

        # Test case
        result = await generator.generate_cover_image(
            title="New PT PMA Rules 2026: What Foreign Investors Need to Know",
            category="business",
            summary="Major changes to foreign company registration in Indonesia",
            article_id="test_001",
        )

        if result.success:
            print(f"✅ SUCCESS!")
            print(f"   Path: {result.image_path}")
            print(f"   Time: {result.generation_time_ms}ms")
            print(f"   Size: {len(result.image_bytes) / 1024:.1f} KB")
        else:
            print(f"❌ FAILED: {result.error}")

        print(f"\nStats: {generator.get_stats()}")

        await generator.close()

    asyncio.run(test())
