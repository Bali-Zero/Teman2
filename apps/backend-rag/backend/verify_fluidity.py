import asyncio
import logging
import os
import sys
from pathlib import Path

# Add current directory to path to allow imports
sys.path.append(os.getcwd())

from backend.app.core.constants import EvidenceScoreConstants
from backend.services.classification.intent_classifier import IntentClassifier

# Configure logger for test output
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


async def test_identity_intent():
    logger.info("\n--- TEST 1: Identity Intent (Tier 0) ---")
    classifier = IntentClassifier()
    query = "tu chi sei"
    result = await classifier.classify_intent(query)
    logger.info(f"Query: '{query}'")
    logger.info(f"Intent classified: {result.get('intent', result.get('category', 'unknown'))}")
    logger.info(f"Skip RAG: {result.get('skip_rag', False)}")

    intent = result.get("intent") or result.get("category", "")
    if intent == "identity" and result.get("skip_rag") is True:
        logger.info("✅ PASS: Identity intent correctly triggers skip_rag=True")
    else:
        logger.info("❌ FAIL: Identity intent did NOT set skip_rag=True")


async def test_fluid_fallback_implementation():
    logger.info("\n--- TEST 2: Fluid Fallback Implementation (Tier 1) ---")
    # Verify that the actual implementation exists in reasoning.py

    backend_path = Path(__file__).parent
    reasoning_file = backend_path / "services" / "rag" / "agentic" / "reasoning.py"

    if not reasoning_file.exists():
        logger.info("❌ FAIL: reasoning.py not found")
        return

    reasoning_content = reasoning_file.read_text()

    # Check 1: _is_critical_domain function exists
    if "_is_critical_domain" in reasoning_content:
        logger.info("✅ PASS: _is_critical_domain function exists")
    else:
        logger.info("❌ FAIL: _is_critical_domain function NOT found")

    # Check 2: Transparency Protocol instruction exists
    transparency_markers = [
        "SYSTEM NOTICE: LOW CONFIDENCE RETRIEVAL",
        "Non ho trovato documenti interni verificati",
        "conoscenza generale",
        "Tier 1",
    ]

    found_markers = sum(1 for marker in transparency_markers if marker in reasoning_content)
    logger.info(f"Found {found_markers}/{len(transparency_markers)} Transparency Protocol markers")

    if found_markers >= 3:
        logger.info("✅ PASS: Transparency Protocol implementation found")
    else:
        logger.info("❌ FAIL: Transparency Protocol implementation incomplete")

    # Check 3: Critical domain logic (ABSTAIN for critical, Tier 1 for non-critical)
    if "is_critical = _is_critical_domain" in reasoning_content:
        logger.info("✅ PASS: Critical domain check logic exists")
    else:
        logger.info("❌ FAIL: Critical domain check logic NOT found")

    # Check 4: Both paths exist (ABSTAIN for critical, Tier 1 for non-critical)
    has_abstain_path = (
        "STRICT ABSTAIN" in reasoning_content or "Triggered ABSTAIN" in reasoning_content
    )
    has_tier1_path = "Tier 1" in reasoning_content and "General Intelligence" in reasoning_content

    if has_abstain_path and has_tier1_path:
        logger.info("✅ PASS: Both ABSTAIN (critical) and Tier 1 (non-critical) paths exist")
    else:
        logger.info(
            f"⚠️  WARNING: Missing paths - ABSTAIN: {has_abstain_path}, Tier 1: {has_tier1_path}",
        )


async def test_critical_domain_detection():
    logger.info("\n--- TEST 3: Critical Domain Detection ---")
    # Import and test the _is_critical_domain function

    try:
        from backend.services.rag.agentic.reasoning import _is_critical_domain

        # Test critical queries
        critical_queries = [
            ("Quanto costa il KITAS E33G?", "business_simple"),
            ("Quali sono i requisiti per il visto?", "business_complex"),
            ("Parlami della legge sul PMA", "business_complex"),
            ("Prezzo servizio visa", "business_simple"),
        ]

        # Test non-critical queries
        non_critical_queries = [
            ("Come funziona il sistema solare?", "casual"),
            ("Qual è la capitale dell'Indonesia?", "casual"),
            ("Dimmi qualcosa su Bali", "casual"),
        ]

        logger.info("Testing critical queries (should return True):")
        all_critical_correct = True
        for query, intent in critical_queries:
            is_critical = _is_critical_domain(query, intent)
            status = "✅" if is_critical else "❌"
            logger.info(f"  {status} '{query}' -> {is_critical}")
            if not is_critical:
                all_critical_correct = False

        logger.info("\nTesting non-critical queries (should return False):")
        all_non_critical_correct = True
        for query, intent in non_critical_queries:
            is_critical = _is_critical_domain(query, intent)
            status = "✅" if not is_critical else "❌"
            logger.info(f"  {status} '{query}' -> {is_critical}")
            if is_critical:
                all_non_critical_correct = False

        if all_critical_correct and all_non_critical_correct:
            logger.info("\n✅ PASS: Critical domain detection works correctly")
        else:
            logger.info("\n❌ FAIL: Critical domain detection has issues")

    except ImportError as e:
        logger.info(f"❌ FAIL: Could not import _is_critical_domain: {e}")


async def test_constants():
    logger.info("\n--- TEST 4: Constants Tuning ---")
    logger.info(f"ABSTAIN_THRESHOLD: {EvidenceScoreConstants.ABSTAIN_THRESHOLD}")
    logger.info(f"CONTEXT_KEYWORD_BONUS: {EvidenceScoreConstants.CONTEXT_KEYWORD_BONUS}")

    if EvidenceScoreConstants.ABSTAIN_THRESHOLD == 0.15:
        logger.info("✅ PASS: ABSTAIN_THRESHOLD is lowered to 0.15")
    else:
        logger.info(
            f"❌ FAIL: ABSTAIN_THRESHOLD is {EvidenceScoreConstants.ABSTAIN_THRESHOLD} (expected 0.15)",
        )

    if EvidenceScoreConstants.CONTEXT_KEYWORD_BONUS == 0.35:
        logger.info("✅ PASS: CONTEXT_KEYWORD_BONUS is increased to 0.35")
    else:
        logger.info(
            f"⚠️  WARNING: CONTEXT_KEYWORD_BONUS is {EvidenceScoreConstants.CONTEXT_KEYWORD_BONUS} (expected 0.35)",
        )


async def main():
    logger.info("=" * 60)
    logger.info("FLUIDITY VERIFICATION TEST SUITE")
    logger.info("=" * 60)

    await test_identity_intent()
    await test_fluid_fallback_implementation()
    await test_critical_domain_detection()
    await test_constants()

    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
