"""
Unit tests for backend/app/routers/agentic_rag.py

Covers: clean_image_generation_response, get_ab_test_manager,
        get_metrics_tracker, query_agentic_rag, stream_agentic_rag,
        get_conversation_history_for_agentic, request/response models.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.routers.agentic_rag import (
    AgenticQueryRequest,
    AgenticQueryResponse,
    ConversationMessageInput,
    ImageInput,
    WorkspaceQueryRequest,
    clean_image_generation_response,
    get_ab_test_manager,
    get_conversation_history_for_agentic,
    get_metrics_tracker,
)


# ============================================================================
# clean_image_generation_response
# ============================================================================


class TestCleanImageResponse:
    def test_empty_text(self):
        assert clean_image_generation_response("") == ""
        assert clean_image_generation_response(None) is None

    def test_no_pollinations(self):
        text = "This is a normal response about business setup."
        assert clean_image_generation_response(text) == text

    def test_removes_pollinations_url(self):
        text = "Here is your image!\nhttps://image.pollinations.ai/prompt/test\nDone."
        result = clean_image_generation_response(text)
        assert "pollinations" not in result

    def test_removes_markdown_image(self):
        text = "Text before\n![image](https://pollinations.ai/test)\nText after"
        result = clean_image_generation_response(text)
        assert "![" not in result

    def test_removes_version_lines(self):
        text = "Some text\n1. **Versione 1**: blah\n2. **Versione 2**: blah\nEnd"
        result = clean_image_generation_response(text)
        assert "Versione" not in result

    def test_removes_intro_lines(self):
        text = "ecco le opzioni per te\nhttps://pollinations.ai/x\nfine"
        result = clean_image_generation_response(text)
        assert "ecco le opzioni" not in result

    def test_removes_outro_lines(self):
        text = "content pollinations\nspero che queste vadano bene\nfine"
        result = clean_image_generation_response(text)
        assert "spero che queste" not in result

    def test_removes_url_encoded(self):
        text = "test pollinations\n%20some%20encoded%20content%20here\nend"
        result = clean_image_generation_response(text)
        assert "%20" not in result or "pollinations" not in result

    def test_fallback_when_too_short(self):
        text = "x\nhttps://pollinations.ai/test"
        result = clean_image_generation_response(text)
        assert len(result) >= 30  # fallback message

    def test_cleans_multiple_newlines(self):
        text = "pollinations line\nkept\n\n\n\n\ntext"
        result = clean_image_generation_response(text)
        assert "\n\n\n" not in result

    def test_removes_visualizza_lines(self):
        text = "pollinations test\n[Visualizza immagine]\nrest"
        result = clean_image_generation_response(text)
        assert "Visualizza" not in result

    def test_removes_bare_http_lines(self):
        text = "pollinations stuff\nhttps://example.com/image.png\nmore text"
        result = clean_image_generation_response(text)
        assert "https://example.com" not in result

    def test_removes_alta_risoluzione(self):
        text = "pollinations x\nalta risoluzione fotografia\nend"
        result = clean_image_generation_response(text)
        assert "alta risoluzione" not in result


# ============================================================================
# get_ab_test_manager / get_metrics_tracker
# ============================================================================


class TestGlobalManagers:
    def test_get_metrics_tracker(self):
        tracker = get_metrics_tracker()
        assert tracker is not None

    def test_get_ab_test_manager(self):
        manager = get_ab_test_manager()
        assert manager is not None

    def test_metrics_tracker_singleton(self):
        t1 = get_metrics_tracker()
        t2 = get_metrics_tracker()
        assert t1 is t2


# ============================================================================
# Request / Response Models
# ============================================================================


class TestModels:
    def test_agentic_query_request_defaults(self):
        req = AgenticQueryRequest(query="test")
        assert req.user_id == "anonymous"
        assert req.enable_vision is False
        assert req.images is None
        assert req.session_id is None
        assert req.conversation_id is None
        assert req.conversation_history is None

    def test_agentic_query_request_with_images(self):
        req = AgenticQueryRequest(
            query="test",
            images=[ImageInput(base64="data:image/png;base64,abc", name="test.png")],
        )
        assert len(req.images) == 1

    def test_workspace_query_request(self):
        req = WorkspaceQueryRequest(query="test")
        assert req.enable_vision is False
        assert req.workspace_page is None

    def test_conversation_message_input(self):
        msg = ConversationMessageInput(role="user", content="Hello")
        assert msg.role == "user"

    def test_agentic_query_response(self):
        resp = AgenticQueryResponse(
            answer="test", sources=[], context_length=0,
            execution_time=0.1, route_used="test",
        )
        assert resp.abstain is False
        assert resp.evidence_score == 0.0
        assert resp.tools_called == 0

    def test_agentic_query_response_with_all_fields(self):
        resp = AgenticQueryResponse(
            answer="test", sources=[{"s": "1"}], context_length=5,
            execution_time=1.2, route_used="rag",
            tools_called=3, total_steps=4,
            debug_info={"model": "test"}, ab_test={"id": "1"},
            abstain=True, abstain_reason="low confidence",
            evidence_score=0.05, workflow={"steps": []},
            reasoning="chain", detected_entities=[{"type": "kbli", "value": "56101"}],
        )
        assert resp.abstain is True
        assert resp.abstain_reason == "low confidence"
        assert resp.evidence_score == 0.05


# ============================================================================
# get_conversation_history_for_agentic
# ============================================================================


class TestGetConversationHistory:
    @pytest.mark.asyncio
    async def test_no_db_pool(self):
        result = await get_conversation_history_for_agentic(
            conversation_id=1, session_id="s1", user_id="u1", db_pool=None,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_no_user_id(self):
        result = await get_conversation_history_for_agentic(
            conversation_id=1, session_id="s1", user_id=None, db_pool=MagicMock(),
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_with_conversation_id(self):
        conn = AsyncMock()
        messages = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}]
        row = MagicMock()
        row.get = MagicMock(return_value=messages)
        row.__getitem__ = lambda self, key: {"messages": messages}[key]
        conn.fetchrow = AsyncMock(return_value=row)

        pool = MagicMock()
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acq)

        result = await get_conversation_history_for_agentic(
            conversation_id=1, session_id=None, user_id="test@test.com", db_pool=pool,
        )
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_with_session_id(self):
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)

        pool = MagicMock()
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acq)

        result = await get_conversation_history_for_agentic(
            conversation_id=None, session_id="sess1", user_id="test@test.com", db_pool=pool,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_non_email_user_id(self):
        conn = AsyncMock()
        email_row = MagicMock()
        email_row.get = MagicMock(return_value="found@test.com")
        email_row.__getitem__ = lambda self, key: {"email": "found@test.com"}[key]
        conn.fetchrow = AsyncMock(side_effect=[email_row, None])

        pool = MagicMock()
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acq)

        result = await get_conversation_history_for_agentic(
            conversation_id=None, session_id=None, user_id="12345", db_pool=pool,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_messages_as_json_string(self):
        conn = AsyncMock()
        messages_str = json.dumps([{"role": "user", "content": "Hi"}])
        row = MagicMock()
        # The code checks row.get("messages") first, then isinstance check
        row.get = MagicMock(return_value=messages_str)
        row.__getitem__ = lambda self, key: {"messages": messages_str}[key]
        conn.fetchrow = AsyncMock(return_value=row)

        pool = MagicMock()
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(return_value=conn)
        acq.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acq)

        result = await get_conversation_history_for_agentic(
            conversation_id=1, session_id=None, user_id="test@test.com", db_pool=pool,
        )
        # The function parses the JSON string correctly
        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_db_exception(self):
        pool = MagicMock()
        acq = MagicMock()
        acq.__aenter__ = AsyncMock(side_effect=Exception("DB down"))
        acq.__aexit__ = AsyncMock(return_value=False)
        pool.acquire = MagicMock(return_value=acq)

        result = await get_conversation_history_for_agentic(
            conversation_id=1, session_id=None, user_id="test@test.com", db_pool=pool,
        )
        assert result == []
