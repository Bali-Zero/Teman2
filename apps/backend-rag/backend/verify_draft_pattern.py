"""
Test Draft-Verify Logic
Simulates a query that might cause hallucinations (fake law) to see if Verifier catches it.
"""
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.join(os.getcwd(), "apps/backend-rag/backend"))

# Mock environment - ensure API key is present
os.environ["GOOGLE_API_KEY"] = "AIza_REDACTED"

from services.rag.verification_service import verification_service


async def test_verifier():
    print("🛡️ Testing Verification Service Standalone...")

    # fake context
    context = [
        "The standard VAT rate in Indonesia is 11% as of 2022.",
        "Corporate Income Tax is generally 22%.",
    ]

    # 1. Good Draft
    good_draft = "In Indonesia, the VAT rate is 11% and corporate tax is 22%."
    res_good = await verification_service.verify_response(
        "What are the tax rates?", good_draft, context
    )
    print(f"\n✅ Good Draft check: {res_good.status} (Score: {res_good.score})")

    # 2. Hallucination Draft
    bad_draft = "The Orbital Tax Law of 2029 introduces a 50% tax on space travel."
    res_bad = await verification_service.verify_response(
        "Tell me about space tax", bad_draft, context
    )
    print(f"❌ Bad Draft check: {res_bad.status} (Score: {res_bad.score})")
    print(f"   Reasoning: {res_bad.reasoning}")


if __name__ == "__main__":
    asyncio.run(test_verifier())
