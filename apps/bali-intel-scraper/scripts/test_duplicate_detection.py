#!/usr/bin/env python3
"""
Test Anti-Duplicate Detection System
Verifica che il sistema riconosca duplicati in varie forme.
"""

import asyncio
import json
from pathlib import Path
from claude_validator import ClaudeValidator
from loguru import logger

# Setup logging
logger.remove()
logger.add(
    lambda msg: print(msg, end=""),
    format="<level>{level: <8}</level> | <level>{message}</level>",
    colorize=True,
)


async def test_duplicate_detection():
    """Test complete duplicate detection workflow"""

    logger.info("=" * 70)
    logger.info("🧪 ANTI-DUPLICATE DETECTION TEST")
    logger.info("=" * 70)

    # Step 1: Setup - Clear registry and add test articles
    logger.info("\n📝 Step 1: Preparing test registry...")

    test_registry = Path(__file__).parent / "data" / "test_published_articles.json"
    test_registry.parent.mkdir(parents=True, exist_ok=True)

    # Create test registry with sample published articles
    test_data = {
        "last_updated": "2026-01-05T10:00:00",
        "count": 3,
        "articles": [
            {
                "title": "Indonesia Extends Digital Nomad Visa to 5 Years",
                "url": "https://balizero.com/immigration/nomad-visa-extension",
                "category": "immigration",
                "published_at": "2026-01-04T09:00:00",
            },
            {
                "title": "New Coretax System Causing NPWP Registration Delays",
                "url": "https://balizero.com/tax/coretax-npwp-delays",
                "category": "tax-legal",
                "published_at": "2026-01-03T14:30:00",
            },
            {
                "title": "Bali Property Tax Increases by 15% in 2026",
                "url": "https://balizero.com/property/bali-tax-increase",
                "category": "property",
                "published_at": "2026-01-02T11:00:00",
            },
        ],
    }

    # Save test registry
    with open(test_registry, "w") as f:
        json.dump(test_data, f, indent=2, ensure_ascii=False)

    logger.success(
        f"✅ Created test registry with {len(test_data['articles'])} published articles"
    )

    # Temporarily replace registry file
    original_file = ClaudeValidator.__dict__.get("PUBLISHED_ARTICLES_FILE")

    # Step 2: Test Quick Duplicate Check
    logger.info("\n🔍 Step 2: Testing quick keyword-based duplicate detection...")

    validator = ClaudeValidator(use_web_research=False)
    validator.published_articles = test_data["articles"]  # Inject test data

    test_cases_quick = [
        {
            "title": "Indonesian Digital Nomad Visa Extended to Five Years",
            "expected": True,  # Should detect (80% keyword overlap)
            "reason": "Same topic, different wording",
        },
        {
            "title": "Indonesia's New 5-Year Digital Nomad Visa Policy",
            "expected": True,  # Should detect (high keyword overlap)
            "reason": "Same topic, reordered words",
        },
        {
            "title": "Coretax NPWP Registration Problems Continue",
            "expected": True,  # Should detect (60%+ overlap)
            "reason": "Same topic about Coretax + NPWP",
        },
        {
            "title": "Indonesia Introduces New Startup Visa for Entrepreneurs",
            "expected": False,  # Should NOT detect (different topic)
            "reason": "Different visa type (startup vs nomad)",
        },
        {
            "title": "Jakarta Traffic Congestion Reaches Record Levels",
            "expected": False,  # Should NOT detect (completely different)
            "reason": "Completely unrelated topic",
        },
    ]

    quick_check_passed = 0
    quick_check_failed = 0

    for i, test in enumerate(test_cases_quick, 1):
        result = validator._quick_duplicate_check(test["title"])
        is_duplicate = result is not None

        if is_duplicate == test["expected"]:
            logger.success(
                f"  ✅ Test {i}: {test['title'][:50]}..."
                + f"\n     Expected: {test['expected']}, Got: {is_duplicate}"
                + (f" (similar to: {result[:40]}...)" if result else "")
            )
            quick_check_passed += 1
        else:
            logger.error(
                f"  ❌ Test {i}: {test['title'][:50]}..."
                + f"\n     Expected: {test['expected']}, Got: {is_duplicate}"
                + f"\n     Reason: {test['reason']}"
            )
            quick_check_failed += 1

    logger.info(
        f"\n📊 Quick Check Results: {quick_check_passed}/{len(test_cases_quick)} passed"
    )

    # Step 3: Test Claude Semantic Validation (requires API)
    logger.info("\n🤖 Step 3: Testing Claude semantic duplicate detection...")
    logger.warning(
        "⚠️  This requires Claude Desktop CLI and may take 20-30 seconds per test"
    )

    # Ask user if they want to run Claude tests
    import sys

    if "--skip-claude" in sys.argv:
        logger.info("   ⏭️  Skipping Claude tests (--skip-claude flag detected)")
        claude_tests_run = False
    else:
        logger.info("   Press ENTER to run Claude tests, or Ctrl+C to skip...")
        try:
            input()
            claude_tests_run = True
        except KeyboardInterrupt:
            logger.info("\n   ⏭️  Skipping Claude tests")
            claude_tests_run = False

    claude_check_passed = 0
    claude_check_failed = 0

    if claude_tests_run:
        test_cases_claude = [
            {
                "title": "Indonesia Announces Five-Year Digital Nomad Visa Extension",
                "summary": "The Indonesian government has extended the digital nomad visa validity from one year to five years, making it more attractive for remote workers.",
                "expected_duplicate": True,
                "reason": "Same news as published article #1",
            },
            {
                "title": "Coretax Glitches Continue to Plague Indonesian Taxpayers",
                "summary": "The new Coretax system is still experiencing technical issues, causing delays in NPWP registration and tax filing.",
                "expected_duplicate": True,
                "reason": "Same issue as published article #2",
            },
            {
                "title": "Indonesia Launches New Entrepreneur Visa for Tech Startups",
                "summary": "A brand new visa category has been introduced specifically for tech entrepreneurs looking to launch startups in Indonesia.",
                "expected_duplicate": False,
                "reason": "Different visa type (entrepreneur vs nomad)",
            },
        ]

        for i, test in enumerate(test_cases_claude, 1):
            logger.info(f"\n   Testing: {test['title'][:60]}...")

            result = await validator.validate_article(
                title=test["title"],
                summary=test["summary"],
                url=f"https://test-source.com/article-{i}",
                source="Test Source",
                llama_score=75,  # High score to test duplicate override
                llama_reason="Test article",
            )

            if result.is_duplicate == test["expected_duplicate"]:
                logger.success(
                    f"   ✅ Claude Test {i}: {'DUPLICATE' if result.is_duplicate else 'UNIQUE'} (expected: {'DUPLICATE' if test['expected_duplicate'] else 'UNIQUE'})"
                )
                if result.similar_to:
                    logger.info(f"      Similar to: {result.similar_to[:50]}...")
                logger.info(f"      Reason: {result.reason}")
                claude_check_passed += 1
            else:
                logger.error(
                    f"   ❌ Claude Test {i}: {'DUPLICATE' if result.is_duplicate else 'UNIQUE'} (expected: {'DUPLICATE' if test['expected_duplicate'] else 'UNIQUE'})"
                )
                logger.error(f"      Test reason: {test['reason']}")
                logger.error(f"      Claude reason: {result.reason}")
                claude_check_failed += 1

        logger.info(
            f"\n📊 Claude Check Results: {claude_check_passed}/{len(test_cases_claude)} passed"
        )

    # Step 4: Test Registry Auto-Update
    logger.info("\n💾 Step 4: Testing registry auto-update...")

    ClaudeValidator.add_published_article(
        title="Test Article: PT PMA Setup Guide for Foreigners",
        url="https://balizero.com/business/pt-pma-setup-guide",
        category="business",
        published_at="2026-01-05T12:00:00",
    )

    # Reload validator
    new_validator = ClaudeValidator(use_web_research=False)

    # Check if test article is in registry
    found = any(
        art.get("title") == "Test Article: PT PMA Setup Guide for Foreigners"
        for art in new_validator.published_articles
    )

    if found:
        logger.success("✅ Registry auto-update working (test article found)")
    else:
        logger.error("❌ Registry auto-update failed (test article not found)")

    # Final Summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 FINAL TEST SUMMARY")
    logger.info("=" * 70)
    logger.info(
        f"Quick Keyword Check:  {quick_check_passed}/{len(test_cases_quick)} passed"
    )

    if claude_tests_run:
        logger.info(
            f"Claude Semantic Check: {claude_check_passed}/{len(test_cases_claude)} passed"
        )
        total_passed = quick_check_passed + claude_check_passed
        total_tests = len(test_cases_quick) + len(test_cases_claude)
    else:
        logger.info("Claude Semantic Check: Skipped")
        total_passed = quick_check_passed
        total_tests = len(test_cases_quick)

    logger.info(f"Registry Update:      {'✅ PASS' if found else '❌ FAIL'}")
    logger.info("=" * 70)

    # Calculate pass rate
    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    if pass_rate == 100:
        logger.success(
            f"\n🎉 ALL TESTS PASSED ({total_passed}/{total_tests}) - Duplicate detection is working!"
        )
    elif pass_rate >= 80:
        logger.warning(
            f"\n⚠️  MOSTLY PASSING ({total_passed}/{total_tests}) - {pass_rate:.1f}% pass rate"
        )
    else:
        logger.error(
            f"\n❌ TESTS FAILED ({total_passed}/{total_tests}) - {pass_rate:.1f}% pass rate - Needs investigation"
        )

    # Cleanup
    if test_registry.exists():
        test_registry.unlink()
        logger.info(f"\n🧹 Cleaned up test registry: {test_registry}")


if __name__ == "__main__":
    logger.info("Anti-Duplicate Detection Test Suite")
    logger.info("Pass --skip-claude to skip Claude API tests (faster)")
    logger.info("")

    asyncio.run(test_duplicate_detection())
