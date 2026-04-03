"""Unit tests for Workflow tools."""

import pytest

from nuzantara_mcp.tools.workflows import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register workflow tools and capture them."""
    tools: dict = {}

    def capture_tool():
        def decorator(fn):
            tools[fn.__name__] = fn
            return fn
        return decorator

    mock_mcp.tool = capture_tool
    register(mock_mcp, mock_call, mock_call_safe)
    return tools


@pytest.mark.asyncio
async def test_create_execution_plan_minimal(mock_mcp, mock_call, mock_call_safe) -> None:
    """create_execution_plan with query only."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "plan_id": "plan-1",
        "task_type": "KITAS_APPLICATION",
        "steps": [{"action": "collect_docs", "safety_level": "SAFE"}],
    }

    result = await tools["create_execution_plan"](query="Apply for KITAS investor visa")
    assert result["plan_id"] == "plan-1"
    mock_call.assert_called_once_with(
        "/api/v1/autonomous-execution/plans",
        method="POST",
        json={"query": "Apply for KITAS investor visa"},
    )


@pytest.mark.asyncio
async def test_create_execution_plan_with_client(mock_mcp, mock_call, mock_call_safe) -> None:
    """create_execution_plan with client_id."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"plan_id": "plan-2"}

    await tools["create_execution_plan"](query="Register NPWP", client_id="client-5")
    call_json = mock_call.call_args[1]["json"]
    assert call_json["client_id"] == "client-5"
    assert call_json["query"] == "Register NPWP"


@pytest.mark.asyncio
async def test_create_execution_plan_no_client_omits(mock_mcp, mock_call, mock_call_safe) -> None:
    """create_execution_plan without client_id should omit it."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"plan_id": "plan-3"}

    await tools["create_execution_plan"](query="test")
    call_json = mock_call.call_args[1]["json"]
    assert "client_id" not in call_json


@pytest.mark.asyncio
async def test_execute_plan(mock_mcp, mock_call, mock_call_safe) -> None:
    """execute_plan should POST to correct URL."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"status": "in_progress", "completed_steps": 2}

    result = await tools["execute_plan"](plan_id="plan-abc")
    assert result["status"] == "in_progress"
    mock_call.assert_called_once_with(
        "/api/v1/autonomous-execution/plans/plan-abc/execute",
        method="POST",
    )


@pytest.mark.asyncio
async def test_get_plan_status(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_plan_status should GET the plan."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "plan_id": "plan-abc",
        "status": "waiting_approval",
        "steps": [],
    }

    result = await tools["get_plan_status"](plan_id="plan-abc")
    assert result["status"] == "waiting_approval"
    mock_call.assert_called_once_with(
        "/api/v1/autonomous-execution/plans/plan-abc"
    )


@pytest.mark.asyncio
async def test_approve_step_approved(mock_mcp, mock_call, mock_call_safe) -> None:
    """approve_step with approved=True."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"step_id": "step-1", "status": "approved"}

    result = await tools["approve_step"](plan_id="plan-1", step_id="step-1")
    assert result["status"] == "approved"
    mock_call.assert_called_once_with(
        "/api/v1/autonomous-execution/plans/plan-1/steps/step-1/approve",
        method="POST",
        json={"approved": True},
    )


@pytest.mark.asyncio
async def test_approve_step_rejected_with_notes(mock_mcp, mock_call, mock_call_safe) -> None:
    """approve_step with approved=False and notes."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"step_id": "step-2", "status": "rejected"}

    await tools["approve_step"](
        plan_id="plan-1", step_id="step-2",
        approved=False, notes="Missing document",
    )
    call_json = mock_call.call_args[1]["json"]
    assert call_json["approved"] is False
    assert call_json["notes"] == "Missing document"


@pytest.mark.asyncio
async def test_approve_step_no_notes_omits(mock_mcp, mock_call, mock_call_safe) -> None:
    """approve_step without notes should not include notes key."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"status": "approved"}

    await tools["approve_step"](plan_id="p", step_id="s", approved=True)
    call_json = mock_call.call_args[1]["json"]
    assert "notes" not in call_json


@pytest.mark.asyncio
async def test_list_plans_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_plans with defaults."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"plans": [], "total": 0}

    result = await tools["list_plans"]()
    mock_call.assert_called_once_with(
        "/api/v1/autonomous-execution/plans", params={"limit": 20}
    )


@pytest.mark.asyncio
async def test_list_plans_with_status(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_plans with status filter."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"plans": [{"id": "p1"}]}

    await tools["list_plans"](status="completed", limit=5)
    call_params = mock_call.call_args[1]["params"]
    assert call_params["status"] == "completed"
    assert call_params["limit"] == 5


@pytest.mark.asyncio
async def test_list_plans_no_status_omits(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_plans without status should not include it."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"plans": []}

    await tools["list_plans"]()
    call_params = mock_call.call_args[1]["params"]
    assert "status" not in call_params


@pytest.mark.asyncio
async def test_run_conversation_trainer(mock_mcp, mock_call, mock_call_safe) -> None:
    """run_conversation_trainer should POST with no payload."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"execution_id": "exec-1", "patterns_found": 12}

    result = await tools["run_conversation_trainer"]()
    assert result["patterns_found"] == 12
    mock_call.assert_called_once_with(
        "/api/autonomous-agents/conversation-trainer/run", method="POST"
    )


@pytest.mark.asyncio
async def test_run_client_predictor(mock_mcp, mock_call, mock_call_safe) -> None:
    """run_client_predictor should POST with no payload."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"vip_nurtured": 5, "high_risk_contacted": 3}

    result = await tools["run_client_predictor"]()
    assert result["vip_nurtured"] == 5
    mock_call.assert_called_once_with(
        "/api/autonomous-agents/client-value-predictor/run", method="POST"
    )


@pytest.mark.asyncio
async def test_get_agents_status(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_agents_status should GET the status endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "conversation_trainer": {"last_run": "2026-04-01", "success_rate": 0.95},
    }

    result = await tools["get_agents_status"]()
    assert "conversation_trainer" in result
    mock_call.assert_called_once_with("/api/autonomous-agents/status")


@pytest.mark.asyncio
async def test_execute_plan_error(mock_mcp, mock_call, mock_call_safe) -> None:
    """Error propagation from _call."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.side_effect = Exception("Service unavailable")

    with pytest.raises(Exception, match="Service unavailable"):
        await tools["execute_plan"](plan_id="p-fail")
