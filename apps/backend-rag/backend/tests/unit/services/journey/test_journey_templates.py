"""
Unit tests for JourneyTemplatesService
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.journey.journey_templates import JourneyTemplatesService


@pytest.fixture
def journey_templates():
    """Create JourneyTemplatesService instance"""
    return JourneyTemplatesService()


class TestJourneyTemplatesService:
    """Tests for JourneyTemplatesService"""

    def test_init(self, journey_templates):
        """Test initialization"""
        assert journey_templates is not None
        assert len(journey_templates.JOURNEY_TEMPLATES) > 0

    def test_get_template_existing(self, journey_templates):
        """Test getting existing template"""
        template = journey_templates.get_template("pt_pma_setup")
        assert template is not None
        assert "title" in template
        assert "steps" in template

    def test_get_template_not_found(self, journey_templates):
        """Test getting non-existent template"""
        template = journey_templates.get_template("nonexistent")
        assert template is None

    def test_list_templates(self, journey_templates):
        """Test listing all templates"""
        templates = journey_templates.list_templates()
        assert isinstance(templates, list)
        assert len(templates) > 0

    def test_template_structure(self, journey_templates):
        """Test template structure"""
        template = journey_templates.get_template("pt_pma_setup")
        if template:
            assert "title" in template
            assert "description" in template
            assert "steps" in template
            assert isinstance(template["steps"], list)

    def test_template_steps_structure(self, journey_templates):
        """Test template steps structure"""
        template = journey_templates.get_template("pt_pma_setup")
        if template and template["steps"]:
            step = template["steps"][0]
            assert "step_id" in step
            assert "title" in step
            assert "description" in step
