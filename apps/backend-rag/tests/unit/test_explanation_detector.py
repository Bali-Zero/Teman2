"""
Unit tests for Explanation Detector Service

Tests the detection of explanation level (simple/expert/standard) and alternative requests.
"""

import sys
from pathlib import Path

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.communication import (
    build_alternatives_instructions,
    build_explanation_instructions,
    detect_explanation_level,
    needs_alternatives_format,
)


class TestExplanationLevelDetection:
    """Test explanation level detection"""

    def test_detect_simple_explanation(self):
        """Test detection of simple explanation requests"""
        test_cases = [
            "Spiegami il KITAS come se fossi un bambino",
            "spiegami semplice",
            "non capisco niente",
            "explain simply",
            "in modo facile",
            "come se fossi un bambino di 5 anni",
        ]

        for query in test_cases:
            level = detect_explanation_level(query)
            assert level == "simple", f"Expected 'simple' for '{query}', got '{level}'"

    def test_detect_expert_explanation(self):
        """Test detection of expert explanation requests"""
        test_cases = [
            "Mi serve una consulenza tecnica dettagliata",
            "dettagli normativi specifici",
            "professional advice",
            "consulenza da avvocato",
            "spiegazione tecnica dettagliata",  # Need "dettagliata" or "tecnica" + context
        ]

        for query in test_cases:
            level = detect_explanation_level(query)
            assert level == "expert", f"Expected 'expert' for '{query}', got '{level}'"

    def test_detect_standard_explanation(self):
        """Test detection of standard explanation (default)"""
        test_cases = [
            "Come funziona il KITAS?",
            "Che cos'è un PT PMA?",
            "ciao",
            "",
            "normal question",
        ]

        for query in test_cases:
            level = detect_explanation_level(query)
            assert level == "standard", f"Expected 'standard' for '{query}', got '{level}'"

    def test_case_insensitive_detection(self):
        """Test that detection is case-insensitive"""
        assert detect_explanation_level("SPIEGAMI SEMPLICE") == "simple"
        assert detect_explanation_level("Spiegami Semplice") == "simple"
        assert detect_explanation_level("TECNICO DETTAGLIATO") == "expert"


class TestAlternativesDetection:
    """Test alternatives request detection"""

    def test_detect_alternatives_request(self):
        """Test detection of alternative requests"""
        test_cases = [
            "Non posso permettermi un PT PMA, ci sono alternative?",
            "ci sono alternative",
            "invece di PT PMA cosa posso fare?",
            "altre opzioni disponibili",
            "non ho i soldi per PT PMA",
            "troppo caro, alternative?",
            "non posso permettermi",
            "più economico",
        ]

        for query in test_cases:
            has_alt = needs_alternatives_format(query)
            assert has_alt, f"Expected alternatives detection for '{query}'"

    def test_no_alternatives_detection(self):
        """Test that normal queries don't trigger alternatives detection"""
        test_cases = [
            "Come funziona il KITAS?",
            "Che cos'è un PT PMA?",
            "ciao",
            "",
            "normal question",
        ]

        for query in test_cases:
            has_alt = needs_alternatives_format(query)
            assert not has_alt, f"Should not detect alternatives for '{query}'"

    def test_case_insensitive_alternatives(self):
        """Test that alternatives detection is case-insensitive"""
        assert needs_alternatives_format("CI SONO ALTERNATIVE?") is True
        assert needs_alternatives_format("Non Posso Permettermi") is True


class TestExplanationInstructions:
    """Test building explanation instructions"""

    def test_build_simple_instructions(self):
        """Test building simple explanation instructions"""
        instructions = build_explanation_instructions("simple")

        assert "SIMPLE" in instructions.upper()
        assert len(instructions) > 100  # Should have substantial content
        # Should mention basic vocabulary or analogies
        assert (
            "basic" in instructions.lower()
            or "analog" in instructions.lower()
            or "semplice" in instructions.lower()
        )

    def test_build_expert_instructions(self):
        """Test building expert explanation instructions"""
        instructions = build_explanation_instructions("expert")

        assert "EXPERT" in instructions.upper()
        assert len(instructions) > 100
        # Should mention technical terms or regulations
        assert (
            "technical" in instructions.lower()
            or "regulat" in instructions.lower()
            or "tecnico" in instructions.lower()
        )

    def test_build_standard_instructions(self):
        """Test building standard explanation instructions"""
        instructions = build_explanation_instructions("standard")

        assert "STANDARD" in instructions.upper() or len(instructions) > 50
        assert len(instructions) > 50  # Should have some content

    def test_invalid_level_defaults(self):
        """Test that invalid levels don't crash"""
        # Should not raise exception
        instructions = build_explanation_instructions("invalid")
        assert isinstance(instructions, str)


class TestAlternativesInstructions:
    """Test building alternatives instructions"""

    def test_build_alternatives_instructions(self):
        """Test building alternatives format instructions"""
        instructions = build_alternatives_instructions()

        assert len(instructions) > 200  # Should have substantial content
        # Should mention numbered list format
        assert (
            "numbered" in instructions.lower()
            or "lista numerata" in instructions.lower()
            or "1)" in instructions
            or "1." in instructions
        )
        # Should mention alternatives
        assert "alternative" in instructions.lower() or "opzioni" in instructions.lower()


class TestIntegration:
    """Integration tests combining multiple detections"""

    def test_simple_with_alternatives(self):
        """Test query that asks for simple explanation of alternatives"""
        query = "Spiegami in modo semplice le alternative al PT PMA"

        level = detect_explanation_level(query)
        has_alt = needs_alternatives_format(query)

        # Should detect both
        assert level == "simple"
        assert has_alt is True

    def test_expert_without_alternatives(self):
        """Test expert query without alternatives"""
        query = "Mi serve una spiegazione tecnica dettagliata sul KITAS"

        level = detect_explanation_level(query)
        has_alt = needs_alternatives_format(query)

        assert level == "expert"
        assert has_alt is False

    def test_standard_with_alternatives(self):
        """Test standard query with alternatives"""
        query = "Non posso permettermi un PT PMA, ci sono alternative?"

        level = detect_explanation_level(query)
        has_alt = needs_alternatives_format(query)

        assert level == "standard"
        assert has_alt is True
