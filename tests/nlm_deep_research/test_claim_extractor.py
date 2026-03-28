"""Tests for claim_extractor.py — extraction, confidence scoring, JSONL append."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.claim_extractor import (
    CLAIM_CATEGORIES,
    CONFIDENCE_PROVISIONAL,
    CONFIDENCE_VERIFIED,
    TIER_AUTHORITY,
    ClaimRecord,
    append_claims_to_registry,
    classify_confidence,
    compute_confidence,
    extract_claims_from_response,
    generate_claim_id,
    load_claims_count,
)

from .conftest import make_claim


# =====================================================================
# Confidence classification
# =====================================================================


class TestClassifyConfidence:
    """Tests for confidence score classification."""

    def test_verified(self):
        assert classify_confidence(0.80) == "VERIFIED"
        assert classify_confidence(0.75) == "VERIFIED"
        assert classify_confidence(1.0) == "VERIFIED"

    def test_provisional(self):
        assert classify_confidence(0.60) == "PROVISIONAL"
        assert classify_confidence(0.55) == "PROVISIONAL"

    def test_low(self):
        assert classify_confidence(0.40) == "LOW"
        assert classify_confidence(0.0) == "LOW"
        assert classify_confidence(0.54) == "LOW"


# =====================================================================
# Confidence computation
# =====================================================================


class TestComputeConfidence:
    """Tests for the 6-factor weighted confidence formula."""

    def test_t0_multi_source_regulatory(self):
        score = compute_confidence(
            highest_tier=0,
            source_count=3,
            has_specific_pasal=True,
            is_regulatory=True,
            days_since_pub=10,
            is_bali_specific=False,
        )
        assert score >= CONFIDENCE_VERIFIED
        assert 0.0 <= score <= 1.0

    def test_t6_single_source_old(self):
        score = compute_confidence(
            highest_tier=6,
            source_count=1,
            has_specific_pasal=False,
            is_regulatory=False,
            days_since_pub=500,
            is_bali_specific=False,
        )
        assert score < CONFIDENCE_VERIFIED

    def test_bali_specific_slightly_lower(self):
        score_national = compute_confidence(
            highest_tier=2, source_count=2,
            has_specific_pasal=True, is_regulatory=True,
            days_since_pub=30, is_bali_specific=False,
        )
        score_bali = compute_confidence(
            highest_tier=2, source_count=2,
            has_specific_pasal=True, is_regulatory=True,
            days_since_pub=30, is_bali_specific=True,
        )
        assert score_bali < score_national  # geo penalty

    def test_recency_tiers(self):
        """More recent sources should have higher confidence."""
        score_new = compute_confidence(
            highest_tier=2, source_count=2,
            has_specific_pasal=False, is_regulatory=False,
            days_since_pub=10, is_bali_specific=False,
        )
        score_old = compute_confidence(
            highest_tier=2, source_count=2,
            has_specific_pasal=False, is_regulatory=False,
            days_since_pub=400, is_bali_specific=False,
        )
        assert score_new > score_old

    def test_result_clamped_to_unit_interval(self):
        # Even with all max factors, should not exceed 1.0
        score = compute_confidence(
            highest_tier=0, source_count=100,
            has_specific_pasal=True, is_regulatory=True,
            days_since_pub=1, is_bali_specific=False,
        )
        assert score <= 1.0

    def test_unknown_tier_fallback(self):
        score = compute_confidence(
            highest_tier=99,  # Not in TIER_AUTHORITY
            source_count=1,
            has_specific_pasal=False,
            is_regulatory=False,
            days_since_pub=30,
            is_bali_specific=False,
        )
        assert 0.0 <= score <= 1.0

    def test_pasal_increases_confidence(self):
        score_no_pasal = compute_confidence(
            highest_tier=2, source_count=2,
            has_specific_pasal=False, is_regulatory=True,
            days_since_pub=30, is_bali_specific=False,
        )
        score_pasal = compute_confidence(
            highest_tier=2, source_count=2,
            has_specific_pasal=True, is_regulatory=True,
            days_since_pub=30, is_bali_specific=False,
        )
        assert score_pasal > score_no_pasal


# =====================================================================
# Claim ID generation
# =====================================================================


class TestGenerateClaimId:
    """Tests for unique claim ID generation."""

    def test_prefix(self):
        cid = generate_claim_id("NB2")
        assert cid.startswith("NB2-")

    def test_uniqueness(self):
        ids = {generate_claim_id() for _ in range(100)}
        assert len(ids) == 100

    def test_custom_prefix(self):
        cid = generate_claim_id("TEST")
        assert cid.startswith("TEST-")
        assert len(cid) == len("TEST-") + 8  # 8 hex chars


# =====================================================================
# Claim extraction from response
# =====================================================================


class TestExtractClaimsFromResponse:
    """Tests for extracting atomic claims from NLM responses."""

    def test_extracts_from_long_paragraphs(self):
        response = (
            "# Update Keimigrasian 2026\n\n"
            "Berdasarkan PP 34/2021 pasal 12, prosedur RPTKA telah berubah secara signifikan. "
            "Perusahaan PT PMA wajib mengajukan melalui portal TKA Online.\n\n"
            "Tim Pora Bali melakukan operasi gabungan di Kuta dan Seminyak sepanjang Maret 2026. "
            "Tercatat 15 WNA di-deportasi karena overstay lebih dari 60 hari di wilayah Badung.\n"
        )
        claims = extract_claims_from_response(
            response_text=response,
            source_ids=["SRC-001", "SRC-002"],
            query_cluster="A",
        )
        assert len(claims) >= 1
        assert all(isinstance(c, ClaimRecord) for c in claims)

    def test_skips_short_lines(self):
        response = "Short line.\nAnother short one.\n"
        claims = extract_claims_from_response(
            response_text=response,
            source_ids=["SRC-001"],
            query_cluster="A",
        )
        assert len(claims) == 0  # lines under 50 chars are skipped

    def test_skips_headers(self):
        response = (
            "# This is a header\n"
            "## Another header\n"
            "This is a paragraph long enough to be considered a claim by the extractor filtering rules.\n"
        )
        claims = extract_claims_from_response(
            response_text=response,
            source_ids=["SRC-001"],
            query_cluster="B",
        )
        # Headers should be skipped, only the paragraph may match
        for c in claims:
            assert not c.claim_text.startswith("#")

    def test_claim_text_truncated_to_500(self):
        long_text = "A" * 1000 + " " + "B" * 100
        response = long_text + "\n"
        claims = extract_claims_from_response(
            response_text=response,
            source_ids=["SRC-001"],
            query_cluster="C",
        )
        for c in claims:
            assert len(c.claim_text) <= 500

    def test_bali_detection_sets_geographic_scope(self):
        response = (
            "Tim Pora Bali melakukan razia gabungan di wilayah Denpasar dan Badung "
            "pada bulan Maret 2026 untuk memeriksa dokumen izin tinggal WNA.\n"
        )
        claims = extract_claims_from_response(
            response_text=response,
            source_ids=["SRC-001"],
            query_cluster="E",
        )
        if claims:
            assert claims[0].geographic_scope == "LOCAL_BALI"

    def test_regulatory_detection(self):
        response = (
            "Peraturan Pemerintah Nomor 34 Tahun 2021 tentang penggunaan tenaga kerja asing "
            "menetapkan bahwa setiap perusahaan wajib memiliki RPTKA sebelum mempekerjakan TKA.\n"
        )
        claims = extract_claims_from_response(
            response_text=response,
            source_ids=["SRC-001"],
            query_cluster="A",
        )
        if claims:
            assert claims[0].confidence_score > 0

    def test_visa_type_detection(self):
        response = (
            "Pemegang Golden Visa E28B 5 tahun wajib memenuhi minimum investasi "
            "sebesar USD 2.5 juta dalam sektor properti atau obligasi pemerintah Indonesia.\n"
        )
        claims = extract_claims_from_response(
            response_text=response,
            source_ids=["SRC-001"],
            query_cluster="D",
        )
        if claims:
            assert len(claims[0].affected_visa_types) >= 1

    def test_empty_response(self):
        claims = extract_claims_from_response(
            response_text="",
            source_ids=["SRC-001"],
            query_cluster="A",
        )
        assert len(claims) == 0

    def test_source_ids_propagated(self):
        response = (
            "Berdasarkan PP 34/2021 pasal 12, prosedur RPTKA telah berubah secara signifikan "
            "dan perusahaan wajib mengajukan permohonan melalui portal TKA Online.\n"
        )
        claims = extract_claims_from_response(
            response_text=response,
            source_ids=["SRC-A", "SRC-B"],
            query_cluster="A",
        )
        for c in claims:
            assert c.source_ids == ["SRC-A", "SRC-B"]


# =====================================================================
# ClaimRecord
# =====================================================================


class TestClaimRecord:
    """Tests for the ClaimRecord dataclass."""

    def test_to_dict_excludes_falsy(self):
        claim = make_claim()
        d = claim.to_dict()
        # Empty lists/dicts should be excluded
        assert "flags" not in d or d["flags"]

    def test_to_dict_includes_required_fields(self):
        claim = make_claim()
        d = claim.to_dict()
        assert "claim_id" in d
        assert "claim_text" in d
        assert "category" in d
        assert "confidence_score" in d


# =====================================================================
# JSONL append and count
# =====================================================================


class TestClaimsRegistry:
    """Tests for append_claims_to_registry and load_claims_count."""

    def test_append_creates_file(self, claims_file):
        claims = [make_claim(claim_id=f"C-{i}") for i in range(3)]
        total = append_claims_to_registry(claims, claims_file)
        assert total == 3
        assert claims_file.exists()

    def test_append_is_additive(self, claims_file):
        batch1 = [make_claim(claim_id="C-1")]
        batch2 = [make_claim(claim_id="C-2"), make_claim(claim_id="C-3")]
        append_claims_to_registry(batch1, claims_file)
        total = append_claims_to_registry(batch2, claims_file)
        assert total == 3

    def test_each_line_is_valid_json(self, claims_file):
        claims = [make_claim(claim_id=f"C-{i}") for i in range(5)]
        append_claims_to_registry(claims, claims_file)
        with open(claims_file) as f:
            for line in f:
                parsed = json.loads(line)
                assert "claim_id" in parsed

    def test_load_claims_count_missing_file(self, tmp_path):
        missing = tmp_path / "does_not_exist.jsonl"
        assert load_claims_count(missing) == 0

    def test_load_claims_count_after_append(self, claims_file):
        claims = [make_claim(claim_id=f"C-{i}") for i in range(4)]
        append_claims_to_registry(claims, claims_file)
        assert load_claims_count(claims_file) == 4

    def test_append_empty_list(self, claims_file):
        total = append_claims_to_registry([], claims_file)
        # File may or may not exist (opened in append mode), count is 0
        assert load_claims_count(claims_file) == 0
