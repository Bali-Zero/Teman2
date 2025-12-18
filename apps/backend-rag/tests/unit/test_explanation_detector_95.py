"""
Unit Tests for services/explanation_detector.py - 95% Coverage Target
Tests the explanation level detection functions
"""

import os
import sys
from pathlib import Path

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test detect_explanation_level
# ============================================================================


class TestDetectExplanationLevel:
    """Test suite for detect_explanation_level function"""

    def test_detect_simple_italian_bambino(self):
        """Test detection of simple level with 'bambino' trigger"""
        from services.communication import detect_explanation_level

        result = detect_explanation_level("Spiegami come se fossi un bambino")

        assert result == "simple"

    def test_detect_simple_italian_semplice(self):
        """Test detection of simple level with 'semplice' trigger"""
        from services.communication import detect_explanation_level

        result = detect_explanation_level("Puoi spiegarmi in modo semplice?")

        assert result == "simple"

    def test_detect_simple_italian_non_capisco(self):
        """Test detection of simple level with 'non capisco' trigger"""
        from services.communication import detect_explanation_level

        result = detect_explanation_level("Non capisco, puoi rispiegare?")

        assert result == "simple"

    def test_detect_simple_english_easy(self):
        """Test detection of simple level with 'easy' trigger"""
        from services.communication import detect_explanation_level

        result = detect_explanation_level("Can you make this easy to understand?")

        assert result == "simple"

    def test_detect_simple_english_dumb_down(self):
        """Test detection of simple level with 'dumb it down' trigger"""
        from services.communication import detect_explanation_level

        result = detect_explanation_level("Can you dumb it down for me?")

        assert result == "simple"

    def test_detect_expert_italian_esperto(self):
        """Test detection of expert level with 'esperto' trigger"""
        from services.communication import detect_explanation_level

        result = detect_explanation_level("Dammi una spiegazione da esperto")

        assert result == "expert"

    def test_detect_expert_italian_tecnico(self):
        """Test detection of expert level with 'tecnico' trigger"""
        from services.communication import detect_explanation_level

        result = detect_explanation_level("Voglio i dettagli tecnici")

        assert result == "expert"

    def test_detect_expert_italian_legalmente(self):
        """Test detection of expert level with 'legalmente' trigger"""
        from services.communication import detect_explanation_level

        result = detect_explanation_level("Cosa dice legalmente la normativa?")

        assert result == "expert"

    def test_detect_expert_english_professional(self):
        """Test detection of expert level with 'professional' trigger"""
        from services.communication import detect_explanation_level

        result = detect_explanation_level("I need a professional explanation")

        assert result == "expert"

    def test_detect_expert_english_detailed(self):
        """Test detection of expert level with 'detailed' trigger"""
        from services.communication import detect_explanation_level

        result = detect_explanation_level("Give me detailed information")

        assert result == "expert"

    def test_detect_standard_default(self):
        """Test default standard level when no triggers match"""
        from services.communication import detect_explanation_level

        result = detect_explanation_level("What is a KITAS?")

        assert result == "standard"

    def test_detect_standard_general_query(self):
        """Test standard level for general query"""
        from services.communication import detect_explanation_level

        result = detect_explanation_level("How do I start a business in Bali?")

        assert result == "standard"

    def test_detect_case_insensitive(self):
        """Test that detection is case insensitive"""
        from services.communication import detect_explanation_level

        result1 = detect_explanation_level("SPIEGAMI IN MODO SEMPLICE")
        result2 = detect_explanation_level("I need EXPERT advice")

        assert result1 == "simple"
        assert result2 == "expert"


# ============================================================================
# Test needs_alternatives_format
# ============================================================================


class TestNeedsAlternativesFormat:
    """Test suite for needs_alternatives_format function"""

    def test_alternatives_italian_alternative(self):
        """Test detection with 'alternative' trigger"""
        from services.communication import needs_alternatives_format

        result = needs_alternatives_format("Quali sono le alternative?")

        assert result is True

    def test_alternatives_italian_altre_opzioni(self):
        """Test detection with 'altre opzioni' trigger"""
        from services.communication import needs_alternatives_format

        result = needs_alternatives_format("Ci sono altre opzioni?")

        assert result is True

    def test_alternatives_italian_troppo_caro(self):
        """Test detection with 'troppo caro' trigger"""
        from services.communication import needs_alternatives_format

        result = needs_alternatives_format("Questo è troppo caro per me")

        assert result is True

    def test_alternatives_italian_piu_economico(self):
        """Test detection with 'più economico' trigger"""
        from services.communication import needs_alternatives_format

        result = needs_alternatives_format("C'è qualcosa di più economico?")

        assert result is True

    def test_alternatives_english_alternatives(self):
        """Test detection with 'alternatives' trigger"""
        from services.communication import needs_alternatives_format

        result = needs_alternatives_format("What alternatives do I have?")

        assert result is True

    def test_alternatives_english_cant_afford(self):
        """Test detection with 'can't afford' trigger"""
        from services.communication import needs_alternatives_format

        result = needs_alternatives_format("I can't afford this option")

        assert result is True

    def test_alternatives_english_cheaper(self):
        """Test detection with 'cheaper' trigger"""
        from services.communication import needs_alternatives_format

        result = needs_alternatives_format("Is there a cheaper way?")

        assert result is True

    def test_alternatives_indonesian_opsi_lain(self):
        """Test detection with Indonesian 'opsi lain' trigger"""
        from services.communication import needs_alternatives_format

        result = needs_alternatives_format("Ada opsi lain?")

        assert result is True

    def test_no_alternatives_regular_query(self):
        """Test no alternatives detected for regular query"""
        from services.communication import needs_alternatives_format

        result = needs_alternatives_format("How do I get a KITAS?")

        assert result is False

    def test_alternatives_case_insensitive(self):
        """Test that detection is case insensitive"""
        from services.communication import needs_alternatives_format

        result = needs_alternatives_format("WHAT ALTERNATIVES do I have?")

        assert result is True


# ============================================================================
# Test build_explanation_instructions
# ============================================================================


class TestBuildExplanationInstructions:
    """Test suite for build_explanation_instructions function"""

    def test_build_simple_instructions(self):
        """Test building simple level instructions"""
        from services.communication import build_explanation_instructions

        result = build_explanation_instructions("simple")

        assert "SIMPLE" in result
        assert "basic vocabulary" in result
        assert "analogies" in result
        assert "step-by-step" in result

    def test_build_expert_instructions(self):
        """Test building expert level instructions"""
        from services.communication import build_explanation_instructions

        result = build_explanation_instructions("expert")

        assert "EXPERT" in result
        assert "technical terminology" in result
        assert "regulations" in result
        assert "legal citations" in result

    def test_build_standard_instructions(self):
        """Test building standard level instructions"""
        from services.communication import build_explanation_instructions

        result = build_explanation_instructions("standard")

        assert "STANDARD" in result
        assert "Balanced" in result
        assert "practical examples" in result


# ============================================================================
# Test build_alternatives_instructions
# ============================================================================


class TestBuildAlternativesInstructions:
    """Test suite for build_alternatives_instructions function"""

    def test_build_alternatives_instructions_content(self):
        """Test building alternatives instructions content"""
        from services.communication import build_alternatives_instructions

        result = build_alternatives_instructions()

        assert "ALTERNATIVES REQUEST" in result
        assert "numbered list" in result
        assert "1)" in result
        assert "2)" in result
        assert "3)" in result

    def test_build_alternatives_instructions_example(self):
        """Test that alternatives instructions include example"""
        from services.communication import build_alternatives_instructions

        result = build_alternatives_instructions()

        assert "Example:" in result
        assert "Digital Nomad" in result

    def test_build_alternatives_instructions_format_requirement(self):
        """Test that alternatives instructions include format requirement"""
        from services.communication import build_alternatives_instructions

        result = build_alternatives_instructions()

        assert "DO NOT use bullet points" in result
        assert "ONLY numbered list format" in result


# ============================================================================
# Test module constants
# ============================================================================


class TestModuleConstants:
    """Test suite for module constants"""

    def test_simplify_triggers_defined(self):
        """Test SIMPLIFY_TRIGGERS constant is defined"""
        from services.communication import SIMPLIFY_TRIGGERS

        assert len(SIMPLIFY_TRIGGERS) > 0
        assert "bambino" in SIMPLIFY_TRIGGERS
        assert "simple" in SIMPLIFY_TRIGGERS

    def test_expert_triggers_defined(self):
        """Test EXPERT_TRIGGERS constant is defined"""
        from services.communication import EXPERT_TRIGGERS

        assert len(EXPERT_TRIGGERS) > 0
        assert "esperto" in EXPERT_TRIGGERS
        assert "expert" in EXPERT_TRIGGERS

    def test_alternatives_triggers_defined(self):
        """Test ALTERNATIVES_TRIGGERS constant is defined"""
        from services.communication import ALTERNATIVES_TRIGGERS

        assert len(ALTERNATIVES_TRIGGERS) > 0
        assert "alternative" in ALTERNATIVES_TRIGGERS
        assert "alternatives" in ALTERNATIVES_TRIGGERS
