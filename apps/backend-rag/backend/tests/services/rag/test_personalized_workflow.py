"""
Unit tests for Personalized Workflow Service
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.rag.personalized_workflow import personalize_workflow


@pytest.fixture
def mock_crm_service():
    service = MagicMock()
    service.search_clients = AsyncMock(
        return_value=([{"id": 1, "full_name": "Test User", "custom_fields": {"has_npwp": True}}], 1),
    )
    service.get_client = AsyncMock(
        return_value={"id": 1, "full_name": "Test User", "practices": []},
    )
    return service


@pytest.fixture
def mock_memory_orchestrator():
    orchestrator = MagicMock()
    context = MagicMock()
    context.profile_facts = ["User has NPWP", "Urgent request"]
    orchestrator.get_user_context = AsyncMock(return_value=context)
    return orchestrator


@pytest.fixture
def base_workflow():
    return {
        "id": "test_wf",
        "name": "Test Workflow",
        "steps": [
            {
                "step_id": "npwp_registration",
                "title": "NPWP Registration",
                "estimated_duration_days": 10,
            },
            {
                "step_id": "submit_passport",
                "title": "Submit Passport",
                "estimated_duration_days": 2,
            },
        ],
    }


@pytest.mark.asyncio
async def test_personalize_workflow_skips_npwp(
    mock_crm_service, mock_memory_orchestrator, base_workflow,
):
    # Setup: User has NPWP in CRM
    result = await personalize_workflow(
        "test@example.com", base_workflow, mock_crm_service, mock_memory_orchestrator,
    )

    # Verify NPWP registration step is skipped
    step_ids = [s["step_id"] for s in result["steps"]]
    assert "npwp_registration" not in step_ids
    assert result["is_personalized"] is True


@pytest.mark.asyncio
async def test_personalize_workflow_completes_passport(
    mock_crm_service, mock_memory_orchestrator, base_workflow,
):
    # Setup: User has passport number
    mock_crm_service.search_clients = AsyncMock(
        return_value=([{"id": 1, "passport_number": "A1234567"}], 1),
    )

    result = await personalize_workflow(
        "test@example.com", base_workflow, mock_crm_service, mock_memory_orchestrator,
    )

    # Verify submit_passport is marked completed
    passport_step = next(s for s in result["steps"] if s["step_id"] == "submit_passport")
    assert passport_step["status"] == "completed"


@pytest.mark.asyncio
async def test_personalize_workflow_urgency_compression(
    mock_crm_service, mock_memory_orchestrator, base_workflow,
):
    # Setup: Memory fact contains "urgent"
    mock_crm_service.search_clients = AsyncMock(return_value=([{"id": 1}], 1))

    result = await personalize_workflow(
        "test@example.com", base_workflow, mock_crm_service, mock_memory_orchestrator,
    )

    # Verify duration is compressed
    passport_step = next(s for s in result["steps"] if s["step_id"] == "submit_passport")
    assert passport_step["estimated_duration_days"] == 1  # 2 * 0.8 = 1.6 -> 1
    assert passport_step["priority"] == "urgent"
