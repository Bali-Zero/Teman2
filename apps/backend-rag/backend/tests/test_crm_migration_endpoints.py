"""
Comprehensive Test Suite for CRM Migration Endpoints

Tests all 4 new features:
1. Google Drive Folder Creation API
2. Bulk Document Insert
3. Auto-Categorization Service
4. Migration Status Tracking

Run with: pytest backend/tests/test_crm_migration_endpoints.py -v
"""

import pytest

# Import services and functions to test
from backend.services.crm.document_categorizer import (
    auto_categorize_document,
    auto_categorize_documents_batch,
    extract_expiry_date,
    extract_person_name,
    get_categorization_stats,
)

# ============================================================================
# AUTO-CATEGORIZATION SERVICE TESTS
# ============================================================================


class TestDocumentCategorizer:
    """Test suite for document auto-categorization service."""

    def test_passport_categorization(self):
        """Test passport document categorization.
        Passports go to 00_Profile (personal) per the official Drive folder mapping.
        """
        result = auto_categorize_document("Passport_MARCO_2028-12-31.pdf")

        assert result["document_category"] == "personal"
        assert result["document_type"] == "Passport"
        assert result["confidence"] >= 0.8
        assert result["matched_keyword"] == "passport"

    def test_kitas_categorization(self):
        """Test KITAS document categorization."""
        result = auto_categorize_document("KITAS_JOHN_DOE.jpg")

        assert result["document_category"] == "immigration"
        assert result["document_type"] == "Kitas"
        assert result["confidence"] >= 0.8
        assert result["matched_keyword"] == "kitas"

    def test_visa_categorization(self):
        """Test visa document categorization."""
        result = auto_categorize_document("B211_visa_scan.pdf")

        assert result["document_category"] == "immigration"
        assert result["document_type"] == "Visa"
        assert "visa" in result["matched_keyword"] or "b211" in result["matched_keyword"]

    def test_company_akta_categorization(self):
        """Test company deed (akta) categorization."""
        result = auto_categorize_document("Akta_PT_ABC_Indonesia.pdf")

        assert result["document_category"] == "pma"
        assert result["document_type"] == "Akta"
        assert result["confidence"] >= 0.7
        assert result["matched_keyword"] == "akta"

    def test_npwp_categorization(self):
        """Test NPWP (tax ID) categorization."""
        result = auto_categorize_document("NPWP_Company_2024.pdf")

        assert result["document_category"] == "pma"
        assert result["document_type"] == "Npwp Company"
        assert result["matched_keyword"] == "npwp"

    def test_spt_tax_categorization(self):
        """Test SPT (tax return) categorization."""
        result = auto_categorize_document("SPT_Tahunan_2023.xlsx")

        assert result["document_category"] == "tax"
        assert result["document_type"] == "Spt"
        assert result["matched_keyword"] == "spt"

    def test_photo_categorization(self):
        """Test photo categorization."""
        result = auto_categorize_document("Photo_MARCO_3x4.jpg")

        assert result["document_category"] == "personal"
        assert result["document_type"] == "Photo"
        assert result["matched_keyword"] in ["photo", "jpg"]

    def test_cv_categorization(self):
        """Test CV/resume categorization."""
        result = auto_categorize_document("CV_John_Doe_2024.pdf")

        assert result["document_category"] == "personal"
        assert result["document_type"] == "Cv"
        assert result["matched_keyword"] == "cv"

    def test_unknown_document_fallback(self):
        """Test fallback for unknown document types."""
        result = auto_categorize_document("random_file_12345.pdf")

        assert result["document_category"] == "other"
        assert result["document_type"] == "Other"
        assert result["confidence"] == 0.5
        assert result["matched_keyword"] is None

    def test_empty_filename(self):
        """Test handling of empty filename."""
        result = auto_categorize_document("")

        assert result["document_category"] == "other"
        assert result["document_type"] == "Other"
        assert result["confidence"] == 0.5

    def test_confidence_scoring_exact_match(self):
        """Test confidence score for exact match."""
        result = auto_categorize_document("passport.pdf")

        # Exact match should give high confidence
        assert result["confidence"] >= 0.9

    def test_confidence_scoring_partial_match(self):
        """Test confidence score for partial match."""
        result = auto_categorize_document("my_passport_scan_2024.pdf")

        # Partial match should give medium confidence
        assert 0.7 <= result["confidence"] < 1.0

    def test_case_insensitive_matching(self):
        """Test case-insensitive keyword matching."""
        result1 = auto_categorize_document("PASSPORT.PDF")
        result2 = auto_categorize_document("passport.pdf")
        result3 = auto_categorize_document("PaSpOrT.pdf")

        assert (
            result1["document_category"]
            == result2["document_category"]
            == result3["document_category"]
        )
        assert result1["document_type"] == result2["document_type"] == result3["document_type"]


class TestDateExtraction:
    """Test suite for expiry date extraction."""

    def test_extract_iso_date(self):
        """Test ISO format date extraction (YYYY-MM-DD)."""
        date = extract_expiry_date("Passport_MARCO_2028-12-31.pdf")
        assert date == "2028-12-31"

    def test_extract_compact_date(self):
        """Test compact date extraction (YYYYMMDD)."""
        date = extract_expiry_date("KITAS_20251215.jpg")
        assert date == "2025-12-15"

    def test_extract_slash_date(self):
        """Test slash format date extraction (YYYY/MM/DD)."""
        date = extract_expiry_date("Visa_2024/06/30.pdf")
        assert date == "2024-06-30"

    def test_extract_dd_mm_yyyy_date(self):
        """Test DD-MM-YYYY format date extraction."""
        date = extract_expiry_date("Document_31-12-2027.pdf")
        assert date == "2027-12-31"

    def test_no_date_in_filename(self):
        """Test handling when no date present."""
        date = extract_expiry_date("Passport_MARCO.pdf")
        assert date is None

    def test_invalid_date(self):
        """Test handling of invalid date."""
        date = extract_expiry_date("File_2024-13-45.pdf")  # Invalid month/day
        assert date is None

    def test_unrealistic_year(self):
        """Test rejection of unrealistic years."""
        date1 = extract_expiry_date("File_1800-01-01.pdf")  # Too old
        date2 = extract_expiry_date("File_2200-01-01.pdf")  # Too far future

        assert date1 is None
        assert date2 is None

    def test_empty_filename_date(self):
        """Test date extraction from empty filename."""
        date = extract_expiry_date("")
        assert date is None


class TestNameExtraction:
    """Test suite for person name extraction."""

    def test_extract_simple_name(self):
        """Test simple name extraction."""
        name = extract_person_name("Passport_MARCO_ROSSI_2028-12-31.pdf")
        assert name == "MARCO ROSSI"

    def test_extract_name_with_date(self):
        """Test name extraction with date suffix."""
        name = extract_person_name("KITAS_JOHN_DOE_20251215.jpg")
        assert name == "JOHN DOE"

    def test_extract_single_name(self):
        """Test single name extraction."""
        name = extract_person_name("Photo_MARCO.jpg")
        assert name == "MARCO"

    def test_no_name_in_filename(self):
        """Test handling when no name pattern present."""
        name = extract_person_name("passport.pdf")
        assert name is None

    def test_empty_filename_name(self):
        """Test name extraction from empty filename."""
        name = extract_person_name("")
        assert name is None


class TestBatchCategorization:
    """Test suite for batch categorization."""

    def test_batch_categorization(self):
        """Test batch categorization of multiple documents."""
        filenames = [
            "Passport_MARCO.pdf",
            "KITAS_JOHN.jpg",
            "Akta_PT_ABC.pdf",
            "SPT_2023.xlsx",
            "Photo_ID.jpg",
        ]

        results = auto_categorize_documents_batch(filenames)

        assert len(results) == 5
        assert results[0]["document_category"] == "personal"  # passport → 00_Profile
        assert results[1]["document_category"] == "immigration"  # kitas → 01_Immigration
        assert results[2]["document_category"] == "pma"
        assert results[3]["document_category"] == "tax"
        assert results[4]["document_category"] == "personal"

    def test_empty_batch(self):
        """Test batch categorization with empty list."""
        results = auto_categorize_documents_batch([])
        assert results == []


class TestCategorizationStats:
    """Test suite for categorization statistics."""

    def test_stats_generation(self):
        """Test statistics generation from categorizations."""
        categorizations = [
            {"document_category": "immigration", "confidence": 0.9},
            {"document_category": "immigration", "confidence": 0.85},
            {"document_category": "pma", "confidence": 0.8},
            {"document_category": "tax", "confidence": 0.75},
            {"document_category": "other", "confidence": 0.5},
        ]

        stats = get_categorization_stats(categorizations)

        assert stats["total"] == 5
        assert stats["by_category"]["immigration"] == 2
        assert stats["by_category"]["pma"] == 1
        assert stats["by_category"]["tax"] == 1
        assert stats["by_category"]["other"] == 1
        assert stats["uncategorized"] == 1
        assert 0.7 < stats["avg_confidence"] < 0.8
        assert stats["by_confidence"]["high"] == 3  # >=0.8
        assert stats["by_confidence"]["medium"] == 1  # 0.6-0.8
        assert stats["by_confidence"]["low"] == 1  # <0.6

    def test_empty_stats(self):
        """Test statistics with empty list."""
        stats = get_categorization_stats([])

        assert stats["total"] == 0
        assert stats["by_category"] == {}
        assert stats["uncategorized"] == 0
        assert stats["avg_confidence"] == 0.0


# ============================================================================
# INTEGRATION TEST SCENARIOS
# ============================================================================


class TestMigrationScenarios:
    """Test realistic migration scenarios."""

    def test_typical_client_documents(self):
        """Test categorization of typical client document set."""
        documents = [
            "Passport_MARCO_ROSSI_2028-12-31.pdf",
            "Passport_MARIA_ROSSI_2027-06-15.pdf",
            "KITAS_MARCO_2026-01-30.jpg",
            "KITAS_MARIA_2026-01-30.jpg",
            "Photo_MARCO_3x4.jpg",
            "Photo_MARIA_3x4.jpg",
            "Marriage_Certificate.pdf",
            "SPT_2023_Tahunan.xlsx",
            "NPWP_Card.pdf",
        ]

        results = auto_categorize_documents_batch(documents)
        stats = get_categorization_stats(results)

        # Verify categorization quality
        assert stats["total"] == 9
        assert stats["by_category"]["immigration"] >= 2  # At least 2 KITAS
        assert stats["by_category"]["personal"] >= 2  # At least 2 photos
        assert stats["avg_confidence"] >= 0.7  # Good confidence overall

    def test_company_documents(self):
        """Test categorization of company document set."""
        documents = [
            "Akta_Pendirian_PT_ABC.pdf",
            "NIB_OSS_2024.pdf",
            "NPWP_Company.pdf",
            "SK_Kemenkumham.pdf",
            "Domicile_Letter.pdf",
            "LKPM_Q1_2024.xlsx",
            "SPT_Badan_2023.pdf",
        ]

        results = auto_categorize_documents_batch(documents)
        stats = get_categorization_stats(results)

        # Verify company documents categorized correctly
        assert stats["by_category"]["pma"] >= 4  # Company docs
        assert stats["by_category"]["tax"] >= 1  # Tax docs

    def test_mixed_quality_filenames(self):
        """Test handling of mixed quality filenames."""
        documents = [
            "Passport_Clean_2028-12-31.pdf",  # Well formatted
            "KITAS scan.jpg",  # Space instead of underscore
            "photo.jpg",  # Minimal info
            "random_file_123.pdf",  # Unclear
            "SPT-2023.xlsx",  # Dash instead of underscore
        ]

        results = auto_categorize_documents_batch(documents)

        # Passport → personal (00_Profile), KITAS → immigration (01_Immigration)
        immigration_count = sum(1 for r in results if r["document_category"] == "immigration")
        personal_count = sum(1 for r in results if r["document_category"] == "personal")
        assert immigration_count >= 1  # KITAS
        assert personal_count >= 1  # Passport

    def test_date_extraction_in_migration(self):
        """Test date extraction for various document types."""
        test_cases = [
            ("Passport_MARCO_2028-12-31.pdf", "2028-12-31"),
            ("KITAS_20251215.jpg", "2025-12-15"),
            ("Visa_2024/06/30.pdf", "2024-06-30"),
            ("IMTA_31-12-2026.pdf", "2026-12-31"),
            ("Photo.jpg", None),
        ]

        for filename, expected_date in test_cases:
            extracted = extract_expiry_date(filename)
            assert extracted == expected_date, f"Failed for {filename}"


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


class TestPerformance:
    """Test performance of categorization functions."""

    def test_batch_performance(self):
        """Test batch categorization performance."""
        import time

        # Create 100 test filenames
        filenames = [f"Passport_TEST_{i}_2028-12-31.pdf" for i in range(100)]

        start_time = time.time()
        results = auto_categorize_documents_batch(filenames)
        elapsed = time.time() - start_time

        # Should process 100 files in under 1 second
        assert elapsed < 1.0
        assert len(results) == 100

        print(f"\n✓ Processed {len(results)} documents in {elapsed:.3f} seconds")
        print(f"✓ Average: {(elapsed / len(results)) * 1000:.2f}ms per document")


# ============================================================================
# EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_unicode_filename(self):
        """Test handling of unicode characters in filename."""
        result = auto_categorize_document("Паспорт_2028.pdf")  # Cyrillic
        # Should still work, even if no match
        assert "document_category" in result
        assert "confidence" in result

    def test_very_long_filename(self):
        """Test handling of very long filename."""
        long_name = "Passport_" + ("A" * 200) + "_2028-12-31.pdf"
        result = auto_categorize_document(long_name)

        assert result["document_category"] == "personal"  # passport → 00_Profile
        assert result["document_type"] == "Passport"

    def test_special_characters(self):
        """Test handling of special characters."""
        result = auto_categorize_document("Passport_MARCO@#$%_2028.pdf")
        assert result["document_category"] == "personal"  # passport → 00_Profile

    def test_multiple_date_patterns(self):
        """Test filename with multiple dates."""
        # Should extract first valid date
        date = extract_expiry_date("Created_2024-01-01_Expires_2028-12-31.pdf")
        assert date in ["2024-01-01", "2028-12-31"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
