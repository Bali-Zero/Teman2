"""
Unit tests for procedural_formatter
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.communication.procedural_formatter import (
    get_procedural_format_instruction,
    is_procedural_question,
)


class TestProceduralFormatter:
    """Tests for procedural formatter"""

    def test_is_procedural_question_true(self):
        """Test detecting procedural question"""
        result = is_procedural_question("Come faccio a ottenere un KITAS?")
        assert result is True

    def test_is_procedural_question_false(self):
        """Test detecting non-procedural question"""
        result = is_procedural_question("Hello")
        assert result is False

    def test_is_procedural_question_empty(self):
        """Test detecting procedural question with empty text"""
        result = is_procedural_question("")
        assert result is False

    def test_get_procedural_format_instruction_it(self):
        """Test getting procedural format instruction for Italian"""
        result = get_procedural_format_instruction("it")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_procedural_format_instruction_en(self):
        """Test getting procedural format instruction for English"""
        result = get_procedural_format_instruction("en")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_procedural_format_instruction_id(self):
        """Test getting procedural format instruction for Indonesian"""
        result = get_procedural_format_instruction("id")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_procedural_format_instruction_default(self):
        """Test getting procedural format instruction for unknown language"""
        result = get_procedural_format_instruction("unknown")
        assert isinstance(result, str)
        assert len(result) > 0
