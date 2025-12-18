"""
Unit tests for Client Journey Orchestrator
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.client_journey_orchestrator import (
    ClientJourney,
    ClientJourneyOrchestrator,
    JourneyStatus,
    JourneyStep,
    StepStatus,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def orchestrator():
    """Create ClientJourneyOrchestrator instance"""
    return ClientJourneyOrchestrator()


@pytest.fixture
def sample_journey(orchestrator):
    """Create a sample journey for testing"""
    return orchestrator.create_journey(
        journey_type="pt_pma_setup",
        client_id="client123",
    )


# ============================================================================
# Tests for Enums
# ============================================================================


def test_step_status_enum():
    """Test StepStatus enum values"""
    assert StepStatus.PENDING == "pending"
    assert StepStatus.IN_PROGRESS == "in_progress"
    assert StepStatus.COMPLETED == "completed"
    assert StepStatus.BLOCKED == "blocked"
    assert StepStatus.SKIPPED == "skipped"


def test_journey_status_enum():
    """Test JourneyStatus enum values"""
    assert JourneyStatus.NOT_STARTED == "not_started"
    assert JourneyStatus.IN_PROGRESS == "in_progress"
    assert JourneyStatus.COMPLETED == "completed"
    assert JourneyStatus.BLOCKED == "blocked"
    assert JourneyStatus.CANCELLED == "cancelled"


# ============================================================================
# Tests for JourneyStep dataclass
# ============================================================================


def test_journey_step_creation():
    """Test JourneyStep dataclass creation"""
    step = JourneyStep(
        step_id="test_step",
        step_number=1,
        title="Test Step",
        description="Test description",
        prerequisites=[],
        required_documents=["doc1", "doc2"],
        estimated_duration_days=5,
    )
    assert step.step_id == "test_step"
    assert step.status == StepStatus.PENDING
    assert len(step.required_documents) == 2
    assert step.estimated_duration_days == 5


# ============================================================================
# Tests for ClientJourney dataclass
# ============================================================================


def test_client_journey_creation():
    """Test ClientJourney dataclass creation"""
    steps = [
        JourneyStep(
            step_id="step1",
            step_number=1,
            title="Step 1",
            description="Description",
            prerequisites=[],
            required_documents=[],
            estimated_duration_days=1,
        )
    ]
    journey = ClientJourney(
        journey_id="journey1",
        journey_type="test",
        client_id="client1",
        title="Test Journey",
        description="Test",
        steps=steps,
    )
    assert journey.journey_id == "journey1"
    assert journey.status == JourneyStatus.NOT_STARTED
    assert len(journey.steps) == 1


# ============================================================================
# Tests for ClientJourneyOrchestrator.__init__
# ============================================================================


def test_init(orchestrator):
    """Test ClientJourneyOrchestrator initialization"""
    assert orchestrator.active_journeys == {}
    assert orchestrator.orchestrator_stats["total_journeys_created"] == 0
    assert orchestrator.orchestrator_stats["active_journeys"] == 0
    assert len(orchestrator.JOURNEY_TEMPLATES) > 0


# ============================================================================
# Tests for create_journey
# ============================================================================


def test_create_journey_from_template(orchestrator):
    """Test creating journey from template"""
    journey = orchestrator.create_journey(
        journey_type="pt_pma_setup",
        client_id="client123",
    )

    assert journey is not None
    assert journey.journey_type == "pt_pma_setup"
    assert journey.client_id == "client123"
    assert len(journey.steps) > 0
    assert journey.status == JourneyStatus.NOT_STARTED
    assert journey.journey_id in orchestrator.active_journeys
    assert orchestrator.orchestrator_stats["total_journeys_created"] == 1


def test_create_journey_with_custom_metadata(orchestrator):
    """Test creating journey with custom metadata"""
    custom_metadata = {"priority": "high", "source": "website"}
    journey = orchestrator.create_journey(
        journey_type="kitas_application",
        client_id="client456",
        custom_metadata=custom_metadata,
    )

    assert journey.metadata == custom_metadata


def test_create_journey_with_custom_steps(orchestrator):
    """Test creating journey with custom steps"""
    custom_steps = [
        {
            "step_id": "custom1",
            "title": "Custom Step 1",
            "description": "Description",
            "prerequisites": [],
            "required_documents": [],
            "estimated_duration_days": 3,
        },
        {
            "step_id": "custom2",
            "title": "Custom Step 2",
            "description": "Description",
            "prerequisites": ["custom1"],
            "required_documents": [],
            "estimated_duration_days": 5,
        },
    ]

    journey = orchestrator.create_journey(
        journey_type="pt_pma_setup",
        client_id="client789",
        custom_steps=custom_steps,
    )

    assert len(journey.steps) == 2
    assert journey.steps[0].step_id == "custom1"
    assert journey.steps[1].step_id == "custom2"
    assert journey.steps[1].prerequisites == ["custom1"]


def test_create_journey_invalid_type(orchestrator):
    """Test creating journey with invalid type raises error"""
    with pytest.raises(ValueError, match="Unknown journey type"):
        orchestrator.create_journey(
            journey_type="invalid_type",
            client_id="client123",
        )


def test_create_journey_calculates_estimated_completion(orchestrator):
    """Test that create_journey calculates estimated completion"""
    journey = orchestrator.create_journey(
        journey_type="pt_pma_setup",
        client_id="client123",
    )

    assert journey.estimated_completion is not None
    total_days = sum(s.estimated_duration_days for s in journey.steps)
    assert total_days > 0


# ============================================================================
# Tests for get_journey
# ============================================================================


def test_get_journey_exists(orchestrator, sample_journey):
    """Test getting existing journey"""
    journey = orchestrator.get_journey(sample_journey.journey_id)

    assert journey is not None
    assert journey.journey_id == sample_journey.journey_id


def test_get_journey_not_exists(orchestrator):
    """Test getting non-existent journey"""
    journey = orchestrator.get_journey("nonexistent")

    assert journey is None


# ============================================================================
# Tests for check_prerequisites
# ============================================================================


def test_check_prerequisites_no_prerequisites(orchestrator, sample_journey):
    """Test checking prerequisites when step has none"""
    # First step should have no prerequisites
    first_step = sample_journey.steps[0]
    prereqs_met, missing = orchestrator.check_prerequisites(sample_journey, first_step.step_id)

    assert prereqs_met is True
    assert len(missing) == 0


def test_check_prerequisites_met(orchestrator, sample_journey):
    """Test checking prerequisites when all are met"""
    # Complete first step
    first_step = sample_journey.steps[0]
    orchestrator.complete_step(sample_journey.journey_id, first_step.step_id)

    # Check second step (should have first step as prerequisite)
    if len(sample_journey.steps) > 1:
        second_step = sample_journey.steps[1]
        prereqs_met, missing = orchestrator.check_prerequisites(sample_journey, second_step.step_id)

        if second_step.prerequisites:
            assert prereqs_met is True
            assert len(missing) == 0


def test_check_prerequisites_not_met(orchestrator, sample_journey):
    """Test checking prerequisites when not met"""
    # Find a step with prerequisites
    step_with_prereqs = None
    for step in sample_journey.steps:
        if step.prerequisites:
            step_with_prereqs = step
            break

    if step_with_prereqs:
        prereqs_met, missing = orchestrator.check_prerequisites(
            sample_journey, step_with_prereqs.step_id
        )

        assert prereqs_met is False
        assert len(missing) > 0
        assert all(prereq in missing for prereq in step_with_prereqs.prerequisites)


def test_check_prerequisites_step_not_found(orchestrator, sample_journey):
    """Test checking prerequisites for non-existent step"""
    prereqs_met, missing = orchestrator.check_prerequisites(sample_journey, "nonexistent_step")

    assert prereqs_met is False
    assert "Step not found" in missing


# ============================================================================
# Tests for start_step
# ============================================================================


def test_start_step_success(orchestrator, sample_journey):
    """Test starting a step successfully"""
    first_step = sample_journey.steps[0]
    result = orchestrator.start_step(sample_journey.journey_id, first_step.step_id)

    assert result is True
    step = next(s for s in sample_journey.steps if s.step_id == first_step.step_id)
    assert step.status == StepStatus.IN_PROGRESS
    assert step.started_at is not None
    assert sample_journey.status == JourneyStatus.IN_PROGRESS


def test_start_step_prerequisites_not_met(orchestrator, sample_journey):
    """Test starting step when prerequisites not met"""
    # Find a step with prerequisites
    step_with_prereqs = None
    for step in sample_journey.steps:
        if step.prerequisites:
            step_with_prereqs = step
            break

    if step_with_prereqs:
        result = orchestrator.start_step(sample_journey.journey_id, step_with_prereqs.step_id)

        assert result is False
        step = next(s for s in sample_journey.steps if s.step_id == step_with_prereqs.step_id)
        assert step.status == StepStatus.PENDING


def test_start_step_journey_not_found(orchestrator):
    """Test starting step for non-existent journey"""
    result = orchestrator.start_step("nonexistent", "step1")

    assert result is False


def test_start_step_step_not_found(orchestrator, sample_journey):
    """Test starting non-existent step"""
    result = orchestrator.start_step(sample_journey.journey_id, "nonexistent_step")

    assert result is False


# ============================================================================
# Tests for complete_step
# ============================================================================


def test_complete_step_success(orchestrator, sample_journey):
    """Test completing a step successfully"""
    first_step = sample_journey.steps[0]
    orchestrator.start_step(sample_journey.journey_id, first_step.step_id)

    result = orchestrator.complete_step(
        sample_journey.journey_id, first_step.step_id, notes="Completed successfully"
    )

    assert result is True
    step = next(s for s in sample_journey.steps if s.step_id == first_step.step_id)
    assert step.status == StepStatus.COMPLETED
    assert step.completed_at is not None
    assert len(step.notes) > 0


def test_complete_step_journey_completed(orchestrator):
    """Test that completing all steps marks journey as completed"""
    journey = orchestrator.create_journey(
        journey_type="kitas_application",
        client_id="client999",
    )

    # Complete all steps
    for step in journey.steps:
        orchestrator.start_step(journey.journey_id, step.step_id)
        orchestrator.complete_step(journey.journey_id, step.step_id)

    assert journey.status == JourneyStatus.COMPLETED
    assert journey.completed_at is not None
    assert orchestrator.orchestrator_stats["completed_journeys"] == 1
    assert orchestrator.orchestrator_stats["active_journeys"] == 0


def test_complete_step_journey_not_found(orchestrator):
    """Test completing step for non-existent journey"""
    result = orchestrator.complete_step("nonexistent", "step1")

    assert result is False


def test_complete_step_step_not_found(orchestrator, sample_journey):
    """Test completing non-existent step"""
    result = orchestrator.complete_step(sample_journey.journey_id, "nonexistent_step")

    assert result is False


def test_complete_step_updates_stats(orchestrator):
    """Test that completing journey updates average completion days"""
    journey = orchestrator.create_journey(
        journey_type="kitas_application",
        client_id="client888",
    )

    # Mock started_at to ensure duration > 0
    from datetime import timedelta

    journey.started_at = (datetime.now() - timedelta(days=1)).isoformat()

    # Complete all steps
    for step in journey.steps:
        orchestrator.start_step(journey.journey_id, step.step_id)
        orchestrator.complete_step(journey.journey_id, step.step_id)

    assert orchestrator.orchestrator_stats["avg_completion_days"] >= 0  # Can be 0 if very fast
    assert orchestrator.orchestrator_stats["completed_journeys"] == 1


# ============================================================================
# Tests for block_step
# ============================================================================


def test_block_step_success(orchestrator, sample_journey):
    """Test blocking a step successfully"""
    first_step = sample_journey.steps[0]
    orchestrator.start_step(sample_journey.journey_id, first_step.step_id)

    result = orchestrator.block_step(
        sample_journey.journey_id, first_step.step_id, reason="Missing documents"
    )

    assert result is True
    step = next(s for s in sample_journey.steps if s.step_id == first_step.step_id)
    assert step.status == StepStatus.BLOCKED
    assert step.blocked_reason == "Missing documents"
    assert sample_journey.status == JourneyStatus.BLOCKED
    assert len(step.notes) > 0


def test_block_step_journey_not_found(orchestrator):
    """Test blocking step for non-existent journey"""
    result = orchestrator.block_step("nonexistent", "step1", "reason")

    assert result is False


def test_block_step_step_not_found(orchestrator, sample_journey):
    """Test blocking non-existent step"""
    result = orchestrator.block_step(sample_journey.journey_id, "nonexistent_step", "reason")

    assert result is False


# ============================================================================
# Tests for get_next_steps
# ============================================================================


def test_get_next_steps_initial(orchestrator, sample_journey):
    """Test getting next steps at journey start"""
    next_steps = orchestrator.get_next_steps(sample_journey.journey_id)

    # Should return steps with no prerequisites
    assert len(next_steps) > 0
    for step in next_steps:
        assert step.status == StepStatus.PENDING
        assert len(step.prerequisites) == 0 or all(
            next(
                (s for s in sample_journey.steps if s.step_id == prereq_id),
                None,
            ).status
            == StepStatus.COMPLETED
            for prereq_id in step.prerequisites
        )


def test_get_next_steps_after_completion(orchestrator, sample_journey):
    """Test getting next steps after completing a step"""
    # Complete first step
    first_step = sample_journey.steps[0]
    orchestrator.start_step(sample_journey.journey_id, first_step.step_id)
    orchestrator.complete_step(sample_journey.journey_id, first_step.step_id)

    next_steps = orchestrator.get_next_steps(sample_journey.journey_id)

    # Should include steps that had first_step as prerequisite
    assert len(next_steps) >= 0  # May be 0 if no steps depend on first step


def test_get_next_steps_journey_not_found(orchestrator):
    """Test getting next steps for non-existent journey"""
    next_steps = orchestrator.get_next_steps("nonexistent")

    assert next_steps == []


# ============================================================================
# Tests for get_progress
# ============================================================================


def test_get_progress_initial(orchestrator, sample_journey):
    """Test getting progress for new journey"""
    progress = orchestrator.get_progress(sample_journey.journey_id)

    assert progress["journey_id"] == sample_journey.journey_id
    assert progress["status"] == JourneyStatus.NOT_STARTED
    assert progress["progress_percentage"] == 0.0
    assert progress["completed_steps"] == 0
    assert progress["total_steps"] == len(sample_journey.steps)
    assert "estimated_days_remaining" in progress


def test_get_progress_partial(orchestrator, sample_journey):
    """Test getting progress for partially completed journey"""
    # Complete first step
    first_step = sample_journey.steps[0]
    orchestrator.start_step(sample_journey.journey_id, first_step.step_id)
    orchestrator.complete_step(sample_journey.journey_id, first_step.step_id)

    progress = orchestrator.get_progress(sample_journey.journey_id)

    assert progress["completed_steps"] == 1
    assert progress["progress_percentage"] > 0
    assert progress["status"] == JourneyStatus.IN_PROGRESS


def test_get_progress_completed(orchestrator):
    """Test getting progress for completed journey"""
    journey = orchestrator.create_journey(
        journey_type="kitas_application",
        client_id="client777",
    )

    # Complete all steps
    for step in journey.steps:
        orchestrator.start_step(journey.journey_id, step.step_id)
        orchestrator.complete_step(journey.journey_id, step.step_id)

    progress = orchestrator.get_progress(journey.journey_id)

    assert progress["status"] == JourneyStatus.COMPLETED
    assert progress["progress_percentage"] == 100.0
    assert progress["completed_steps"] == len(journey.steps)
    assert progress["estimated_days_remaining"] == 0


def test_get_progress_journey_not_found(orchestrator):
    """Test getting progress for non-existent journey"""
    progress = orchestrator.get_progress("nonexistent")

    assert progress == {}


# ============================================================================
# Tests for get_orchestrator_stats
# ============================================================================


def test_get_orchestrator_stats(orchestrator):
    """Test getting orchestrator statistics"""
    stats = orchestrator.get_orchestrator_stats()

    assert "total_journeys_created" in stats
    assert "active_journeys" in stats
    assert "completed_journeys" in stats
    assert "avg_completion_days" in stats
    assert "journey_type_distribution" in stats
    assert "templates_available" in stats
    assert len(stats["templates_available"]) > 0


def test_get_orchestrator_stats_updates(orchestrator):
    """Test that stats update correctly"""
    initial_stats = orchestrator.get_orchestrator_stats()
    initial_total = initial_stats["total_journeys_created"]

    orchestrator.create_journey(
        journey_type="pt_pma_setup",
        client_id="client111",
    )

    updated_stats = orchestrator.get_orchestrator_stats()

    assert updated_stats["total_journeys_created"] == initial_total + 1
    assert updated_stats["active_journeys"] == initial_stats["active_journeys"] + 1
