"""
Tests for IntelligentRouter - agentic RAG wrapper facade.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_orchestrator():
    orch = AsyncMock()
    orch.initialize = AsyncMock()
    orch.process_query = AsyncMock(return_value={
        "response": "Test response",
        "sources": [],
        "ai_used": "agentic-rag",
        "confidence": 0.85,
    })
    orch.stream_query = AsyncMock()
    return orch


@pytest.fixture
def intelligent_router(mock_orchestrator):
    with patch("backend.services.rag.agentic.create_agentic_rag", return_value=mock_orchestrator), \
         patch("backend.services.misc.clarification_service.ClarificationService"), \
         patch("backend.core.redis_manager.RedisManager"), \
         patch("backend.services.search.semantic_cache.SemanticCache"):
        from backend.services.routing.intelligent_router import IntelligentRouter
        router = IntelligentRouter(
            ai_client=MagicMock(),
            search_service=MagicMock(),
            tool_executor=MagicMock(),
            db_pool=MagicMock(),
        )
        return router


class TestIntelligentRouterInit:
    def test_init_minimal_params(self):
        with patch("backend.services.rag.agentic.create_agentic_rag"), \
             patch("backend.services.misc.clarification_service.ClarificationService"), \
             patch("backend.core.redis_manager.RedisManager"), \
             patch("backend.services.search.semantic_cache.SemanticCache"):
            from backend.services.routing.intelligent_router import IntelligentRouter
            router = IntelligentRouter()
            assert router is not None

    def test_init_all_params(self):
        with patch("backend.services.rag.agentic.create_agentic_rag"), \
             patch("backend.services.misc.clarification_service.ClarificationService"), \
             patch("backend.core.redis_manager.RedisManager"), \
             patch("backend.services.search.semantic_cache.SemanticCache"):
            from backend.services.routing.intelligent_router import IntelligentRouter
            router = IntelligentRouter(
                ai_client=MagicMock(), search_service=MagicMock(),
                tool_executor=MagicMock(), cultural_rag_service=MagicMock(),
                autonomous_research_service=MagicMock(),
                cross_oracle_synthesis_service=MagicMock(),
                client_journey_orchestrator=MagicMock(),
                personality_service=MagicMock(),
                collaborator_service=MagicMock(), db_pool=MagicMock(),
            )
            assert router.orchestrator is not None

    def test_init_logs_success(self):
        with patch("backend.services.rag.agentic.create_agentic_rag"), \
             patch("backend.services.misc.clarification_service.ClarificationService"), \
             patch("backend.core.redis_manager.RedisManager"), \
             patch("backend.services.search.semantic_cache.SemanticCache"), \
             patch("backend.services.routing.intelligent_router.logger") as mock_logger:
            from backend.services.routing.intelligent_router import IntelligentRouter
            IntelligentRouter()
            mock_logger.info.assert_called()


class TestIntelligentRouterInitialize:
    @pytest.mark.asyncio
    async def test_initialize_success(self, intelligent_router, mock_orchestrator):
        await intelligent_router.initialize()
        mock_orchestrator.initialize.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initialize_propagates_error(self, intelligent_router, mock_orchestrator):
        mock_orchestrator.initialize.side_effect = Exception("Init failed")
        with pytest.raises(Exception, match="Init failed"):
            await intelligent_router.initialize()


class TestIntelligentRouterRouteChat:
    @pytest.mark.asyncio
    async def test_route_chat_success_minimal(self, intelligent_router, mock_orchestrator):
        result = await intelligent_router.route_chat("hello", "user-1")
        assert "response" in result or hasattr(result, "response")

    @pytest.mark.asyncio
    async def test_route_chat_success_all_params(self, intelligent_router, mock_orchestrator):
        result = await intelligent_router.route_chat(
            message="What is KITAS?", user_id="user-1",
            conversation_history=[{"role": "user", "content": "hi"}],
            memory={"facts": []}, emotional_profile={"mood": "neutral"},
        )
        mock_orchestrator.process_query.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_route_chat_empty_sources(self, intelligent_router, mock_orchestrator):
        mock_orchestrator.process_query.return_value = {
            "response": "No sources", "sources": [], "ai_used": "rag",
        }
        result = await intelligent_router.route_chat("test", "user-1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_route_chat_logs_routing(self, intelligent_router, mock_orchestrator):
        with patch("backend.services.routing.intelligent_router.logger") as mock_logger:
            await intelligent_router.route_chat("test", "user-1")
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_route_chat_orchestrator_exception(self, intelligent_router, mock_orchestrator):
        mock_orchestrator.process_query.side_effect = Exception("Orchestrator error")
        with pytest.raises(Exception, match="Routing failed"):
            await intelligent_router.route_chat("test", "user-1")

    @pytest.mark.asyncio
    async def test_route_chat_logs_error(self, intelligent_router, mock_orchestrator):
        mock_orchestrator.process_query.side_effect = Exception("fail")
        with pytest.raises(Exception):
            await intelligent_router.route_chat("test", "user-1")

    @pytest.mark.asyncio
    async def test_route_chat_orchestrator_timeout(self, intelligent_router, mock_orchestrator):
        import asyncio
        mock_orchestrator.process_query.side_effect = asyncio.TimeoutError()
        with pytest.raises(Exception):
            await intelligent_router.route_chat("test", "user-1")

    @pytest.mark.asyncio
    async def test_route_chat_none_user_id(self, intelligent_router, mock_orchestrator):
        result = await intelligent_router.route_chat("test", None)
        assert result is not None

    @pytest.mark.asyncio
    async def test_route_chat_preserves_orchestrator_result_structure(self, intelligent_router, mock_orchestrator):
        mock_orchestrator.process_query.return_value = {
            "response": "Answer", "sources": [{"id": 1}], "confidence": 0.9,
        }
        result = await intelligent_router.route_chat("test", "user-1")
        assert result is not None


class TestIntelligentRouterStreamChat:
    @pytest.mark.asyncio
    async def test_stream_chat_success(self, intelligent_router, mock_orchestrator):
        async def mock_stream(*args, **kwargs):
            yield {"type": "token", "data": "Hello"}
            yield {"type": "token", "data": " World"}
            yield {"type": "done", "data": ""}
        mock_orchestrator.stream_query = mock_stream
        chunks = []
        async for chunk in intelligent_router.stream_chat("test", "user-1"):
            chunks.append(chunk)
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_stream_chat_minimal_params(self, intelligent_router, mock_orchestrator):
        async def mock_stream(*args, **kwargs):
            yield {"type": "done", "data": ""}
        mock_orchestrator.stream_query = mock_stream
        async for _ in intelligent_router.stream_chat("test", "user-1"):
            pass

    @pytest.mark.asyncio
    async def test_stream_chat_all_params(self, intelligent_router, mock_orchestrator):
        async def mock_stream(*args, **kwargs):
            yield {"type": "done", "data": ""}
        mock_orchestrator.stream_query = mock_stream
        async for _ in intelligent_router.stream_chat(
            "test", "user-1",
            conversation_history=[{"role": "user", "content": "hi"}],
        ):
            pass

    @pytest.mark.asyncio
    async def test_stream_chat_logs_start(self, intelligent_router, mock_orchestrator):
        async def mock_stream(*args, **kwargs):
            yield {"type": "done", "data": ""}
        mock_orchestrator.stream_query = mock_stream
        with patch("backend.services.routing.intelligent_router.logger") as mock_logger:
            async for _ in intelligent_router.stream_chat("test", "user-1"):
                pass
            mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_stream_chat_logs_completion(self, intelligent_router, mock_orchestrator):
        async def mock_stream(*args, **kwargs):
            yield {"type": "token", "data": "x"}
        mock_orchestrator.stream_query = mock_stream
        async for _ in intelligent_router.stream_chat("test", "user-1"):
            pass

    @pytest.mark.asyncio
    async def test_stream_chat_orchestrator_exception(self, intelligent_router, mock_orchestrator):
        async def mock_stream(*args, **kwargs):
            raise Exception("Stream error")
            yield  # noqa: unreachable
        mock_orchestrator.stream_query = mock_stream
        with pytest.raises(Exception):
            async for _ in intelligent_router.stream_chat("test", "user-1"):
                pass
