import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

# Load env vars
load_dotenv(override=True)

# Add project root to sys.path
sys.path.append(os.getcwd())

import google.generativeai as genai

from services.rag.agentic import AgenticRAGOrchestrator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configure Gemini
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env")
genai.configure(api_key=api_key)


async def test_soul_persona():
    logger.info("🔮 Testing The Soul of Zantara (Charisma Upgrade)...")

    # Use the model defined in agentic.py
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
    except Exception as e:
        logger.warning("Fallback to gemini-1.5-pro due to: %s", e)
        model = genai.GenerativeModel("gemini-1.5-pro")

    orchestrator = AgenticRAGOrchestrator()

    # Query designed to trigger the "Pivot" (Straight answer -> Strategy risk)
    user_query = "Cara, gue mau setup PT PMA tapi modal 10M itu kegedean. Bisa pake nominee gak?"

    from prompts.jaksel_persona import SYSTEM_INSTRUCTION

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
    response = model.generate_content(prompt)

    logger.info("Zantara Response:")
    logger.info(response.text)
    logger.info("--------------------------------------------------")

    text = response.text.lower()
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
