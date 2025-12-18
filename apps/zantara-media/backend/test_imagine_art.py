#!/usr/bin/env python3
"""
Test ImagineArt API Integration
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.imagine_art import (
    ImagineArtClient,
    ImageStyle,
    AspectRatio,
    VideoModel,
)


IMAGINEART_API_KEY = os.environ.get("IMAGINEART_API_KEY", "vk-3zVt3g8xJ7dSg6KZ3pbpPRUPDwtSAQDlJssPQrKZTp7Kp")


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def test_basic_image(client: ImagineArtClient):
    """Test basic image generation."""
    print_header("TEST: Basic Image Generation")

    prompt = "A modern coworking space in Bali with tropical plants, natural lighting, minimalist design"

    print(f"\nPrompt: {prompt[:60]}...")
    print("Style: REALISTIC")
    print("Generating...")

    try:
        result = await client.generate_image(
            prompt=prompt,
            style=ImageStyle.REALISTIC,
            aspect_ratio=AspectRatio.LANDSCAPE,
        )

        if result.success:
            print(f"\n✅ Success!")
            print(f"Size: {result.width}x{result.height}")
            print(f"Format: {result.format}")
            print(f"Generation time: {result.generation_time_ms}ms")
            print(f"Credits used: {result.credits_used}")

            if result.data:
                output_path = "/tmp/imagineart_basic.png"
                with open(output_path, "wb") as f:
                    f.write(result.data)
                print(f"Saved to: {output_path}")
                print(f"File size: {len(result.data) / 1024:.1f} KB")
            return True
        else:
            print(f"\n❌ Failed: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


async def test_anime_style(client: ImagineArtClient):
    """Test anime style generation."""
    print_header("TEST: Anime Style")

    prompt = "A young entrepreneur working on laptop in a cafe, determined expression, warm atmosphere"

    print(f"\nPrompt: {prompt[:60]}...")
    print("Style: ANIME")
    print("Generating...")

    try:
        result = await client.generate_image(
            prompt=prompt,
            style=ImageStyle.ANIME,
            aspect_ratio=AspectRatio.SQUARE,
        )

        if result.success:
            print(f"\n✅ Success!")
            print(f"Generation time: {result.generation_time_ms}ms")

            if result.data:
                output_path = "/tmp/imagineart_anime.png"
                with open(output_path, "wb") as f:
                    f.write(result.data)
                print(f"Saved to: {output_path}")
            return True
        else:
            print(f"\n❌ Failed: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


async def test_social_image(client: ImagineArtClient):
    """Test social media image generation."""
    print_header("TEST: Social Media Image (Instagram)")

    topic = "Digital nomad lifestyle in Bali - freedom and success"
    platform = "instagram"

    print(f"\nTopic: {topic}")
    print(f"Platform: {platform}")
    print("Generating...")

    try:
        result = await client.generate_social_visual(
            topic=topic,
            platform=platform,
            mood="professional",
        )

        if result.success:
            print(f"\n✅ Success!")
            print(f"Generation time: {result.generation_time_ms}ms")

            if result.data:
                output_path = "/tmp/imagineart_social.png"
                with open(output_path, "wb") as f:
                    f.write(result.data)
                print(f"Saved to: {output_path}")
            return True
        else:
            print(f"\n❌ Failed: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


async def test_article_cover(client: ImagineArtClient):
    """Test article cover generation."""
    print_header("TEST: Article Cover")

    title = "How to Start a Business in Indonesia as a Foreigner"
    category = "business"

    print(f"\nTitle: {title}")
    print(f"Category: {category}")
    print("Generating...")

    try:
        result = await client.generate_article_cover(
            title=title,
            category=category,
        )

        if result.success:
            print(f"\n✅ Success!")
            print(f"Generation time: {result.generation_time_ms}ms")

            if result.data:
                output_path = "/tmp/imagineart_article.png"
                with open(output_path, "wb") as f:
                    f.write(result.data)
                print(f"Saved to: {output_path}")
            return True
        else:
            print(f"\n❌ Failed: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


async def test_thumbnail(client: ImagineArtClient):
    """Test YouTube thumbnail generation."""
    print_header("TEST: YouTube Thumbnail")

    title = "5 Visa Secrets for Living in Bali"

    print(f"\nTitle: {title}")
    print("Generating...")

    try:
        result = await client.generate_thumbnail(
            title=title,
            style_hint="dramatic",
        )

        if result.success:
            print(f"\n✅ Success!")
            print(f"Generation time: {result.generation_time_ms}ms")

            if result.data:
                output_path = "/tmp/imagineart_thumbnail.png"
                with open(output_path, "wb") as f:
                    f.write(result.data)
                print(f"Saved to: {output_path}")
            return True
        else:
            print(f"\n❌ Failed: {result.error}")
            return False

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        return False


async def show_stats(client: ImagineArtClient):
    """Show usage stats."""
    print_header("USAGE STATS")

    stats = client.get_stats()

    print(f"\nTotal generations: {stats['total_generations']}")
    print(f"Total credits used: {stats['total_credits_used']}")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test ImagineArt API")
    parser.add_argument("--basic", action="store_true", help="Test basic image generation")
    parser.add_argument("--anime", action="store_true", help="Test anime style")
    parser.add_argument("--social", action="store_true", help="Test social media image")
    parser.add_argument("--article", action="store_true", help="Test article cover")
    parser.add_argument("--thumbnail", action="store_true", help="Test YouTube thumbnail")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("  IMAGINEART API - TEST SUITE")
    print("="*60)

    print(f"\nAPI Key: {IMAGINEART_API_KEY[:20]}...")

    if not any([args.basic, args.anime, args.social, args.article, args.thumbnail, args.all]):
        print("\nUsage:")
        print("  --basic     : Test basic image generation")
        print("  --anime     : Test anime style")
        print("  --social    : Test social media image")
        print("  --article   : Test article cover")
        print("  --thumbnail : Test YouTube thumbnail")
        print("  --all       : Run all tests")
        print("\nExample:")
        print("  IMAGINEART_API_KEY='...' python3 test_imagine_art.py --basic")
        return

    client = ImagineArtClient(IMAGINEART_API_KEY)

    results = {}

    try:
        if args.basic or args.all:
            results["basic_image"] = await test_basic_image(client)

        if args.anime or args.all:
            results["anime_style"] = await test_anime_style(client)

        if args.social or args.all:
            results["social_image"] = await test_social_image(client)

        if args.article or args.all:
            results["article_cover"] = await test_article_cover(client)

        if args.thumbnail or args.all:
            results["thumbnail"] = await test_thumbnail(client)

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
