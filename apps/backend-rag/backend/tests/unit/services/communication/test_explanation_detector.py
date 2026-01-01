"""
Unit tests for explanation_detector
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.communication.explanation_detector import (
    detect_explanation_level,
    needs_alternatives_format,
    build_explanation_instructions,
    build_alternatives_instructions
)


class TestExplanationDetector:
    """Tests for explanation detector"""

    def test_detect_explanation_level_simple(self):
        """Test detecting simple explanation level"""
        result = detect_explanation_level("Spiegami in modo semplice")
        assert result == "simple"

    def test_detect_explanation_level_expert(self):
        """Test detecting expert explanation level"""
        result = detect_explanation_level("Spiegazione tecnica dettagliata")
        assert result == "expert"

    def test_detect_explanation_level_standard(self):
        """Test detecting standard explanation level"""
        result = detect_explanation_level("Hello")
        assert result == "standard"

    def test_needs_alternatives_format_true(self):
        """Test detecting need for alternatives"""
        result = needs_alternatives_format("Altre opzioni?")
        assert result is True

    def test_needs_alternatives_format_false(self):
        """Test detecting no need for alternatives"""
        result = needs_alternatives_format("Hello")
        assert result is False

    def test_build_explanation_instructions_simple(self):
        """Test building simple explanation instructions"""
        result = build_explanation_instructions("simple")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_explanation_instructions_expert(self):
        """Test building expert explanation instructions"""
        result = build_explanation_instructions("expert")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_explanation_instructions_standard(self):
        """Test building standard explanation instructions"""
        result = build_explanation_instructions("standard")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_alternatives_instructions(self):
        """Test building alternatives instructions"""
        result = build_alternatives_instructions()
        assert isinstance(result, str)
        assert len(result) > 0
