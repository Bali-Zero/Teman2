#!/usr/bin/env python3
"""
Test script for ZANTARA AI Engine
Tests the intelligent model routing with OpenRouter's free models
"""

import asyncio
import os
import sys

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.ai_engine import (
    AIEngine,
    TaskType,
    FREE_MODELS,
    TASK_FALLBACK_CHAINS,
)

# OpenRouter API Key
API_KEY = os.environ.get("OPENROUTER_API_KEY", "sk-REDACTED")


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_models_info():
    """Print information about available models."""
    print_header("AVAILABLE FREE MODELS")

    print(f"\nTotal models: {len(FREE_MODELS)}")
    print("\nBy Provider:")

    providers = {}
    for key, model in FREE_MODELS.items():
        if model.provider not in providers:
            providers[model.provider] = []
        providers[model.provider].append(model.name)

    for provider, models in sorted(providers.items()):
        print(f"  {provider}: {', '.join(models)}")

    print("\nTask Routing:")
    for task_type, chain in TASK_FALLBACK_CHAINS.items():
        models = [FREE_MODELS[k].name for k in chain[:3]]
        print(f"  {task_type.value}: {' → '.join(models)} ...")


async def test_health_check(engine: AIEngine):
    """Test health check functionality."""
    print_header("HEALTH CHECK")

    print("\nPinging key models...")
    result = await engine.health_check()

    print(f"\nOverall status: {result['overall']}")
    print(f"Timestamp: {result['timestamp']}")

    for model, status in result['models'].items():
        emoji = "✅" if status['status'] == 'ok' else "❌"
        if status['status'] == 'ok':
            print(f"  {emoji} {model}: {status['latency_ms']}ms")
        else:
            print(f"  {emoji} {model}: {status.get('error', 'failed')[:50]}")


async def test_short_generation(engine: AIEngine):
    """Test short content generation (social post)."""
    print_header("TEST: SHORT-FORM GENERATION (Social Post)")

    topic = "New KITAS regulations in Indonesia 2025 - processing time reduced to 3 days"

    print(f"\nTopic: {topic}")
    print("Task: SHORT_FORM (Social Post)")
    print("Expected models: Mistral Small → Gemini Flash → DeepSeek Chat")
    print("\nGenerating...")

    try:
        content, model = await engine.generate_social_post(
            topic=topic,
            platform="twitter",
        )

        print(f"\n✅ Success with: {model.name} ({model.provider})")
        print(f"\nGenerated content ({len(content)} chars):")
        print("-" * 40)
        print(content[:500] + ("..." if len(content) > 500 else ""))
        print("-" * 40)

        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False


async def test_long_generation(engine: AIEngine):
    """Test long content generation (article)."""
    print_header("TEST: LONG-FORM GENERATION (Article)")

    topic = "Guide to E33G Remote Worker KITAS for Digital Nomads in Bali"

    print(f"\nTopic: {topic}")
    print("Task: LONG_FORM (Article)")
    print("Expected models: Gemini 2.5 Pro → Llama Scout → DeepSeek V3.1")
    print("\nGenerating (this may take 30-60 seconds)...")

    try:
        content, model = await engine.generate_article(
            topic=topic,
            language="en",
            tone="professional",
        )

        print(f"\n✅ Success with: {model.name} ({model.provider})")
        print(f"\nGenerated content ({len(content)} chars, ~{len(content.split())} words):")
        print("-" * 40)
        # Show first 800 chars
        print(content[:800] + ("..." if len(content) > 800 else ""))
        print("-" * 40)

        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False


async def test_reasoning(engine: AIEngine):
    """Test reasoning/analysis generation."""
    print_header("TEST: REASONING GENERATION (Analysis)")

    intel = "Indonesian government announces new tax amnesty program for 2025, targeting overseas assets of Indonesian citizens"

    print(f"\nIntel: {intel[:80]}...")
    print("Task: REASONING (Analysis)")
    print("Expected models: DeepSeek R1 → Gemini Thinking → QwQ-32B")
    print("\nAnalyzing (reasoning models can be slower)...")

    try:
        content, model = await engine.analyze_intel(
            intel_summary=intel,
            source="DJP Online",
            category="tax",
        )

        print(f"\n✅ Success with: {model.name} ({model.provider})")
        print(f"\nAnalysis ({len(content)} chars):")
        print("-" * 40)
        print(content[:600] + ("..." if len(content) > 600 else ""))
        print("-" * 40)

        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False


async def test_thread_generation(engine: AIEngine):
    """Test Twitter thread generation."""
    print_header("TEST: THREAD GENERATION (Twitter)")

    topic = "5 things expats in Bali MUST know about the 2025 tax changes"

    print(f"\nTopic: {topic}")
    print("Task: THREAD")
    print("Expected models: DeepSeek Chat → Llama 3.3 → Llama Scout")
    print("\nGenerating thread...")

    try:
        content, model = await engine.generate_thread(
            topic=topic,
            num_posts=5,
        )

        print(f"\n✅ Success with: {model.name} ({model.provider})")
        print(f"\nThread:")
        print("-" * 40)
        print(content[:800] + ("..." if len(content) > 800 else ""))
        print("-" * 40)

        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False


async def test_summarization(engine: AIEngine):
    """Test content summarization."""
    print_header("TEST: SUMMARIZATION")

    long_content = """
    The Indonesian government has announced significant changes to the remote worker visa program,
    known as the E33G KITAS. Starting January 2025, the processing time for this visa category
    has been reduced from the previous 14 working days to just 3 working days. This change is
    part of the government's broader initiative to attract digital nomads and remote workers to
    Indonesia, particularly to destinations like Bali.

    The new regulations also include several other improvements: the visa validity period has
    been extended from 1 year to 2 years, the minimum income requirement has been adjusted to
    $60,000 per year (down from $75,000), and applicants can now apply online through the new
    digital immigration portal.

    However, there are some important considerations for applicants. The visa still requires
    proof of health insurance coverage valid in Indonesia, a clean criminal record from the
    applicant's home country, and evidence of ongoing employment or business ownership outside
    Indonesia. Tax implications have also been clarified - remote workers on this visa will be
    considered tax residents if they stay in Indonesia for more than 183 days in a calendar year.
    """

    print(f"\nOriginal content: {len(long_content)} chars")
    print("Task: SUMMARIZATION")
    print("Expected models: Gemini Flash → Llama Scout → Mistral")
    print("\nSummarizing...")

    try:
        summary, model = await engine.summarize(long_content, "short")

        print(f"\n✅ Success with: {model.name} ({model.provider})")
        print(f"\nSummary ({len(summary)} chars):")
        print("-" * 40)
        print(summary)
        print("-" * 40)

        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False


async def test_translation(engine: AIEngine):
    """Test content translation."""
    print_header("TEST: TRANSLATION (EN → ID)")

    content = "Welcome to Bali Zero! We help expats navigate business and life in Indonesia."

    print(f"\nOriginal (EN): {content}")
    print("Task: TRANSLATION")
    print("Expected models: Gemini Flash → Gemini 2.5 → DeepSeek Chat")
    print("\nTranslating...")

    try:
        translation, model = await engine.translate(content, "English", "Indonesian")

        print(f"\n✅ Success with: {model.name} ({model.provider})")
        print(f"\nTranslation (ID):")
        print("-" * 40)
        print(translation)
        print("-" * 40)

        return True

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        return False


async def show_final_status(engine: AIEngine):
    """Show final model status after tests."""
    print_header("FINAL MODEL STATUS")

    status = engine.get_model_status()

    print(f"\nHealthy models: {len(engine.get_healthy_models())}/{len(FREE_MODELS)}")
    print("\nModel Performance:")

    # Sort by health score
    sorted_status = sorted(status, key=lambda x: x['health_score'], reverse=True)

    for s in sorted_status:
        if s['success_count'] > 0 or s['failure_count'] > 0:
            emoji = "✅" if s['is_healthy'] else "⚠️"
            print(f"  {emoji} {s['name']}: {s['success_count']} ok, {s['failure_count']} fail, {s['avg_latency_ms']:.0f}ms avg")


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("  ZANTARA AI ENGINE - TEST SUITE")
    print("  Using OpenRouter FREE Models")
    print("="*60)

    # Initialize engine
    engine = AIEngine(API_KEY)

    # Show models info
    print_models_info()

    results = {}

    # Run tests
    try:
        # 1. Health check
        await test_health_check(engine)

        # 2. Short generation (fastest)
        results['short_form'] = await test_short_generation(engine)

        # 3. Summarization (fast)
        results['summarization'] = await test_summarization(engine)

        # 4. Translation (fast)
        results['translation'] = await test_translation(engine)

        # 5. Thread generation (medium)
        results['thread'] = await test_thread_generation(engine)

        # 6. Reasoning (can be slow)
        results['reasoning'] = await test_reasoning(engine)

        # 7. Long form (slowest)
        results['long_form'] = await test_long_generation(engine)

    finally:
        await engine.close()

    # Show final status
    await show_final_status(AIEngine(API_KEY))

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
