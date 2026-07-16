"""Unit tests for the LAM grounding heartbeat workflow.

Regression guard for the retired ``/api/generals/activity`` call (PENDING-ARMS
ledger line, opened 2026-07-12): the "Generals" multi-agent system it reported
on was decommissioned along with the Air machine, and the endpoint has 404'd
by design since 2026-04-03. ``lam_grounding_snapshot`` used to feed the
error-shaped 404 response straight into ``recent_activity`` — every
session-start grounding call silently carried a dead field. It now omits the
call entirely and returns an explicit ``None`` instead.
"""

from pathlib import Path

import pytest

from nuzantara_mcp.workflows.heartbeat import register


def _register_tools(mock_mcp, mock_call, mock_call_safe) -> dict:
    """Register heartbeat tools and capture them."""
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
async def test_lam_grounding_snapshot_never_calls_generals_activity(
    mock_mcp, mock_call, mock_call_safe
) -> None:
    """Guilt test: the dead endpoint must never be requested."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)

    await tools["lam_grounding_snapshot"]()

    called_endpoints = [c.args[0] for c in mock_call_safe.call_args_list if c.args]
    assert "/api/generals/activity" not in called_endpoints


@pytest.mark.asyncio
async def test_lam_grounding_snapshot_recent_activity_is_explicitly_none(
    mock_mcp, mock_call, mock_call_safe
) -> None:
    """recent_activity must be a real explicit null, not an error-shaped dict."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)

    result = await tools["lam_grounding_snapshot"]()

    assert "recent_activity" in result
    assert result["recent_activity"] is None


@pytest.mark.asyncio
async def test_lam_grounding_snapshot_other_sections_still_populated(
    mock_mcp, mock_call, mock_call_safe
) -> None:
    """Innocence: retiring recent_activity must not regress the other 3 sections."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"status": "ok"}

    result = await tools["lam_grounding_snapshot"]()

    assert result["critical_alerts"] == {"status": "ok"}
    assert result["system_health"] == {"status": "ok"}
    assert result["recent_memory"] == {"status": "ok"}


def test_heartbeat_source_never_calls_generals_activity() -> None:
    """Source-level guard: the workflow may document the retired route in
    prose (docstring context) but must never issue a call against it — i.e.
    the string must not appear inside a ``_call``/``_call_safe(`` invocation.
    """
    source = Path(__file__).resolve().parents[1] / "nuzantara_mcp" / "workflows" / "heartbeat.py"
    for line in source.read_text().splitlines():
        if "/api/generals/activity" in line:
            assert "_call" not in line, f"dead endpoint referenced in a call: {line!r}"
