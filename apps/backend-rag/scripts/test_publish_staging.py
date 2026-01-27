#!/usr/bin/env python3
"""
Test script for publish_staging_item functionality.

Tests:
1. convert_staging_to_enriched_article() conversion
2. EnrichedArticle structure validation
3. Cover image handling
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Set PYTHONPATH to include backend
import os

os.environ.setdefault("PYTHONPATH", str(backend_path))

from backend.app.routers.intel import convert_staging_to_enriched_article


def test_conversion_basic():
    """Test basic conversion with minimal data."""
    print("\n" + "=" * 80)
    print("TEST 1: Basic Conversion (Minimal Data)")
    print("=" * 80)

    staging_data = {
        "title": "Indonesia's Golden Visa: Who Actually Qualifies",
        "content": "## Summary\nIndonesia has introduced a new Golden Visa program for high-net-worth individuals.\n## Facts\nIndonesia launched the Golden Visa program in 2024. The program requires a minimum investment of $350,000. Applicants must have a valid passport and proof of funds.\n## Bali Zero Take\nThis is a significant opportunity for investors looking to establish residency in Indonesia.\n## Next Steps\n- Contact immigration consultant\n- Prepare required documents",
        "category": "immigration",
        "relevance_score": 85,
        "source_url": "https://example.com/golden-visa",
        "source_name": "Bali Intel Scraper",
        "detected_at": "2026-01-24T10:00:00Z",
    }

    try:
        result = convert_staging_to_enriched_article(staging_data)

        print("✅ Conversion successful!")
        print("\n📊 Results:")
        print(f"   Title: {result['title']}")
        print(f"   Headline: {result['headline']}")
        print(f"   Category: {result['category']}")
        print(f"   Priority: {result['priority']}")
        print(f"   Relevance Score: {result['relevance_score']}")
        print("\n📝 TLDR:")
        print(f"   Should Worry: {result['tldr']['should_worry']}")
        print(f"   What: {result['tldr']['what'][:100]}...")
        print(f"   Who: {result['tldr']['who']}")
        print(f"   When: {result['tldr']['when']}")
        print(f"   Risk Level: {result['tldr']['risk_level']}")
        print("\n📰 Facts:")
        print(f"   Length: {len(result['facts'])} chars")
        print(f"   Preview: {result['facts'][:150]}...")
        print("\n💡 Bali Zero Take:")
        print(f"   Hidden Insight: {result['bali_zero_take']['hidden_insight'][:100]}...")
        print(f"   Our Analysis: {result['bali_zero_take']['our_analysis'][:100]}...")
        print(f"   Our Advice: {result['bali_zero_take']['our_advice'][:100]}...")
        print("\n✅ Next Steps:")
        print(f"   Expat: {len(result['next_steps']['expat'])} items")
        print(f"   Investor: {len(result['next_steps']['investor'])} items")
        print(f"\n🏷️ Tags: {result['ai_tags']}")
        print(f"📦 Components: {result['suggested_components']}")

        # Validate structure
        assert result["title"] == staging_data["title"], "Title mismatch"
        assert result["category"] == staging_data["category"], "Category mismatch"
        assert result["priority"] == "high", f"Expected 'high' priority, got '{result['priority']}'"
        assert len(result["facts"]) > 0, "Facts should not be empty"
        assert len(result["next_steps"]["expat"]) > 0, "Expat steps should not be empty"
        assert len(result["next_steps"]["investor"]) > 0, "Investor steps should not be empty"

        print("\n✅ All validations passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_conversion_with_sections():
    """Test conversion with well-structured markdown sections."""
    print("\n" + "=" * 80)
    print("TEST 2: Conversion with Structured Sections")
    print("=" * 80)

    staging_data = {
        "title": "Bali Property Market: New Regulations for Foreign Ownership",
        "content": """## Summary
New regulations have been introduced for foreign property ownership in Bali, affecting both residential and commercial properties.

## Facts
The Indonesian government has updated property ownership regulations effective January 2025. Foreigners can now own property through Hak Pakai (Right to Use) for up to 80 years. Minimum investment is set at $350,000 for residential properties. Commercial properties require a minimum investment of $1 million. The new regulations apply to all provinces, including Bali.

## Bali Zero Take

### Hidden Insight
The new regulations actually make it easier for foreigners to own property long-term, but the minimum investment thresholds are higher than expected.

### Our Analysis
This represents a significant shift in Indonesia's property market policy. The 80-year Hak Pakai is more attractive than previous 30-year leases, but the higher investment thresholds may limit accessibility.

### Our Advice
Consult with a property lawyer before making any investment decisions. Consider the long-term implications of Hak Pakai vs. leasehold structures.

## Next Steps

### For Expats
- Review current property holdings
- Consult with property lawyer
- Consider Hak Pakai conversion if eligible
- Update property documentation

### For Investors
- Evaluate investment opportunities
- Assess minimum investment requirements
- Consider commercial property options
- Plan for long-term property strategy""",
        "category": "property",
        "relevance_score": 90,
        "source_url": "https://example.com/property-regulations",
        "source_name": "Bali Intel Scraper",
        "detected_at": "2026-01-24T10:00:00Z",
    }

    try:
        result = convert_staging_to_enriched_article(staging_data)

        print("✅ Conversion successful!")
        print("\n📊 Results:")
        print(f"   Title: {result['title']}")
        print(f"   Category: {result['category']}")
        print(f"   Priority: {result['priority']}")

        # Check that sections were parsed correctly
        assert "80 years" in result["facts"] or "80-year" in result["facts"], (
            "Facts should contain key information"
        )
        assert len(result["bali_zero_take"]["hidden_insight"]) > 50, (
            "Hidden insight should be extracted"
        )
        assert len(result["bali_zero_take"]["our_analysis"]) > 50, (
            "Our analysis should be extracted"
        )
        assert len(result["bali_zero_take"]["our_advice"]) > 50, "Our advice should be extracted"
        assert len(result["next_steps"]["expat"]) >= 3, "Should have multiple expat steps"
        assert len(result["next_steps"]["investor"]) >= 3, "Should have multiple investor steps"

        print("\n✅ Sections parsed correctly:")
        print(f"   Facts length: {len(result['facts'])} chars")
        print(f"   Hidden Insight length: {len(result['bali_zero_take']['hidden_insight'])} chars")
        print(f"   Our Analysis length: {len(result['bali_zero_take']['our_analysis'])} chars")
        print(f"   Our Advice length: {len(result['bali_zero_take']['our_advice'])} chars")
        print(f"   Expat steps: {len(result['next_steps']['expat'])}")
        print(f"   Investor steps: {len(result['next_steps']['investor'])}")

        print("\n✅ All validations passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_conversion_minimal_data():
    """Test conversion with minimal data (missing sections)."""
    print("\n" + "=" * 80)
    print("TEST 3: Conversion with Minimal Data (Missing Sections)")
    print("=" * 80)

    staging_data = {
        "title": "Quick News Update",
        "content": "This is a simple news article without structured sections.",
        "category": "news",
        "relevance_score": 40,
        "source_url": "https://example.com/news",
        "source_name": "Bali Intel Scraper",
    }

    try:
        result = convert_staging_to_enriched_article(staging_data)

        print("✅ Conversion successful with minimal data!")
        print("\n📊 Results:")
        print(f"   Title: {result['title']}")
        print(f"   Priority: {result['priority']} (should be 'low' for score 40)")
        print(f"   Facts: {len(result['facts'])} chars")

        # Validate defaults
        assert result["priority"] == "low", f"Expected 'low' priority, got '{result['priority']}'"
        assert len(result["facts"]) > 0, "Facts should have default content"
        assert len(result["next_steps"]["expat"]) > 0, "Should have default expat steps"
        assert len(result["next_steps"]["investor"]) > 0, "Should have default investor steps"
        assert result["tldr"]["should_worry"] in ["Yes", "No", "Depends"], (
            "Should have valid worry level"
        )

        print("\n✅ Defaults generated correctly:")
        print(f"   Facts: {result['facts'][:100]}...")
        print(f"   Expat steps: {result['next_steps']['expat']}")
        print(f"   Investor steps: {result['next_steps']['investor']}")

        print("\n✅ All validations passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_enriched_article_structure():
    """Test that converted data matches EnrichedArticle structure."""
    print("\n" + "=" * 80)
    print("TEST 4: EnrichedArticle Structure Validation")
    print("=" * 80)

    staging_data = {
        "title": "Test Article",
        "content": "## Summary\nTest summary.\n## Facts\nTest facts.\n## Bali Zero Take\nTest analysis.\n## Next Steps\n- Step 1\n- Step 2",
        "category": "immigration",
        "relevance_score": 75,
        "source_url": "https://example.com",
        "source_name": "Test Source",
    }

    try:
        result = convert_staging_to_enriched_article(staging_data)

        # Check all required fields
        required_fields = [
            "title",
            "headline",
            "tldr",
            "facts",
            "bali_zero_take",
            "next_steps",
            "category",
            "priority",
            "relevance_score",
            "ai_summary",
            "ai_tags",
            "suggested_components",
            "source",
            "source_url",
            "enriched_at",
        ]

        missing_fields = [field for field in required_fields if field not in result]
        if missing_fields:
            print(f"❌ Missing fields: {missing_fields}")
            return False

        # Check nested structures
        assert isinstance(result["tldr"], dict), "TLDR should be dict"
        assert isinstance(result["bali_zero_take"], dict), "Bali Zero Take should be dict"
        assert isinstance(result["next_steps"], dict), "Next Steps should be dict"
        assert isinstance(result["ai_tags"], list), "AI tags should be list"
        assert isinstance(result["suggested_components"], list), (
            "Suggested components should be list"
        )

        # Check TLDR fields
        tldr_fields = ["should_worry", "what", "who", "when", "risk_level"]
        missing_tldr = [field for field in tldr_fields if field not in result["tldr"]]
        if missing_tldr:
            print(f"❌ Missing TLDR fields: {missing_tldr}")
            return False

        # Check Bali Zero Take fields
        bzt_fields = ["hidden_insight", "our_analysis", "our_advice"]
        missing_bzt = [field for field in bzt_fields if field not in result["bali_zero_take"]]
        if missing_bzt:
            print(f"❌ Missing Bali Zero Take fields: {missing_bzt}")
            return False

        # Check Next Steps fields
        ns_fields = ["expat", "investor"]
        missing_ns = [field for field in ns_fields if field not in result["next_steps"]]
        if missing_ns:
            print(f"❌ Missing Next Steps fields: {missing_ns}")
            return False

        print("✅ All required fields present:")
        print(f"   Top-level fields: {len(required_fields)}")
        print(f"   TLDR fields: {len(tldr_fields)}")
        print(f"   Bali Zero Take fields: {len(bzt_fields)}")
        print(f"   Next Steps fields: {len(ns_fields)}")

        print("\n✅ Structure validation passed!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("TEST SUITE: publish_staging_item Conversion")
    print("=" * 80)

    tests = [
        ("Basic Conversion", test_conversion_basic),
        ("Structured Sections", test_conversion_with_sections),
        ("Minimal Data", test_conversion_minimal_data),
        ("Structure Validation", test_enriched_article_structure),
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
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {status}: {test_name}")

    print(f"\n📊 Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
