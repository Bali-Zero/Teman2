from backend.services.journey.journey_builder import JourneyBuilderService
from backend.services.journey.progress_tracker import ProgressTrackerService
from backend.services.journey.step_manager import StepManagerService
from backend.services.misc.client_journey_orchestrator import StepStatus


def make_linear_journey():
    return JourneyBuilderService().build_custom_journey(
        journey_id="j-1",
        journey_type="custom",
        client_id="c-1",
        title="Custom",
        description="Custom",
        steps=[
            {"step_id": "one", "title": "One"},
            {"step_id": "two", "title": "Two", "prerequisites": ["one"]},
            {"step_id": "three", "title": "Three"},
        ],
    )


def test_get_next_steps_returns_pending_steps_with_met_prerequisites() -> None:
    journey = make_linear_journey()
    tracker = ProgressTrackerService()

    initial = tracker.get_next_steps(journey)

    assert [step.step_id for step in initial] == ["one", "three"]

    StepManagerService().complete_step(journey, "one")
    next_steps = tracker.get_next_steps(journey)

    assert [step.step_id for step in next_steps] == ["two", "three"]


def test_get_next_steps_skips_in_progress_completed_and_blocked() -> None:
    journey = make_linear_journey()
    manager = StepManagerService()
    manager.start_step(journey, "one")
    manager.block_step(journey, "three", "waiting")

    next_steps = ProgressTrackerService().get_next_steps(journey)

    assert next_steps == []


def test_get_progress_counts_statuses_and_percentage() -> None:
    journey = make_linear_journey()
    manager = StepManagerService()
    manager.complete_step(journey, "one")
    manager.start_step(journey, "two")
    journey.steps[2].status = StepStatus.BLOCKED

    progress = ProgressTrackerService().get_progress(journey)

    assert progress["total_steps"] == 3
    assert progress["completed"] == 1
    assert progress["in_progress"] == 1
    assert progress["blocked"] == 1
    assert progress["pending"] == 0
    assert progress["progress_percent"] == 33.3
