"""
Unit tests for JourneyBuilderService
Target: 100% coverage
Composer: 5
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.journey.journey_builder import JourneyBuilderService
from services.journey.journey_templates import JourneyTemplatesService


@pytest.fixture
def mock_templates_service():
    """Mock JourneyTemplatesService"""
    service = MagicMock(spec=JourneyTemplatesService)
    service.get_template = MagicMock(return_value={
        "title": "Test Journey",
        "description": "Test Description",
        "steps": [
            {
                "step_id": "step1",
                "title": "Step 1",
                "description": "First step",
                "prerequisites": [],
                "required_documents": [],
                "estimated_duration_days": 5
            },
            {
                "step_id": "step2",
                "title": "Step 2",
                "description": "Second step",
                "prerequisites": ["step1"],
                "required_documents": ["doc1"],
                "estimated_duration_days": 3
            }
        ]
    })
    return service


@pytest.fixture
def journey_builder(mock_templates_service):
    """Create JourneyBuilderService instance"""
    return JourneyBuilderService(templates_service=mock_templates_service)


class TestJourneyBuilderService:
    """Tests for JourneyBuilderService"""

    def test_init_with_templates_service(self, mock_templates_service):
        """Test initialization with templates service"""
        builder = JourneyBuilderService(templates_service=mock_templates_service)
        assert builder.templates == mock_templates_service

    def test_init_without_templates_service(self):
        """Test initialization without templates service"""
        builder = JourneyBuilderService()
        assert builder.templates is not None
        assert isinstance(builder.templates, JourneyTemplatesService)

    def test_build_journey_from_template(self, journey_builder, mock_templates_service):
        """Test building journey from template"""
        journey = journey_builder.build_journey_from_template(
            journey_id="journey1",
            journey_type="company_setup",
            client_id="client1",
            template_key="pt_pma_setup"
        )
        assert journey.journey_id == "journey1"
        assert journey.journey_type == "company_setup"
        assert journey.client_id == "client1"
        assert len(journey.steps) == 2
        assert journey.steps[0].step_id == "step1"
        assert journey.steps[1].step_id == "step2"

    def test_build_journey_from_template_with_metadata(self, journey_builder):
        """Test building journey with metadata"""
        journey = journey_builder.build_journey_from_template(
            journey_id="journey1",
            journey_type="company_setup",
            client_id="client1",
            template_key="pt_pma_setup",
            metadata={"priority": "high"}
        )
        assert journey.metadata["priority"] == "high"

    def test_build_journey_from_template_unknown_template(self, journey_builder, mock_templates_service):
        """Test building journey with unknown template"""
        mock_templates_service.get_template.return_value = None
        with pytest.raises(ValueError, match="Unknown template"):
            journey_builder.build_journey_from_template(
                journey_id="journey1",
                journey_type="company_setup",
                client_id="client1",
                template_key="unknown_template"
            )

    def test_build_journey_from_template_estimated_completion(self, journey_builder):
        """Test estimated completion calculation"""
        journey = journey_builder.build_journey_from_template(
            journey_id="journey1",
            journey_type="company_setup",
            client_id="client1",
            template_key="pt_pma_setup"
        )
        # Total days = 5 + 3 = 8
        assert journey.estimated_completion is not None

    def test_build_custom_journey(self, journey_builder):
        """Test building custom journey"""
        steps = [
            {
                "step_id": "custom_step1",
                "title": "Custom Step 1",
                "description": "Custom description",
                "prerequisites": [],
                "required_documents": [],
                "estimated_duration_days": 10
            }
        ]
        journey = journey_builder.build_custom_journey(
            journey_id="custom_journey1",
            journey_type="custom_type",
            client_id="client1",
            title="Custom Journey",
            description="Custom Description",
            steps=steps
        )
        assert journey.journey_id == "custom_journey1"
        assert journey.title == "Custom Journey"
        assert len(journey.steps) == 1
        assert journey.steps[0].step_id == "custom_step1"

    def test_build_custom_journey_with_minimal_steps(self, journey_builder):
        """Test building custom journey with minimal step data"""
        steps = [
            {
                "title": "Step 1"
            }
        ]
        journey = journey_builder.build_custom_journey(
            journey_id="custom_journey1",
            journey_type="custom_type",
            client_id="client1",
            title="Custom Journey",
            description="Custom Description",
            steps=steps
        )
        assert len(journey.steps) == 1
        assert journey.steps[0].step_number == 1

    def test_build_custom_journey_with_metadata(self, journey_builder):
        """Test building custom journey with metadata"""
        steps = []
        journey = journey_builder.build_custom_journey(
            journey_id="custom_journey1",
            journey_type="custom_type",
            client_id="client1",
            title="Custom Journey",
            description="Custom Description",
            steps=steps,
            metadata={"custom": "value"}
        )
        assert journey.metadata["custom"] == "value"

