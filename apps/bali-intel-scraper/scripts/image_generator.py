"""
BALI ZERO JOURNAL - Image Generator
Generates professional cover images for articles using AI

Primary: Google Imagen 4 (high quality)
Fallback: ImagineArt (alternative)

Cost: ~$0.03-0.04 per image
"""

import os
import httpx
from pathlib import Path
from typing import Dict, Optional
from loguru import logger


class ImageGenerator:
    """Generate cover images for articles using Google AI or ImagineArt"""

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        imagine_api_key: Optional[str] = None,
    ):
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        self.imagine_api_key = imagine_api_key or os.getenv("IMAGINEART_API_KEY")

        # Track metrics
        self.metrics = {
            "total_generated": 0,
            "google_success": 0,
            "imagine_success": 0,
            "failed": 0,
            "total_cost_usd": 0.0,
        }

        # Category-specific image styles
        self.category_styles = {
            "immigration": "professional government office setting, official documents, visa stamps, passport, clean modern corporate photography, high quality",
            "tax_bkpm": "business financial charts, professional accountant, tax forms, modern office, corporate photography, high quality",
            "property": "modern luxury Bali villa architecture, tropical real estate, beautiful property exterior, professional real estate photography, high quality",
            "business": "Indonesian business professionals meeting, modern office in Bali, corporate handshake, professional business photography, high quality",
            "legal": "professional law office, legal documents, courthouse, lawyer consultation, corporate legal photography, high quality",
            "customs": "international shipping port, cargo containers, customs checkpoint, import export, professional trade photography, high quality",
            "banking": "modern bank interior, financial technology, professional banking, ATM, corporate finance photography, high quality",
            "technology": "modern tech startup office, computers, innovation, digital workspace, professional tech photography, high quality",
            "tourism": "beautiful Bali tourism, beaches, cultural sites, professional travel photography, vibrant colors, high quality",
            "employment": "professional workplace, hiring, job interview, office environment, corporate HR photography, high quality",
            "health": "modern hospital or clinic in Indonesia, medical professionals, healthcare facility, professional medical photography, high quality",
            "environment": "Bali nature, environmental conservation, sustainability, tropical landscape, professional environmental photography, high quality",
        }

        logger.info("ImageGenerator initialized")
        if self.google_api_key:
            logger.info("  ✓ Google Imagen available")
        if self.imagine_api_key:
            logger.info("  ✓ ImagineArt available")

    async def generate_article_cover(
        self,
        title: str,
        category: str,
        output_path: Path,
    ) -> Dict:
        """
        Generate cover image for an article

        Args:
            title: Article title
            category: Article category (immigration, tax, property, etc.)
            output_path: Where to save the image

        Returns:
            {"success": bool, "provider": str, "cost_usd": float, "error": str}
        """

        logger.info(f"🎨 Generating cover image for: {title[:50]}...")
        logger.info(f"   Category: {category}")

        # Build prompt
        style = self.category_styles.get(
            category,
            "professional business news, modern editorial photography, high quality",
        )

        prompt = f"""Professional editorial cover image for business news publication.

Article topic: {title}
Category: {category}

Style: {style}

Requirements:
- NO TEXT or watermarks in the image
- Clean, professional, eye-catching
- Suitable for business publication
- High quality, sharp focus
- Modern aesthetic"""

        negative_prompt = "text, words, letters, watermark, logo, signature, blurry, low quality, amateur, cartoon, illustration"

        # Try Google Imagen first (higher quality)
        if self.google_api_key:
            result = await self._generate_with_google(
                prompt, negative_prompt, output_path
            )
            if result["success"]:
                self.metrics["google_success"] += 1
                self.metrics["total_generated"] += 1
                self.metrics["total_cost_usd"] += result.get("cost_usd", 0.04)
                return result

        # Fallback to ImagineArt
        if self.imagine_api_key:
            result = await self._generate_with_imagine(
                prompt, negative_prompt, output_path
            )
            if result["success"]:
                self.metrics["imagine_success"] += 1
                self.metrics["total_generated"] += 1
                self.metrics["total_cost_usd"] += result.get("cost_usd", 0.03)
                return result

        # Both failed
        self.metrics["failed"] += 1
        return {
            "success": False,
            "error": "No image generation service available or both failed",
            "cost_usd": 0.0,
        }

    async def _generate_with_google(
        self, prompt: str, negative_prompt: str, output_path: Path
    ) -> Dict:
        """Generate image using Google Imagen 4"""

        try:
            logger.info("  Trying Google Imagen 4...")

            # Google AI API endpoint
            url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key={self.google_api_key}"

            payload = {
                "instances": [
                    {
                        "prompt": prompt,
                        "negativePrompt": negative_prompt,
                    }
                ],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": "16:9",  # Landscape for article covers
                    "personGeneration": "allow_adult",
                },
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            # Extract image
            predictions = data.get("predictions", [])
            if not predictions:
                return {"success": False, "error": "No image in response"}

            import base64

            img_bytes = base64.b64decode(predictions[0]["bytesBase64Encoded"])

            # Save image
            output_path.write_bytes(img_bytes)

            logger.success(f"  ✅ Google Imagen generated image: {output_path.name}")

            return {
                "success": True,
                "provider": "google_imagen",
                "cost_usd": 0.04,  # Imagen cost per image
                "path": str(output_path),
            }

        except Exception as e:
            logger.warning(f"  ❌ Google Imagen failed: {e}")
            return {"success": False, "error": str(e)}

    async def _generate_with_imagine(
        self, prompt: str, negative_prompt: str, output_path: Path
    ) -> Dict:
        """Generate image using ImagineArt"""

        try:
            logger.info("  Trying ImagineArt...")

            url = "https://api.imagine.art/v1/generate"

            payload = {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "style": "REALISTIC",
                "aspect_ratio": "16:9",
                "cfg_scale": 7.5,
            }

            headers = {
                "Authorization": f"Bearer {self.imagine_api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            # Extract image URL or data
            if "data" in data and len(data["data"]) > 0:
                image_url = data["data"][0].get("url")
                if image_url:
                    # Download image
                    async with httpx.AsyncClient() as client:
                        img_response = await client.get(image_url)
                        img_response.raise_for_status()
                        output_path.write_bytes(img_response.content)

                    logger.success(
                        f"  ✅ ImagineArt generated image: {output_path.name}"
                    )

                    return {
                        "success": True,
                        "provider": "imagine_art",
                        "cost_usd": 0.03,  # ImagineArt cost
                        "path": str(output_path),
                    }

            return {"success": False, "error": "No image in response"}

        except Exception as e:
            logger.warning(f"  ❌ ImagineArt failed: {e}")
            return {"success": False, "error": str(e)}

    def get_metrics(self) -> Dict:
        """Get generation metrics"""
        return {
            **self.metrics,
            "success_rate": f"{(self.metrics['total_generated'] / max(self.metrics['total_generated'] + self.metrics['failed'], 1)) * 100:.1f}%",
        }


async def main():
    """Test image generator"""
    generator = ImageGenerator()

    # Test image generation
    output_path = Path("test_cover.png")

    result = await generator.generate_article_cover(
        title="New Visa Regulations for Indonesia 2025",
        category="immigration",
        output_path=output_path,
    )

    print(f"\nResult: {result}")
    print(f"Metrics: {generator.get_metrics()}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
