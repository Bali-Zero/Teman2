"""Unit tests for journey orchestration tools."""

import pytest

from nuzantara_mcp.tools.journey import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register journey tools and capture them."""
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
async def test_create_journey_basic(mock_mcp, mock_call, mock_call_safe) -> None:
    """create_journey should POST journey type and client."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "j-1", "steps": 7}

    result = await tools["create_journey"](
        journey_type="pt_pma_setup", client_id="c-100"
    )
    assert result["id"] == "j-1"
    payload = mock_call.call_args[1]["json"]
    assert payload["journey_type"] == "pt_pma_setup"
    assert payload["client_id"] == "c-100"
    assert "custom_steps" not in payload


@pytest.mark.asyncio
async def test_create_journey_custom_steps(mock_mcp, mock_call, mock_call_safe) -> None:
    """create_journey should include custom_steps when provided."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "j-2"}

    await tools["create_journey"](
        journey_type="kitas_application",
        client_id="c-200",
        custom_steps=["Step A", "Step B"],
    )
    payload = mock_call.call_args[1]["json"]
    assert payload["custom_steps"] == ["Step A", "Step B"]


@pytest.mark.asyncio
async def test_get_journey(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_journey should fetch by ID."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "j-1", "completion": 60}

    result = await tools["get_journey"](journey_id="j-1")
    assert result["completion"] == 60
    mock_call.assert_called_once_with("/api/agents/journey/j-1")


@pytest.mark.asyncio
async def test_complete_journey_step(mock_mcp, mock_call, mock_call_safe) -> None:
    """complete_journey_step should POST to step completion endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"completion": 80}

    await tools["complete_journey_step"](
        journey_id="j-1", step_id="s-3", notes="Done"
    )
    mock_call.assert_called_once_with(
        "/api/agents/journey/j-1/step/s-3/complete",
        method="POST",
        params={"notes": "Done"},
    )


@pytest.mark.asyncio
async def test_complete_journey_step_no_notes(mock_mcp, mock_call, mock_call_safe) -> None:
    """complete_journey_step without notes should not pass params."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"completion": 40}

    await tools["complete_journey_step"](journey_id="j-1", step_id="s-1")
    mock_call.assert_called_once_with(
        "/api/agents/journey/j-1/step/s-1/complete",
        method="POST",
        params=None,
    )


@pytest.mark.asyncio
async def test_get_journey_next_steps(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_journey_next_steps should fetch next steps."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"steps": [{"id": "s-4", "title": "Submit docs"}]}

    result = await tools["get_journey_next_steps"](journey_id="j-1")
    assert len(result["steps"]) == 1
    mock_call.assert_called_once_with("/api/agents/journey/j-1/next-steps")
