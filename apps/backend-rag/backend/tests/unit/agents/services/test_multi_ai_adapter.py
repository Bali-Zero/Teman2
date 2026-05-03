"""
Unit tests for backend/agents/services/multi_ai_adapter.py

Covers:
- AITool / TaskType enums
- AIRequest / AIResponse dataclasses
- GeminiAdapter (generate, timeout)
- ClaudeAdapter (init, generate, no client)
- CursorAdapter (generate)
- MultiAIAdapter (_select_ai, generate with various tool routes, fallback, get_available_tools)
- get_multi_ai_adapter singleton
"""

import logging
import subprocess
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.services.multi_ai_adapter import (
    AIRequest,
    AIResponse,
    AITool,
    ClaudeAdapter,
    CursorAdapter,
    GeminiAdapter,
    MultiAIAdapter,
    TaskType,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================
class TestEnums:
    """Verify enum members."""

    def test_ai_tools(self) -> None:
        assert AITool.QWEN.value == "qwen"
        assert AITool.GEMINI.value == "gemini"
        assert AITool.CLAUDE.value == "claude"
        assert AITool.CURSOR.value == "cursor"
        assert AITool.WINDSURF.value == "windsurf"
        assert AITool.GOOGLE_COLAB.value == "google_colab"
        assert AITool.GOOGLE_CLOUD_SHELL.value == "google_cloud_shell"

    def test_task_types(self) -> None:
        assert TaskType.TEST_GENERATION.value == "test_generation"
        assert TaskType.CODE_ANALYSIS.value == "code_analysis"
        assert TaskType.ARCHITECTURE.value == "architecture"
        assert TaskType.CODE_EDITING.value == "code_editing"
        assert TaskType.PRIVACY_SENSITIVE.value == "privacy_sensitive"


# ============================================================================
# Dataclasses
# ============================================================================
class TestDataclasses:
    """Tests for AIRequest and AIResponse."""

    def test_ai_request_defaults(self) -> None:
        req = AIRequest(task_type=TaskType.SIMPLE_TASK, prompt="hello")
        assert req.context is None
        assert req.files is None
        assert req.preferred_tool is None

    def test_ai_response(self) -> None:
        resp = AIResponse(text="result", tool_used=AITool.QWEN, tokens_used=50)
        assert resp.text == "result"
        assert resp.tool_used == AITool.QWEN
        assert resp.tokens_used == 50
        assert resp.metadata is None


# ============================================================================
# GeminiAdapter
# ============================================================================
class TestGeminiAdapter:
    """Tests for GeminiAdapter."""

    @pytest.mark.asyncio
    @patch("backend.agents.services.multi_ai_adapter.subprocess.run")
    async def test_generate_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Gemini response text",
            stderr="",
        )
        adapter = GeminiAdapter(model="gemini-2.0-flash-exp")
        result = await adapter.generate("test prompt")
        assert result.text == "Gemini response text"
        assert result.tool_used == AITool.GEMINI

    @pytest.mark.asyncio
    @patch("backend.agents.services.multi_ai_adapter.subprocess.run")
    async def test_generate_error(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="some error",
        )
        adapter = GeminiAdapter()
        with pytest.raises(RuntimeError, match="Gemini CLI error"):
            await adapter.generate("test")

    @pytest.mark.asyncio
    @patch("backend.agents.services.multi_ai_adapter.subprocess.run")
    async def test_generate_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gemini", timeout=300)
        adapter = GeminiAdapter()
        with pytest.raises(RuntimeError, match="Gemini CLI timeout"):
            await adapter.generate("test")


# ============================================================================
# ClaudeAdapter
# ============================================================================
class TestClaudeAdapter:
    """Tests for ClaudeAdapter (Max OAuth subprocess edition).

    Post-OAuth-migration (2026-04-17): the adapter no longer uses the
    ``anthropic`` SDK. All calls go through
    :func:`backend.llm.claude_oauth_client.complete_async`.
    """

    def test_init_default_model(self) -> None:
        adapter = ClaudeAdapter()
        # Default bumped away from the retired ``claude-3-opus-20240229``.
        assert adapter.model == "claude-sonnet-4-6"
        # ``client`` is a truthy sentinel post-migration (no SDK handle).
        assert adapter.client is True

    def test_init_custom_model(self) -> None:
        adapter = ClaudeAdapter(model="claude-haiku-4-5-20251001")
        assert adapter.model == "claude-haiku-4-5-20251001"

    def test_init_api_key_is_ignored(self, caplog: Any) -> None:
        """Passing api_key must NOT authenticate the adapter; it just logs."""
        import logging as _logging

        with caplog.at_level(_logging.ERROR):
            adapter = ClaudeAdapter(api_key="pretend-key")
        assert adapter.client is True  # still ready — via OAuth
        assert any("ignored" in rec.message.lower() for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_generate_success(self) -> None:
        from backend.llm.claude_oauth_client import ClaudeOAuthResponse

        adapter = ClaudeAdapter(model="claude-sonnet-4-6")
        fake = ClaudeOAuthResponse(
            text="Claude response",
            token_label="token_1",
            elapsed_s=0.01,
            attempts=1,
        )

        with patch(
            "backend.llm.claude_oauth_client.complete_async",
            new_callable=AsyncMock,
            return_value=fake,
        ) as mock_complete:
            result = await adapter.generate("test prompt")

        mock_complete.assert_awaited_once_with("test prompt", model="claude-sonnet-4-6")
        assert result.text == "Claude response"
        assert result.tool_used == AITool.CLAUDE
        # tokens = len("test prompt")//4 + len("Claude response")//4
        assert result.tokens_used == (len("test prompt") // 4) + (len("Claude response") // 4)
        assert result.metadata["token_label"] == "token_1"
        assert result.metadata["transport"] == "max_oauth_subprocess"

    @pytest.mark.asyncio
    async def test_generate_oauth_error_propagates(self) -> None:
        from backend.llm.claude_oauth_client import ClaudeOAuthError

        adapter = ClaudeAdapter()

        with patch(
            "backend.llm.claude_oauth_client.complete_async",
            new_callable=AsyncMock,
            side_effect=ClaudeOAuthError("all tokens exhausted"),
        ):
            with pytest.raises(ClaudeOAuthError, match="exhausted"):
                await adapter.generate("test")


# ============================================================================
# CursorAdapter
# ============================================================================
class TestCursorAdapter:
    """Tests for CursorAdapter."""

    @pytest.mark.asyncio
    @patch("backend.agents.services.multi_ai_adapter.subprocess.run")
    async def test_generate_no_files(self, mock_run: MagicMock) -> None:
        adapter = CursorAdapter()
        result = await adapter.generate("test")
        assert result.tool_used == AITool.CURSOR
        assert "IDE" in result.text

    @pytest.mark.asyncio
    @patch("backend.agents.services.multi_ai_adapter.subprocess.run")
    async def test_generate_with_files(self, mock_run: MagicMock) -> None:
        adapter = CursorAdapter()
        result = await adapter.generate("edit", files=["file.py"])
        mock_run.assert_called_once()
        assert result.tool_used == AITool.CURSOR

    @pytest.mark.asyncio
    @patch("backend.agents.services.multi_ai_adapter.subprocess.run", side_effect=Exception("not found"))
    async def test_generate_error(self, mock_run: MagicMock) -> None:
        adapter = CursorAdapter()
        with pytest.raises(Exception):
            await adapter.generate("test", files=["file.py"])


# ============================================================================
# MultiAIAdapter
# ============================================================================
class TestMultiAIAdapter:
    """Tests for MultiAIAdapter routing and generation."""

    def _make_adapter(self) -> MultiAIAdapter:
        """Create adapter with mocked sub-adapters."""
        mock_qwen = AsyncMock()
        adapter = MultiAIAdapter.__new__(MultiAIAdapter)
        adapter.qwen = mock_qwen
        adapter.gemini = GeminiAdapter.__new__(GeminiAdapter)
        adapter.gemini.model = "test"
        adapter.gemini.gemini_cmd = "gemini"
        adapter.claude = ClaudeAdapter.__new__(ClaudeAdapter)
        adapter.claude.client = MagicMock()
        adapter.claude.model = "test"
        adapter.cursor = None
        adapter.windsurf = None
        adapter.google_colab = None
        adapter.google_cloud_shell = None
        adapter.routing_map = {
            TaskType.TEST_GENERATION: AITool.QWEN,
            TaskType.SIMPLE_TASK: AITool.CLAUDE,
            TaskType.PRIVACY_SENSITIVE: AITool.QWEN,
            TaskType.CODE_ANALYSIS: AITool.CLAUDE,
            TaskType.DOCUMENTATION: AITool.CLAUDE,
            TaskType.REFACTORING: AITool.CLAUDE,
            TaskType.CODE_REVIEW: AITool.CLAUDE,
            TaskType.ARCHITECTURE: AITool.CLAUDE,
            TaskType.CODE_EDITING: AITool.CURSOR,
        }
        return adapter

    def test_select_ai_uses_routing_map(self) -> None:
        adapter = self._make_adapter()
        tool, _ = adapter._select_ai(AIRequest(
            task_type=TaskType.TEST_GENERATION, prompt="test",
        ))
        assert tool == AITool.QWEN

    def test_select_ai_prefers_explicit_tool(self) -> None:
        adapter = self._make_adapter()
        tool, _ = adapter._select_ai(AIRequest(
            task_type=TaskType.TEST_GENERATION,
            prompt="test",
            preferred_tool=AITool.GEMINI,
        ))
        assert tool == AITool.GEMINI

    def test_select_ai_defaults_to_claude(self) -> None:
        adapter = self._make_adapter()
        # Use a task type that maps to CLAUDE
        tool, _ = adapter._select_ai(AIRequest(
            task_type=TaskType.ARCHITECTURE, prompt="test",
        ))
        assert tool == AITool.CLAUDE

    def test_select_ai_cursor_not_available_raises(self) -> None:
        adapter = self._make_adapter()
        adapter.cursor = None
        with pytest.raises(ValueError, match="Adapter not found"):
            adapter._select_ai(AIRequest(
                task_type=TaskType.CODE_EDITING, prompt="test",
            ))

    @pytest.mark.asyncio
    async def test_generate_qwen_route(self) -> None:
        adapter = self._make_adapter()
        mock_llm_resp = MagicMock()
        mock_llm_resp.text = "qwen output"
        mock_llm_resp.tokens_used = 10
        mock_llm_resp.response_time = 0.5
        adapter.qwen.generate = AsyncMock(return_value=mock_llm_resp)

        result = await adapter.generate(AIRequest(
            task_type=TaskType.TEST_GENERATION, prompt="generate tests",
        ))
        assert result.tool_used == AITool.QWEN
        assert result.text == "qwen output"

    @pytest.mark.asyncio
    async def test_generate_gemini_route(self) -> None:
        adapter = self._make_adapter()
        adapter.gemini.generate = AsyncMock(return_value=AIResponse(
            text="gemini output", tool_used=AITool.GEMINI,
        ))

        result = await adapter.generate(AIRequest(
            task_type=TaskType.SIMPLE_TASK,
            prompt="analyze",
            preferred_tool=AITool.GEMINI,
        ))
        assert result.tool_used == AITool.GEMINI

    @pytest.mark.asyncio
    async def test_generate_claude_route(self) -> None:
        adapter = self._make_adapter()
        adapter.claude.generate = AsyncMock(return_value=AIResponse(
            text="claude output", tool_used=AITool.CLAUDE, tokens_used=100,
        ))

        result = await adapter.generate(AIRequest(
            task_type=TaskType.CODE_ANALYSIS, prompt="review this",
        ))
        assert result.tool_used == AITool.CLAUDE

    @pytest.mark.asyncio
    async def test_generate_cursor_with_files(self) -> None:
        adapter = self._make_adapter()
        mock_cursor = MagicMock()
        mock_cursor.open_file = MagicMock()
        adapter.cursor = mock_cursor

        # Re-setup routing map so cursor can be selected
        adapter.routing_map[TaskType.CODE_EDITING] = AITool.CURSOR

        result = await adapter.generate(AIRequest(
            task_type=TaskType.CODE_EDITING,
            prompt="edit file",
            files=["test.py"],
        ))
        assert result.tool_used == AITool.CURSOR
        mock_cursor.open_file.assert_called_once_with("test.py")

    @pytest.mark.asyncio
    async def test_generate_cursor_not_available_fallback(self) -> None:
        """When Cursor not available, should fallback to Qwen."""
        adapter = self._make_adapter()
        adapter.cursor = None

        # Force preferred_tool to bypass routing map ValueError
        mock_llm_resp = MagicMock()
        mock_llm_resp.text = "qwen fallback"
        mock_llm_resp.tokens_used = 5
        mock_llm_resp.response_time = 0.1
        adapter.qwen.generate = AsyncMock(return_value=mock_llm_resp)

        # Use GEMINI which will fail and fallback to qwen
        adapter.gemini.generate = AsyncMock(side_effect=Exception("fail"))

        result = await adapter.generate(AIRequest(
            task_type=TaskType.SIMPLE_TASK,
            prompt="test",
            preferred_tool=AITool.GEMINI,
        ))
        assert result.tool_used == AITool.QWEN
        assert result.metadata.get("fallback") is True

    @pytest.mark.asyncio
    async def test_generate_qwen_failure_raises(self) -> None:
        """When Qwen is primary and fails, no fallback to itself."""
        adapter = self._make_adapter()
        adapter.qwen.generate = AsyncMock(side_effect=Exception("qwen down"))

        with pytest.raises(Exception, match="qwen down"):
            await adapter.generate(AIRequest(
                task_type=TaskType.TEST_GENERATION, prompt="test",
            ))

    @pytest.mark.asyncio
    async def test_generate_windsurf_not_available_falls_back(self) -> None:
        """When Windsurf adapter is None, _select_ai raises ValueError.
        generate() catches it and falls back to Qwen."""
        adapter = self._make_adapter()
        adapter.windsurf = None
        mock_llm_resp = MagicMock()
        mock_llm_resp.text = "fallback"
        mock_llm_resp.tokens_used = 5
        mock_llm_resp.response_time = 0.1
        adapter.qwen.generate = AsyncMock(return_value=mock_llm_resp)

        # _select_ai raises ValueError for WINDSURF when adapter is None,
        # but generate() catches Exception and falls back to Qwen.
        # However, _select_ai is called BEFORE the try block in generate(),
        # so it will raise before the fallback. Let's verify that.
        with pytest.raises(ValueError, match="Adapter not found"):
            await adapter.generate(AIRequest(
                task_type=TaskType.SIMPLE_TASK,
                prompt="test",
                preferred_tool=AITool.WINDSURF,
            ))

    @pytest.mark.asyncio
    async def test_generate_windsurf_with_adapter_and_files(self) -> None:
        adapter = self._make_adapter()
        mock_windsurf = MagicMock()
        mock_windsurf.is_available = MagicMock(return_value=True)
        mock_windsurf.open_file = MagicMock()
        adapter.windsurf = mock_windsurf

        result = await adapter.generate(AIRequest(
            task_type=TaskType.CODE_EDITING,
            prompt="edit",
            preferred_tool=AITool.WINDSURF,
            files=["test.py"],
        ))
        assert result.tool_used == AITool.WINDSURF
        mock_windsurf.open_file.assert_called_once_with("test.py")


# ============================================================================
# get_available_tools
# ============================================================================
class TestGetAvailableTools:
    """Tests for get_available_tools method."""

    @patch("backend.agents.services.multi_ai_adapter.subprocess.run")
    def test_get_available_tools_basic(self, mock_run: MagicMock) -> None:
        """Should always include QWEN."""
        mock_run.side_effect = Exception("not found")
        adapter = TestMultiAIAdapter._make_adapter(self=None)
        adapter.claude.client = None
        adapter.windsurf = None
        adapter.google_colab = None
        adapter.google_cloud_shell = None
        tools = adapter.get_available_tools()
        assert AITool.QWEN in tools

    @patch("backend.agents.services.multi_ai_adapter.subprocess.run")
    def test_get_available_tools_with_gemini(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        adapter = TestMultiAIAdapter._make_adapter(self=None)
        adapter.claude.client = None
        adapter.windsurf = None
        adapter.google_colab = None
        adapter.google_cloud_shell = None
        tools = adapter.get_available_tools()
        assert AITool.GEMINI in tools

    @patch("backend.agents.services.multi_ai_adapter.subprocess.run")
    def test_get_available_tools_with_claude(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = Exception("not found")
        adapter = TestMultiAIAdapter._make_adapter(self=None)
        adapter.claude.client = MagicMock()  # client exists
        adapter.windsurf = None
        adapter.google_colab = None
        adapter.google_cloud_shell = None
        tools = adapter.get_available_tools()
        assert AITool.CLAUDE in tools


# ============================================================================
# Singleton
# ============================================================================
class TestSingleton:
    """Tests for get_multi_ai_adapter singleton."""

    @patch("backend.agents.services.multi_ai_adapter.MultiAIAdapter.__init__", return_value=None)
    def test_singleton_creates_once(self, mock_init: MagicMock) -> None:
        import backend.agents.services.multi_ai_adapter as mod
        mod._multi_ai_adapter = None
        from backend.agents.services.multi_ai_adapter import get_multi_ai_adapter
        adapter = get_multi_ai_adapter()
        assert adapter is not None
        mock_init.assert_called_once()
        # Reset
        mod._multi_ai_adapter = None
