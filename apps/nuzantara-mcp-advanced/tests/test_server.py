"""Tests for nuzantara-mcp-advanced server."""

import importlib
import json
from unittest.mock import MagicMock, patch

import pytest


def test_server_imports() -> None:
    """Server module should import without errors."""
    mod = importlib.import_module("nuzantara_mcp_advanced.server")
    assert hasattr(mod, "mcp")
    assert hasattr(mod, "main")


def test_mcp_instance_configured() -> None:
    """MCP instance should have correct name."""
    from nuzantara_mcp_advanced.server import mcp
    assert mcp.name == "Nuzantara Advanced Operations"


@pytest.mark.asyncio
async def test_check_fly_status_success() -> None:
    """check_fly_status should parse fly status JSON output."""
    from nuzantara_mcp_advanced.server import check_fly_status

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"Name": "nuzantara-rag", "Status": "running"})

    with patch("nuzantara_mcp_advanced.server.subprocess.run", return_value=mock_result):
        result = await check_fly_status()

    assert result["success"] is True
    assert result["status"]["Status"] == "running"


@pytest.mark.asyncio
async def test_check_fly_status_failure() -> None:
    """check_fly_status should return error on non-zero exit."""
    from nuzantara_mcp_advanced.server import check_fly_status

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "fly: app not found"

    with patch("nuzantara_mcp_advanced.server.subprocess.run", return_value=mock_result):
        result = await check_fly_status()

    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_check_fly_status_exception() -> None:
    """check_fly_status should handle subprocess exceptions."""
    from nuzantara_mcp_advanced.server import check_fly_status

    with patch(
        "nuzantara_mcp_advanced.server.subprocess.run",
        side_effect=FileNotFoundError("fly not found"),
    ):
        result = await check_fly_status()

    assert result["success"] is False
    assert "fly not found" in result["error"]


@pytest.mark.asyncio
async def test_get_fly_logs_default() -> None:
    """get_fly_logs should retrieve default number of lines."""
    from nuzantara_mcp_advanced.server import get_fly_logs

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "2026-04-01 INFO: Health check passed\n2026-04-01 INFO: Request served"

    with patch("nuzantara_mcp_advanced.server.subprocess.run", return_value=mock_result):
        result = await get_fly_logs()

    assert result["success"] is True


@pytest.mark.asyncio
async def test_get_fly_logs_with_filter() -> None:
    """get_fly_logs should apply filter when provided."""
    from nuzantara_mcp_advanced.server import get_fly_logs

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "2026-04-01 ERROR: Connection refused\n"

    with patch("nuzantara_mcp_advanced.server.subprocess.run", return_value=mock_result):
        result = await get_fly_logs(lines=10, filter_str="ERROR")

    assert result["success"] is True
