#!/usr/bin/env python3
"""
Test script for KBLI Notebook chat fix.

This script tests the critical fix for the empty `answer` field issue
in the /api/v1/kbli-notebook/chat endpoint.

Usage:
    cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
    source .venv/bin/activate
    python test_kbli_chat_fix.py

Environment Variables Required:
    - GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS (for LLM)
    - QDRANT_URL (for search)
    - OPENAI_API_KEY (for embeddings)
"""

import asyncio
import os
import sys

# Add the backend to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_llm_gateway():
    """Test LLM Gateway availability and response generation."""
    print("=" * 60)
    print("TEST 1: LLM Gateway Availability")
    print("=" * 60)

    try:
        from backend.services.rag.agentic.llm_gateway import TIER_FLASH, LLMGateway

        gateway = LLMGateway()
        print("✅ LLMGateway initialized")
        print(f"   Available: {gateway._available}")
        print(f"   Primary Model: {gateway.model_name_flash}")
        print(f"   Fallback Model: {gateway.model_name_fallback}")

        if not gateway._available:
            print("\n❌ CRITICAL: LLM Gateway is not available!")
            print("   Please check:")
            print("   - GOOGLE_API_KEY is set correctly")
            print("   - GOOGLE_APPLICATION_CREDENTIALS is configured")
            return False

        # Test simple generation
        print("\n   Testing simple generation...")
        chat = gateway.create_chat_with_history(
            history_to_use=[],
            model_tier=TIER_FLASH,
            system_instruction="You are a helpful assistant. Be brief.",
        )

        response_text, model_used, resp_obj, usage = await gateway.send_message(
            chat=chat,
            message="Say 'OK'",
            system_prompt="You are a helpful assistant. Be brief.",
            tier=TIER_FLASH,
            enable_function_calling=False,
            conversation_messages=[{"role": "user", "content": "Say 'OK'"}],
        )

        print(f"   Model used: {model_used}")
        print(
            f"   Response: '{response_text[:100]}...' "
            if len(response_text) > 100
            else f"   Response: '{response_text}'"
        )
        print(f"   Tokens: {usage.prompt_tokens} prompt, {usage.completion_tokens} completion")
        print(f"   Cost: ${usage.cost_usd:.6f}")

        if not response_text or not response_text.strip():
            print("\n❌ CRITICAL: LLM returned empty response!")
            return False

        print("\n✅ LLM Gateway test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_kbli_explanation():
    """Test the KBLI explanation generation function."""
    print("\n" + "=" * 60)
    print("TEST 2: KBLI Explanation Generation")
    print("=" * 60)

    try:
        from backend.app.routers.kbli_notebook import KBLISearchResult, _generate_kbli_explanation

        # Create mock results
        mock_results = [
            KBLISearchResult(
                code="47111",
                title="Supermarket",
                description="Retail trade of various goods in supermarkets...",
                score=0.95,
                pma_status="TERBATAS",
                risk_category="High",
            ),
            KBLISearchResult(
                code="56101",
                title="Restoran",
                description="Restaurant activities...",
                score=0.87,
                pma_status="TERBUKA",
                risk_category="Medium",
            ),
        ]

        print("   Testing with query: 'voglio aprire un ristorante'")
        answer = await _generate_kbli_explanation("voglio aprire un ristorante", mock_results)

        print(f"   Answer length: {len(answer)} characters")
        print(
            f"   Answer preview: '{answer[:150]}...'"
            if len(answer) > 150
            else f"   Answer: '{answer}'"
        )

        if not answer or not answer.strip():
            print("\n❌ CRITICAL: Answer is empty!")
            return False

        if len(answer) < 10:
            print(f"\n❌ WARNING: Answer is suspiciously short ({len(answer)} chars)")
            return False

        print("\n✅ KBLI Explanation test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_empty_results_fallback():
    """Test fallback behavior when no results are found."""
    print("\n" + "=" * 60)
    print("TEST 3: Empty Results Fallback")
    print("=" * 60)

    try:
        from backend.app.routers.kbli_notebook import _generate_kbli_explanation

        print("   Testing with empty results...")
        answer = await _generate_kbli_explanation("query", [])

        print(f"   Answer: '{answer}'")

        if not answer or not answer.strip():
            print("\n❌ CRITICAL: Empty results fallback returned empty answer!")
            return False

        print("\n✅ Empty Results Fallback test PASSED")
        return True

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        return False


def check_environment():
    """Check required environment variables."""
    print("=" * 60)
    print("ENVIRONMENT CHECK")
    print("=" * 60)

    required_vars = {
        "GOOGLE_API_KEY": "For LLM generation (Gemini)",
        "GOOGLE_APPLICATION_CREDENTIALS": "Alternative to GOOGLE_API_KEY (Service Account)",
        "OPENAI_API_KEY": "For embeddings",
        "QDRANT_URL": "For vector search",
    }

    missing = []
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if value:
            # Mask the value for security
            masked = value[:10] + "..." if len(value) > 10 else "***"
            print(f"   ✅ {var}: {masked} ({description})")
        else:
            print(f"   ❌ {var}: NOT SET ({description})")
            if var not in [
                "GOOGLE_API_KEY",
                "GOOGLE_APPLICATION_CREDENTIALS",
            ]:  # At least one needed
                missing.append(var)

    # Check if at least one Google auth method is available
    has_google_auth = bool(
        os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    )
    if not has_google_auth:
        print("\n   ❌ CRITICAL: No Google authentication configured!")
        print("      Set either GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS")
        missing.append("GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS")

    print()
    return len(missing) == 0


async def main():
    """Run all tests."""
    print("\n🔧 KBLI Notebook Chat Fix Verification\n")

    # Check environment first
    check_environment()

    # Run tests
    results = []

    # Test 1: LLM Gateway
    llm_ok = await test_llm_gateway()
    results.append(("LLM Gateway", llm_ok))

    # Test 2: KBLI Explanation (only if LLM is available)
    if llm_ok:
        expl_ok = await test_kbli_explanation()
        results.append(("KBLI Explanation", expl_ok))
    else:
        print("\n⚠️  Skipping KBLI Explanation test (LLM not available)")
        results.append(("KBLI Explanation", False))

    # Test 3: Empty Results Fallback
    empty_ok = await test_empty_results_fallback()
    results.append(("Empty Results Fallback", empty_ok))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {status}: {name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n🎉 All tests PASSED! The fix is working correctly.")
    else:
        print("\n⚠️  Some tests FAILED. Please check the errors above.")
        print("\nTroubleshooting:")
        print("   1. Ensure GOOGLE_API_KEY is set correctly")
        print("   2. Check that the API key has access to Gemini models")
        print("   3. Verify Qdrant is accessible")
        print("   4. Check logs for more details")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
