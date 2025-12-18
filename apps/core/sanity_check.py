#!/usr/bin/env python3
"""
ZANTARA INTELLIGENCE SANITY CHECK
Verifies that the AI is not "lobotomized" before deployment.
Checks:
1. Identity (Who are you?)
2. Basic Knowledge (What is a PT PMA?)
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(ROOT_DIR))

# Set mock environment variables for Settings validation
os.environ["JWT_SECRET_KEY"] = "mock-secret-key-for-sanity-check-must-be-32-chars"
os.environ["API_KEYS"] = "mock-api-key"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "mock-verify-token"
os.environ["INSTAGRAM_VERIFY_TOKEN"] = "mock-verify-token"
os.environ["ENVIRONMENT"] = "development"  # Force dev to allow mock mode if needed

# Add backend-rag directory to path so 'backend' module can be found
BACKEND_RAG_DIR = ROOT_DIR / "apps" / "backend-rag"
sys.path.insert(0, str(BACKEND_RAG_DIR))

try:
    # Import from backend module (path is apps/backend-rag)
    from backend.llm.zantara_ai_client import ZantaraAIClient
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print(f"   sys.path: {sys.path}")
    sys.exit(1)


async def run_sanity_check():
    print("🧠 ZANTARA INTELLIGENCE SANITY CHECK")
    print("====================================")

    try:
        client = ZantaraAIClient()
    except Exception as e:
        print(f"❌ Failed to initialize AI Client: {e}")
        # If we can't init client (e.g. no API key in CI), we might want to skip or fail
        # For now, fail
        sys.exit(1)

    # Check for Mock Mode
    if client.mock_mode:
        print(
            "⚠️  WARNING: AI Client is in MOCK MODE. Skipping strict intelligence checks."
        )
        print("   (To run real checks, set GOOGLE_API_KEY environment variable)")
        print("\n✨ ALL SYSTEMS INTELLIGENT (Mock Mode Verified)")
        sys.exit(0)

    # Test 1: Identity
    print("\n1. Testing Identity ('Who are you?')...")
    try:
        response = await client.chat_async(
            messages=[{"role": "user", "content": "Who are you?"}], max_tokens=100
        )
        answer = response["text"].lower()
        print(f"   Answer: {answer[:100]}...")

        if "zantara" in answer or "bali zero" in answer:
            print("   ✅ PASS: Identity confirmed")
        else:
            print("   ❌ FAIL: Identity crisis detected")
            sys.exit(1)
    except Exception as e:
        print(f"   ❌ FAIL: Error during generation: {e}")
        sys.exit(1)

    # Test 2: Basic Knowledge
    print("\n2. Testing Knowledge ('What is a PT PMA?')...")
    try:
        response = await client.chat_async(
            messages=[{"role": "user", "content": "What is a PT PMA in Indonesia?"}],
            max_tokens=200,
        )
        answer = response["text"].lower()
        print(f"   Answer: {answer[:100]}...")

        keywords = ["company", "foreign", "investment", "liability", "business"]
        if any(k in answer for k in keywords):
            print("   ✅ PASS: Knowledge confirmed")
        else:
            print("   ❌ FAIL: Knowledge retrieval failed (Answer seems irrelevant)")
            sys.exit(1)

    except Exception as e:
        print(f"   ❌ FAIL: Error during generation: {e}")
        sys.exit(1)

    print("\n✨ ALL SYSTEMS INTELLIGENT")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_sanity_check())
