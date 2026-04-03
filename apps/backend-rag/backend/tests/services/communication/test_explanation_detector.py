"""
Tests for explanation_detector.py - Explanation level detection and alternative requests.
"""

import pytest

from backend.services.communication.explanation_detector import (
    build_alternatives_instructions,
    build_explanation_instructions,
    detect_explanation_level,
    needs_alternatives_format,
)


class TestDetectExplanationLevel:
    """Tests for detect_explanation_level function."""

    def test_simple_italian(self):
        assert detect_explanation_level("Spiegami come se fossi un bambino") == "simple"
        assert detect_explanation_level("In modo semplice per favore") == "simple"

    def test_simple_english(self):
        assert detect_explanation_level("Explain simply what KITAS is") == "simple"
        assert detect_explanation_level("Dumb it down for me") == "simple"

    def test_expert_italian(self):
        assert detect_explanation_level("Dammi i dettagli tecnici della normativa") == "expert"
        assert detect_explanation_level("Consulenza tecnica sul regolamento") == "expert"

    def test_expert_english(self):
        assert detect_explanation_level("Give me the technical details") == "expert"
        assert detect_explanation_level("I need expert legal advice") == "expert"

    def test_standard_default(self):
        assert detect_explanation_level("What documents do I need for KITAS?") == "standard"
        assert detect_explanation_level("How much does PT PMA cost?") == "standard"

    def test_simple_has_priority_over_expert(self):
        """When both triggers present, simple wins."""
        # "semplice" (simple) + "tecnico" (expert) - simple should win
        assert detect_explanation_level("spiegami in modo semplice i dettagli tecnici") == "simple"

    def test_case_insensitive(self):
        assert detect_explanation_level("SPIEGAMI IN MODO SEMPLICE") == "simple"
        assert detect_explanation_level("TECHNICAL DETAILS PLEASE") == "expert"


class TestNeedsAlternativesFormat:
    """Tests for needs_alternatives_format function."""

    def test_italian_alternatives(self):
        assert needs_alternatives_format("Ci sono alternative al PT PMA?") is True
        assert needs_alternatives_format("Altre opzioni più economiche?") is True
        assert needs_alternatives_format("Non posso permettermi questo, troppo caro") is True

    def test_english_alternatives(self):
        assert needs_alternatives_format("Are there alternatives to this visa?") is True
        assert needs_alternatives_format("I can't afford this, any cheaper options?") is True
        assert needs_alternatives_format("What are the other options?") is True

    def test_indonesian_alternatives(self):
        assert needs_alternatives_format("Apakah ada opsi lain yang lebih murah?") is True

    def test_no_alternatives(self):
        assert needs_alternatives_format("What is KITAS?") is False
        assert needs_alternatives_format("How to apply?") is False


class TestBuildExplanationInstructions:
    """Tests for build_explanation_instructions function."""

    def test_simple_instructions(self):
        result = build_explanation_instructions("simple")
        assert "SIMPLE" in result
        assert "basic vocabulary" in result.lower()
        assert "analogies" in result.lower()

    def test_expert_instructions(self):
        result = build_explanation_instructions("expert")
        assert "EXPERT" in result
        assert "technical terminology" in result.lower()

    def test_standard_instructions(self):
        result = build_explanation_instructions("standard")
        assert "STANDARD" in result
        assert "balanced" in result.lower()

    def test_instructions_not_empty(self):
        for level in ["simple", "standard", "expert"]:
            result = build_explanation_instructions(level)
            assert len(result) > 50


class TestBuildAlternativesInstructions:
    """Tests for build_alternatives_instructions function."""

    def test_contains_numbered_format(self):
        result = build_alternatives_instructions()
        assert "numbered list" in result.lower()
        assert "1)" in result
        assert "2)" in result
        assert "3)" in result

    def test_not_empty(self):
        result = build_alternatives_instructions()
        assert len(result) > 50
