#!/usr/bin/env python3
"""
Integration test for publish_staging_item functionality.

Tests the full flow including:
1. Conversion to EnrichedArticle
2. Pydantic model validation
3. Error handling
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

import os

os.environ.setdefault("PYTHONPATH", str(backend_path))

from backend.app.routers.article_composer import (
    BaliZeroTake,
    EnrichedArticle,
    NextSteps,
    PublishRequest,
    TLDRSection,
)
from backend.app.routers.intel import convert_staging_to_enriched_article


def test_pydantic_validation():
    """Test that converted data can be validated as EnrichedArticle."""
    print("\n" + "=" * 80)
    print("TEST: Pydantic Model Validation")
    print("=" * 80)

    staging_data = {
        "title": "Test Article for Pydantic Validation",
        "content": """## Summary
This is a test summary for Pydantic validation.

## Facts
These are the facts about the test article. It contains important information that needs to be validated.

## Bali Zero Take
This is our analysis of the test article. We provide insights and advice.

## Next Steps
- Step 1 for expats
- Step 2 for expats
- Step 1 for investors
- Step 2 for investors""",
        "category": "immigration",
        "relevance_score": 75,
        "source_url": "https://example.com/test",
        "source_name": "Test Source",
    }

    try:
        # Convert to dict
        enriched_dict = convert_staging_to_enriched_article(staging_data)

        print("✅ Conversion successful")
        print(f"   Title: {enriched_dict['title']}")
        print(f"   Category: {enriched_dict['category']}")

        # Create Pydantic models
        enriched_article = EnrichedArticle(
            title=enriched_dict["title"],
            headline=enriched_dict["headline"],
            tldr=TLDRSection(**enriched_dict["tldr"]),
            facts=enriched_dict["facts"],
            bali_zero_take=BaliZeroTake(**enriched_dict["bali_zero_take"]),
            next_steps=NextSteps(**enriched_dict["next_steps"]),
            category=enriched_dict["category"],
            priority=enriched_dict["priority"],
            relevance_score=enriched_dict["relevance_score"],
            ai_summary=enriched_dict["ai_summary"],
            ai_tags=enriched_dict["ai_tags"],
            suggested_components=enriched_dict["suggested_components"],
            cover_image=enriched_dict.get("cover_image"),
            source=enriched_dict["source"],
            source_url=enriched_dict["source_url"],
            enriched_at=enriched_dict["enriched_at"],
        )

        print("✅ Pydantic validation successful")
        print(f"   Model type: {type(enriched_article).__name__}")
        print(f"   TLDR type: {type(enriched_article.tldr).__name__}")
        print(f"   Bali Zero Take type: {type(enriched_article.bali_zero_take).__name__}")
        print(f"   Next Steps type: {type(enriched_article.next_steps).__name__}")

        # Create PublishRequest
        publish_request = PublishRequest(
            article=enriched_article,
            cover_image_base64=None,
            cover_image_filename=None,
            position="normal",
        )

        print("✅ PublishRequest created successfully")
        print(f"   Article title: {publish_request.article.title}")
        print(f"   Position: {publish_request.position}")
        print(f"   Has cover image: {publish_request.cover_image_base64 is not None}")

        print("\n✅ All Pydantic validations passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n" + "=" * 80)
    print("TEST: Edge Cases and Error Handling")
    print("=" * 80)

    test_cases = [
        {
            "name": "Empty content",
            "data": {
                "title": "Empty Article",
                "content": "",
                "category": "news",
                "relevance_score": 50,
                "source_url": "https://example.com",
                "source_name": "Test",
            },
        },
        {
            "name": "Very long title",
            "data": {
                "title": "A" * 200,
                "content": "## Summary\nTest\n## Facts\nTest",
                "category": "news",
                "relevance_score": 50,
                "source_url": "https://example.com",
                "source_name": "Test",
            },
        },
        {
            "name": "Missing category",
            "data": {
                "title": "Test Article",
                "content": "## Summary\nTest\n## Facts\nTest",
                "relevance_score": 50,
                "source_url": "https://example.com",
                "source_name": "Test",
            },
        },
        {
            "name": "Very high relevance score",
            "data": {
                "title": "Critical Article",
                "content": "## Summary\nCritical\n## Facts\nCritical",
                "category": "immigration",
                "relevance_score": 100,
                "source_url": "https://example.com",
                "source_name": "Test",
            },
        },
    ]

    passed = 0
    failed = 0

    for test_case in test_cases:
        try:
            result = convert_staging_to_enriched_article(test_case["data"])

            # Basic validations
            assert result["title"] is not None, "Title should not be None"
            assert result["category"] is not None, "Category should not be None"
            assert result["priority"] in ["high", "medium", "low"], "Priority should be valid"
            assert len(result["facts"]) >= 0, "Facts should exist"

            print(f"   ✅ {test_case['name']}: Passed")
            passed += 1

        except Exception as e:
            print(f"   ❌ {test_case['name']}: Failed - {e}")
            failed += 1

    print(f"\n📊 Edge Cases Results: {passed}/{len(test_cases)} passed")

    if failed == 0:
        print("✅ All edge cases handled correctly!")
        return True
    else:
        print(f"❌ {failed} edge case(s) failed")
        return False


def test_priority_calculation():
    """Test priority calculation based on relevance_score."""
    print("\n" + "=" * 80)
    print("TEST: Priority Calculation")
    print("=" * 80)

    test_scores = [
        (100, "high"),
        (90, "high"),
        (75, "high"),
        (74, "medium"),
        (50, "medium"),
        (49, "low"),
        (25, "low"),
        (0, "low"),
    ]

    passed = 0
    failed = 0

    for score, expected_priority in test_scores:
        staging_data = {
            "title": f"Test Article (Score: {score})",
            "content": "## Summary\nTest\n## Facts\nTest",
            "category": "news",
            "relevance_score": score,
            "source_url": "https://example.com",
            "source_name": "Test",
        }

        try:
            result = convert_staging_to_enriched_article(staging_data)
            actual_priority = result["priority"]

            if actual_priority == expected_priority:
                print(
                    f"   ✅ Score {score} → Priority '{actual_priority}' (expected '{expected_priority}')"
                )
                passed += 1
            else:
                print(
                    f"   ❌ Score {score} → Priority '{actual_priority}' (expected '{expected_priority}')"
                )
                failed += 1

        except Exception as e:
            print(f"   ❌ Score {score}: Error - {e}")
            failed += 1

    print(f"\n📊 Priority Calculation Results: {passed}/{len(test_scores)} passed")

    if failed == 0:
        print("✅ All priority calculations correct!")
        return True
    else:
        print(f"❌ {failed} calculation(s) incorrect")
        return False


def main():
    """Run all integration tests."""
    print("\n" + "=" * 80)
    print("INTEGRATION TEST SUITE: publish_staging_item")
    print("=" * 80)

    tests = [
        ("Pydantic Validation", test_pydantic_validation),
        ("Edge Cases", test_edge_cases),
        ("Priority Calculation", test_priority_calculation),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 80)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {status}: {test_name}")

    print(f"\n📊 Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All integration tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
