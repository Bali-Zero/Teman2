#!/usr/bin/env python3
"""
Test Google Gemini AI Integration
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.google_ai import GoogleAIClient, GEMINI_MODELS


GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "AIza_REDACTED")


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def test_basic_generation(client: GoogleAIClient):
    """Test basic text generation."""
    print_header("TEST: Basic Generation")

    prompt = "Write a short haiku about Indonesia"

    print(f"\nPrompt: {prompt}")
    print("Generating...")

    try:
        content, metadata = await client.generate(
            prompt=prompt,
            model="gemini-2.0-flash",
            max_tokens=100,
        )

        print(f"\n✅ Success!")
        print(f"Model: {metadata['model']}")
        print(f"Tokens: {metadata['input_tokens']} in, {metadata['output_tokens']} out")
        print(f"Latency: {metadata['latency_ms']}ms")
        print(f"\nResult:\n{content}")
        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False


async def test_summarization(client: GoogleAIClient):
    """Test summarization."""
    print_header("TEST: Summarization")

    long_text = """
    Indonesia is a country in Southeast Asia and Oceania, between the Indian and Pacific oceans.
    It consists of over 17,000 islands, including Sumatra, Java, Sulawesi, and parts of Borneo and New Guinea.
    Indonesia is the world's largest island country and the 14th-largest country by land area, at 1,904,569 km².
    With over 275 million people, Indonesia is the world's fourth-most populous country and the most populous
    Muslim-majority country. Java, the world's most populous island, is home to more than half of the country's population.
    The nation's capital, Jakarta, is the second-most populous urban area in the world.
    Indonesia's republican form of government includes an elected legislature and president.
    The country has 38 provinces, of which nine have special status.
    """

    print(f"\nOriginal: {len(long_text)} chars")
    print("Summarizing...")

    try:
        summary = await client.summarize(long_text, "short")

        print(f"\n✅ Success!")
        print(f"\nSummary:\n{summary}")
        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False


async def test_translation(client: GoogleAIClient):
    """Test translation."""
    print_header("TEST: Translation (EN → ID)")

    text = "Hello! Welcome to Bali Zero. We help expats succeed in Indonesia."

    print(f"\nOriginal: {text}")
    print("Translating to Indonesian...")

    try:
        translation = await client.translate(text, "English", "Indonesian")

        print(f"\n✅ Success!")
        print(f"\nTranslation:\n{translation}")
        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False


async def test_system_prompt(client: GoogleAIClient):
    """Test with system prompt."""
    print_header("TEST: System Prompt (ZANTARA personality)")

    system = """You are ZANTARA, the AI content writer for Bali Zero.
You write in a professional but friendly tone.
You always include practical advice for expats in Indonesia."""

    prompt = "Give me one tip about opening a bank account in Bali"

    print(f"\nSystem: {system[:80]}...")
    print(f"Prompt: {prompt}")
    print("Generating...")

    try:
        content, metadata = await client.generate(
            prompt=prompt,
            system_prompt=system,
            max_tokens=300,
            temperature=0.7,
        )

        print(f"\n✅ Success! ({metadata['latency_ms']}ms)")
        print(f"\nResponse:\n{content}")
        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False


async def test_fast_model(client: GoogleAIClient):
    """Test the flash-lite model for speed."""
    print_header("TEST: Fast Model (gemini-2.0-flash)")

    prompt = "Say 'Hello from Gemini!' in one line"

    print(f"\nPrompt: {prompt}")
    print("Testing speed...")

    try:
        content, metadata = await client.generate(
            prompt=prompt,
            model="gemini-2.0-flash",
            max_tokens=50,
            temperature=0,
        )

        print(f"\n✅ Success!")
        print(f"Latency: {metadata['latency_ms']}ms")
        print(f"Response: {content}")
        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False


async def test_health_check(client: GoogleAIClient):
    """Test health check."""
    print_header("HEALTH CHECK")

    result = await client.health_check()

    if result["status"] == "healthy":
        print(f"\n✅ Status: {result['status']}")
        print(f"Latency: {result['latency_ms']}ms")
        print(f"Model: {result['model']}")
        return True
    else:
        print(f"\n❌ Status: {result['status']}")
        print(f"Error: {result.get('error')}")
        return False


async def show_stats(client: GoogleAIClient):
    """Show usage stats."""
    print_header("USAGE STATS")

    stats = client.get_stats()

    print(f"\nTotal requests: {stats['total_requests']}")
    print(f"Input tokens: {stats['total_input_tokens']}")
    print(f"Output tokens: {stats['total_output_tokens']}")
    print(f"Estimated cost: ${stats['estimated_cost_usd']}")


async def main():
    print("\n" + "="*60)
    print("  GOOGLE GEMINI AI - TEST SUITE")
    print("="*60)

    print(f"\nAvailable models:")
    for key, model in GEMINI_MODELS.items():
        print(f"  - {model.name}: {model.context_length:,} ctx, ${model.input_price_per_1m}/M in")

    client = GoogleAIClient(GOOGLE_API_KEY)

    results = {}

    try:
        results["health"] = await test_health_check(client)
        results["basic"] = await test_basic_generation(client)
        results["fast"] = await test_fast_model(client)
        results["summarize"] = await test_summarization(client)
        results["translate"] = await test_translation(client)
        results["system_prompt"] = await test_system_prompt(client)

    finally:
        await client.close()

    await show_stats(client)

    # Summary
    print_header("TEST SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\nResults: {passed}/{total} tests passed")

    for test_name, passed in results.items():
        emoji = "✅" if passed else "❌"
        print(f"  {emoji} {test_name}")

    print("\n" + "="*60)
    print("  TEST COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
