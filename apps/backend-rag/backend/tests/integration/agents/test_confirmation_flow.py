"""
Integration test for VASSAL Phase 3 confirmation flow.

End-to-end through execute_tool with a mock ImageGenerationTool and a
real ConfirmationService backed by fakeredis.

Covers:
    * Approve → tool runs and returns result
    * Reject → tool does NOT run
    * No ConfirmationService wired → fail-closed deny
    * Legacy path (agent_role=None) → no confirmation, tool runs
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from backend.services.agents.confirmation_service import ConfirmationService
from backend.services.agents.team_agent_config import (
    ROLE_ADMIN,
    ROLE_VISA_SPECIALIST,
)
from backend.services.agents.tool_authorizer import ToolAuthorizer
from backend.services.rag.agentic import tool_executor
from backend.services.rag.agentic.tool_executor import (
    configure_tool_executor,
    execute_tool,
)
from backend.services.tools.definitions import BaseTool


# ─────────────────────────────────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────────────────────────────────


class _MockImageGenerationTool(BaseTool):
    """Minimal mock of ImageGenerationTool that records calls."""

    def __init__(self) -> None:
        self.execute_called: bool = False
        self.last_kwargs: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return "image_generation"

    @property
    def description(self) -> str:
        return "mock image generation"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {"prompt": {"type": "string"}}}

    async def execute(self, **kwargs: Any) -> str:
        self.execute_called = True
        self.last_kwargs = kwargs
        return '{"success": true, "image_url": "https://example.com/img.png"}'


class _FakeRedisManager:
    def __init__(self) -> None:
        self._client = fakeredis.aioredis.FakeRedis(decode_responses=True)

    @property
    def available(self) -> bool:
        return True

    def get_async_client(self) -> Any:
        return self._client


@pytest.fixture
def tool_and_map() -> tuple[_MockImageGenerationTool, dict[str, BaseTool]]:
    tool = _MockImageGenerationTool()
    return tool, {"image_generation": tool}


@pytest.fixture
def wired_confirmation_service() -> ConfirmationService:
    """A real ConfirmationService backed by fakeredis."""
    return ConfirmationService(redis_manager=_FakeRedisManager())


@pytest.fixture(autouse=True)
def _restore_module_state():
    """Ensure module-level singletons are restored after each test."""
    original_auth = tool_executor._authorizer
    original_cs = tool_executor._confirmation_service
    yield
    tool_executor._authorizer = original_auth
    tool_executor._confirmation_service = original_cs


# ─────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────


class TestConfirmationFlowIntegration:
    @pytest.mark.asyncio
    async def test_approve_executes_tool(
        self,
        tool_and_map: tuple[_MockImageGenerationTool, dict[str, BaseTool]],
        wired_confirmation_service: ConfirmationService,
    ) -> None:
        """
        Full path: execute_tool → authorizer NEEDS_CONFIRMATION →
        ConfirmationService.request_and_wait (with emitter) →
        resolve(approve) → tool.execute runs.
        """
        tool, tool_map = tool_and_map
        authorizer = ToolAuthorizer()
        configure_tool_executor(
            authorizer=authorizer,
            confirmation_service=wired_confirmation_service,
        )

        emitter = AsyncMock()

        async def approve_soon() -> None:
            # Wait for the emitter to be called with the request_id
            for _ in range(50):
                await asyncio.sleep(0.02)
                if emitter.call_count > 0:
                    break
            assert emitter.call_count == 1, "emitter should be called once"
            request_id = emitter.call_args[0][0]["data"]["request_id"]
            resolved = await wired_confirmation_service.resolve_confirmation(
                request_id=request_id,
                decision="approve",
                user_email="damar@balizero.com",
            )
            assert resolved

        approve_task = asyncio.create_task(approve_soon())

        result, duration = await execute_tool(
            tool_map=tool_map,
            tool_name="image_generation",
            arguments={"prompt": "a KITAS card"},
            user_id="damar@balizero.com",
            tool_execution_counter=None,
            agent_role=ROLE_VISA_SPECIALIST,
            confirmation_emitter=emitter,
        )
        await approve_task

        assert tool.execute_called, "tool must have executed after approval"
        assert "success" in result
        assert duration > 0

    @pytest.mark.asyncio
    async def test_reject_does_not_execute_tool(
        self,
        tool_and_map: tuple[_MockImageGenerationTool, dict[str, BaseTool]],
        wired_confirmation_service: ConfirmationService,
    ) -> None:
        """
        Full path: execute_tool → authorizer NEEDS_CONFIRMATION →
        ConfirmationService.request_and_wait → resolve(reject) →
        tool.execute NEVER called. Clear "rejected" message returned.
        """
        tool, tool_map = tool_and_map
        configure_tool_executor(
            authorizer=ToolAuthorizer(),
            confirmation_service=wired_confirmation_service,
        )

        emitter = AsyncMock()

        async def reject_soon() -> None:
            for _ in range(50):
                await asyncio.sleep(0.02)
                if emitter.call_count > 0:
                    break
            request_id = emitter.call_args[0][0]["data"]["request_id"]
            await wired_confirmation_service.resolve_confirmation(
                request_id=request_id,
                decision="reject",
                user_email="damar@balizero.com",
            )

        reject_task = asyncio.create_task(reject_soon())

        result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="image_generation",
            arguments={"prompt": "a KITAS card"},
            user_id="damar@balizero.com",
            tool_execution_counter=None,
            agent_role=ROLE_VISA_SPECIALIST,
            confirmation_emitter=emitter,
        )
        await reject_task

        assert not tool.execute_called, "tool must NOT execute after rejection"
        assert "rejected" in result.lower()

    @pytest.mark.asyncio
    async def test_no_confirmation_service_fails_closed(
        self,
        tool_and_map: tuple[_MockImageGenerationTool, dict[str, BaseTool]],
    ) -> None:
        """No ConfirmationService wired → fail-closed deny."""
        tool, tool_map = tool_and_map
        configure_tool_executor(
            authorizer=ToolAuthorizer(),
            confirmation_service=None,
        )

        result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="image_generation",
            arguments={"prompt": "test"},
            user_id="damar@balizero.com",
            tool_execution_counter=None,
            agent_role=ROLE_VISA_SPECIALIST,
        )
        assert not tool.execute_called
        assert "unavailable" in result.lower() or "denied" in result.lower()

    @pytest.mark.asyncio
    async def test_admin_no_confirmation_needed(
        self,
        tool_and_map: tuple[_MockImageGenerationTool, dict[str, BaseTool]],
        wired_confirmation_service: ConfirmationService,
    ) -> None:
        """Admin role → image_generation runs without confirmation."""
        tool, tool_map = tool_and_map
        configure_tool_executor(
            authorizer=ToolAuthorizer(),
            confirmation_service=wired_confirmation_service,
        )

        result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="image_generation",
            arguments={"prompt": "test"},
            user_id="zero@balizero.com",
            tool_execution_counter=None,
            agent_role=ROLE_ADMIN,
        )
        assert tool.execute_called
        assert "success" in result

    @pytest.mark.asyncio
    async def test_legacy_path_no_confirmation(
        self,
        tool_and_map: tuple[_MockImageGenerationTool, dict[str, BaseTool]],
        wired_confirmation_service: ConfirmationService,
    ) -> None:
        """Legacy path (agent_role=None) → tool runs without confirmation."""
        tool, tool_map = tool_and_map
        configure_tool_executor(
            authorizer=ToolAuthorizer(),
            confirmation_service=wired_confirmation_service,
        )

        result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="image_generation",
            arguments={"prompt": "test"},
            user_id="anon@x",
            tool_execution_counter=None,
            agent_role=None,
        )
        assert tool.execute_called
        assert "success" in result
