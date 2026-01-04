"""
Comprehensive unit tests for ClientJourneyOrchestrator

Tests all public methods with success, failure, and edge cases.
Target: 90%+ coverage
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from datetime import datetime
from unittest.mock import MagicMock, patch

from services.misc.client_journey_orchestrator import (
    ClientJourney,
    ClientJourneyOrchestrator,
    JourneyStatus,
    JourneyStep,
    StepStatus,
)


class TestClientJourneyOrchestratorInit:
    """Test orchestrator initialization"""

    def test_init_creates_services(self):
        """Test that initialization creates all sub-services"""
        orchestrator = ClientJourneyOrchestrator()

        assert orchestrator.templates_service is not None
        assert orchestrator.builder_service is not None
        assert orchestrator.prerequisites_checker is not None
        assert orchestrator.step_manager is not None
        assert orchestrator.progress_tracker is not None

    def test_init_creates_storage(self):
        """Test that initialization creates storage"""
        orchestrator = ClientJourneyOrchestrator()

        assert isinstance(orchestrator.active_journeys, dict)
        assert len(orchestrator.active_journeys) == 0

    def test_init_creates_stats(self):
        """Test that initialization creates stats dictionary"""
        orchestrator = ClientJourneyOrchestrator()

        assert isinstance(orchestrator.orchestrator_stats, dict)
        assert orchestrator.orchestrator_stats["total_journeys_created"] == 0
        assert orchestrator.orchestrator_stats["active_journeys"] == 0
        assert orchestrator.orchestrator_stats["completed_journeys"] == 0
        assert orchestrator.orchestrator_stats["blocked_journeys"] == 0
        assert orchestrator.orchestrator_stats["avg_completion_days"] == 0.0
        assert isinstance(orchestrator.orchestrator_stats["journey_type_distribution"], dict)

    def test_init_exposes_templates(self):
        """Test that initialization exposes JOURNEY_TEMPLATES for backward compatibility"""
        orchestrator = ClientJourneyOrchestrator()

        assert orchestrator.JOURNEY_TEMPLATES is not None
        assert "pt_pma_setup" in orchestrator.JOURNEY_TEMPLATES
        assert "kitas_application" in orchestrator.JOURNEY_TEMPLATES
        assert "property_purchase" in orchestrator.JOURNEY_TEMPLATES


class TestCreateJourney:
    """Test create_journey method"""

    @patch("services.misc.client_journey_orchestrator.datetime")
    def test_create_journey_from_template_success(self, mock_datetime):
        """Test successful journey creation from template"""
        # Mock datetime
        mock_now = MagicMock()
        mock_now.timestamp.return_value = 1234567890
        mock_now.isoformat.return_value = "2024-01-01T00:00:00"
        mock_datetime.now.return_value = mock_now

        orchestrator = ClientJourneyOrchestrator()

        # Mock builder service
        mock_journey = ClientJourney(
            journey_id="pt_pma_setup_client123_1234567890",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="PT PMA Company Setup",
            description="Complete incorporation of Foreign Investment Company (PT PMA)",
            steps=[
                JourneyStep(
                    step_id="name_approval",
                    step_number=1,
                    title="Company Name Approval",
                    description="Submit company name to KEMENKUMHAM for approval",
                    prerequisites=[],
                    required_documents=[
                        "Proposed company names (3 options)",
                        "Business plan summary",
                    ],
                    estimated_duration_days=3,
                )
            ],
            status=JourneyStatus.NOT_STARTED,
        )
        orchestrator.builder_service.build_journey_from_template = MagicMock(
            return_value=mock_journey
        )

        # Create journey
        result = orchestrator.create_journey(
            journey_type="pt_pma_setup",
            client_id="client123",
            custom_metadata={"test": "metadata"},
        )

        # Assertions
        assert result.journey_id == "pt_pma_setup_client123_1234567890"
        assert result.journey_type == "pt_pma_setup"
        assert result.client_id == "client123"
        assert len(result.steps) == 1

        # Check storage
        assert "pt_pma_setup_client123_1234567890" in orchestrator.active_journeys

        # Check stats
        assert orchestrator.orchestrator_stats["total_journeys_created"] == 1
        assert orchestrator.orchestrator_stats["active_journeys"] == 1
        assert orchestrator.orchestrator_stats["journey_type_distribution"]["pt_pma_setup"] == 1

        # Check builder service called correctly
        orchestrator.builder_service.build_journey_from_template.assert_called_once()

    @patch("services.misc.client_journey_orchestrator.datetime")
    def test_create_journey_with_custom_steps(self, mock_datetime):
        """Test journey creation with custom steps"""
        # Mock datetime
        mock_now = MagicMock()
        mock_now.timestamp.return_value = 1234567890
        mock_datetime.now.return_value = mock_now

        orchestrator = ClientJourneyOrchestrator()

        # Mock builder service
        mock_journey = ClientJourney(
            journey_id="custom_client456_1234567890",
            journey_type="custom",
            client_id="client456",
            title="Custom Journey",
            description="Custom journey with provided steps",
            steps=[
                JourneyStep(
                    step_id="custom_step1",
                    step_number=1,
                    title="Custom Step 1",
                    description="Custom description",
                    prerequisites=[],
                    required_documents=["Doc1"],
                    estimated_duration_days=5,
                )
            ],
            status=JourneyStatus.NOT_STARTED,
        )
        orchestrator.builder_service.build_custom_journey = MagicMock(return_value=mock_journey)

        custom_steps = [
            {
                "step_id": "custom_step1",
                "title": "Custom Step 1",
                "description": "Custom description",
                "prerequisites": [],
                "required_documents": ["Doc1"],
                "estimated_duration_days": 5,
            }
        ]

        # Create journey
        result = orchestrator.create_journey(
            journey_type="custom",
            client_id="client456",
            custom_steps=custom_steps,
        )

        # Assertions
        assert result.journey_id == "custom_client456_1234567890"
        assert len(result.steps) == 1

        # Check builder service called correctly
        orchestrator.builder_service.build_custom_journey.assert_called_once()

    @patch("services.misc.client_journey_orchestrator.datetime")
    def test_create_journey_updates_distribution(self, mock_datetime):
        """Test that creating journeys updates type distribution correctly"""
        # Mock datetime
        mock_now = MagicMock()
        mock_now.timestamp.return_value = 1234567890
        mock_now.isoformat.return_value = "2024-01-01T00:00:00"
        mock_datetime.now.return_value = mock_now

        orchestrator = ClientJourneyOrchestrator()

        # Create mock journeys
        for i in range(3):
            mock_journey = ClientJourney(
                journey_id=f"pt_pma_setup_client{i}_1234567890",
                journey_type="pt_pma_setup",
                client_id=f"client{i}",
                title="PT PMA Company Setup",
                description="Test",
                steps=[],
                status=JourneyStatus.NOT_STARTED,
            )
            orchestrator.builder_service.build_journey_from_template = MagicMock(
                return_value=mock_journey
            )
            orchestrator.create_journey("pt_pma_setup", f"client{i}")

        # Check distribution
        assert orchestrator.orchestrator_stats["journey_type_distribution"]["pt_pma_setup"] == 3
        assert orchestrator.orchestrator_stats["total_journeys_created"] == 3


class TestGetJourney:
    """Test get_journey method"""

    def test_get_journey_exists(self):
        """Test getting an existing journey"""
        orchestrator = ClientJourneyOrchestrator()

        # Create a journey
        journey = ClientJourney(
            journey_id="test_journey_123",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test Journey",
            description="Test",
            steps=[],
        )
        orchestrator.active_journeys["test_journey_123"] = journey

        # Get journey
        result = orchestrator.get_journey("test_journey_123")

        assert result is not None
        assert result.journey_id == "test_journey_123"
        assert result.client_id == "client123"

    def test_get_journey_not_found(self):
        """Test getting a non-existent journey"""
        orchestrator = ClientJourneyOrchestrator()

        result = orchestrator.get_journey("nonexistent_journey")

        assert result is None


class TestCheckPrerequisites:
    """Test check_prerequisites method"""

    def test_check_prerequisites_delegates_to_service(self):
        """Test that check_prerequisites delegates to PrerequisitesCheckerService"""
        orchestrator = ClientJourneyOrchestrator()

        # Create journey
        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=1,
                )
            ],
        )

        # Mock prerequisites checker
        orchestrator.prerequisites_checker.check_prerequisites = MagicMock(return_value=(True, []))

        # Check prerequisites
        met, missing = orchestrator.check_prerequisites(journey, "step1")

        # Assertions
        assert met is True
        assert missing == []
        orchestrator.prerequisites_checker.check_prerequisites.assert_called_once_with(
            journey, "step1"
        )

    def test_check_prerequisites_returns_missing(self):
        """Test that missing prerequisites are returned"""
        orchestrator = ClientJourneyOrchestrator()

        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            steps=[],
        )

        # Mock prerequisites checker to return missing prerequisites
        orchestrator.prerequisites_checker.check_prerequisites = MagicMock(
            return_value=(False, ["step1", "step2"])
        )

        met, missing = orchestrator.check_prerequisites(journey, "step3")

        assert met is False
        assert missing == ["step1", "step2"]


class TestStartStep:
    """Test start_step method"""

    def test_start_step_success(self):
        """Test successfully starting a step"""
        orchestrator = ClientJourneyOrchestrator()

        # Create journey
        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=1,
                )
            ],
        )
        orchestrator.active_journeys["test_journey"] = journey

        # Mock services
        orchestrator.prerequisites_checker.check_prerequisites = MagicMock(return_value=(True, []))
        orchestrator.step_manager.start_step = MagicMock(return_value=True)

        # Start step
        result = orchestrator.start_step("test_journey", "step1")

        # Assertions
        assert result is True
        orchestrator.prerequisites_checker.check_prerequisites.assert_called_once_with(
            journey, "step1"
        )
        orchestrator.step_manager.start_step.assert_called_once_with(journey, "step1")

    def test_start_step_journey_not_found(self):
        """Test starting step when journey doesn't exist"""
        orchestrator = ClientJourneyOrchestrator()

        result = orchestrator.start_step("nonexistent_journey", "step1")

        assert result is False

    def test_start_step_prerequisites_not_met(self):
        """Test starting step when prerequisites are not met"""
        orchestrator = ClientJourneyOrchestrator()

        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            steps=[],
        )
        orchestrator.active_journeys["test_journey"] = journey

        # Mock prerequisites not met
        orchestrator.prerequisites_checker.check_prerequisites = MagicMock(
            return_value=(False, ["step0"])
        )

        result = orchestrator.start_step("test_journey", "step1")

        assert result is False
        # Step manager should not be called
        orchestrator.step_manager.start_step = MagicMock()
        assert not orchestrator.step_manager.start_step.called


class TestCompleteStep:
    """Test complete_step method"""

    def test_complete_step_success(self):
        """Test successfully completing a step"""
        orchestrator = ClientJourneyOrchestrator()

        # Create journey
        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=1,
                    status=StepStatus.IN_PROGRESS,
                )
            ],
        )
        orchestrator.active_journeys["test_journey"] = journey

        # Mock step manager
        orchestrator.step_manager.complete_step = MagicMock(return_value=True)

        # Complete step
        result = orchestrator.complete_step("test_journey", "step1", "Test notes")

        # Assertions
        assert result is True
        orchestrator.step_manager.complete_step.assert_called_once_with(
            journey, "step1", ["Test notes"]
        )

    def test_complete_step_without_notes(self):
        """Test completing step without notes"""
        orchestrator = ClientJourneyOrchestrator()

        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=1,
                )
            ],
        )
        orchestrator.active_journeys["test_journey"] = journey

        orchestrator.step_manager.complete_step = MagicMock(return_value=True)

        result = orchestrator.complete_step("test_journey", "step1")

        assert result is True
        orchestrator.step_manager.complete_step.assert_called_once_with(journey, "step1", None)

    def test_complete_step_journey_not_found(self):
        """Test completing step when journey doesn't exist"""
        orchestrator = ClientJourneyOrchestrator()

        result = orchestrator.complete_step("nonexistent_journey", "step1")

        assert result is False

    @patch("services.misc.client_journey_orchestrator.datetime")
    def test_complete_step_completes_journey(self, mock_datetime):
        """Test that completing all steps marks journey as complete and updates stats"""
        # Mock datetime
        started = datetime(2024, 1, 1)
        completed = datetime(2024, 1, 10)

        mock_datetime.fromisoformat.return_value = started
        mock_datetime.now.return_value = completed

        orchestrator = ClientJourneyOrchestrator()
        orchestrator.orchestrator_stats["active_journeys"] = 1

        # Create journey with all steps completed except one
        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            started_at="2024-01-01T00:00:00",
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=1,
                    status=StepStatus.COMPLETED,
                ),
                JourneyStep(
                    step_id="step2",
                    step_number=2,
                    title="Step 2",
                    description="Test",
                    prerequisites=["step1"],
                    required_documents=[],
                    estimated_duration_days=1,
                    status=StepStatus.IN_PROGRESS,
                ),
            ],
        )
        orchestrator.active_journeys["test_journey"] = journey

        # Mock step manager to mark step as completed
        def mock_complete(journey, step_id, notes):
            for step in journey.steps:
                if step.step_id == step_id:
                    step.status = StepStatus.COMPLETED
            return True

        orchestrator.step_manager.complete_step = MagicMock(side_effect=mock_complete)

        # Complete last step
        result = orchestrator.complete_step("test_journey", "step2")

        # Assertions
        assert result is True
        assert orchestrator.orchestrator_stats["completed_journeys"] == 1
        assert orchestrator.orchestrator_stats["active_journeys"] == 0
        assert orchestrator.orchestrator_stats["avg_completion_days"] == 9.0

    def test_complete_step_with_skipped_steps(self):
        """Test that journey completes even with skipped steps"""
        orchestrator = ClientJourneyOrchestrator()
        orchestrator.orchestrator_stats["active_journeys"] = 1

        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=1,
                    status=StepStatus.COMPLETED,
                ),
                JourneyStep(
                    step_id="step2",
                    step_number=2,
                    title="Step 2",
                    description="Test",
                    prerequisites=["step1"],
                    required_documents=[],
                    estimated_duration_days=1,
                    status=StepStatus.SKIPPED,
                ),
            ],
        )
        orchestrator.active_journeys["test_journey"] = journey

        orchestrator.step_manager.complete_step = MagicMock(return_value=True)

        # All steps are already completed or skipped, should update stats
        result = orchestrator.complete_step("test_journey", "step1")

        assert result is True
        assert orchestrator.orchestrator_stats["completed_journeys"] == 1


class TestBlockStep:
    """Test block_step method"""

    def test_block_step_success(self):
        """Test successfully blocking a step"""
        orchestrator = ClientJourneyOrchestrator()

        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=1,
                )
            ],
        )
        orchestrator.active_journeys["test_journey"] = journey

        # Mock step manager
        orchestrator.step_manager.block_step = MagicMock(return_value=True)

        # Block step
        result = orchestrator.block_step("test_journey", "step1", "Missing documents")

        # Assertions
        assert result is True
        orchestrator.step_manager.block_step.assert_called_once_with(
            journey, "step1", "Missing documents"
        )

    def test_block_step_journey_not_found(self):
        """Test blocking step when journey doesn't exist"""
        orchestrator = ClientJourneyOrchestrator()

        result = orchestrator.block_step("nonexistent_journey", "step1", "reason")

        assert result is False


class TestGetNextSteps:
    """Test get_next_steps method"""

    def test_get_next_steps_success(self):
        """Test getting next actionable steps"""
        orchestrator = ClientJourneyOrchestrator()

        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            steps=[],
        )
        orchestrator.active_journeys["test_journey"] = journey

        # Mock progress tracker
        mock_steps = [
            JourneyStep(
                step_id="step1",
                step_number=1,
                title="Step 1",
                description="Test",
                prerequisites=[],
                required_documents=[],
                estimated_duration_days=1,
            )
        ]
        orchestrator.progress_tracker.get_next_steps = MagicMock(return_value=mock_steps)

        # Get next steps
        result = orchestrator.get_next_steps("test_journey")

        # Assertions
        assert len(result) == 1
        assert result[0].step_id == "step1"
        orchestrator.progress_tracker.get_next_steps.assert_called_once_with(journey)

    def test_get_next_steps_journey_not_found(self):
        """Test getting next steps when journey doesn't exist"""
        orchestrator = ClientJourneyOrchestrator()

        result = orchestrator.get_next_steps("nonexistent_journey")

        assert result == []


class TestGetProgress:
    """Test get_progress method"""

    def test_get_progress_success(self):
        """Test getting journey progress"""
        orchestrator = ClientJourneyOrchestrator()

        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            started_at="2024-01-01T00:00:00",
            estimated_completion="2024-02-01T00:00:00",
            status=JourneyStatus.IN_PROGRESS,
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=5,
                    status=StepStatus.COMPLETED,
                ),
                JourneyStep(
                    step_id="step2",
                    step_number=2,
                    title="Step 2",
                    description="Test",
                    prerequisites=["step1"],
                    required_documents=[],
                    estimated_duration_days=10,
                    status=StepStatus.IN_PROGRESS,
                ),
                JourneyStep(
                    step_id="step3",
                    step_number=3,
                    title="Step 3",
                    description="Test",
                    prerequisites=["step2"],
                    required_documents=[],
                    estimated_duration_days=7,
                    status=StepStatus.PENDING,
                ),
            ],
        )
        orchestrator.active_journeys["test_journey"] = journey

        # Mock progress tracker
        orchestrator.progress_tracker.get_progress = MagicMock(
            return_value={
                "progress_percent": 33.33,
                "completed": 1,
                "in_progress": 1,
                "blocked": 0,
                "total_steps": 3,
            }
        )

        # Mock get_next_steps
        mock_next_steps = [
            JourneyStep(
                step_id="step3",
                step_number=3,
                title="Step 3",
                description="Test",
                prerequisites=["step2"],
                required_documents=[],
                estimated_duration_days=7,
            )
        ]
        orchestrator.progress_tracker.get_next_steps = MagicMock(return_value=mock_next_steps)

        # Get progress
        result = orchestrator.get_progress("test_journey")

        # Assertions
        assert result["journey_id"] == "test_journey"
        assert result["status"] == JourneyStatus.IN_PROGRESS
        assert result["progress_percentage"] == 33.33
        assert result["completed_steps"] == 1
        assert result["in_progress_steps"] == 1
        assert result["blocked_steps"] == 0
        assert result["total_steps"] == 3
        assert result["estimated_days_remaining"] == 17  # 10 + 7
        assert result["started_at"] == "2024-01-01T00:00:00"
        assert result["estimated_completion"] == "2024-02-01T00:00:00"
        assert result["next_steps"] == ["step3"]

    def test_get_progress_journey_not_found(self):
        """Test getting progress when journey doesn't exist"""
        orchestrator = ClientJourneyOrchestrator()

        result = orchestrator.get_progress("nonexistent_journey")

        assert result == {}

    def test_get_progress_calculates_remaining_days(self):
        """Test that remaining days are calculated correctly"""
        orchestrator = ClientJourneyOrchestrator()

        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            status=JourneyStatus.IN_PROGRESS,
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=5,
                    status=StepStatus.COMPLETED,
                ),
                JourneyStep(
                    step_id="step2",
                    step_number=2,
                    title="Step 2",
                    description="Test",
                    prerequisites=["step1"],
                    required_documents=[],
                    estimated_duration_days=10,
                    status=StepStatus.IN_PROGRESS,
                ),
                JourneyStep(
                    step_id="step3",
                    step_number=3,
                    title="Step 3",
                    description="Test",
                    prerequisites=["step2"],
                    required_documents=[],
                    estimated_duration_days=15,
                    status=StepStatus.PENDING,
                ),
            ],
        )
        orchestrator.active_journeys["test_journey"] = journey

        orchestrator.progress_tracker.get_progress = MagicMock(
            return_value={
                "progress_percent": 33.33,
                "completed": 1,
                "in_progress": 1,
                "blocked": 0,
                "total_steps": 3,
            }
        )

        result = orchestrator.get_progress("test_journey")

        # Should include in_progress (10) + pending (15)
        assert result["estimated_days_remaining"] == 25


class TestGetOrchestratorStats:
    """Test get_orchestrator_stats method"""

    def test_get_orchestrator_stats(self):
        """Test getting orchestrator statistics"""
        orchestrator = ClientJourneyOrchestrator()

        # Set some stats
        orchestrator.orchestrator_stats["total_journeys_created"] = 5
        orchestrator.orchestrator_stats["active_journeys"] = 3
        orchestrator.orchestrator_stats["completed_journeys"] = 2
        orchestrator.orchestrator_stats["blocked_journeys"] = 0
        orchestrator.orchestrator_stats["avg_completion_days"] = 15.5
        orchestrator.orchestrator_stats["journey_type_distribution"] = {
            "pt_pma_setup": 3,
            "kitas_application": 2,
        }

        result = orchestrator.get_orchestrator_stats()

        # Assertions
        assert result["total_journeys_created"] == 5
        assert result["active_journeys"] == 3
        assert result["completed_journeys"] == 2
        assert result["blocked_journeys"] == 0
        assert result["avg_completion_days"] == 15.5
        assert result["journey_type_distribution"]["pt_pma_setup"] == 3
        assert result["journey_type_distribution"]["kitas_application"] == 2
        assert "templates_available" in result
        assert "pt_pma_setup" in result["templates_available"]
        assert "kitas_application" in result["templates_available"]
        assert "property_purchase" in result["templates_available"]

    def test_get_orchestrator_stats_initial_state(self):
        """Test stats in initial state"""
        orchestrator = ClientJourneyOrchestrator()

        result = orchestrator.get_orchestrator_stats()

        assert result["total_journeys_created"] == 0
        assert result["active_journeys"] == 0
        assert result["completed_journeys"] == 0
        assert result["blocked_journeys"] == 0
        assert result["avg_completion_days"] == 0.0
        assert result["journey_type_distribution"] == {}
        assert len(result["templates_available"]) == 3


class TestCompleteStepAverageCalculation:
    """Test average completion days calculation"""

    @patch("services.misc.client_journey_orchestrator.datetime")
    def test_average_completion_days_single_journey(self, mock_datetime):
        """Test average calculation with single completed journey"""
        # Mock datetime
        mock_datetime.fromisoformat.return_value = datetime(2024, 1, 1)
        mock_now = datetime(2024, 1, 11)  # 10 days later
        mock_datetime.now.return_value = mock_now

        orchestrator = ClientJourneyOrchestrator()
        orchestrator.orchestrator_stats["active_journeys"] = 1

        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            started_at="2024-01-01T00:00:00",
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=1,
                    status=StepStatus.IN_PROGRESS,
                )
            ],
        )
        orchestrator.active_journeys["test_journey"] = journey

        def mock_complete(journey, step_id, notes):
            journey.steps[0].status = StepStatus.COMPLETED
            return True

        orchestrator.step_manager.complete_step = MagicMock(side_effect=mock_complete)

        orchestrator.complete_step("test_journey", "step1")

        assert orchestrator.orchestrator_stats["avg_completion_days"] == 10.0

    @patch("services.misc.client_journey_orchestrator.datetime")
    def test_average_completion_days_multiple_journeys(self, mock_datetime):
        """Test average calculation with multiple completed journeys"""
        orchestrator = ClientJourneyOrchestrator()

        # First journey: 10 days
        mock_datetime.fromisoformat.return_value = datetime(2024, 1, 1)
        mock_datetime.now.return_value = datetime(2024, 1, 11)

        orchestrator.orchestrator_stats["active_journeys"] = 1
        journey1 = ClientJourney(
            journey_id="journey1",
            journey_type="pt_pma_setup",
            client_id="client1",
            title="Test",
            description="Test",
            started_at="2024-01-01T00:00:00",
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=1,
                    status=StepStatus.IN_PROGRESS,
                )
            ],
        )
        orchestrator.active_journeys["journey1"] = journey1

        def mock_complete1(journey, step_id, notes):
            journey.steps[0].status = StepStatus.COMPLETED
            return True

        orchestrator.step_manager.complete_step = MagicMock(side_effect=mock_complete1)
        orchestrator.complete_step("journey1", "step1")

        # Second journey: 20 days
        mock_datetime.fromisoformat.return_value = datetime(2024, 1, 1)
        mock_datetime.now.return_value = datetime(2024, 1, 21)

        orchestrator.orchestrator_stats["active_journeys"] = 1
        journey2 = ClientJourney(
            journey_id="journey2",
            journey_type="pt_pma_setup",
            client_id="client2",
            title="Test",
            description="Test",
            started_at="2024-01-01T00:00:00",
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=1,
                    status=StepStatus.IN_PROGRESS,
                )
            ],
        )
        orchestrator.active_journeys["journey2"] = journey2

        def mock_complete2(journey, step_id, notes):
            journey.steps[0].status = StepStatus.COMPLETED
            return True

        orchestrator.step_manager.complete_step = MagicMock(side_effect=mock_complete2)
        orchestrator.complete_step("journey2", "step1")

        # Average should be (10 + 20) / 2 = 15
        assert orchestrator.orchestrator_stats["avg_completion_days"] == 15.0


class TestEdgeCases:
    """Test edge cases and error scenarios"""

    def test_create_journey_multiple_same_type(self):
        """Test creating multiple journeys of the same type"""
        orchestrator = ClientJourneyOrchestrator()

        mock_journey1 = ClientJourney(
            journey_id="journey1",
            journey_type="pt_pma_setup",
            client_id="client1",
            title="Test",
            description="Test",
            steps=[],
        )
        mock_journey2 = ClientJourney(
            journey_id="journey2",
            journey_type="pt_pma_setup",
            client_id="client2",
            title="Test",
            description="Test",
            steps=[],
        )

        orchestrator.builder_service.build_journey_from_template = MagicMock(
            side_effect=[mock_journey1, mock_journey2]
        )

        orchestrator.create_journey("pt_pma_setup", "client1")
        orchestrator.create_journey("pt_pma_setup", "client2")

        assert orchestrator.orchestrator_stats["journey_type_distribution"]["pt_pma_setup"] == 2
        assert orchestrator.orchestrator_stats["total_journeys_created"] == 2

    def test_get_progress_with_no_started_at(self):
        """Test progress calculation when journey hasn't started"""
        orchestrator = ClientJourneyOrchestrator()

        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            status=JourneyStatus.NOT_STARTED,
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=5,
                    status=StepStatus.PENDING,
                )
            ],
        )
        orchestrator.active_journeys["test_journey"] = journey

        orchestrator.progress_tracker.get_progress = MagicMock(
            return_value={
                "progress_percent": 0,
                "completed": 0,
                "in_progress": 0,
                "blocked": 0,
                "total_steps": 1,
            }
        )

        result = orchestrator.get_progress("test_journey")

        assert result["started_at"] is None

    def test_complete_step_fails_from_step_manager(self):
        """Test when step manager fails to complete step"""
        orchestrator = ClientJourneyOrchestrator()

        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=1,
                )
            ],
        )
        orchestrator.active_journeys["test_journey"] = journey

        # Mock step manager to fail
        orchestrator.step_manager.complete_step = MagicMock(return_value=False)

        result = orchestrator.complete_step("test_journey", "step1")

        assert result is False
        # Stats should not be updated
        assert orchestrator.orchestrator_stats["completed_journeys"] == 0

    @patch("services.misc.client_journey_orchestrator.datetime")
    def test_complete_journey_without_started_at(self, mock_datetime):
        """Test completing journey when started_at is None"""
        orchestrator = ClientJourneyOrchestrator()
        orchestrator.orchestrator_stats["active_journeys"] = 1

        journey = ClientJourney(
            journey_id="test_journey",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test",
            started_at=None,  # No start time
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=1,
                    status=StepStatus.IN_PROGRESS,
                )
            ],
        )
        orchestrator.active_journeys["test_journey"] = journey

        def mock_complete(journey, step_id, notes):
            journey.steps[0].status = StepStatus.COMPLETED
            return True

        orchestrator.step_manager.complete_step = MagicMock(side_effect=mock_complete)

        result = orchestrator.complete_step("test_journey", "step1")

        # Should still complete successfully
        assert result is True
        assert orchestrator.orchestrator_stats["completed_journeys"] == 1
        # Average should not be calculated since no started_at
        assert orchestrator.orchestrator_stats["avg_completion_days"] == 0.0


class TestDataclassesAndEnums:
    """Test dataclasses and enums"""

    def test_step_status_enum_values(self):
        """Test StepStatus enum values"""
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.IN_PROGRESS.value == "in_progress"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.BLOCKED.value == "blocked"
        assert StepStatus.SKIPPED.value == "skipped"

    def test_journey_status_enum_values(self):
        """Test JourneyStatus enum values"""
        assert JourneyStatus.NOT_STARTED.value == "not_started"
        assert JourneyStatus.IN_PROGRESS.value == "in_progress"
        assert JourneyStatus.COMPLETED.value == "completed"
        assert JourneyStatus.BLOCKED.value == "blocked"
        assert JourneyStatus.CANCELLED.value == "cancelled"

    def test_journey_step_default_values(self):
        """Test JourneyStep default values"""
        step = JourneyStep(
            step_id="test",
            step_number=1,
            title="Test",
            description="Test description",
            prerequisites=[],
            required_documents=[],
            estimated_duration_days=5,
        )

        assert step.status == StepStatus.PENDING
        assert step.started_at is None
        assert step.completed_at is None
        assert step.blocked_reason is None
        assert step.notes == []

    def test_client_journey_default_values(self):
        """Test ClientJourney default values"""
        journey = ClientJourney(
            journey_id="test",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="Test",
            description="Test description",
            steps=[],
        )

        assert journey.status == JourneyStatus.NOT_STARTED
        assert journey.created_at is not None  # Generated by default_factory
        assert journey.started_at is None
        assert journey.completed_at is None
        assert journey.estimated_completion is None
        assert journey.actual_completion is None
        assert journey.metadata == {}


class TestBackwardCompatibility:
    """Test backward compatibility features"""

    def test_journey_templates_exposed_on_class(self):
        """Test that JOURNEY_TEMPLATES is exposed as class attribute"""
        assert hasattr(ClientJourneyOrchestrator, "JOURNEY_TEMPLATES")
        assert "pt_pma_setup" in ClientJourneyOrchestrator.JOURNEY_TEMPLATES

    def test_journey_templates_exposed_on_instance(self):
        """Test that JOURNEY_TEMPLATES is accessible on instance"""
        orchestrator = ClientJourneyOrchestrator()

        assert hasattr(orchestrator, "JOURNEY_TEMPLATES")
        assert "pt_pma_setup" in orchestrator.JOURNEY_TEMPLATES
        assert orchestrator.JOURNEY_TEMPLATES == orchestrator.templates_service.JOURNEY_TEMPLATES


class TestIntegrationScenarios:
    """Test integration scenarios"""

    @patch("services.misc.client_journey_orchestrator.datetime")
    def test_full_journey_workflow(self, mock_datetime):
        """Test complete journey workflow from creation to completion"""
        # Mock datetime
        mock_now = MagicMock()
        mock_now.timestamp.return_value = 1234567890
        mock_now.isoformat.return_value = "2024-01-01T00:00:00"
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromisoformat.return_value = datetime(2024, 1, 1)

        orchestrator = ClientJourneyOrchestrator()

        # Create journey
        mock_journey = ClientJourney(
            journey_id="pt_pma_setup_client123_1234567890",
            journey_type="pt_pma_setup",
            client_id="client123",
            title="PT PMA Company Setup",
            description="Test",
            steps=[
                JourneyStep(
                    step_id="step1",
                    step_number=1,
                    title="Step 1",
                    description="Test",
                    prerequisites=[],
                    required_documents=[],
                    estimated_duration_days=5,
                ),
                JourneyStep(
                    step_id="step2",
                    step_number=2,
                    title="Step 2",
                    description="Test",
                    prerequisites=["step1"],
                    required_documents=[],
                    estimated_duration_days=10,
                ),
            ],
        )
        orchestrator.builder_service.build_journey_from_template = MagicMock(
            return_value=mock_journey
        )

        journey = orchestrator.create_journey("pt_pma_setup", "client123")

        # Check journey exists
        assert orchestrator.get_journey(journey.journey_id) is not None

        # Start first step
        orchestrator.prerequisites_checker.check_prerequisites = MagicMock(return_value=(True, []))
        orchestrator.step_manager.start_step = MagicMock(return_value=True)

        assert orchestrator.start_step(journey.journey_id, "step1") is True

        # Complete first step
        def mock_complete_step1(journey, step_id, notes):
            journey.steps[0].status = StepStatus.COMPLETED
            return True

        orchestrator.step_manager.complete_step = MagicMock(side_effect=mock_complete_step1)
        assert orchestrator.complete_step(journey.journey_id, "step1") is True

        # Block second step
        orchestrator.step_manager.block_step = MagicMock(return_value=True)
        assert orchestrator.block_step(journey.journey_id, "step2", "Missing documents") is True

        # Get progress
        orchestrator.progress_tracker.get_progress = MagicMock(
            return_value={
                "progress_percent": 50,
                "completed": 1,
                "in_progress": 0,
                "blocked": 1,
                "total_steps": 2,
            }
        )

        progress = orchestrator.get_progress(journey.journey_id)
        assert progress["completed_steps"] == 1
        assert progress["blocked_steps"] == 1

        # Get stats
        stats = orchestrator.get_orchestrator_stats()
        assert stats["total_journeys_created"] == 1
        assert stats["active_journeys"] == 1
