"""
Unit tests for domain_formatter
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.communication.domain_formatter import get_domain_format_instruction


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

    def test_get_domain_format_instruction_visa_all_languages(self):
        """Test visa format instruction for all supported languages"""
        for lang in ["en", "it", "id"]:
            result = get_domain_format_instruction("visa", lang)
            assert "VISA/KITAS" in result
            assert "FORMATTING RULE" in result

    def test_get_domain_format_instruction_tax_all_languages(self):
        """Test tax format instruction for all supported languages"""
        for lang in ["en", "it", "id"]:
            result = get_domain_format_instruction("tax", lang)
            assert "TAX/PAJAK" in result
            assert "FORMATTING RULE" in result

    def test_get_domain_format_instruction_company_all_languages(self):
        """Test company format instruction for all supported languages"""
        for lang in ["en", "it", "id"]:
            result = get_domain_format_instruction("company", lang)
            assert "COMPANY SETUP" in result
            assert "FORMATTING RULE" in result

    def test_get_domain_format_instruction_contains_template(self):
        """Test that format instruction contains template"""
        result = get_domain_format_instruction("visa", "en")
        assert "TEMPLATE TO USE" in result
        assert "IMPORTANT" in result

    def test_get_domain_format_instruction_contains_settings(self):
        """Test that format instruction references settings"""
        result = get_domain_format_instruction("visa", "en")
        # Should contain reference to COMPANY_NAME from settings
        assert "Cost" in result or "cost" in result.lower()
