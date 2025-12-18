"""
Integration tests for ToolExecutor
Tests tool execution during AI conversations
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestToolExecutorIntegration:
    """Integration tests for ToolExecutor"""

    def test_tool_executor_init(self):
        """Test ToolExecutor initialization"""
        with patch("services.zantara_tools.ZantaraTools") as mock_tools:
            from services.tool_executor import ToolExecutor

            executor = ToolExecutor(zantara_tools=mock_tools.return_value)
            assert executor is not None
            assert executor.zantara_tools is not None

    @pytest.mark.asyncio
    async def test_execute_tool_calls(self):
        """Test executing tool calls"""
        with patch("services.zantara_tools.ZantaraTools") as mock_tools_class:
            mock_tools = MagicMock()
            mock_tools.get_team_overview = AsyncMock(return_value={"total": 10})
            mock_tools_class.return_value = mock_tools

            from services.tool_executor import ToolExecutor

            executor = ToolExecutor(zantara_tools=mock_tools)

            tool_uses = [
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "get_team_overview",
                    "input": {},
                }
            ]

            results = await executor.execute_tool_calls(tool_uses)
            assert len(results) == 1
            assert results[0]["type"] == "tool_result"

    @pytest.mark.asyncio
    async def test_execute_tool_calls_unknown_tool(self):
        """Test executing unknown tool calls"""
        with patch("services.zantara_tools.ZantaraTools") as mock_tools_class:
            mock_tools = MagicMock()
            mock_tools_class.return_value = mock_tools

            from services.tool_executor import ToolExecutor

            executor = ToolExecutor(zantara_tools=mock_tools)

            tool_uses = [
                {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "unknown_tool",
                    "input": {},
                }
            ]

            results = await executor.execute_tool_calls(tool_uses)
            assert len(results) == 1
            assert "error" in results[0].get("content", [{}])[0].get("text", "").lower()
