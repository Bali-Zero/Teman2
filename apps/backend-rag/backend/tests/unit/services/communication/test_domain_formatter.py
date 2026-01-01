"""
Unit tests for domain_formatter
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.communication.domain_formatter import get_domain_format_instruction


class TestDomainFormatter:
    """Tests for domain formatter"""

    def test_get_domain_format_instruction_visa(self):
        """Test getting format instruction for visa domain"""
        result = get_domain_format_instruction("visa", "en")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_domain_format_instruction_tax(self):
        """Test getting format instruction for tax domain"""
        result = get_domain_format_instruction("tax", "en")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_domain_format_instruction_company(self):
        """Test getting format instruction for company domain"""
        result = get_domain_format_instruction("company", "en")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_domain_format_instruction_unknown(self):
        """Test getting format instruction for unknown domain"""
        result = get_domain_format_instruction("unknown", "en")
        assert result == ""

    def test_get_domain_format_instruction_different_languages(self):
        """Test getting format instruction for different languages"""
        for lang in ["en", "it", "id"]:
            result = get_domain_format_instruction("visa", lang)
            assert isinstance(result, str)
            assert len(result) > 0
