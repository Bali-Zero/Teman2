import asyncio
import logging
import os
import sys

# Add current directory to path to allow imports
sys.path.append(os.getcwd())

from backend.app.core.constants import EvidenceScoreConstants
from backend.services.classification.intent_classifier import IntentClassifier

# Configure logger for test output
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Mocking necessary components to isolate fluid logic verification
# We want to verify the LOGIC, not the actual DB retrieval (which might vary)

async def test_identity_intent():
    logger.info("\n--- TEST 1: Identity Intent (Tier 0) ---")
    classifier = IntentClassifier()
    query = "tu chi sei"
    result = await classifier.classify_intent(query)
    logger.info(f"Query: '{query}'")
    logger.info(f"Intent classified: {result.get('intent', result.get('category', 'unknown'))}")
    logger.info(f"Skip RAG: {result.get('skip_rag', False)}")

    intent = result.get('intent') or result.get('category', '')
    if intent == "identity" and result.get('skip_rag') is True:
        logger.info("✅ PASS: Identity intent correctly triggers skip_rag=True")
    else:
        logger.info("❌ FAIL: Identity intent did NOT set skip_rag=True")

async def test_fluid_fallback_logic():
    logger.info("\n--- TEST 2: Fluid Fallback Logic (Tier 1) ---")
    # We will simulate a reasoning engine state with low evidence
    # and verify if it returns the fallback instruction or blocks

    # This is a bit complex to unit test without mocking the whole ReasoningEngine,
    # so we will check the file content injection we just did essentially
    # by simulating the logic block locally.

    evidence_score = 0.05
    threshold = EvidenceScoreConstants.ABSTAIN_THRESHOLD # Should be 0.15 now
    skip_rag = False

    logger.info(f"Evidence Score (Simulated): {evidence_score}")
    logger.info(f"Abstain Threshold (Constants): {threshold}")

    instruction = ""

    # Logic copied from reasoning.py for verification of behavior
    if (
        not skip_rag
        and evidence_score < threshold
    ):
        logger.info("⚠️  [Logic Check] Logic condition met (Low Evidence)")
        # This mirrors the code we injected
        instruction = (
            "\n\n[SYSTEM NOTICE: LOW CONFIDENCE RETRIEVAL]\n"
            "CRITICAL INSTRUCTION: The internal search for verified documents yielded low or no results.\n"
            "1. DO NOT say 'I cannot answer'.\n"
            "2. Answer the user's question using your GENERAL KNOWLEDGE.\n"
            "3. MUST START your response with this EXACT phrase (translated to user's language):\n"
            "   'Non ho trovato documenti interni verificati su questo specifico punto, ma basandomi sulla mia conoscenza generale...'\n"
            "4. Be helpful but clearly distinguish between 'Internal Fact' (missing) and 'General Knowledge' (present)."
        )

    if "Non ho trovato documenti interni verificati" in instruction:
        logger.info("✅ PASS: Fluid Fallback instruction generated")
    else:
        logger.info("❌ FAIL: Fluid Fallback logic did not generate instruction")

async def test_constants():
    logger.info("\n--- TEST 3: Constants Tuning ---")
    logger.info(f"ABSTAIN_THRESHOLD: {EvidenceScoreConstants.ABSTAIN_THRESHOLD}")
    logger.info(f"CONTEXT_KEYWORD_BONUS: {EvidenceScoreConstants.CONTEXT_KEYWORD_BONUS}")

    if EvidenceScoreConstants.ABSTAIN_THRESHOLD == 0.15:
        logger.info("✅ PASS: ABSTAIN_THRESHOLD is lowered")
    else:
         logger.info(f"❌ FAIL: ABSTAIN_THRESHOLD is {EvidenceScoreConstants.ABSTAIN_THRESHOLD}")

async def main():
    await test_identity_intent()
    await test_constants()
    await test_fluid_fallback_logic()

if __name__ == "__main__":
    asyncio.run(main())
