"""Tests for backend.core.claims shared library.

Covers: ClaimRecord model, CLAIM_CATEGORIES, compute_confidence,
classify_confidence, extract_claims_from_response.
"""

from backend.core.claims import (
    CLAIM_CATEGORIES,
    ClaimRecord,
    VerificationLevel,
    classify_confidence,
    compute_confidence,
    extract_claims_from_response,
)

# ---------------------------------------------------------------------------
# ClaimRecord model
# ---------------------------------------------------------------------------


class TestClaimRecord:
    """Tests for the ClaimRecord dataclass."""

    def test_creation_minimal(self) -> None:
        """ClaimRecord can be created with required fields only."""
        rec = ClaimRecord(
            claim_id="NB2-abc12345",
            claim_text="Some claim text",
            category="LEGAL_CHANGE",
            confidence_class="VERIFIED",
            confidence_score=0.85,
            source_ids=["s1"],
            extracted="2026-04-03T00:00:00+00:00",
        )
        assert rec.claim_id == "NB2-abc12345"
        assert rec.status == "active"
        assert rec.geographic_scope == "NATIONAL"
        assert rec.affected_visa_types == []
        assert rec.affected_services == []
        assert rec.flags == {}

    def test_to_dict_omits_empty(self) -> None:
        """to_dict() omits falsy values (empty lists, dicts, empty strings)."""
        rec = ClaimRecord(
            claim_id="NB2-test0001",
            claim_text="Test claim",
            category="FEE_CHANGE",
            confidence_class="LOW",
            confidence_score=0.40,
            source_ids=["s1"],
            extracted="2026-04-03T00:00:00+00:00",
        )
        d = rec.to_dict()
        assert "claim_id" in d
        assert "affected_visa_types" not in d  # empty list omitted
        assert "flags" not in d  # empty dict omitted

    def test_to_dict_preserves_populated_fields(self) -> None:
        """to_dict() preserves populated optional fields."""
        rec = ClaimRecord(
            claim_id="NB2-test0002",
            claim_text="Visa fee increased",
            category="FEE_CHANGE",
            confidence_class="PROVISIONAL",
            confidence_score=0.60,
            source_ids=["s1", "s2"],
            extracted="2026-04-03T00:00:00+00:00",
            affected_visa_types=["KITAS_E23"],
            flags={"urgent": True},
        )
        d = rec.to_dict()
        assert d["affected_visa_types"] == ["KITAS_E23"]
        assert d["flags"] == {"urgent": True}


# ---------------------------------------------------------------------------
# CLAIM_CATEGORIES
# ---------------------------------------------------------------------------


class TestClaimCategories:
    """Tests for the CLAIM_CATEGORIES constant."""

    def test_has_15_entries(self) -> None:
        """CLAIM_CATEGORIES contains exactly 15 entries."""
        assert len(CLAIM_CATEGORIES) == 15

    def test_known_categories_present(self) -> None:
        """Key categories are in the list."""
        for cat in [
            "LEGAL_CHANGE",
            "FEE_CHANGE",
            "ENFORCEMENT_ACTION",
            "PROCEDURAL_STEP",
            "ELIGIBILITY_RULE",
        ]:
            assert cat in CLAIM_CATEGORIES


# ---------------------------------------------------------------------------
# VerificationLevel
# ---------------------------------------------------------------------------


class TestVerificationLevel:
    """Tests for VerificationLevel constants."""

    def test_thresholds(self) -> None:
        assert VerificationLevel.VERIFIED == 0.75
        assert VerificationLevel.PROVISIONAL == 0.55
        assert VerificationLevel.LOW == 0.55  # boundary below PROVISIONAL


# ---------------------------------------------------------------------------
# compute_confidence
# ---------------------------------------------------------------------------


class TestComputeConfidence:
    """Tests for the 6-factor confidence scoring function."""

    def test_returns_float_in_range(self) -> None:
        """Output is always a float in [0, 1]."""
        score = compute_confidence(
            highest_tier=3,
            source_count=2,
            has_specific_pasal=False,
            is_regulatory=False,
            days_since_pub=60,
            is_bali_specific=False,
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_high_tier_gov_source_gives_verified(self) -> None:
        """T0 government source with corroboration and pasal gives >= 0.75."""
        score = compute_confidence(
            highest_tier=0,
            source_count=3,
            has_specific_pasal=True,
            is_regulatory=True,
            days_since_pub=10,
            is_bali_specific=False,
        )
        assert score >= 0.75

    def test_single_blog_source_gives_low(self) -> None:
        """Single T6 blog source, no pasal, old publication gives < 0.55."""
        score = compute_confidence(
            highest_tier=6,
            source_count=1,
            has_specific_pasal=False,
            is_regulatory=False,
            days_since_pub=400,
            is_bali_specific=False,
        )
        assert score < 0.55

    def test_more_sources_increases_score(self) -> None:
        """Corroboration from more sources raises confidence."""
        base = {
            "highest_tier": 3,
            "has_specific_pasal": False,
            "is_regulatory": False,
            "days_since_pub": 30,
            "is_bali_specific": False,
        }
        score_1 = compute_confidence(source_count=1, **base)
        score_3 = compute_confidence(source_count=3, **base)
        assert score_3 > score_1

    def test_clamped_to_zero_one(self) -> None:
        """Score never exceeds 1.0 even with perfect inputs."""
        score = compute_confidence(
            highest_tier=0,
            source_count=10,
            has_specific_pasal=True,
            is_regulatory=True,
            days_since_pub=1,
            is_bali_specific=True,
        )
        assert score <= 1.0


# ---------------------------------------------------------------------------
# classify_confidence
# ---------------------------------------------------------------------------


class TestClassifyConfidence:
    """Tests for the confidence classification function."""

    def test_verified(self) -> None:
        assert classify_confidence(0.80) == "VERIFIED"

    def test_verified_boundary(self) -> None:
        assert classify_confidence(0.75) == "VERIFIED"

    def test_provisional(self) -> None:
        assert classify_confidence(0.65) == "PROVISIONAL"

    def test_provisional_boundary(self) -> None:
        assert classify_confidence(0.55) == "PROVISIONAL"

    def test_low(self) -> None:
        assert classify_confidence(0.40) == "LOW"

    def test_low_zero(self) -> None:
        assert classify_confidence(0.0) == "LOW"


# ---------------------------------------------------------------------------
# extract_claims_from_response
# ---------------------------------------------------------------------------


class TestExtractClaims:
    """Tests for the claim extraction pipeline."""

    SAMPLE_RESPONSE = (
        "## Header to skip\n"
        "\n"
        "Peraturan Pemerintah Nomor 48 Tahun 2023 tentang Pemberian Perizinan Berusaha, "
        "Pasal 12 ayat (3) menetapkan bahwa KITAS kerja wajib melalui proses persetujuan.\n"
        "\n"
        "Tarif PNBP untuk perpanjangan KITAS E23 telah dinaikkan menjadi Rp 2.000.000 "
        "berlaku sejak 1 Januari 2026, sesuai PP PNBP terbaru.\n"
        "\n"
        "Kantor Imigrasi Ngurah Rai di Bali melakukan operasi gabungan penertiban "
        "overstay pada bulan Maret 2026.\n"
        "\n"
        "Short line under 50 chars.\n"
    )

    def test_returns_list_of_claim_records(self) -> None:
        """Extraction returns a list of ClaimRecord instances."""
        claims = extract_claims_from_response(
            response_text=self.SAMPLE_RESPONSE,
            source_ids=["s1"],
            query_cluster="A",
        )
        assert isinstance(claims, list)
        assert all(isinstance(c, ClaimRecord) for c in claims)

    def test_detects_regulatory_text(self) -> None:
        """Claims from regulatory text get appropriate category or pasal detection."""
        claims = extract_claims_from_response(
            response_text=self.SAMPLE_RESPONSE,
            source_ids=["s1"],
            query_cluster="A",
        )
        # At least one claim should have pasal-based specificity
        # reflected in higher confidence
        assert len(claims) >= 1
        # The first paragraph has "Pasal" and "peraturan" -> should score higher
        categories = [c.category for c in claims]
        # Should detect at least one of these regulatory categories
        assert any(
            cat in categories
            for cat in [
                "LEGAL_CHANGE",
                "FEE_CHANGE",
                "ENFORCEMENT_PATTERN",
                "ENFORCEMENT_ACTION",
                "ELIGIBILITY_RULE",
                "PROCEDURAL_STEP",
            ]
        )

    def test_detects_bali_specific(self) -> None:
        """Claims mentioning Bali locations get LOCAL_BALI scope."""
        claims = extract_claims_from_response(
            response_text=self.SAMPLE_RESPONSE,
            source_ids=["s1"],
            query_cluster="A",
        )
        bali_claims = [c for c in claims if c.geographic_scope == "LOCAL_BALI"]
        assert len(bali_claims) >= 1

    def test_empty_input_returns_empty(self) -> None:
        """Empty or whitespace input returns empty list."""
        assert extract_claims_from_response("", ["s1"], "A") == []
        assert extract_claims_from_response("   \n\n  ", ["s1"], "A") == []

    def test_short_lines_skipped(self) -> None:
        """Lines under 50 characters are filtered out."""
        claims = extract_claims_from_response(
            response_text="Short.\nAlso short.\n",
            source_ids=["s1"],
            query_cluster="A",
        )
        assert claims == []

    def test_source_metadata_affects_confidence(self) -> None:
        """Providing sources_metadata with tier info adjusts confidence."""
        text = (
            "Peraturan baru tentang izin tinggal tetap KITAP ditetapkan oleh Kemenkumham "
            "berdasarkan Pasal 54 UU Keimigrasian Nomor 6 Tahun 2011, berlaku nasional."
        )
        meta = {"s1": {"tier": 0}, "s2": {"tier": 1}}
        claims = extract_claims_from_response(
            response_text=text,
            source_ids=["s1", "s2"],
            query_cluster="A",
            sources_metadata=meta,
        )
        assert len(claims) >= 1
        # T0 source + 2 corroborating + pasal -> should be high
        assert claims[0].confidence_score >= 0.70

    def test_detects_visa_types(self) -> None:
        """Claims mentioning visa types populate affected_visa_types."""
        claims = extract_claims_from_response(
            response_text=self.SAMPLE_RESPONSE,
            source_ids=["s1"],
            query_cluster="A",
        )
        all_visa_types = []
        for c in claims:
            all_visa_types.extend(c.affected_visa_types)
        # SAMPLE_RESPONSE mentions KITAS kerja (E23) and Ngurah Rai
        assert "KITAS_E23" in all_visa_types
