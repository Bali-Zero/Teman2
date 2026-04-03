"""
Tests for document_categorizer.py - Document auto-categorization from filenames.
"""

import pytest

from backend.services.crm.document_categorizer import (
    auto_categorize_document,
    auto_categorize_documents_batch,
    extract_expiry_date,
    extract_person_name,
    get_categorization_stats,
)


class TestAutoCategorizeDocument:
    """Tests for auto_categorize_document function."""

    def test_passport_categorized_as_personal(self):
        result = auto_categorize_document("passport_john.pdf")
        assert result["document_category"] == "personal"
        assert result["document_type"] == "Passport"
        assert result["confidence"] >= 0.7

    def test_kitas_categorized_as_immigration(self):
        result = auto_categorize_document("KITAS_scan_2024.jpg")
        assert result["document_category"] == "immigration"
        assert "kitas" in result["matched_keyword"].lower()

    def test_akta_categorized_as_pma(self):
        result = auto_categorize_document("akta_pendirian_pt_balizero.pdf")
        assert result["document_category"] == "pma"

    def test_spt_categorized_as_tax(self):
        result = auto_categorize_document("SPT_2024_company.pdf")
        assert result["document_category"] == "tax"

    def test_contract_categorized_as_other(self):
        result = auto_categorize_document("contract_lease_2024.pdf")
        assert result["document_category"] == "other"
        assert result["document_type"] == "Contract"

    def test_family_passport_categorized_as_family(self):
        result = auto_categorize_document("passport_family_spouse_maria.pdf")
        assert result["document_category"] == "family"

    def test_marriage_certificate_categorized_as_family(self):
        result = auto_categorize_document("marriage_certificate_2020.pdf")
        assert result["document_category"] == "family"

    def test_unknown_filename_returns_other(self):
        result = auto_categorize_document("random_file_xyz.pdf")
        assert result["document_category"] == "other"
        assert result["confidence"] == 0.5

    def test_empty_filename_returns_fallback(self):
        result = auto_categorize_document("")
        assert result["document_category"] == "other"
        assert result["matched_keyword"] is None

    def test_visa_categorized_as_immigration(self):
        result = auto_categorize_document("e-visa_approval_2025.pdf")
        assert result["document_category"] == "immigration"

    def test_npwp_categorized(self):
        result = auto_categorize_document("npwp_company_pt_balizero.pdf")
        # Could be pma or tax depending on keyword matching priority
        assert result["document_category"] in ("pma", "tax")

    def test_nib_categorized_as_pma(self):
        result = auto_categorize_document("nib_oss_registration.pdf")
        assert result["document_category"] == "pma"

    def test_case_insensitive(self):
        result1 = auto_categorize_document("PASSPORT_JOHN.PDF")
        result2 = auto_categorize_document("passport_john.pdf")
        assert result1["document_category"] == result2["document_category"]

    def test_birth_certificate_as_family(self):
        result = auto_categorize_document("birth_certificate_child_2020.pdf")
        assert result["document_category"] == "family"


class TestExtractExpiryDate:
    """Tests for extract_expiry_date function."""

    def test_iso_date_format(self):
        result = extract_expiry_date("Passport_MARCO_2028-12-31.pdf")
        assert result == "2028-12-31"

    def test_compact_date_format(self):
        result = extract_expiry_date("KITAS_20251215.jpg")
        assert result == "2025-12-15"

    def test_no_date_returns_none(self):
        result = extract_expiry_date("random_file.pdf")
        assert result is None

    def test_empty_filename(self):
        result = extract_expiry_date("")
        assert result is None

    def test_none_filename(self):
        result = extract_expiry_date(None)
        assert result is None

    def test_european_date_format(self):
        result = extract_expiry_date("visa_31-12-2024.pdf")
        assert result == "2024-12-31"


class TestExtractPersonName:
    """Tests for extract_person_name function."""

    def test_standard_format(self):
        result = extract_person_name("Passport_MARCO_ROSSI_2028-12-31.pdf")
        assert result == "MARCO ROSSI"

    def test_single_name(self):
        result = extract_person_name("KITAS_JOHN.jpg")
        assert result == "JOHN"

    def test_no_name_returns_none(self):
        result = extract_person_name("document.pdf")
        assert result is None

    def test_empty_filename(self):
        result = extract_person_name("")
        assert result is None

    def test_none_filename(self):
        result = extract_person_name(None)
        assert result is None


class TestAutoCategorizeDocumentsBatch:
    """Tests for auto_categorize_documents_batch function."""

    def test_batch_categorization(self):
        filenames = [
            "passport_john.pdf",
            "KITAS_scan.jpg",
            "contract_2024.pdf",
        ]
        results = auto_categorize_documents_batch(filenames)
        assert len(results) == 3
        assert results[0]["document_category"] == "personal"
        assert results[1]["document_category"] == "immigration"
        assert results[2]["document_category"] == "other"

    def test_empty_batch(self):
        results = auto_categorize_documents_batch([])
        assert results == []


class TestGetCategorizationStats:
    """Tests for get_categorization_stats function."""

    def test_stats_calculation(self):
        categorizations = [
            {"document_category": "immigration", "confidence": 0.9},
            {"document_category": "immigration", "confidence": 0.85},
            {"document_category": "pma", "confidence": 0.7},
            {"document_category": "other", "confidence": 0.5},
        ]
        stats = get_categorization_stats(categorizations)
        assert stats["total"] == 4
        assert stats["by_category"]["immigration"] == 2
        assert stats["by_category"]["pma"] == 1
        assert stats["uncategorized"] == 1
        assert stats["by_confidence"]["high"] == 2  # >= 0.8
        assert stats["by_confidence"]["medium"] == 1  # >= 0.6
        assert stats["by_confidence"]["low"] == 1  # < 0.6

    def test_empty_categorizations(self):
        stats = get_categorization_stats([])
        assert stats["total"] == 0
        assert stats["avg_confidence"] == 0.0

    def test_avg_confidence(self):
        categorizations = [
            {"document_category": "immigration", "confidence": 0.8},
            {"document_category": "pma", "confidence": 0.6},
        ]
        stats = get_categorization_stats(categorizations)
        assert abs(stats["avg_confidence"] - 0.7) < 0.01
