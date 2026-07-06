from backend.services.journey.journey_builder import JourneyBuilderService
from backend.services.journey.step_manager import StepManagerService
from backend.services.misc.client_journey_orchestrator import JourneyStatus, StepStatus


def make_journey():
    return JourneyBuilderService().build_custom_journey(
        journey_id="j-1",
        journey_type="custom",
        client_id="c-1",
        title="Custom",
        description="Custom",
        steps=[
            {"step_id": "one", "title": "One"},
            {"step_id": "two", "title": "Two"},
        ],
    )


def test_start_step_marks_step_and_journey_in_progress() -> None:
    journey = make_journey()
    manager = StepManagerService()

    assert manager.start_step(journey, "one") is True
    assert journey.steps[0].status == StepStatus.IN_PROGRESS
    assert journey.steps[0].started_at is not None
    assert journey.status == JourneyStatus.IN_PROGRESS
    assert journey.started_at is not None


def test_start_step_rejects_completed_or_missing_step() -> None:
    journey = make_journey()
    manager = StepManagerService()
    manager.complete_step(journey, "one")

    assert manager.start_step(journey, "one") is False
    assert manager.start_step(journey, "missing") is False


def test_complete_step_adds_notes_and_completes_journey_when_all_steps_done() -> None:
    journey = make_journey()
    manager = StepManagerService()

    assert manager.complete_step(journey, "one", notes=["sent to client"]) is True
    assert journey.steps[0].status == StepStatus.COMPLETED
    assert journey.steps[0].notes == ["sent to client"]
    assert journey.status == JourneyStatus.NOT_STARTED

    assert manager.complete_step(journey, "two") is True
    assert journey.status == JourneyStatus.COMPLETED
    assert journey.completed_at is not None
    assert journey.actual_completion is not None


def test_complete_step_rejects_already_completed_or_missing_step() -> None:
    journey = make_journey()
    manager = StepManagerService()
    manager.complete_step(journey, "one")

    assert manager.complete_step(journey, "one") is False
    assert manager.complete_step(journey, "missing") is False


def test_block_step_sets_step_reason_and_journey_status() -> None:
    journey = make_journey()
    manager = StepManagerService()

    assert manager.block_step(journey, "two", "Missing passport") is True
    assert journey.steps[1].status == StepStatus.BLOCKED
    assert journey.steps[1].blocked_reason == "Missing passport"
    assert journey.status == JourneyStatus.BLOCKED
    assert manager.block_step(journey, "missing", "No step") is False
