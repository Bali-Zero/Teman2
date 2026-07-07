import pytest

from backend.services.journey.journey_builder import JourneyBuilderService
from backend.services.journey.journey_templates import JourneyTemplatesService
from backend.services.misc.client_journey_orchestrator import JourneyStatus


def test_build_journey_from_template_maps_steps_and_metadata() -> None:
    builder = JourneyBuilderService(JourneyTemplatesService())

    journey = builder.build_journey_from_template(
        journey_id="journey-1",
        journey_type="company_setup",
        client_id="client-1",
        template_key="pt_pma_setup",
        metadata={"source": "test"},
    )

    assert journey.journey_id == "journey-1"
    assert journey.client_id == "client-1"
    assert journey.status == JourneyStatus.NOT_STARTED
    assert journey.metadata == {"source": "test"}
    assert journey.steps[0].step_id == "name_approval"
    assert journey.steps[0].step_number == 1
    assert journey.steps[1].prerequisites == ["name_approval"]
    assert journey.estimated_completion is not None


def test_build_journey_from_template_rejects_unknown_template() -> None:
    builder = JourneyBuilderService(JourneyTemplatesService())

    with pytest.raises(ValueError, match="Unknown template"):
        builder.build_journey_from_template(
            journey_id="journey-1",
            journey_type="company_setup",
            client_id="client-1",
            template_key="missing",
        )


def test_build_custom_journey_applies_defaults_and_step_order() -> None:
    builder = JourneyBuilderService()

    journey = builder.build_custom_journey(
        journey_id="custom-1",
        journey_type="bespoke",
        client_id="client-1",
        title="Custom Journey",
        description="Bespoke flow",
        steps=[
            {
                "title": "Collect Documents",
                "description": "Ask client for documents",
                "estimated_duration_days": 2,
            },
            {"step_id": "review", "title": "Review"},
        ],
    )

    assert journey.title == "Custom Journey"
    assert journey.steps[0].step_id == "step_1"
    assert journey.steps[0].step_number == 1
    assert journey.steps[1].step_id == "review"
    assert journey.steps[1].description == ""
    assert journey.steps[1].estimated_duration_days == 0
