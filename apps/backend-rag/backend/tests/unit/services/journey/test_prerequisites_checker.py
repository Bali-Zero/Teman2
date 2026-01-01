"""
Unit tests for PrerequisitesCheckerService
Target: >95% coverage
"""

import sys
from pathlib import Path
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.journey.prerequisites_checker import PrerequisitesCheckerService
from services.misc.client_journey_orchestrator import ClientJourney, JourneyStatus, JourneyStep, StepStatus


@pytest.fixture
def prerequisites_checker():
    """Create PrerequisitesCheckerService instance"""
    return PrerequisitesCheckerService()


@pytest.fixture
def mock_journey():
    """Create mock journey with steps"""
    steps = [
        JourneyStep(
            step_id="step1",
            step_number=1,
            title="Step 1",
            description="First step",
            prerequisites=[],
            required_documents=[],
            estimated_duration_days=5,
            status=StepStatus.COMPLETED
        ),
        JourneyStep(
            step_id="step2",
            step_number=2,
            title="Step 2",
            description="Second step",
            prerequisites=["step1"],
            required_documents=[],
            estimated_duration_days=3,
            status=StepStatus.PENDING
        ),
        JourneyStep(
            step_id="step3",
            step_number=3,
            title="Step 3",
            description="Third step",
            prerequisites=["step1", "step2"],
            required_documents=[],
            estimated_duration_days=2,
            status=StepStatus.PENDING
        )
    ]
    journey = ClientJourney(
        journey_id="journey1",
        journey_type="company_setup",
        client_id="client1",
        title="Test Journey",
        description="Test Description",
        steps=steps,
        status=JourneyStatus.IN_PROGRESS
    )
    return journey


class TestPrerequisitesCheckerService:
    """Tests for PrerequisitesCheckerService"""

    def test_init(self, prerequisites_checker):
        """Test initialization"""
        assert prerequisites_checker is not None

    def test_check_prerequisites_no_prerequisites(self, prerequisites_checker, mock_journey):
        """Test checking step with no prerequisites"""
        met, missing = prerequisites_checker.check_prerequisites(mock_journey, "step1")
        assert met is True
        assert len(missing) == 0

    def test_check_prerequisites_all_met(self, prerequisites_checker, mock_journey):
        """Test checking step with all prerequisites met"""
        met, missing = prerequisites_checker.check_prerequisites(mock_journey, "step2")
        assert met is True
        assert len(missing) == 0

    def test_check_prerequisites_some_missing(self, prerequisites_checker, mock_journey):
        """Test checking step with some prerequisites missing"""
        # Make step1 incomplete
        mock_journey.steps[0].status = StepStatus.PENDING
        met, missing = prerequisites_checker.check_prerequisites(mock_journey, "step2")
        assert met is False
        assert len(missing) > 0

    def test_check_prerequisites_multiple_prerequisites(self, prerequisites_checker, mock_journey):
        """Test checking step with multiple prerequisites"""
        # Complete step2 first
        mock_journey.steps[1].status = StepStatus.COMPLETED
        met, missing = prerequisites_checker.check_prerequisites(mock_journey, "step3")
        assert met is True  # Both step1 and step2 are completed
        assert len(missing) == 0

    def test_check_prerequisites_multiple_missing(self, prerequisites_checker, mock_journey):
        """Test checking step with multiple missing prerequisites"""
        # Make both prerequisites incomplete
        mock_journey.steps[0].status = StepStatus.PENDING
        mock_journey.steps[1].status = StepStatus.PENDING
        met, missing = prerequisites_checker.check_prerequisites(mock_journey, "step3")
        assert met is False
        assert len(missing) >= 2

    def test_check_prerequisites_step_not_found(self, prerequisites_checker, mock_journey):
        """Test checking prerequisites for non-existent step"""
        met, missing = prerequisites_checker.check_prerequisites(mock_journey, "nonexistent")
        assert met is False
        assert len(missing) == 1
        assert "not found" in missing[0].lower()

    def test_check_prerequisites_prerequisite_not_found(self, prerequisites_checker):
        """Test checking step with prerequisite that doesn't exist"""
        steps = [
            JourneyStep(
                step_id="step1",
                step_number=1,
                title="Step 1",
                description="First step",
                prerequisites=["nonexistent_prereq"],
                required_documents=[],
                estimated_duration_days=5,
                status=StepStatus.PENDING
            )
        ]
        journey = ClientJourney(
            journey_id="journey1",
            journey_type="company_setup",
            client_id="client1",
            title="Test Journey",
            description="Test Description",
            steps=steps,
            status=JourneyStatus.NOT_STARTED
        )
        met, missing = prerequisites_checker.check_prerequisites(journey, "step1")
        assert met is False
        assert len(missing) > 0

