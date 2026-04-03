"""Shared fixtures for nuzantara-mcp tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest


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
