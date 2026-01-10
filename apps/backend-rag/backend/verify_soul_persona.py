"""
Verify Soul Persona - Test script for Zantara personality

UPDATED 2025-12-23:
- Migrated to new google-genai SDK via GenAIClient wrapper
"""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# Load env vars
load_dotenv(override=True)

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend.llm.genai_client import GENAI_AVAILABLE, GenAIClient

from backend.services.rag.agentic import AgenticRAGOrchestrator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize GenAI client
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env")

_genai_client = None
if GENAI_AVAILABLE:
    _genai_client = GenAIClient(api_key=api_key)
    if not _genai_client.is_available:
        raise RuntimeError("GenAI client initialization failed")


async def test_soul_persona():
    logger.info("🔮 Testing The Soul of Zantara (Charisma Upgrade)...")

    if not _genai_client or not _genai_client.is_available:
        raise RuntimeError("GenAI client not available")

    model_name = "gemini-2.0-flash"

    orchestrator = AgenticRAGOrchestrator()

    # Query designed to trigger the "Pivot" (Straight answer -> Strategy risk)
    user_query = "Cara, gue mau setup PT PMA tapi modal 10M itu kegedean. Bisa pake nominee gak?"

    from backend.prompts.jaksel_persona import SYSTEM_INSTRUCTION

    logger.info("\n--- SYSTEM PROMPT (Snippet) ---")
    logger.info("%s...", SYSTEM_INSTRUCTION[:300])
    logger.info("-------------------------------")

    logger.info("\nUser Query: %s", user_query)
    logger.info("--------------------------------------------------")

    # We simulate a direct call to the model with the persona to see the raw style
    # iterating over agentic flow might be too complex for a unit test, let's just
    # test the prompt's influence on a direct generation or use orchestrator if possible.
    # The orchestrator uses _build_system_prompt which includes JAKSEL_PERSONA.

    # Let's use the orchestrator to be authentic
    # This might require DB connection which we want to avoid if possible,
    # but AgenticRAGOrchestrator needs db_pool for tools.
    # If we just want to test the prompt tone, we can simple call the model with the system instruction.

    prompt = f"{SYSTEM_INSTRUCTION}\n\nUser: {user_query}\nZantara:"
    result = await _genai_client.generate_content(
        contents=prompt,
        model=model_name,
        max_output_tokens=8192,
    )
    response_text = result.get("text", "")

    logger.info("Zantara Response:")
    logger.info(response_text)
    logger.info("--------------------------------------------------")

    text = response_text.lower()
    markers = [
        "straight to",
        "but wait",
        "strategically",
        "sedia payung",
        "alon-alon",
        "nominee",
        "risk",
        "10m",
        "safe",
        "foundation",
    ]
    found = [m for m in markers if m in text]
    logger.info("✅ Markers found: %s", found)


if __name__ == "__main__":
    asyncio.run(test_soul_persona())
