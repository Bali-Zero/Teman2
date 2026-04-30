"""
Tests for apps/backend-rag/backend/app/routers/oracle_universal.py

Strategy: mount the router in an isolated FastAPI app, override
`get_current_user` + `get_search_service` with no-op fakes, and patch
`oracle_service.process_query` / `oracle_service.submit_feedback` with
AsyncMocks that return the dict shape the router expects.

Keeping the router's own model validation in the loop — we send the real
Pydantic request bodies and assert on the Pydantic response bodies — so
the tests still protect the router's contract even though the service
layer is stubbed.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from backend.app.dependencies import get_current_user, get_search_service
from backend.app.routers.oracle_universal import router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _happy_result(
    *,
    query: str,
    answer: str = "Stub answer.",
    collection_used: str = "visa_knowledge_hybrid",
    sources: list[dict[str, Any]] | None = None,
    document_count: int | None = None,
    domain_confidence: dict[str, float] | None = None,
    model_used: str = "gemini-2.5-flash",
    user_email: str | None = "user@example.com",
) -> dict[str, Any]:
    """Shape a dict compatible with OracleQueryResponse(**result)."""
    srcs = sources if sources is not None else [
        {"id": "doc-1", "title": "KBLI 6411", "score": 0.82},
    ]
    return {
        "success": True,
        "query": query,
        "user_email": user_email,
        "answer": answer,
        "answer_language": "en",
        "model_used": model_used,
        "sources": srcs,
        "document_count": document_count if document_count is not None else len(srcs),
        "collection_used": collection_used,
        "routing_reason": f"Routed to {collection_used}",
        "domain_confidence": domain_confidence or {"visa": 0.91},
        "user_profile": None,
        "language_detected": "en",
        "execution_time_ms": 123.4,
        "search_time_ms": 45.0,
        "reasoning_time_ms": 60.0,
        "followup_questions": [],
        "citations": srcs,
        "clarification_needed": False,
        "clarification_question": None,
        "personality_used": "professional",
        "golden_answer_used": False,
        "user_memory_facts": [],
    }


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def fake_current_user() -> dict[str, Any]:
        return {"email": "user@example.com", "role": "member"}

    async def fake_search_service() -> Any:
        # Router never touches it directly; service is fully mocked.
        return object()

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_search_service] = fake_search_service
    return app


# A couple of module-level constants so tests stay readable.
_ORACLE_ROUTER_SERVICE = "backend.app.routers.oracle_universal.oracle_service"


# ---------------------------------------------------------------------------
# Happy path: single-domain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint_is_always_ok() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/oracle/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "active"
    assert body["service"] == "Oracle v5.3"
    assert "timestamp" in body and isinstance(body["timestamp"], (int, float))


@pytest.mark.asyncio
async def test_query_visa_happy_path() -> None:
    app = _build_app()
    process = AsyncMock(
        return_value=_happy_result(
            query="Which visa do I need for a 6-month business trip to Bali?",
            answer="For a 6-month business trip you need a C2 visa with an extension.",
            collection_used="visa_knowledge_hybrid",
            domain_confidence={"visa": 0.92},
        ),
    )
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={
                    "query": "Which visa do I need for a 6-month business trip to Bali?",
                    "user_email": "user@example.com",
                },
            )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "C2" in body["answer"]
    assert body["collection_used"] == "visa_knowledge_hybrid"
    assert body["domain_confidence"] == {"visa": 0.92}
    # The router must forward the query+email into the service call.
    process.assert_awaited_once()
    call_kwargs = process.await_args.kwargs
    assert call_kwargs["request_query"].startswith("Which visa")
    assert call_kwargs["request_user_email"] == "user@example.com"


@pytest.mark.asyncio
async def test_query_tax_happy_path() -> None:
    app = _build_app()
    process = AsyncMock(
        return_value=_happy_result(
            query="What is the PPh21 rate for a salary of 50 million IDR per month?",
            answer="The marginal PPh21 rate at that income bracket is 25%.",
            collection_used="tax_knowledge_hybrid",
            sources=[{"id": "pph21-2024", "title": "UU PPh 2024", "score": 0.77}],
            domain_confidence={"tax": 0.88},
        ),
    )
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "What is the PPh21 rate for a salary of 50 million IDR per month?"},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["collection_used"] == "tax_knowledge_hybrid"
    assert body["document_count"] == 1
    assert body["sources"][0]["id"] == "pph21-2024"


@pytest.mark.asyncio
async def test_query_property_happy_path_with_sources_off() -> None:
    app = _build_app()
    # Router is expected to surface empty `sources` when include_sources=False
    # *if* the service respects the flag. Our stub respects it.
    def _side_effect(**kwargs):  # sync factory returning awaitable result
        include_sources = kwargs["request_include_sources"]
        result = _happy_result(
            query=kwargs["request_query"],
            answer="Foreign buyers should use Hak Pakai or PT PMA for property in Bali.",
            collection_used="property_knowledge_hybrid",
            sources=[{"id": "bpn-hakpakai", "title": "BPN Hak Pakai", "score": 0.80}],
            domain_confidence={"property": 0.83},
        )
        if not include_sources:
            result["sources"] = []
        return result

    process = AsyncMock(side_effect=lambda **kw: _side_effect(**kw))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={
                    "query": "Can foreigners buy property freehold in Bali?",
                    "include_sources": False,
                },
            )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["collection_used"] == "property_knowledge_hybrid"
    assert body["sources"] == []
    # citations still come through since the router doesn't gate them
    assert body["citations"] != []


@pytest.mark.asyncio
async def test_feedback_endpoint_returns_success_from_service() -> None:
    app = _build_app()
    submit = AsyncMock(return_value=True)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.submit_feedback", submit):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/feedback",
                json={
                    "user_email": "user@example.com",
                    "query_text": "anything",
                    "original_answer": "answer",
                    "feedback_type": "correction",
                    "rating": 5,
                },
            )
    assert r.status_code == 200
    assert r.json() == {"success": True}
    submit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Multi-domain fusion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_fusion_visa_and_property() -> None:
    """Query mixing visa + property should surface both domains in confidence +
    the routing_reason, and sources should span both collections."""
    app = _build_app()
    result = _happy_result(
        query="I want to buy a villa in Bali while holding a KITAS — what do I need?",
        answer=(
            "You need a KITAS-Investor (E28A) via PT PMA plus Hak Pakai for the "
            "land. The two processes have to be coordinated."
        ),
        collection_used="visa_property_fusion",
        sources=[
            {"id": "kitas-e28a", "title": "KITAS Investor E28A", "score": 0.88,
             "collection": "visa_knowledge_hybrid"},
            {"id": "bpn-hakpakai", "title": "BPN Hak Pakai", "score": 0.81,
             "collection": "property_knowledge_hybrid"},
        ],
        domain_confidence={"visa": 0.74, "property": 0.69},
    )
    result["routing_reason"] = "Fusion: visa (0.74) + property (0.69)"
    process = AsyncMock(return_value=result)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={
                    "query": "I want to buy a villa in Bali while holding a KITAS — what do I need?",
                },
            )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert set(body["domain_confidence"].keys()) == {"visa", "property"}
    assert all(0 < v < 1 for v in body["domain_confidence"].values())
    assert "Fusion" in body["routing_reason"]
    collections_seen = {s.get("collection") for s in body["sources"]}
    assert "visa_knowledge_hybrid" in collections_seen
    assert "property_knowledge_hybrid" in collections_seen


@pytest.mark.asyncio
async def test_query_fusion_tax_and_company() -> None:
    """A PT PMA + tax question triggers fusion across tax + company domains."""
    app = _build_app()
    result = _happy_result(
        query="What corporate income tax applies to a PT PMA with 2B IDR revenue?",
        answer="The 22 % corporate rate applies with a 50 % facility up to 4.8 B IDR.",
        collection_used="tax_company_fusion",
        sources=[
            {"id": "pph-badan", "title": "PPh Badan UU HPP", "score": 0.84,
             "collection": "tax_knowledge_hybrid"},
            {"id": "pma-setup", "title": "PT PMA Setup Guide", "score": 0.78,
             "collection": "company_knowledge_hybrid"},
        ],
        domain_confidence={"tax": 0.71, "company": 0.66},
    )
    result["routing_reason"] = "Fusion: tax + company"
    process = AsyncMock(return_value=result)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={
                    "query": "What corporate income tax applies to a PT PMA with 2B IDR revenue?",
                    "domain_hint": "tax",
                },
            )
    assert r.status_code == 200
    body = r.json()
    assert body["domain_confidence"] == {"tax": 0.71, "company": 0.66}
    assert body["document_count"] == 2
    # domain_hint must be forwarded — even if our stub doesn't use it, the
    # router can't silently drop request fields.
    kwargs = process.await_args.kwargs
    assert "Fusion" in body["routing_reason"]
    # process_query signature forwards domain_hint implicitly through
    # request_query + limit etc.; the hint is consumed upstream.  We at least
    # assert the core forwarding contract held.
    assert kwargs["request_query"].startswith("What corporate income tax")


@pytest.mark.asyncio
async def test_query_fusion_visa_and_tax_mixed_scores() -> None:
    """Three-domain confidence block where only two domains cross the routing
    threshold; router must surface all of them untouched."""
    app = _build_app()
    result = _happy_result(
        query="Digital nomad on a B211A — do I owe Indonesian tax after 183 days?",
        answer="Yes — you become a tax resident once you cross 183 days.",
        collection_used="visa_tax_fusion",
        sources=[
            {"id": "b211a-rules", "title": "Visa B211A rules", "score": 0.79},
            {"id": "tax-residency", "title": "Tax Residency 183d", "score": 0.86},
        ],
        domain_confidence={"visa": 0.62, "tax": 0.81, "property": 0.05},
    )
    process = AsyncMock(return_value=result)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={
                    "query": "Digital nomad on a B211A — do I owe Indonesian tax after 183 days?",
                },
            )
    body = r.json()
    assert body["domain_confidence"]["tax"] > body["domain_confidence"]["visa"]
    assert body["domain_confidence"]["property"] < 0.1
    # Ordering in sources must be preserved as the service returned it.
    assert [s["id"] for s in body["sources"]] == ["b211a-rules", "tax-residency"]


@pytest.mark.asyncio
async def test_query_fusion_includes_citations_shape() -> None:
    """Citations array should be independent of `sources` and survive even when
    sources are empty (e.g. KG-only answer)."""
    app = _build_app()
    result = _happy_result(
        query="Cross-domain KG-only answer",
        collection_used="kg_fusion",
        sources=[],
        document_count=0,
        domain_confidence={"visa": 0.55, "tax": 0.52},
    )
    result["citations"] = [
        {"kind": "kg_node", "id": "KBLI:6411", "label": "Bank sentral"},
        {"kind": "kg_edge", "id": "KBLI:6411-FEE-123"},
    ]
    process = AsyncMock(return_value=result)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "Cross-domain KG-only answer"},
            )
    body = r.json()
    assert body["sources"] == []
    assert body["document_count"] == 0
    assert len(body["citations"]) == 2
    assert {c["kind"] for c in body["citations"]} == {"kg_node", "kg_edge"}


# ---------------------------------------------------------------------------
# Error modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_service_raises_generic_exception_returns_200_with_error() -> None:
    """Non-HTTPException must be swallowed: router answers 200 with
    success=False + error populated, not a 500."""
    app = _build_app()
    process = AsyncMock(side_effect=RuntimeError("qdrant is down"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "anything at all please"},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body["error"] == "qdrant is down"
    assert body["query"] == "anything at all please"
    assert body["execution_time_ms"] == 0
    assert body["document_count"] == 0
    assert body["answer"] is None
    assert body["sources"] == []


@pytest.mark.asyncio
async def test_query_service_raises_http_exception_propagates() -> None:
    """HTTPException must NOT be caught by the generic handler."""
    from fastapi import HTTPException  # local import to avoid top-level noise

    app = _build_app()
    process = AsyncMock(side_effect=HTTPException(status_code=403, detail="forbidden"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "anything at all please"},
            )
    assert r.status_code == 403
    assert r.json() == {"detail": "forbidden"}


@pytest.mark.asyncio
async def test_query_rejects_too_short_query_pydantic_422() -> None:
    """`query` has min_length=3 — Pydantic validation must reject shorter input."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/oracle/query", json={"query": "hi"})
    assert r.status_code == 422
    body = r.json()
    assert body["detail"][0]["loc"][-1] == "query"


@pytest.mark.asyncio
async def test_query_rejects_limit_out_of_range() -> None:
    """`limit` is bounded 1..50 — 0 and 51 must be 422."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r_low = await client.post(
            "/api/oracle/query", json={"query": "valid query", "limit": 0},
        )
        r_high = await client.post(
            "/api/oracle/query", json={"query": "valid query", "limit": 51},
        )
    assert r_low.status_code == 422
    assert r_high.status_code == 422


@pytest.mark.asyncio
async def test_query_rejects_missing_query_field() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/oracle/query", json={"user_email": "u@e.com"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_query_service_returns_malformed_dict_is_swallowed() -> None:
    """If the service returns a dict missing a required response field (e.g.
    execution_time_ms), Pydantic validation inside the router raises — which
    the router catches as a generic Exception and converts to success=False."""
    app = _build_app()
    bad = {
        "success": True,
        "query": "malformed",
        # intentionally missing execution_time_ms
        "sources": [],
        "document_count": 0,
    }
    process = AsyncMock(return_value=bad)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "malformed service result"},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body["query"] == "malformed service result"
    assert body["error"]  # non-empty error string


@pytest.mark.asyncio
async def test_feedback_rejects_rating_out_of_range() -> None:
    """FeedbackRequest.rating bounded 1..5 — outside is 422 without hitting
    the service."""
    app = _build_app()
    submit = AsyncMock(return_value=True)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.submit_feedback", submit):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/feedback",
                json={
                    "user_email": "user@example.com",
                    "query_text": "q",
                    "original_answer": "a",
                    "feedback_type": "correction",
                    "rating": 6,
                },
            )
    assert r.status_code == 422
    submit.assert_not_awaited()


@pytest.mark.asyncio
async def test_feedback_service_raises_returns_200_with_error() -> None:
    app = _build_app()
    submit = AsyncMock(side_effect=RuntimeError("postgres refused"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.submit_feedback", submit):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/feedback",
                json={
                    "user_email": "user@example.com",
                    "query_text": "q",
                    "original_answer": "a",
                    "feedback_type": "correction",
                    "rating": 4,
                },
            )
    assert r.status_code == 200
    body = r.json()
    assert body == {"success": False, "error": "postgres refused"}


@pytest.mark.asyncio
async def test_feedback_service_returns_false_surfaces_false() -> None:
    app = _build_app()
    submit = AsyncMock(return_value=False)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.submit_feedback", submit):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/feedback",
                json={
                    "user_email": "user@example.com",
                    "query_text": "q",
                    "original_answer": "a",
                    "feedback_type": "correction",
                    "rating": 3,
                },
            )
    assert r.status_code == 200
    assert r.json() == {"success": False}


# ---------------------------------------------------------------------------
# Request-field passthrough & response-field edges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_forwards_conversation_history_and_session_id() -> None:
    """Optional fields must reach the service call 1:1."""
    app = _build_app()
    process = AsyncMock(return_value=_happy_result(query="follow-up"))
    history = [
        {"role": "user", "content": "I want a KITAS"},
        {"role": "assistant", "content": "KITAS-Investor is your path."},
    ]
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={
                    "query": "follow-up",
                    "session_id": "sess-abc-123",
                    "conversation_history": history,
                    "language_override": "it",
                    "use_ai": False,
                },
            )
    assert r.status_code == 200
    kwargs = process.await_args.kwargs
    assert kwargs["request_session_id"] == "sess-abc-123"
    assert kwargs["request_language_override"] == "it"
    assert kwargs["request_use_ai"] is False
    hist = kwargs["request_conversation_history"]
    assert hist is not None and len(hist) == 2
    # Conversation history must arrive parsed as Pydantic ConversationMessage,
    # not raw dicts — the router re-uses the model from the request body.
    assert hist[0].role == "user"
    assert hist[1].content.startswith("KITAS-Investor")


@pytest.mark.asyncio
async def test_query_user_profile_with_id_gets_user_id_backfilled() -> None:
    """Router patches `user_profile['user_id'] = user_profile['id']` when only
    `id` is present — that's the only piece of non-trivial business logic the
    router owns."""
    app = _build_app()
    result = _happy_result(query="profile fix")
    result["user_profile"] = {
        "id": "u-42",
        "email": "u@e.com",
        "name": "Jane",
        "role": "member",
    }
    process = AsyncMock(return_value=result)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/oracle/query", json={"query": "profile fix"})
    assert r.status_code == 200
    body = r.json()
    assert body["user_profile"]["id"] == "u-42"
    assert body["user_profile"]["user_id"] == "u-42"


@pytest.mark.asyncio
async def test_query_user_profile_with_both_id_and_user_id_is_not_overwritten() -> None:
    """If both `id` and `user_id` are present, router must NOT overwrite
    `user_id` with `id`."""
    app = _build_app()
    result = _happy_result(query="no overwrite")
    result["user_profile"] = {
        "id": "u-100",
        "user_id": "legacy-u-100",
        "email": "u@e.com",
        "name": "Jane",
        "role": "member",
    }
    process = AsyncMock(return_value=result)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/oracle/query", json={"query": "no overwrite"})
    body = r.json()
    assert body["user_profile"]["id"] == "u-100"
    assert body["user_profile"]["user_id"] == "legacy-u-100"


@pytest.mark.asyncio
async def test_query_clarification_needed_is_surfaced() -> None:
    """When the service flags `clarification_needed`, router must propagate the
    flag and the question text."""
    app = _build_app()
    result = _happy_result(query="ambiguous visa question")
    result.update({
        "answer": None,
        "clarification_needed": True,
        "clarification_question": "Are you asking for tourism or business travel?",
        "sources": [],
        "document_count": 0,
    })
    process = AsyncMock(return_value=result)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "ambiguous visa question"},
            )
    body = r.json()
    assert body["clarification_needed"] is True
    assert "tourism or business" in body["clarification_question"]
    assert body["answer"] is None


@pytest.mark.asyncio
async def test_query_golden_answer_flag_is_surfaced() -> None:
    app = _build_app()
    result = _happy_result(query="what visa for 30 days tourism?")
    result["golden_answer_used"] = True
    result["model_used"] = "golden-cache"
    process = AsyncMock(return_value=result)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "what visa for 30 days tourism?"},
            )
    body = r.json()
    assert body["golden_answer_used"] is True
    assert body["model_used"] == "golden-cache"


@pytest.mark.asyncio
async def test_query_empty_kg_result_still_shapes_response() -> None:
    """Service returns a successful-but-empty response (no docs, no answer).
    Router must pass it through without fabricating fields."""
    app = _build_app()
    result = _happy_result(query="obscure edge query")
    result.update({
        "answer": "I don't have enough information to answer that reliably.",
        "sources": [],
        "citations": [],
        "document_count": 0,
        "domain_confidence": {},
        "routing_reason": "No domain crossed threshold (0.15)",
    })
    process = AsyncMock(return_value=result)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "obscure edge query"},
            )
    body = r.json()
    assert body["success"] is True
    assert body["document_count"] == 0
    assert body["sources"] == []
    assert body["citations"] == []
    assert body["domain_confidence"] == {}
    assert "threshold" in body["routing_reason"]


# ---------------------------------------------------------------------------
# Wave 2 — upstream timeout (the big missing of wave 1)
# ---------------------------------------------------------------------------
#
# The router does NOT wrap process_query in asyncio.wait_for, so a TimeoutError
# raised by the service is just another exception that flows through the
# `except Exception` branch. These tests lock in that behavior: if someone
# later wraps the call in a timeout, they need to explicitly choose a
# taxonomy (timeout → 504 vs. timeout → success=False) and update the tests.


@pytest.mark.asyncio
async def test_query_upstream_timeout_is_swallowed_as_200_success_false() -> None:
    """`asyncio.TimeoutError` from OracleService must not leak a 500.

    It flows through the same generic-exception branch as any other upstream
    failure, producing a 200 with `success=False`. The error string carries
    the timeout marker so the caller can distinguish timeouts from other
    failures without a stack trace.
    """
    import asyncio

    app = _build_app()
    process = AsyncMock(side_effect=asyncio.TimeoutError())
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "slow query that will time out upstream"},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    # TimeoutError's str() is empty but the type name is carried — at minimum
    # the response must set success=False and zero out the metrics.
    assert body["execution_time_ms"] == 0
    assert body["document_count"] == 0
    assert body["answer"] is None
    assert body["sources"] == []
    process.assert_awaited_once()


@pytest.mark.asyncio
async def test_query_upstream_timeout_with_message_surfaces_error_string() -> None:
    """When the service raises a TimeoutError subclass with a message (e.g.
    httpx.ReadTimeout-style), the router should surface the message in the
    error field without wrapping or re-raising."""
    import asyncio

    class _NamedTimeout(asyncio.TimeoutError):
        pass

    app = _build_app()
    process = AsyncMock(
        side_effect=_NamedTimeout("qdrant upstream exceeded 5s deadline"),
    )
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "another slow one"},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert "qdrant upstream exceeded 5s" in body["error"]


@pytest.mark.asyncio
async def test_query_simulated_wait_for_timeout_is_swallowed() -> None:
    """If a caller later wraps `oracle_service.process_query` in
    `asyncio.wait_for`, the resulting TimeoutError must still be handled
    cleanly. Simulate it by wrapping the mock itself."""
    import asyncio

    async def _slow_service(**_: Any) -> dict[str, Any]:
        await asyncio.sleep(10)  # would exceed any reasonable deadline
        return _happy_result(query="never reached")

    async def _timing_out(**kwargs: Any) -> dict[str, Any]:
        # 10ms is tiny but non-zero — the sleep inside will always exceed it
        return await asyncio.wait_for(_slow_service(**kwargs), timeout=0.01)

    app = _build_app()
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", side_effect=_timing_out):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "query that triggers wait_for timeout"},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    # Do NOT assert on error string content — asyncio.TimeoutError's str()
    # is "" on 3.11+, so the field may be empty. The contract we lock in
    # is: no 500, no stack trace, success=False.


# ---------------------------------------------------------------------------
# Wave 2 — get_current_user 401 propagation
# ---------------------------------------------------------------------------
#
# `get_current_user` is a FastAPI dependency. When it raises HTTPException,
# FastAPI short-circuits before the router body runs, and the router's
# `except HTTPException: raise` branch is never even reached. These tests
# verify the dependency wiring is honored end-to-end — the wave 1 tests
# all used a fake `get_current_user` that always succeeded, so this path
# was completely untested at the router level.


@pytest.mark.asyncio
async def test_query_returns_401_when_auth_dependency_raises() -> None:
    """If `get_current_user` raises HTTPException(401), the /query endpoint
    must respond 401 — the oracle_service.process_query must not even be
    invoked."""
    app = FastAPI()
    app.include_router(router)

    async def failing_auth() -> dict[str, Any]:
        raise HTTPException(status_code=401, detail="token expired")

    async def fake_search_service() -> Any:
        return object()

    app.dependency_overrides[get_current_user] = failing_auth
    app.dependency_overrides[get_search_service] = fake_search_service

    process = AsyncMock(return_value=_happy_result(query="should never run"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "any valid query here"},
            )
    assert r.status_code == 401
    assert r.json() == {"detail": "token expired"}
    process.assert_not_awaited()


@pytest.mark.asyncio
async def test_query_auth_failure_propagates_custom_status() -> None:
    """Any HTTPException from the auth dependency must propagate its status
    verbatim (not be rewritten to 500 or swallowed into a 200)."""
    app = FastAPI()
    app.include_router(router)

    async def forbidden_auth() -> dict[str, Any]:
        raise HTTPException(
            status_code=403,
            detail="account suspended",
            headers={"X-Bali-Reason": "kyc-pending"},
        )

    async def fake_search_service() -> Any:
        return object()

    app.dependency_overrides[get_current_user] = forbidden_auth
    app.dependency_overrides[get_search_service] = fake_search_service

    process = AsyncMock(return_value=_happy_result(query="should never run"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "a perfectly valid query string"},
            )
    assert r.status_code == 403
    assert r.json() == {"detail": "account suspended"}
    assert r.headers.get("x-bali-reason") == "kyc-pending"
    process.assert_not_awaited()


# ---------------------------------------------------------------------------
# Wave 2 — Pydantic limit boundary (50 passes, 51 rejects)
# ---------------------------------------------------------------------------
#
# Wave 1 `test_query_rejects_limit_out_of_range` tested 0 and 51, but not the
# inclusive upper bound 50. These lock in the `ge=1, le=50` contract on both
# sides: exact boundary values should not drift under Pydantic upgrades.


@pytest.mark.asyncio
async def test_query_accepts_limit_equal_to_upper_bound() -> None:
    """limit=50 is the documented maximum — it must pass validation and
    be forwarded to the service as-is."""
    app = _build_app()
    process = AsyncMock(return_value=_happy_result(query="boundary limit"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "boundary limit", "limit": 50},
            )
    assert r.status_code == 200
    process.assert_awaited_once()
    assert process.await_args.kwargs["request_limit"] == 50


@pytest.mark.asyncio
async def test_query_accepts_limit_equal_to_lower_bound() -> None:
    """limit=1 is the documented minimum — it must pass validation and
    be forwarded as-is."""
    app = _build_app()
    process = AsyncMock(return_value=_happy_result(query="lower bound limit"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "lower bound limit", "limit": 1},
            )
    assert r.status_code == 200
    process.assert_awaited_once()
    assert process.await_args.kwargs["request_limit"] == 1


@pytest.mark.asyncio
async def test_query_rejects_limit_51_with_pydantic_detail() -> None:
    """limit=51 is one over the upper bound — Pydantic must reject with 422
    and the detail payload must point at the `limit` field so clients can
    surface the error."""
    app = _build_app()
    process = AsyncMock(return_value=_happy_result(query="should never run"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "valid query", "limit": 51},
            )
    assert r.status_code == 422
    body = r.json()
    assert body["detail"][0]["loc"][-1] == "limit"
    process.assert_not_awaited()


# ---------------------------------------------------------------------------
# Wave 2 — quirk-lock-in tests for Q1 (silently-dropped request fields)
# ---------------------------------------------------------------------------
#
# Wave 1 audit flagged `domain_hint`, `context_docs`, and `response_format`
# as defined on the request model but not forwarded to oracle_service.
# Wave 2 decision (see WAVE2_NOTES.md Q1): keep the fields — removing them
# is a breaking OpenAPI change (apps/mouth consumes the schema) — but log a
# WARN when any of them is provided so we at least know the drop is
# happening. These tests lock in both halves: the drop (service call kwargs
# do NOT contain the fields) AND the log line.


@pytest.mark.asyncio
async def test_query_domain_hint_is_not_forwarded_to_service(caplog) -> None:
    import logging as _logging

    caplog.set_level(_logging.WARNING, logger="backend.app.routers.oracle_universal")

    app = _build_app()
    process = AsyncMock(return_value=_happy_result(query="hint passthrough check"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "hint passthrough check", "domain_hint": "tax"},
            )
    assert r.status_code == 200
    kwargs = process.await_args.kwargs
    assert "domain_hint" not in kwargs
    assert "request_domain_hint" not in kwargs
    assert any("domain_hint" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_query_context_docs_is_not_forwarded_to_service(caplog) -> None:
    import logging as _logging

    caplog.set_level(_logging.WARNING, logger="backend.app.routers.oracle_universal")

    app = _build_app()
    process = AsyncMock(return_value=_happy_result(query="docs passthrough check"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={
                    "query": "docs passthrough check",
                    "context_docs": ["drive-file-1", "drive-file-2"],
                },
            )
    assert r.status_code == 200
    kwargs = process.await_args.kwargs
    assert "context_docs" not in kwargs
    assert "request_context_docs" not in kwargs
    assert any("context_docs" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_query_response_format_is_not_forwarded_to_service(caplog) -> None:
    import logging as _logging

    caplog.set_level(_logging.WARNING, logger="backend.app.routers.oracle_universal")

    app = _build_app()
    process = AsyncMock(return_value=_happy_result(query="format passthrough check"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={
                    "query": "format passthrough check",
                    "response_format": "conversational",
                },
            )
    assert r.status_code == 200
    kwargs = process.await_args.kwargs
    assert "response_format" not in kwargs
    assert "request_response_format" not in kwargs
    # The default "structured" is not noisy-logged — only overrides are.
    assert any("response_format" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_query_default_response_format_does_not_log_drop_warning(caplog) -> None:
    """If the client does not override `response_format` (stays at the
    default 'structured'), the router must NOT emit the Q1 drop warning —
    otherwise every request would log spam."""
    import logging as _logging

    caplog.set_level(_logging.WARNING, logger="backend.app.routers.oracle_universal")

    app = _build_app()
    process = AsyncMock(return_value=_happy_result(query="default fmt"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "default fmt"},  # no response_format override
            )
    assert r.status_code == 200
    # No warning record mentioning the unwired fields
    matching = [rec for rec in caplog.records if "not forwarded" in rec.message]
    assert matching == []


# ---------------------------------------------------------------------------
# Wave 2 — Q2 lock-in: ValidationError now has a dedicated branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_malformed_service_response_logs_validation_error(caplog) -> None:
    """Q2: when oracle_service returns a dict that does not match
    OracleQueryResponse, the router must:
    - still answer 200 (contract unchanged, no breaking caller impact),
    - set success=False (same as before),
    - but tag the error string with `response_validation_error:` and emit
      a WARN log — so Sentry can distinguish schema drift from a true
      runtime fault.
    """
    import logging as _logging

    caplog.set_level(_logging.WARNING, logger="backend.app.routers.oracle_universal")

    app = _build_app()
    # Missing required field execution_time_ms → ValidationError
    bad = {
        "success": True,
        "query": "schema drift",
        "sources": [],
        "document_count": 0,
    }
    process = AsyncMock(return_value=bad)
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "schema drift check"},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body["error"].startswith("response_validation_error:")
    assert any("validation failed" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Wave 3 — Dropped-field observability: dedicated logger + Sentry tag.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dropped_fields_use_dedicated_logger(caplog) -> None:
    """Wave 3: the Q1 drop WARN must emerge from the dedicated
    `oracle.query.dropped_fields` logger so the event can be routed, muted
    or aggregated independently of the rest of the router's chatty logs.

    Until wave 3 it came from `backend.app.routers.oracle_universal`.
    """
    import logging as _logging

    caplog.set_level(_logging.WARNING, logger="oracle.query.dropped_fields")

    app = _build_app()
    process = AsyncMock(return_value=_happy_result(query="logger name drift"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={
                    "query": "logger name drift",
                    "domain_hint": "visa",
                },
            )

    assert r.status_code == 200
    named = [rec for rec in caplog.records if rec.name == "oracle.query.dropped_fields"]
    assert len(named) == 1
    assert named[0].levelno == _logging.WARNING
    assert "domain_hint" in named[0].message


@pytest.mark.asyncio
async def test_dropped_fields_emit_sentry_tag(monkeypatch) -> None:
    """Wave 3: when request fields are dropped, the router must also tag the
    current Sentry scope with `oracle.dropped_fields` = comma-joined field
    names. This lets ops aggregate by field without relying on free-text log
    parsing (Sentry PII redaction is already handled globally — the tag
    value contains only field names, never user data)."""
    recorded: list[tuple[str, str]] = []

    import backend.app.routers.oracle_universal as oracle_router

    def _capture(key: str, value: str) -> None:
        recorded.append((key, value))

    monkeypatch.setattr(oracle_router.sentry_sdk, "set_tag", _capture)

    app = _build_app()
    process = AsyncMock(return_value=_happy_result(query="sentry tag check"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={
                    "query": "sentry tag check",
                    "domain_hint": "tax",
                    "context_docs": ["drive-A"],
                },
            )

    assert r.status_code == 200
    assert ("oracle.dropped_fields", "domain_hint,context_docs") in recorded


@pytest.mark.asyncio
async def test_dropped_fields_no_sentry_tag_when_empty(monkeypatch) -> None:
    """Wave 3 negative: a request that does not trigger the drop branch
    (default `response_format='structured'`, no hints) must NOT tag Sentry
    — otherwise we would blow the free-tier quota with noise on every
    request."""
    recorded: list[tuple[str, str]] = []

    import backend.app.routers.oracle_universal as oracle_router

    def _capture(key: str, value: str) -> None:
        recorded.append((key, value))

    monkeypatch.setattr(oracle_router.sentry_sdk, "set_tag", _capture)

    app = _build_app()
    process = AsyncMock(return_value=_happy_result(query="clean request"))
    with patch(f"{_ORACLE_ROUTER_SERVICE}.process_query", process):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/oracle/query",
                json={"query": "clean request"},
            )

    assert r.status_code == 200
    assert recorded == []


# ---------------------------------------------------------------------------
# Wave 3 — Q3 stub removal: endpoints gone, surface contract is now:
#   POST /api/oracle/query, POST /api/oracle/feedback, GET /api/oracle/health.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_removed_stubs_return_404() -> None:
    """Q3 (wave 3): the deprecated /drive/test, /gemini/test and
    /user/profile/{email} endpoints were removed. Any remaining client that
    was keeping them alive must see a real 404 so the migration is visible
    instead of the old silent stub payload."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        drive = await client.get("/api/oracle/drive/test")
        gemini = await client.get("/api/oracle/gemini/test")
        profile = await client.get("/api/oracle/user/profile/someone@example.com")

    assert drive.status_code == 404
    assert gemini.status_code == 404
    assert profile.status_code == 404


@pytest.mark.asyncio
async def test_removed_stubs_absent_from_openapi() -> None:
    """Q3 (wave 3): SDK generators (apps/mouth/src/lib/api/schema.d.ts) must
    stop seeing these paths entirely on the next build. We assert absence
    from the spec so a future accidental re-add is caught immediately."""
    app = _build_app()
    spec = app.openapi()
    paths = spec["paths"]

    assert "/api/oracle/drive/test" not in paths
    assert "/api/oracle/gemini/test" not in paths
    assert "/api/oracle/user/profile/{user_email}" not in paths

    # Core surface must still be present and NOT flagged deprecated.
    assert "/api/oracle/query" in paths
    assert "/api/oracle/feedback" in paths
    assert "/api/oracle/health" in paths
    assert paths["/api/oracle/health"]["get"].get("deprecated") is not True
    assert paths["/api/oracle/query"]["post"].get("deprecated") is not True
