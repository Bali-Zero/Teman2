"""
Test Suite for Cell-Giant Architecture.

Tests cover:
- KNOWN_CORRECTIONS trigger patterns
- PRACTICAL_INSIGHTS topic detection
- BALI_ZERO_SERVICES calibrations
- Giant Reasoner extraction functions
- Zantara Synthesizer formatting
- Pipeline integration

Run: pytest tests/unit/rag/test_cell_giant.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import modules under test
from services.rag.agentic.cell_giant.cell_conscience import (
    KNOWN_CORRECTIONS,
    PRACTICAL_INSIGHTS,
    BALI_ZERO_SERVICES,
    cell_calibrate,
    _detect_topics,
    _get_calibrations,
)
from services.rag.agentic.cell_giant.giant_reasoner import (
    GiantConfig,
    GiantResult,
    _detect_domain,
    _extract_key_points,
    _extract_warnings,
    _extract_suggestions,
    _extract_legal_refs,
    _extract_costs,
    _extract_steps,
    _calculate_quality_score,
)
from services.rag.agentic.cell_giant.zantara_synthesizer import (
    SynthesizerConfig,
    ResponseTone,
    _detect_tone,
    _validate_response,
    _format_corrections,
    _format_calibrations,
    _format_enhancements,
    _format_legal_refs,
    _clean_response,
    _fallback_synthesis,
)


# ============================================================================
# TEST: KNOWN_CORRECTIONS
# ============================================================================

class TestKnownCorrections:
    """Test the KNOWN_CORRECTIONS dictionary."""

    def test_corrections_structure(self):
        """Each correction should have required keys."""
        required_keys = {"trigger_patterns", "correction", "source", "severity"}
        for key, correction in KNOWN_CORRECTIONS.items():
            assert required_keys.issubset(correction.keys()), f"Missing keys in {key}"

    def test_corrections_severity_values(self):
        """Severity should be one of: critical, high, medium."""
        valid_severities = {"critical", "high", "medium"}
        for key, correction in KNOWN_CORRECTIONS.items():
            assert correction["severity"] in valid_severities, f"Invalid severity in {key}"

    def test_kitas_sponsor_correction(self):
        """Test KITAS sponsor correction triggers."""
        correction = KNOWN_CORRECTIONS.get("kitas_sponsor")
        assert correction is not None
        assert correction["severity"] == "critical"
        assert "sponsor" in correction["correction"].lower()

    def test_dni_restrictions_correction(self):
        """Test DNI restrictions correction triggers."""
        correction = KNOWN_CORRECTIONS.get("dni_restrictions")
        assert correction is not None
        assert correction["severity"] == "critical"
        assert "dni" in correction["correction"].lower() or "daftar negatif" in correction["correction"].lower()

    def test_b211a_deprecated(self):
        """B211A visa should trigger correction (deprecated)."""
        import re
        correction = KNOWN_CORRECTIONS.get("b211a")
        assert correction is not None
        assert correction["severity"] == "critical"
        # Test pattern matching
        test_text = "I need a B211A visa for Bali"
        matched = any(
            re.search(p, test_text, re.IGNORECASE)
            for p in correction["trigger_patterns"]
        )
        assert matched, "B211A pattern should match"

    def test_nominee_arrangement_critical(self):
        """Nominee arrangement should be flagged as critical."""
        correction = KNOWN_CORRECTIONS.get("nominee arrangement")
        assert correction is not None
        assert correction["severity"] == "critical"
        assert "illegale" in correction["correction"].lower() or "illegal" in correction["correction"].lower()


# ============================================================================
# TEST: PRACTICAL_INSIGHTS
# ============================================================================

class TestPracticalInsights:
    """Test the PRACTICAL_INSIGHTS dictionary."""

    def test_insights_structure(self):
        """Each topic should have a list of string insights."""
        for topic, insights in PRACTICAL_INSIGHTS.items():
            assert isinstance(insights, list), f"{topic} should be a list"
            assert len(insights) >= 3, f"{topic} should have at least 3 insights"
            for insight in insights:
                assert isinstance(insight, str), f"Insights in {topic} should be strings"

    def test_core_topics_exist(self):
        """Core topics should exist."""
        core_topics = ["pt_pma", "kitas", "tax", "f&b", "ghost_kitchen"]
        for topic in core_topics:
            assert topic in PRACTICAL_INSIGHTS, f"{topic} should exist in PRACTICAL_INSIGHTS"

    def test_round4_topics_exist(self):
        """Round 4 topics should exist."""
        round4_topics = ["banking", "real_estate", "employment", "permits", "digital_nomad"]
        for topic in round4_topics:
            assert topic in PRACTICAL_INSIGHTS, f"{topic} should exist in PRACTICAL_INSIGHTS"


# ============================================================================
# TEST: BALI_ZERO_SERVICES
# ============================================================================

class TestBaliZeroServices:
    """Test the BALI_ZERO_SERVICES dictionary."""

    def test_services_structure(self):
        """Each service should have required keys."""
        required_keys = {"price_range", "timeline", "includes", "consultant"}
        for key, service in BALI_ZERO_SERVICES.items():
            assert required_keys.issubset(service.keys()), f"Missing keys in {key}"

    def test_visa_services_exist(self):
        """Visa services should exist."""
        visa_services = ["kitas_e33g", "kitas_e31a_worker", "kitas_e28a_investor", "kitas_renewal"]
        for service in visa_services:
            assert service in BALI_ZERO_SERVICES, f"{service} should exist"

    def test_fb_services_exist(self):
        """F&B services should exist."""
        fb_services = ["ghost_kitchen_setup", "restaurant_full_setup", "halal_certification"]
        for service in fb_services:
            assert service in BALI_ZERO_SERVICES, f"{service} should exist"


# ============================================================================
# TEST: TOPIC DETECTION
# ============================================================================

class TestTopicDetection:
    """Test topic detection functions."""

    def test_detect_pt_pma_topic(self):
        """Should detect PT PMA topic."""
        topics = _detect_topics("voglio aprire una pt pma", "")
        assert "pt_pma" in topics

    def test_detect_kitas_topic(self):
        """Should detect KITAS topic."""
        topics = _detect_topics("come ottenere un kitas lavorativo", "")
        assert "kitas" in topics

    def test_detect_multiple_topics(self):
        """Should detect multiple topics."""
        topics = _detect_topics("pt pma e kitas per ristorante", "")
        assert "pt_pma" in topics
        assert "kitas" in topics
        # f&b or ghost_kitchen should be detected
        assert "f&b" in topics or "ghost_kitchen" in topics

    def test_detect_digital_nomad(self):
        """Should detect digital nomad topic."""
        topics = _detect_topics("e33g second home visa", "")
        assert "digital_nomad" in topics or "kitas" in topics


# ============================================================================
# TEST: GIANT REASONER EXTRACTORS
# ============================================================================

class TestGiantExtractors:
    """Test Giant Reasoner extraction functions."""

    def test_detect_domain_visa(self):
        """Should detect visa domain."""
        assert _detect_domain("come ottenere un kitas") == "visa"
        assert _detect_domain("e33g digital nomad") == "visa"

    def test_detect_domain_company(self):
        """Should detect company domain."""
        assert _detect_domain("aprire una pt pma") == "company"
        assert _detect_domain("registrazione NIB OSS") == "company"

    def test_detect_domain_tax(self):
        """Should detect tax domain."""
        assert _detect_domain("npwp e obbligatorio") == "tax"
        assert _detect_domain("pph 21 ritenuta") == "tax"

    def test_extract_legal_refs(self):
        """Should extract legal references."""
        text = "Secondo UU 6/2011 e PP 28/2025 Art. 212, i requisiti sono..."
        refs = _extract_legal_refs(text)
        assert len(refs) >= 2
        assert any("UU" in r for r in refs)
        assert any("PP" in r for r in refs)

    def test_extract_warnings(self):
        """Should extract warnings."""
        text = """
        ### ⚠️ Rischi e Trappole
        1. Non usare mai nominee
        2. Attenzione al capitale minimo
        """
        warnings = _extract_warnings(text)
        assert len(warnings) >= 1

    def test_calculate_quality_score(self):
        """Quality score should be between 0 and 1."""
        config = GiantConfig()
        short_text = "Brief answer."
        long_text = """
        ### Analisi Legale
        - UU 6/2011 tentang Keimigrasian
        - PP 28/2025 requisiti

        ### ⚠️ Rischi e Trappole
        1. Attenzione al capitale
        2. Rischio nominee

        ### Costi Stimati
        - Total: 50-100 juta IDR

        Timeline: 4-6 settimane
        """
        short_score = _calculate_quality_score(short_text, config)
        long_score = _calculate_quality_score(long_text, config)

        assert 0 <= short_score <= 1
        assert 0 <= long_score <= 1
        assert long_score > short_score  # Longer, structured text should score higher


# ============================================================================
# TEST: ZANTARA SYNTHESIZER FORMATTERS
# ============================================================================

class TestZantaraFormatters:
    """Test Zantara Synthesizer formatting functions."""

    def test_detect_tone_urgent(self):
        """Should detect urgent tone for critical corrections."""
        corrections = [{"severity": "critical", "correction": "Test"}]
        tone = _detect_tone("any query", corrections)
        assert tone == ResponseTone.URGENT

    def test_detect_tone_educational(self):
        """Should detect educational tone for how-to questions."""
        tone = _detect_tone("come faccio a ottenere un kitas", [])
        assert tone == ResponseTone.EDUCATIONAL

    def test_detect_tone_casual_default(self):
        """Should default to casual tone."""
        tone = _detect_tone("info su bali", [])
        assert tone == ResponseTone.CASUAL

    def test_format_corrections_empty(self):
        """Should handle empty corrections."""
        result = _format_corrections([])
        assert "nessuna" in result.lower() or "accurato" in result.lower()

    def test_format_corrections_critical(self):
        """Should format critical corrections with icon."""
        corrections = [
            {"severity": "critical", "correction": "Test correction", "source": "Test source"}
        ]
        result = _format_corrections(corrections)
        assert "🚨" in result
        assert "Test correction" in result

    def test_format_calibrations(self):
        """Should format calibrations properly."""
        calibrations = {
            "test_service": {
                "price": "10-20 juta",
                "timeline": "2 weeks",
                "includes": "Everything",
                "consultant": "Team Test",
                "category": "test"
            }
        }
        result = _format_calibrations(calibrations)
        assert "10-20 juta" in result
        assert "Team Test" in result

    def test_clean_response(self):
        """Should remove internal terminology."""
        text = "Secondo il ragionamento base, la calibrazione indica... severity: critical"
        cleaned = _clean_response(text)
        assert "ragionamento base" not in cleaned.lower()
        assert "calibrazion" not in cleaned.lower()
        assert "severity" not in cleaned.lower()

    def test_validate_response_valid(self):
        """Should validate good response."""
        response = "Ecco la risposta dettagliata con informazioni utili. " * 10
        is_valid, issues = _validate_response(response, [])
        assert is_valid
        assert len(issues) == 0

    def test_validate_response_too_short(self):
        """Should flag too short response."""
        is_valid, issues = _validate_response("Short", [])
        assert not is_valid
        assert any("short" in i.lower() for i in issues)


# ============================================================================
# TEST: FALLBACK SYNTHESIS
# ============================================================================

class TestFallbackSynthesis:
    """Test fallback synthesis function."""

    def test_fallback_with_corrections(self):
        """Fallback should include critical corrections."""
        giant = {"key_points": [], "warnings": []}
        cell = {
            "corrections": [
                {"severity": "critical", "correction": "Critical test correction", "source": "test"}
            ],
            "enhancements": [],
            "calibrations": {}
        }
        result = _fallback_synthesis(giant, cell)
        assert "Critical test correction" in result

    def test_fallback_with_key_points(self):
        """Fallback should include key points."""
        giant = {
            "key_points": ["Point 1", "Point 2"],
            "warnings": [],
            "steps": []
        }
        cell = {"corrections": [], "enhancements": [], "calibrations": {}}
        result = _fallback_synthesis(giant, cell)
        assert "Point 1" in result

    def test_fallback_empty(self):
        """Fallback should handle empty input gracefully."""
        result = _fallback_synthesis({}, {})
        assert len(result) > 0  # Should return contact info


# ============================================================================
# TEST: ASYNC FUNCTIONS (with mocks)
# ============================================================================

class TestAsyncFunctions:
    """Test async functions with mocked LLM client."""

    @pytest.mark.asyncio
    async def test_cell_calibrate_detects_corrections(self):
        """cell_calibrate should detect corrections from Giant reasoning."""
        # Mock Giant reasoning that contains a known error pattern
        giant_reasoning = {
            "reasoning": "Per il B211A visa, dovresti...",  # B211A is deprecated
            "key_points": [],
            "warnings": []
        }

        result = await cell_calibrate(
            query="visa b211a",
            giant_reasoning=giant_reasoning,
            user_id=None,
            user_facts=None
        )

        # Should detect the B211A error
        assert len(result["corrections"]) >= 1
        assert any("b211a" in c["error_key"].lower() for c in result["corrections"])

    @pytest.mark.asyncio
    async def test_cell_calibrate_adds_enhancements(self):
        """cell_calibrate should add enhancements for detected topics."""
        giant_reasoning = {
            "reasoning": "Per aprire una PT PMA ristorante...",
            "key_points": [],
            "warnings": []
        }

        result = await cell_calibrate(
            query="pt pma ristorante",
            giant_reasoning=giant_reasoning,
            user_id=None,
            user_facts=None
        )

        # Should add enhancements for pt_pma and/or f&b topics
        assert len(result["enhancements"]) >= 1


# ============================================================================
# TEST: CONFIGURATION
# ============================================================================

class TestConfiguration:
    """Test configuration classes."""

    def test_giant_config_defaults(self):
        """GiantConfig should have sensible defaults."""
        config = GiantConfig()
        assert config.temperature > 0
        assert config.max_tokens > 1000
        assert config.min_reasoning_length > 100

    def test_synthesizer_config_defaults(self):
        """SynthesizerConfig should have sensible defaults."""
        config = SynthesizerConfig()
        assert config.max_words > 100
        assert config.temperature >= 0 and config.temperature <= 1

    def test_giant_result_to_dict(self):
        """GiantResult.to_dict() should work correctly."""
        result = GiantResult(
            reasoning="Test reasoning",
            key_points=["Point 1"],
            warnings=["Warning 1"],
            quality_score=0.8
        )
        d = result.to_dict()
        assert d["reasoning"] == "Test reasoning"
        assert d["quality_score"] == 0.8
        assert "Point 1" in d["key_points"]


# ============================================================================
# TEST: INTEGRATION
# ============================================================================

class TestIntegration:
    """Integration tests for the full pipeline."""

    def test_corrections_count(self):
        """Should have at least 15 corrections (Round 1-3)."""
        assert len(KNOWN_CORRECTIONS) >= 15

    def test_insights_topics_count(self):
        """Should have at least 15 insight topics (Round 4-6)."""
        assert len(PRACTICAL_INSIGHTS) >= 15

    def test_services_count(self):
        """Should have at least 15 services (Round 7-9)."""
        assert len(BALI_ZERO_SERVICES) >= 15

    def test_all_services_have_category(self):
        """All services should have a category."""
        for key, service in BALI_ZERO_SERVICES.items():
            assert "category" in service, f"{key} missing category"

