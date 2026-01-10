"""
Unit tests for ComplianceTemplatesService
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.compliance.templates import ComplianceTemplatesService, ComplianceType


class TestComplianceTemplatesService:
    """Tests for ComplianceTemplatesService"""

    def test_init(self):
        """Test initialization"""
        service = ComplianceTemplatesService()
        assert service.ANNUAL_DEADLINES is not None
        assert len(service.ANNUAL_DEADLINES) > 0

    def test_get_template_exists(self):
        """Test getting existing template"""
        service = ComplianceTemplatesService()
        template = service.get_template("spt_tahunan_individual")

        assert template is not None
        assert template["title"] == "SPT Tahunan (Individual Tax Return)"
        assert template["deadline_month"] == 3
        assert template["deadline_day"] == 31

    def test_get_template_not_exists(self):
        """Test getting non-existent template"""
        service = ComplianceTemplatesService()
        template = service.get_template("nonexistent")
        assert template is None

    def test_get_annual_deadlines(self):
        """Test getting all annual deadlines"""
        service = ComplianceTemplatesService()
        deadlines = service.get_annual_deadlines()

        assert isinstance(deadlines, dict)
        assert "spt_tahunan_individual" in deadlines
        assert "spt_tahunan_corporate" in deadlines

    def test_list_templates(self):
        """Test listing all template keys"""
        service = ComplianceTemplatesService()
        templates = service.list_templates()

        assert isinstance(templates, list)
        assert "spt_tahunan_individual" in templates
        assert len(templates) > 0

    def test_validate_template_exists(self):
        """Test validating existing template"""
        service = ComplianceTemplatesService()
        assert service.validate_template("spt_tahunan_individual") is True

    def test_validate_template_not_exists(self):
        """Test validating non-existent template"""
        service = ComplianceTemplatesService()
        assert service.validate_template("nonexistent") is False

    def test_template_structure(self):
        """Test that templates have required structure"""
        service = ComplianceTemplatesService()
        template = service.get_template("spt_tahunan_individual")

        assert "title" in template
        assert "deadline_month" in template
        assert "deadline_day" in template
        assert "description" in template
        assert "compliance_type" in template
        assert template["compliance_type"] == ComplianceType.TAX_FILING
