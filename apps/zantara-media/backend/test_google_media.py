#!/usr/bin/env python3
"""
Test Google Media Generation (Imagen 4, Veo 2/3, Gemini Image)
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.google_ai import (
    GoogleAIClient,
    ImagenAspectRatio,
    VeoAspectRatio,
    IMAGEN_MODELS,
    VEO_MODELS,
    GEMINI_IMAGE_MODELS,
)


GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "AIza_REDACTED")


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def test_gemini_image(client: GoogleAIClient):
    """Test Gemini native image generation (FREE)."""
    print_header("TEST: Gemini Image Generation (FREE)")

    prompt = "A professional business meeting in modern office, people discussing around table, natural lighting"

    print(f"\nPrompt: {prompt[:60]}...")
    print("Generating with Gemini (FREE)...")

    try:
        result = await client.generate_image_gemini(
            prompt=prompt,
            model="gemini-2.0-flash-image",
        )

        if result.success:
            print(f"\n✅ Success!")
            print(f"Images generated: {len(result.images)}")
            print(f"Generation time: {result.generation_time_ms}ms")

            if result.images:
                output_path = "/tmp/zantara_gemini_image.png"
                with open(output_path, "wb") as f:
                    f.write(result.images[0])
                print(f"Saved to: {output_path}")
                print(f"Image size: {len(result.images[0]) / 1024:.1f} KB")
            return True
        else:
            print(f"\n❌ Failed: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


async def test_imagen_basic(client: GoogleAIClient):
    """Test Imagen 4 image generation."""
    print_header("TEST: Imagen 4 - Basic Generation")

    prompt = "A beautiful sunset over rice terraces in Bali, Indonesia. Professional photography, golden hour lighting."

    print(f"\nPrompt: {prompt[:60]}...")
    print("Generating with Imagen 4 (costs ~$0.04)...")

    try:
        result = await client.generate_image(
            prompt=prompt,
            num_images=1,
            aspect_ratio=ImagenAspectRatio.LANDSCAPE_16_9,
            model="imagen-4",
        )

        if result.success:
            print(f"\n✅ Success!")
            print(f"Images generated: {len(result.images)}")
            print(f"MIME type: {result.mime_type}")
            print(f"Generation time: {result.generation_time_ms}ms")

            if result.images:
                output_path = "/tmp/zantara_imagen_test.png"
                with open(output_path, "wb") as f:
                    f.write(result.images[0])
                print(f"Saved to: {output_path}")
                print(f"Image size: {len(result.images[0]) / 1024:.1f} KB")
            return True
        else:
            print(f"\n❌ Failed: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


async def test_imagen_fast(client: GoogleAIClient):
    """Test Imagen 4 Fast (cheaper, faster)."""
    print_header("TEST: Imagen 4 Fast")

    prompt = "Modern coworking space in tropical location, minimalist design"

    print(f"\nPrompt: {prompt[:60]}...")
    print("Generating with Imagen 4 Fast...")

    try:
        result = await client.generate_image(
            prompt=prompt,
            model="imagen-4-fast",
            aspect_ratio=ImagenAspectRatio.SQUARE,
        )

        if result.success:
            print(f"\n✅ Success!")
            print(f"Generation time: {result.generation_time_ms}ms")

            if result.images:
                output_path = "/tmp/zantara_imagen_fast.png"
                with open(output_path, "wb") as f:
                    f.write(result.images[0])
                print(f"Saved to: {output_path}")
            return True
        else:
            print(f"\n❌ Failed: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


async def test_veo_video(client: GoogleAIClient):
    """Test Veo 2 video generation (async operation)."""
    print_header("TEST: Veo 2 - Video Generation")

    prompt = "Aerial drone shot of Bali coastline with waves crashing on beach, cinematic, smooth motion"

    print(f"\nPrompt: {prompt[:60]}...")
    print("Starting video generation (this is async)...")

    try:
        result = await client.generate_video(
            prompt=prompt,
            aspect_ratio=VeoAspectRatio.LANDSCAPE_16_9,
            duration_seconds=8,
        )

        if result.success:
            print(f"\n✅ Operation started!")
            if result.operation_name:
                print(f"Operation: {result.operation_name}")
            print(f"Initial latency: {result.generation_time_ms}ms")
            print("\nNote: Video takes 2-5 minutes. Use poll_video_operation() to wait.")
            return True
        else:
            print(f"\n❌ Failed: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


async def show_available_models():
    """Show available models."""
    print_header("AVAILABLE MODELS")

    print("\nImagen 4 Models:")
    for name, model_id in IMAGEN_MODELS.items():
        print(f"  - {name}: {model_id}")

    print("\nVeo Models:")
    for name, model_id in VEO_MODELS.items():
        print(f"  - {name}: {model_id}")

    print("\nGemini Image Models (FREE):")
    for name, model_id in GEMINI_IMAGE_MODELS.items():
        print(f"  - {name}: {model_id}")


async def show_stats(client: GoogleAIClient):
    """Show usage stats."""
    print_header("USAGE STATS")

    stats = client.get_stats()

    print(f"\nImages generated: {stats['total_images_generated']}")
    print(f"Videos generated: {stats['total_videos_generated']}")
    print(f"Estimated image cost: ${stats['estimated_image_cost_usd']:.2f}")
    print(f"Estimated text cost: ${stats['estimated_text_cost_usd']:.4f}")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test Google Media Generation")
    parser.add_argument("--gemini", action="store_true", help="Test Gemini image gen (FREE)")
    parser.add_argument("--imagen", action="store_true", help="Test Imagen 4 (~$0.04/image)")
    parser.add_argument("--veo", action="store_true", help="Test Veo video (async)")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--models", action="store_true", help="Show available models")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("  GOOGLE MEDIA GENERATION - TEST SUITE")
    print("="*60)

    print(f"\nAPI Key: {GOOGLE_API_KEY[:20]}...")

    if args.models:
        await show_available_models()
        return

    if not args.gemini and not args.imagen and not args.veo and not args.all:
        print("\nUsage:")
        print("  --gemini  : Test Gemini image generation (FREE!)")
        print("  --imagen  : Test Imagen 4 (~$0.04 per image)")
        print("  --veo     : Test Veo 2 video generation (async)")
        print("  --all     : Run all tests")
        print("  --models  : Show available models")
        print("\nExample:")
        print("  GOOGLE_API_KEY='...' python3 test_google_media.py --gemini")
        return

    client = GoogleAIClient(GOOGLE_API_KEY)

    results = {}

    try:
        if args.gemini or args.all:
            print("\n[Gemini Image Generation - FREE]")
            results["gemini_image"] = await test_gemini_image(client)

        if args.imagen or args.all:
            print("\n[Imagen 4 - Paid ~$0.04/image]")
            results["imagen_4"] = await test_imagen_basic(client)
            results["imagen_4_fast"] = await test_imagen_fast(client)

        if args.veo or args.all:
            print("\n[Veo Video Generation]")
            results["veo_video"] = await test_veo_video(client)

    finally:
        await client.close()

    await show_stats(client)

    # Summary
    print_header("TEST SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\nResults: {passed}/{total} tests passed")

    for test_name, success in results.items():
        emoji = "✅" if success else "❌"
        print(f"  {emoji} {test_name}")

    print("\n" + "="*60)
    print("  TEST COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
