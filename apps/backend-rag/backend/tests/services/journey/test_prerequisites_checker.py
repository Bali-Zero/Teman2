from backend.services.journey.journey_builder import JourneyBuilderService
from backend.services.journey.prerequisites_checker import PrerequisitesCheckerService
from backend.services.journey.step_manager import StepManagerService


def test_check_prerequisites_reports_missing_incomplete_and_met_dependencies() -> None:
    journey = JourneyBuilderService().build_custom_journey(
        journey_id="j-1",
        journey_type="custom",
        client_id="c-1",
        title="Custom",
        description="Custom",
        steps=[
            {"step_id": "one", "title": "One"},
            {"step_id": "two", "title": "Two", "prerequisites": ["one", "ghost"]},
        ],
    )
    checker = PrerequisitesCheckerService()

    met, missing = checker.check_prerequisites(journey, "two")

    assert met is False
    assert "Prerequisite one (One) not completed" in missing
    assert "Prerequisite step ghost not found" in missing

    StepManagerService().complete_step(journey, "one")
    met, missing = checker.check_prerequisites(journey, "two")

    assert met is False
    assert missing == ["Prerequisite step ghost not found"]


def test_check_prerequisites_handles_unknown_step() -> None:
    journey = JourneyBuilderService().build_custom_journey(
        journey_id="j-1",
        journey_type="custom",
        client_id="c-1",
        title="Custom",
        description="Custom",
        steps=[],
    )

    met, missing = PrerequisitesCheckerService().check_prerequisites(journey, "missing")

    assert met is False
    assert missing == ["Step missing not found"]
