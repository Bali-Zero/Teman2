import asyncio
import sys
import os
import logging

# Configure logging FIRST
logging.basicConfig(level=logging.INFO)

# Ensure backend modules can be imported
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "apps", "backend-rag"))

print("🚀 INITIALIZING ZANTARA IDENTITY CHECK...")

from backend.services.rag.agentic.llm_gateway import LLMGateway
from backend.services.rag.agentic.prompt_builder import SystemPromptBuilder
from backend.services.rag.agentic.llm_gateway import TIER_FLASH


async def test_identity():
    # 1. Initialize Gateway
    gateway = LLMGateway()
    print(f"✅ Gateway initialized with model: {gateway.model_name_flash}")

    if "gemini-3" not in gateway.model_name_flash:
        print("❌ CRITICAL FAIL: DEFAULT MODEL IS NOT GEMINI 3!")
        return

    # 2. Build Zantara Prompt (Identity Fusion)
    builder = SystemPromptBuilder()
    context = {
        "profile": {
            "name": "Antonello",
            "role": "Creator",
            "email": "antonello@balizero.com",
        },
        "facts": ["User is the Creator"],
    }
    # Force minimal prompt but with identity
    system_prompt = builder.build_system_prompt(
        user_id="antonello@balizero.com", context=context, query="Who are you?"
    )

    print("\n📜 SYSTEM PROMPT GENERATED (Snippet):")
    print(system_prompt[:200] + "...")

    # 3. Send Message
    print("\n💬 SENDING QUERY: 'Who are you?'")
    try:
        response_text, model_used, _, _ = await gateway.send_message(
            chat=None,
            message="Who are you? Answer briefly.",
            system_prompt=system_prompt,  # This is key for OpenRouter fallback, but for Gemini it should be passed in config
            tier=TIER_FLASH,
        )

        print("\n🤖 RESPONSE:")
        print(f"Model Used: {model_used}")
        print("-" * 40)
        print(response_text)
        print("-" * 40)

        if (
            "google" in response_text.lower()
            and "large language model" in response_text.lower()
        ):
            print("❌ FAIL: Generic AI identity detected.")
        elif "zantara" in response_text.lower():
            print("✅ SUCCESS: Zantara Identity Confirmed.")
        else:
            print("⚠️ WARNING: Identity ambiguous.")

    except Exception as e:
        print(f"❌ ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(test_identity())
