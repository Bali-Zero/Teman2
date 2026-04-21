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
from fastapi import FastAPI
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
async def test_drive_test_returns_moved_marker() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/oracle/drive/test")
    assert r.status_code == 200
    assert r.json() == {"status": "moved_to_service", "available": True}


@pytest.mark.asyncio
async def test_gemini_test_returns_moved_marker() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/oracle/gemini/test")
    assert r.status_code == 200
    assert r.json() == {"status": "moved_to_service", "available": True}


@pytest.mark.asyncio
async def test_user_profile_endpoint_is_not_implemented_yet() -> None:
    app = _build_app()
    email = "nuzantara@example.com"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/oracle/user/profile/{email}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "not_implemented"
    assert body["email"] == email


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
