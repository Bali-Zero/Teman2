"""
Integration Tests for Explanation Detector
Tests explanation level detection and alternative requests
"""

import os
import sys
from pathlib import Path

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestExplanationDetectorIntegration:
    """Comprehensive integration tests for explanation_detector"""

    def test_detect_explanation_level_simple(self):
        """Test detecting simple explanation level"""
        from services.communication import detect_explanation_level

        assert detect_explanation_level("Spiegami in modo semplice") == "simple"
        assert detect_explanation_level("Explain it simply") == "simple"
        assert (
            detect_explanation_level("Non capisco, spiegami come se fossi un bambino") == "simple"
        )

    def test_detect_explanation_level_expert(self):
        """Test detecting expert explanation level"""
        from services.communication import detect_explanation_level

        assert detect_explanation_level("Spiegazione tecnica dettagliata") == "expert"
        assert detect_explanation_level("Expert explanation with regulations") == "expert"
        assert detect_explanation_level("Consulenza legale specifica") == "expert"

    def test_detect_explanation_level_standard(self):
        """Test detecting standard explanation level"""
        from services.communication import detect_explanation_level

        assert detect_explanation_level("What is PT PMA?") == "standard"
        assert detect_explanation_level("Come ottenere un visto?") == "standard"

    def test_needs_alternatives_format(self):
        """Test detecting alternatives request"""
        from services.communication import needs_alternatives_format

        assert needs_alternatives_format("Quali sono le alternative?") is True
        assert needs_alternatives_format("What are the other options?") is True
        assert needs_alternatives_format("Non posso permettermi, ci sono alternative?") is True
        assert needs_alternatives_format("What is PT PMA?") is False

    def test_build_explanation_instructions_simple(self):
        """Test building simple explanation instructions"""
        from services.communication import build_explanation_instructions

        instruction = build_explanation_instructions("simple")

        assert instruction is not None
        assert "simple" in instruction.lower()
        assert "basic" in instruction.lower() or "semplice" in instruction.lower()

    def test_build_explanation_instructions_expert(self):
        """Test building expert explanation instructions"""
        from services.communication import build_explanation_instructions

        instruction = build_explanation_instructions("expert")

        assert instruction is not None
        assert "expert" in instruction.lower() or "tecnico" in instruction.lower()
        assert "technical" in instruction.lower() or "dettagli" in instruction.lower()

    def test_build_explanation_instructions_standard(self):
        """Test building standard explanation instructions"""
        from services.communication import build_explanation_instructions

        instruction = build_explanation_instructions("standard")

        assert instruction is not None
        assert "standard" in instruction.lower() or "balanced" in instruction.lower()

    def test_build_alternatives_instructions(self):
        """Test building alternatives instructions"""
        from services.communication import build_alternatives_instructions

        instruction = build_alternatives_instructions()

        assert instruction is not None
        assert "alternative" in instruction.lower()
        assert "numbered" in instruction.lower() or "list" in instruction.lower()
