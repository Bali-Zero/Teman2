"""
Unit tests for backend/app/routers/agentic_rag.py

Covers: clean_image_generation_response, get_ab_test_manager,
        get_metrics_tracker, query_agentic_rag, stream_agentic_rag,
        get_conversation_history_for_agentic, request/response models.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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
            answer="test",
            sources=[],
            context_length=0,
            execution_time=0.1,
            route_used="test",
        )
        assert resp.abstain is False
        assert resp.evidence_score == 0.0
        assert resp.tools_called == 0

    def test_agentic_query_response_with_all_fields(self):
        resp = AgenticQueryResponse(
            answer="test",
            sources=[{"s": "1"}],
            context_length=5,
            execution_time=1.2,
            route_used="rag",
            tools_called=3,
            total_steps=4,
            debug_info={"model": "test"},
            ab_test={"id": "1"},
            abstain=True,
            abstain_reason="low confidence",
            evidence_score=0.05,
            workflow={"steps": []},
            reasoning="chain",
            detected_entities=[{"type": "kbli", "value": "56101"}],
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
            conversation_id=1,
            session_id="s1",
            user_id="u1",
            db_pool=None,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_no_user_id(self):
        result = await get_conversation_history_for_agentic(
            conversation_id=1,
            session_id="s1",
            user_id=None,
            db_pool=MagicMock(),
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
            conversation_id=1,
            session_id=None,
            user_id="test@test.com",
            db_pool=pool,
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
            conversation_id=None,
            session_id="sess1",
            user_id="test@test.com",
            db_pool=pool,
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
            conversation_id=None,
            session_id=None,
            user_id="12345",
            db_pool=pool,
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
            conversation_id=1,
            session_id=None,
            user_id="test@test.com",
            db_pool=pool,
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
            conversation_id=1,
            session_id=None,
            user_id="test@test.com",
            db_pool=pool,
        )
        assert result == []


# ============================================================================
# query_agentic_rag — ab_config.rerank honesty (2026-07-18)
#
# `rerank_config` is the A/B experiment's randomly-assigned INTENDED variant
# (e.g. "with_rerank" -> {"use_reranking": True}) — it is never actually
# wired into orchestrator.process_query and does not reflect whether
# reranking really ran. search_service._init_reranker() used to hardcode
# enabled=True regardless of settings.enable_reranker, so a query could
# report "with_rerank" here while the cross-encoder silently failed to
# import sentence_transformers and returned zero scores. debug_info must
# also carry the REAL global on/off switch.
# ============================================================================


class TestQueryAgenticRagRerankHonesty:
    def _mock_result(self) -> MagicMock:
        result = MagicMock()
        result.answer = "answer"
        result.sources = []
        result.document_count = 0
        result.timings = {"total": 0.1}
        result.route_used = "flash"
        result.tools_called = []
        result.model_used = "gemini-3-flash"
        result.cache_hit = False
        result.abstain = False
        result.abstain_reason = None
        result.evidence_score = 0.9
        result.workflow = None
        result.reasoning = None
        result.entities = {}
        result.confidence_score = 0.9
        return result

    def _mock_ab_manager(self) -> MagicMock:
        manager = MagicMock()
        manager.assign_variant.return_value = "with_rerank"
        manager.get_variant_config.side_effect = lambda exp, variant: (
            {"use_reranking": True, "top_k": 5} if exp == "reranking_on_off" else {}
        )
        manager.metrics_tracker.record_query_metrics = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_reports_actual_state_false_even_when_ab_says_with_rerank(self, monkeypatch):
        """Guilt: A/B bucket says 'with_rerank' but the real global switch
        is off — debug_info must surface the real state, not just the A/B
        intent."""
        from backend.app.routers import agentic_rag as router_module

        orchestrator = AsyncMock()
        orchestrator.process_query = AsyncMock(return_value=self._mock_result())

        monkeypatch.setattr(router_module, "get_ab_test_manager", lambda: self._mock_ab_manager())
        monkeypatch.setattr(router_module, "_lf_enabled", lambda: False)
        monkeypatch.setattr(router_module.settings, "enable_reranker", False)

        request = router_module.AgenticQueryRequest(query="what is KITAS?")
        response = await router_module.query_agentic_rag(
            request=request,
            current_user=None,
            orchestrator=orchestrator,
            db_pool=None,
        )

        rerank_debug = response.debug_info["ab_config"]["rerank"]
        assert rerank_debug["use_reranking"] is True  # A/B intent preserved
        assert rerank_debug["reranker_actually_enabled"] is False  # real state

    @pytest.mark.asyncio
    async def test_reports_actual_state_true_when_setting_enabled(self, monkeypatch):
        """Innocence: when settings.enable_reranker=True, the honesty field
        reflects that too — behavior for the True case is unchanged."""
        from backend.app.routers import agentic_rag as router_module

        orchestrator = AsyncMock()
        orchestrator.process_query = AsyncMock(return_value=self._mock_result())

        monkeypatch.setattr(router_module, "get_ab_test_manager", lambda: self._mock_ab_manager())
        monkeypatch.setattr(router_module, "_lf_enabled", lambda: False)
        monkeypatch.setattr(router_module.settings, "enable_reranker", True)

        request = router_module.AgenticQueryRequest(query="what is KITAS?")
        response = await router_module.query_agentic_rag(
            request=request,
            current_user=None,
            orchestrator=orchestrator,
            db_pool=None,
        )

        assert response.debug_info["ab_config"]["rerank"]["reranker_actually_enabled"] is True

    @pytest.mark.asyncio
    async def test_trusted_wa_skips_ab_assignment_metrics_and_preview(self, monkeypatch):
        """Trusted WA must bypass experiments and request-level trace wrappers."""
        from backend.app.routers import agentic_rag as router_module

        orchestrator = AsyncMock()
        orchestrator.process_query = AsyncMock(return_value=self._mock_result())
        ab_factory = MagicMock(side_effect=AssertionError("WA reached A/B manager"))
        init_observability = MagicMock(
            side_effect=AssertionError("WA initialized request observability"),
        )
        traced_query = AsyncMock(
            side_effect=AssertionError("WA reached request trace wrapper"),
        )

        monkeypatch.setattr(router_module, "get_ab_test_manager", ab_factory)
        monkeypatch.setattr(router_module, "_lf_enabled", lambda: True)
        monkeypatch.setattr(router_module, "init_observability", init_observability)
        monkeypatch.setattr(router_module, "_process_query_traced", traced_query)
        monkeypatch.setattr(
            router_module,
            "_resolve_trusted_wa_profile",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            router_module,
            "_derive_wa_memory_subject_for_request",
            lambda *_args: None,
        )
        monkeypatch.setattr(router_module.settings, "wa_bot_agent_role_enabled", False)

        response = await router_module.query_agentic_rag(
            request=router_module.AgenticQueryRequest(
                query="What is a public KITAS requirement?",
                user_id="whatsapp_SYNTHETIC_PHONE_CANARY_8d11",
            ),
            current_user=None,
            orchestrator=orchestrator,
            db_pool=None,
            is_wa_inbox_bot=True,
        )

        ab_factory.assert_not_called()
        init_observability.assert_not_called()
        traced_query.assert_not_awaited()
        orchestrator.process_query.assert_awaited_once()
        assert response.ab_test is None
        assert "ab_config" not in response.debug_info

    @pytest.mark.asyncio
    async def test_trusted_wa_never_loads_database_conversation_history(self, monkeypatch):
        """Only bounded history supplied by the WA ingress may reach the core."""
        from backend.app.routers import agentic_rag as router_module

        orchestrator = AsyncMock()
        orchestrator.process_query = AsyncMock(return_value=self._mock_result())
        ab_factory = MagicMock(return_value=self._mock_ab_manager())
        history_loader = AsyncMock(side_effect=AssertionError("WA reached history DB"))

        monkeypatch.setattr(router_module, "get_ab_test_manager", ab_factory)
        monkeypatch.setattr(
            router_module,
            "get_conversation_history_for_agentic",
            history_loader,
        )
        monkeypatch.setattr(router_module, "_lf_enabled", lambda: False)
        monkeypatch.setattr(
            router_module,
            "_resolve_trusted_wa_profile",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            router_module,
            "_derive_wa_memory_subject_for_request",
            lambda *_args: None,
        )
        monkeypatch.setattr(router_module.settings, "wa_bot_agent_role_enabled", False)

        await router_module.query_agentic_rag(
            request=router_module.AgenticQueryRequest(
                query="What is a public KITAS requirement?",
                session_id="SYNTHETIC_SESSION_CANARY_58aa",
                user_id="whatsapp_SYNTHETIC_PHONE_CANARY_8d11",
            ),
            current_user=None,
            orchestrator=orchestrator,
            db_pool=MagicMock(),
            is_wa_inbox_bot=True,
        )

        ab_factory.assert_not_called()
        history_loader.assert_not_awaited()
        query_kwargs = orchestrator.process_query.await_args.kwargs
        assert "conversation_history" not in query_kwargs

    @pytest.mark.asyncio
    async def test_trusted_wa_sync_failure_never_logs_raw_canaries(
        self,
        monkeypatch,
        caplog,
    ):
        from fastapi import HTTPException

        from backend.app.routers import agentic_rag as router_module

        user_canary = "SYNTHETIC_USER_CANARY_0f91@example.test"
        session_canary = "SYNTHETIC_SESSION_CANARY_b441"
        query_canary = "SYNTHETIC_QUERY_CANARY_34aa"
        error_canary = "SYNTHETIC_SYNC_EXCEPTION_CANARY_a091"
        orchestrator = SimpleNamespace(
            process_query=AsyncMock(side_effect=RuntimeError(error_canary)),
        )

        monkeypatch.setattr(
            router_module,
            "get_ab_test_manager",
            lambda: self._mock_ab_manager(),
        )
        monkeypatch.setattr(router_module, "_lf_enabled", lambda: False)
        monkeypatch.setattr(
            router_module,
            "_resolve_trusted_wa_profile",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(
            router_module,
            "_derive_wa_memory_subject_for_request",
            lambda *_args: None,
        )
        monkeypatch.setattr(router_module.settings, "wa_bot_agent_role_enabled", False)

        request = router_module.AgenticQueryRequest(
            query=query_canary,
            session_id=session_canary,
            user_id="whatsapp_SYNTHETIC_PHONE_CANARY_5f11",
        )
        with caplog.at_level("INFO", logger=router_module.logger.name):
            with pytest.raises(HTTPException) as exc_info:
                await router_module.query_agentic_rag(
                    request=request,
                    current_user={"email": user_canary},
                    orchestrator=orchestrator,
                    db_pool=None,
                    is_wa_inbox_bot=True,
                )

        assert exc_info.value.detail == (
            "Internal Server Error: The request could not be processed."
        )
        for canary in (user_canary, session_canary, query_canary, error_canary):
            assert canary not in caplog.text
        assert "error_type=RuntimeError" in caplog.text
        assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_public_stream_body_channel_never_grants_wa_and_errors_are_generic(
    monkeypatch,
    caplog,
) -> None:
    from backend.app.routers import agentic_rag as router_module

    user_canary = "SYNTHETIC_STREAM_USER_CANARY_013a@example.test"
    session_canary = "SYNTHETIC_STREAM_SESSION_CANARY_73be"
    query_canary = "SYNTHETIC_STREAM_QUERY_CANARY_9ac2"
    error_canary = "SYNTHETIC_STREAM_EXCEPTION_CANARY_f2d4"
    forwarded = {}

    async def exploding_stream(**kwargs):
        forwarded.update(kwargs)
        raise RuntimeError(error_canary)
        yield  # pragma: no cover - makes this an async generator

    orchestrator = SimpleNamespace(stream_query=exploding_stream)
    http_request = MagicMock()
    http_request.state.correlation_id = "synthetic-correlation"
    http_request.state.request_id = None
    http_request.headers = {}
    http_request.is_disconnected = AsyncMock(return_value=False)
    request = router_module.AgenticQueryRequest(
        query=query_canary,
        session_id=session_canary,
        channel="whatsapp",
    )

    with (
        caplog.at_level("INFO", logger=router_module.logger.name),
        monkeypatch.context() as patch_context,
    ):
        trace_span = MagicMock()
        trace_span.return_value.__enter__.return_value = None
        trace_span.return_value.__exit__.return_value = False
        add_span_event = MagicMock()
        patch_context.setattr(router_module, "trace_span", trace_span)
        patch_context.setattr(router_module, "add_span_event", add_span_event)
        response = await router_module.stream_agentic_rag(
            request_body=request,
            http_request=http_request,
            current_user={"email": user_canary},
            orchestrator=orchestrator,
            db_pool=None,
        )
        chunks = [chunk async for chunk in response.body_iterator]

    rendered_sse = "".join(
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in chunks
    )
    assert forwarded["channel"] == "whatsapp"
    assert "is_whatsapp" not in forwarded
    assert "profile" not in forwarded
    for canary in (user_canary, session_canary, query_canary, error_canary):
        assert canary not in caplog.text
        assert canary not in rendered_sse
        assert canary not in repr(trace_span.call_args_list)
        assert canary not in repr(add_span_event.call_args_list)
    assert "Unable to complete the streamed response." in rendered_sse
    assert "error_type=RuntimeError" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.asyncio
async def test_workspace_stream_never_emits_or_logs_raw_identity_session_or_errors(
    monkeypatch,
    caplog,
) -> None:
    """Authenticated workspace streaming keeps observability metadata opaque."""
    from backend.app.routers import agentic_rag as router_module

    email_canary = "SYNTHETIC_WORKSPACE_EMAIL_CANARY@example.test"
    session_canary = "SYNTHETIC_WORKSPACE_SESSION_CANARY_0ba1"
    query_canary = "SYNTHETIC_WORKSPACE_QUERY_CANARY_e4d2"
    error_canary = "SYNTHETIC_WORKSPACE_EXCEPTION_CANARY_2a17"
    correlation_canary = "SYNTHETIC_WORKSPACE_CORRELATION_CANARY_9c51"
    forwarded: dict = {}

    async def leaking_stream(**kwargs):
        forwarded.update(kwargs)
        yield {
            "type": "error",
            "data": {
                "message": error_canary,
                "session_id": session_canary,
            },
        }
        raise RuntimeError(error_canary)

    role = SimpleNamespace(role_id="support", client_scope="all")
    monkeypatch.setattr(router_module, "get_agent_role", lambda _email: role)
    monkeypatch.setattr(
        router_module,
        "build_agent_context",
        lambda **_kwargs: {
            "agent_name": "Synthetic Agent",
            "agent_role_display": "Support",
            "agent_system_context": "Use ordinary workspace tools.",
            "agent_client_scope": "all",
            "agent_email": email_canary,
        },
    )

    http_request = MagicMock()
    http_request.state.correlation_id = correlation_canary
    http_request.state.request_id = None
    http_request.headers = {}
    http_request.is_disconnected = AsyncMock(return_value=False)
    request = router_module.WorkspaceQueryRequest(
        query=query_canary,
        session_id=session_canary,
    )

    with caplog.at_level("INFO", logger=router_module.logger.name):
        response = await router_module.stream_workspace_agent(
            request_body=request,
            http_request=http_request,
            current_user={"email": email_canary},
            orchestrator=SimpleNamespace(stream_query=leaking_stream),
            db_pool=None,
        )
        chunks = [chunk async for chunk in response.body_iterator]

    rendered_sse = "".join(
        chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in chunks
    )
    for canary in (
        email_canary,
        session_canary,
        query_canary,
        error_canary,
        correlation_canary,
    ):
        assert canary not in caplog.text
        assert canary not in rendered_sse
    assert "Unable to complete the workspace stream." in rendered_sse
    assert "error_type=RuntimeError" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    assert forwarded["channel"] == "workspace"
    assert forwarded.get("is_whatsapp", False) is False
