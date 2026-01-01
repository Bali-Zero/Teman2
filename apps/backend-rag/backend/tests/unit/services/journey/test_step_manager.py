"""
Unit tests for StepManagerService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import patch
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.journey.step_manager import StepManagerService
from services.misc.client_journey_orchestrator import ClientJourney, JourneyStatus, JourneyStep, StepStatus


@pytest.fixture
def step_manager():
    """Create StepManagerService instance"""
    return StepManagerService()


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
            status=StepStatus.PENDING
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
    return journey


class TestStepManagerService:
    """Tests for StepManagerService"""

    def test_init(self, step_manager):
        """Test initialization"""
        assert step_manager is not None

    def test_start_step(self, step_manager, mock_journey):
        """Test starting a step"""
        result = step_manager.start_step(mock_journey, "step1")
        assert result is True
        assert mock_journey.steps[0].status == StepStatus.IN_PROGRESS
        assert mock_journey.status == JourneyStatus.IN_PROGRESS

    def test_start_step_not_found(self, step_manager, mock_journey):
        """Test starting non-existent step"""
        result = step_manager.start_step(mock_journey, "nonexistent")
        assert result is False

    def test_start_step_already_completed(self, step_manager, mock_journey):
        """Test starting already completed step"""
        mock_journey.steps[0].status = StepStatus.COMPLETED
        result = step_manager.start_step(mock_journey, "step1")
        assert result is False

    def test_complete_step(self, step_manager, mock_journey):
        """Test completing a step"""
        mock_journey.steps[0].status = StepStatus.IN_PROGRESS
        result = step_manager.complete_step(mock_journey, "step1", notes=["Done"])
        assert result is True
        assert mock_journey.steps[0].status == StepStatus.COMPLETED

    def test_complete_step_not_found(self, step_manager, mock_journey):
        """Test completing non-existent step"""
        result = step_manager.complete_step(mock_journey, "nonexistent")
        assert result is False

    def test_complete_step_already_completed(self, step_manager, mock_journey):
        """Test completing already completed step"""
        mock_journey.steps[0].status = StepStatus.COMPLETED
        result = step_manager.complete_step(mock_journey, "step1")
        assert result is False

    def test_complete_step_with_notes(self, step_manager, mock_journey):
        """Test completing step with notes"""
        mock_journey.steps[0].status = StepStatus.IN_PROGRESS
        notes = ["Document submitted", "Payment received"]
        result = step_manager.complete_step(mock_journey, "step1", notes=notes)
        assert result is True
        assert len(mock_journey.steps[0].notes) > 0

    def test_block_step(self, step_manager, mock_journey):
        """Test blocking a step"""
        result = step_manager.block_step(mock_journey, "step1", reason="Missing documents")
        assert result is True
        assert mock_journey.steps[0].status == StepStatus.BLOCKED

    def test_block_step_not_found(self, step_manager, mock_journey):
        """Test blocking non-existent step"""
        result = step_manager.block_step(mock_journey, "nonexistent", reason="Test")
        assert result is False

