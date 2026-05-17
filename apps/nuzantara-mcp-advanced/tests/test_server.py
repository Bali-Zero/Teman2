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


def test_persistent_health_client_factory() -> None:
    """_get_health_client should return an httpx.AsyncClient."""
    from nuzantara_mcp_advanced import server
    # Reset global
    server._health_client = None
    client = server._get_health_client()
    assert client is not None
    assert not client.is_closed
    # Second call returns same instance
    client2 = server._get_health_client()
    assert client is client2
    # Cleanup
    server._health_client = None


# --- Subprocess-based tools: use the module-level functions before @mcp.tool wrapping ---
# Since @mcp.tool() wraps them in FunctionTool objects, we test the underlying logic
# by importing the module and calling the internal functions via the MCP run API pattern.
# For these tests, we mock subprocess.run and test via the server function bodies directly.


@pytest.mark.asyncio
async def test_check_fly_status_success() -> None:
    """check_fly_status should parse fly status JSON output."""
    import nuzantara_mcp_advanced.server as srv

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"Name": "nuzantara-rag", "Status": "running"})

    with patch.object(srv, "subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        # Access the underlying function from the FunctionTool
        fn = srv.check_fly_status.fn if hasattr(srv.check_fly_status, 'fn') else srv.check_fly_status
        result = await fn()

    assert result["success"] is True
    assert result["status"]["Status"] == "running"


@pytest.mark.asyncio
async def test_check_fly_status_failure() -> None:
    """check_fly_status should return error on non-zero exit."""
    import nuzantara_mcp_advanced.server as srv

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "fly: app not found"

    with patch.object(srv, "subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        fn = srv.check_fly_status.fn if hasattr(srv.check_fly_status, 'fn') else srv.check_fly_status
        result = await fn()

    assert result["success"] is False
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_check_fly_status_exception() -> None:
    """check_fly_status should handle subprocess exceptions."""
    import nuzantara_mcp_advanced.server as srv

    with patch.object(srv, "subprocess") as mock_subprocess:
        mock_subprocess.run.side_effect = FileNotFoundError("fly not found")
        fn = srv.check_fly_status.fn if hasattr(srv.check_fly_status, 'fn') else srv.check_fly_status
        result = await fn()

    assert result["success"] is False
    assert "fly not found" in result["error"]


@pytest.mark.asyncio
async def test_get_fly_logs_default() -> None:
    """get_fly_logs should retrieve default number of lines."""
    import nuzantara_mcp_advanced.server as srv

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "2026-04-01 INFO: Health check passed\n2026-04-01 INFO: Request served"

    with patch.object(srv, "subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        fn = srv.get_fly_logs.fn if hasattr(srv.get_fly_logs, 'fn') else srv.get_fly_logs
        result = await fn()

    assert result["success"] is True


@pytest.mark.asyncio
async def test_get_fly_logs_with_filter() -> None:
    """get_fly_logs should filter logs when filter_str is provided."""
    import nuzantara_mcp_advanced.server as srv

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "INFO: Health OK\nERROR: Connection refused\nINFO: Request served"

    with patch.object(srv, "subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        fn = srv.get_fly_logs.fn if hasattr(srv.get_fly_logs, 'fn') else srv.get_fly_logs
        result = await fn(lines=10, filter_str="ERROR")

    assert result["success"] is True
    assert "ERROR" in result["logs"]
    assert "Health OK" not in result["logs"]


@pytest.mark.asyncio
async def test_run_backend_tests() -> None:
    """run_backend_tests should invoke pytest."""
    import nuzantara_mcp_advanced.server as srv

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "3 passed in 1.0s"
    mock_result.stderr = ""

    with patch.object(srv, "subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        fn = srv.run_backend_tests.fn if hasattr(srv.run_backend_tests, 'fn') else srv.run_backend_tests
        result = await fn(test_path="backend/tests/", verbose=True)

    assert result["success"] is True
    assert "3 passed" in result["stdout"]


@pytest.mark.asyncio
async def test_execute_recovery_restart_defaults_to_dry_run() -> None:
    """execute_recovery_action should not mutate Fly by default."""
    import nuzantara_mcp_advanced.server as srv

    fn = srv.execute_recovery_action.fn if hasattr(srv.execute_recovery_action, 'fn') else srv.execute_recovery_action
    result = await fn(action="restart")

    assert result["success"] is True
    assert result["dry_run"] is True
    assert result["requires_confirmation"] is True
    assert result["command"] == ["fly", "apps", "restart", srv.FLY_APP]


@pytest.mark.asyncio
async def test_execute_recovery_restart_blocked_without_env() -> None:
    """execute_recovery_action should require explicit env gating."""
    import nuzantara_mcp_advanced.server as srv

    fn = srv.execute_recovery_action.fn if hasattr(srv.execute_recovery_action, 'fn') else srv.execute_recovery_action
    result = await fn(action="restart", confirm=True, dry_run=False)

    assert result["success"] is False
    assert result["blocked"] is True
    assert srv.MUTATION_CONFIRM_ENV in result["error"]


@pytest.mark.asyncio
async def test_execute_recovery_restart_confirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    """execute_recovery_action with restart should call fly apps restart only when gated."""
    import nuzantara_mcp_advanced.server as srv

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Machines restarted"
    mock_result.stderr = ""
    monkeypatch.setenv(srv.MUTATION_CONFIRM_ENV, "1")

    with patch.object(srv, "subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        mock_subprocess.TimeoutExpired = TimeoutError
        fn = srv.execute_recovery_action.fn if hasattr(srv.execute_recovery_action, 'fn') else srv.execute_recovery_action
        result = await fn(action="restart", confirm=True, dry_run=False)

    assert result["success"] is True
    mock_subprocess.run.assert_called_once()


@pytest.mark.asyncio
async def test_execute_recovery_invalid_action() -> None:
    """execute_recovery_action with unknown action should return error."""
    import nuzantara_mcp_advanced.server as srv

    fn = srv.execute_recovery_action.fn if hasattr(srv.execute_recovery_action, 'fn') else srv.execute_recovery_action
    result = await fn(action="destroy")

    assert result["success"] is False
    assert "Unsupported action" in result["error"]


@pytest.mark.asyncio
async def test_analyze_fly_health_clean() -> None:
    """analyze_fly_health should report stable when no issues."""
    import nuzantara_mcp_advanced.server as srv

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "2026-04-01 INFO: Request served\n2026-04-01 INFO: Query completed"

    with patch.object(srv, "subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        fn = srv.analyze_fly_health.fn if hasattr(srv.analyze_fly_health, 'fn') else srv.analyze_fly_health
        result = await fn(lines=10)

    assert result["risk_score"] == 0.0
    assert len(result["issues_found"]) == 0
    assert "stable" in result["recommendation"].lower()


@pytest.mark.asyncio
async def test_analyze_fly_health_oom() -> None:
    """analyze_fly_health should detect OOM."""
    import nuzantara_mcp_advanced.server as srv

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "2026-04-01 CRITICAL: Out of Memory - killed process 1234"

    with patch.object(srv, "subprocess") as mock_subprocess:
        mock_subprocess.run.return_value = mock_result
        fn = srv.analyze_fly_health.fn if hasattr(srv.analyze_fly_health, 'fn') else srv.analyze_fly_health
        result = await fn(lines=10)

    assert result["risk_score"] > 0.5
    assert any("OOM" in issue for issue in result["issues_found"])
