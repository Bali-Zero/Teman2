"""
Tests for domain_formatter.py - Domain-specific formatting instructions.
"""


from backend.services.communication.domain_formatter import get_domain_format_instruction


class TestGetDomainFormatInstruction:
    """Tests for get_domain_format_instruction function."""

    def test_visa_domain(self):
        result = get_domain_format_instruction("visa", "en")
        assert "VISA" in result
        assert "FORMATTING RULE" in result
        assert "TEMPLATE" in result

    def test_tax_domain(self):
        result = get_domain_format_instruction("tax", "en")
        assert "TAX" in result
        assert "FORMATTING RULE" in result

    def test_company_domain(self):
        result = get_domain_format_instruction("company", "en")
        assert "COMPANY" in result or "PT PMA" in result
        assert "FORMATTING RULE" in result

    def test_unknown_domain_returns_empty(self):
        result = get_domain_format_instruction("unknown_domain", "en")
        assert result == ""

    def test_contains_template_instruction(self):
        result = get_domain_format_instruction("visa", "it")
        assert "TEMPLATE" in result
        assert "IMPORTANT" in result

    def test_all_supported_domains_return_content(self):
        for domain in ["visa", "tax", "company"]:
            result = get_domain_format_instruction(domain, "en")
            assert len(result) > 50, f"{domain} should return substantial content"
