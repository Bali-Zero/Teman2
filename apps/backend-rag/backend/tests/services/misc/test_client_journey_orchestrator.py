from __future__ import annotations

from backend.services.misc.client_journey_orchestrator import (
    ClientJourney,
    ClientJourneyOrchestrator,
    JourneyStatus,
    StepStatus,
)


def _custom_steps() -> list[dict]:
    return [
        {
            "step_id": "collect_docs",
            "title": "Collect Documents",
            "description": "Collect client identity and company documents.",
            "prerequisites": [],
            "required_documents": ["Passport", "NIB"],
            "estimated_duration_days": 2,
        },
        {
            "step_id": "submit_application",
            "title": "Submit Application",
            "description": "Submit the prepared application.",
            "prerequisites": ["collect_docs"],
            "required_documents": ["Signed application"],
            "estimated_duration_days": 3,
        },
    ]


def _journey() -> tuple[ClientJourneyOrchestrator, ClientJourney]:
    orchestrator = ClientJourneyOrchestrator()
    journey = orchestrator.create_journey(
        journey_type="custom_kitas",
        client_id="client-1",
        custom_metadata={"source": "test"},
        custom_steps=_custom_steps(),
    )
    return orchestrator, journey


def test_create_journey_from_template_stores_steps_and_updates_stats() -> None:
    orchestrator = ClientJourneyOrchestrator()

    journey = orchestrator.create_journey("pt_pma_setup", "client-1")

    assert journey.journey_id in orchestrator.active_journeys
    assert journey.client_id == "client-1"
    assert journey.title == "PT PMA Company Setup"
    assert journey.status == JourneyStatus.NOT_STARTED
    assert [step.step_id for step in journey.steps[:2]] == ["name_approval", "notary_deed"]
    assert journey.steps[1].prerequisites == ["name_approval"]
    assert orchestrator.get_orchestrator_stats()["total_journeys_created"] == 1
    assert orchestrator.get_orchestrator_stats()["journey_type_distribution"] == {
        "pt_pma_setup": 1,
    }


def test_start_step_requires_prerequisites_then_unlocks_next_step_after_completion() -> None:
    orchestrator, journey = _journey()

    prereqs_met, missing = orchestrator.check_prerequisites(journey, "submit_application")
    assert prereqs_met is False
    assert missing == ["Prerequisite collect_docs (Collect Documents) not completed"]
    assert orchestrator.start_step(journey.journey_id, "submit_application") is False

    assert orchestrator.start_step(journey.journey_id, "collect_docs") is True
    assert journey.status == JourneyStatus.IN_PROGRESS
    assert journey.steps[0].status == StepStatus.IN_PROGRESS
    assert journey.started_at is not None

    assert orchestrator.complete_step(journey.journey_id, "collect_docs", "Docs verified") is True
    assert journey.steps[0].status == StepStatus.COMPLETED
    assert journey.steps[0].notes == ["Docs verified"]
    assert orchestrator.check_prerequisites(journey, "submit_application") == (True, [])
    assert [step.step_id for step in orchestrator.get_next_steps(journey.journey_id)] == [
        "submit_application",
    ]


def test_block_step_marks_journey_blocked_and_progress_counts_blocked_step() -> None:
    orchestrator, journey = _journey()

    assert orchestrator.block_step(journey.journey_id, "collect_docs", "Missing passport") is True
    progress = orchestrator.get_progress(journey.journey_id)

    assert journey.status == JourneyStatus.BLOCKED
    assert journey.steps[0].status == StepStatus.BLOCKED
    assert journey.steps[0].blocked_reason == "Missing passport"
    assert progress["blocked_steps"] == 1
    assert progress["progress_percentage"] == 0.0
    assert progress["next_steps"] == []


def test_completing_all_steps_marks_journey_complete_and_updates_stats() -> None:
    orchestrator, journey = _journey()

    assert orchestrator.start_step(journey.journey_id, "collect_docs") is True
    assert orchestrator.complete_step(journey.journey_id, "collect_docs") is True
    assert orchestrator.start_step(journey.journey_id, "submit_application") is True
    assert orchestrator.complete_step(journey.journey_id, "submit_application") is True

    stats = orchestrator.get_orchestrator_stats()
    progress = orchestrator.get_progress(journey.journey_id)

    assert journey.status == JourneyStatus.COMPLETED
    assert journey.completed_at is not None
    assert stats["completed_journeys"] == 1
    assert stats["active_journeys"] == 0
    assert progress["progress_percentage"] == 100.0
    assert progress["completed_steps"] == 2
    assert progress["estimated_days_remaining"] == 0


def test_missing_journey_or_step_returns_safe_defaults() -> None:
    orchestrator, journey = _journey()

    assert orchestrator.get_journey("missing") is None
    assert orchestrator.start_step("missing", "collect_docs") is False
    assert orchestrator.complete_step("missing", "collect_docs") is False
    assert orchestrator.block_step("missing", "collect_docs", "reason") is False
    assert orchestrator.get_next_steps("missing") == []
    assert orchestrator.get_progress("missing") == {}
    assert orchestrator.check_prerequisites(journey, "missing-step") == (
        False,
        ["Step missing-step not found"],
    )
