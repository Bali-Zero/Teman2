"""Shared fixtures for nuzantara-mcp tests."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _default_agent_role(request):
    """Most tool/chain tests assume admin-level access.

    The per-tool auth tests in test_per_tool_auth.py opt out via their own
    ``clear_agent_role`` fixture so they can exercise role denial.
    """
    if "test_per_tool_auth" in request.node.nodeid:
        yield
        return
    original = os.environ.get("AGENT_ROLE")
    os.environ["AGENT_ROLE"] = "admin"
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("AGENT_ROLE", None)
        else:
            os.environ["AGENT_ROLE"] = original


@pytest.fixture
def mock_call():
    """Mock for _call() — returns successful dict responses."""
    return AsyncMock(return_value={"status": "ok"})


@pytest.fixture
def mock_call_safe():
    """Mock for _call_safe() — returns successful dict responses."""
    return AsyncMock(return_value={"status": "ok"})


@pytest.fixture
def mock_mcp():
    """Mock FastMCP instance that captures tool registrations."""
    mcp = MagicMock()
    mcp.tool = MagicMock(side_effect=lambda: lambda fn: fn)
    mcp.prompt = MagicMock(side_effect=lambda: lambda fn: fn)
    mcp.resource = MagicMock(side_effect=lambda uri: lambda fn: fn)
    return mcp
