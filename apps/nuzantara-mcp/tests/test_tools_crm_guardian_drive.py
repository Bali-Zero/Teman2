"""Unit tests for CRM Guardian Drive tools."""

import pytest

from nuzantara_mcp.tools.crm_guardian_drive import register


def _register_tools(mock_mcp, mock_call, mock_call_safe) -> dict:
    """Register CRM Guardian Drive tools and capture them."""
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
async def test_validation_summary_uses_admin_auth(
    mock_mcp,
    mock_call,
    mock_call_safe,
) -> None:
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"by_status": {}}

    result = await tools["crm_guardian_drive_validation_summary"]()

    assert result == {"by_status": {}}
    mock_call.assert_called_once_with(
        "/api/crm-guardian/drive/validation-summary",
        admin=True,
    )


@pytest.mark.asyncio
async def test_external_owner_risks_uses_admin_auth(
    mock_mcp,
    mock_call,
    mock_call_safe,
) -> None:
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = []

    result = await tools["crm_guardian_find_external_owner_risks"](limit=10)

    mock_call.assert_called_once_with(
        "/api/crm-guardian/drive/external-owner-risks",
        params={"limit": 10},
        admin=True,
    )
    assert result == {"items": [], "count": 0}


@pytest.mark.asyncio
async def test_stale_drive_links_uses_admin_auth(
    mock_mcp,
    mock_call,
    mock_call_safe,
) -> None:
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = []

    result = await tools["crm_guardian_find_stale_drive_links"](limit=5)

    mock_call.assert_called_once_with(
        "/api/crm-guardian/drive/stale-link-candidates",
        params={"limit": 5},
        admin=True,
    )
    assert result == {"items": [], "count": 0}


@pytest.mark.asyncio
async def test_unlinked_drive_items_uses_admin_auth(
    mock_mcp,
    mock_call,
    mock_call_safe,
) -> None:
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = []

    result = await tools["crm_guardian_find_unlinked_drive_items"](limit=7)

    mock_call.assert_called_once_with(
        "/api/crm-guardian/drive/unlinked-items",
        params={"limit": 7},
        admin=True,
    )
    assert result == {"items": [], "count": 0}


@pytest.mark.asyncio
async def test_shortcut_resolution_status_uses_admin_auth(
    mock_mcp,
    mock_call,
    mock_call_safe,
) -> None:
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = []

    result = await tools["crm_guardian_shortcut_resolution_status"](
        status="resolved",
        limit=3,
    )

    mock_call.assert_called_once_with(
        "/api/crm-guardian/drive/shortcut-edges",
        params={"limit": 3, "status": "resolved"},
        admin=True,
    )
    assert result == {"items": [], "count": 0}


@pytest.mark.asyncio
async def test_all_registered_tools_pass_admin_flag(
    mock_mcp,
    mock_call,
    mock_call_safe,
) -> None:
    """Class-guard: every tool in this module must call _call with admin=True.

    A future tool added to crm_guardian_drive.py without admin=True will fail
    this suite, catching the same 403-Admin-access-required bug at the source.
    """
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)

    for name, tool in tools.items():
        mock_call.reset_mock()
        mock_call.return_value = []

        await tool()

        for call in mock_call.await_args_list:
            assert call.kwargs.get("admin") is True, (
                f"tool {name!r} called _call without admin=True: {call}"
            )
