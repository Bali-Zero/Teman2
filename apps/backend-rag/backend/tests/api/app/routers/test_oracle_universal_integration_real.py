"""
Wave 3 — narrow integration tests for /api/oracle/query against the REAL
OracleService.

Unlike wave 2 (which patches `oracle_service.process_query` wholesale), these
exercise the real `OracleService.process_query` adapter: real
UserContextService (no profile branch), real LanguageDetectionService, real
OracleAnalyticsService.build_analytics_data. Only the two network-heavy
boundaries are stubbed:

1. `OracleService._get_orchestrator` — otherwise it would call
   `create_agentic_rag` which needs a live asyncpg pool + Qdrant + an LLM.
2. `OracleService.analytics.store_query_analytics` — otherwise it opens a
   real asyncpg connection.

Everything between those two boundaries runs for real. This is the "narrow
integration" choice (see WAVE3_NOTES.md): not full e2e, but far more code
under test than wave 2's router-only characterization.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.dependencies import get_current_user, get_search_service
from backend.app.routers.oracle_universal import router
from backend.services.oracle.oracle_service import oracle_service
from backend.services.rag.agentic.schema import CoreResult


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _build_app() -> FastAPI:
    """Mount the real oracle_universal router with stubbed FastAPI deps.

    The dependency overrides are minimal — auth and search_service are
    bypassed because the real OracleService does not consume search_service
    in its own code path (it's passed to the orchestrator, which is stubbed).
    """
    app = FastAPI()
    app.include_router(router)

    async def fake_current_user() -> dict[str, Any]:
        return {"email": "user@example.com", "role": "member"}

    async def fake_search_service() -> Any:
        return object()

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_search_service] = fake_search_service
    return app


def _core_result(**overrides: Any) -> CoreResult:
    """Build a CoreResult with sensible defaults for happy-path assertions."""
    defaults: dict[str, Any] = {
        "answer": "PT PMA requires a minimum capital of IDR 10 billion.",
        "sources": [
            {"id": "doc-1", "title": "BKPM Reg 4/2021", "score": 0.81},
            {"id": "doc-2", "title": "KBLI 47711", "score": 0.77},
            {"id": "doc-3", "title": "PMA guide", "score": 0.74},
        ],
        "model_used": "gemini-2.5-flash",
        "collection_used": "company_knowledge_hybrid",
        "document_count": 3,
        "is_ambiguous": False,
        "clarification_question": None,
        # Note: CoreResult.timings is typed dict[str, float] so we cannot
        # stuff a `domain_scores` sub-dict here (the oracle adapter reads it
        # with `.get("domain_scores", {})` — a latent type drift flagged in
        # WAVE3_NOTES.md). We leave `timings` as floats only and let the
        # adapter fall back to the default empty domain_confidence.
        "timings": {"total": 0.123},
    }
    defaults.update(overrides)
    return CoreResult(**defaults)


class _FakeOrchestrator:
    """Minimal duck-typed stand-in for AgenticRAGOrchestrator.

    We only need the `process_query` coroutine and the `entity_extractor`
    attribute that the real OracleService injects.
    """

    def __init__(self, result: CoreResult) -> None:
        self._result = result
        self.entity_extractor: Any = None
        self.process_query = AsyncMock(return_value=result)


@pytest.fixture
def fake_orchestrator_factory():
    """Return a callable that installs a _FakeOrchestrator on oracle_service
    for the duration of the test and reverts state afterwards."""
    def _factory(result: CoreResult) -> _FakeOrchestrator:
        fake = _FakeOrchestrator(result)

        async def _return_fake(_search_service: Any) -> _FakeOrchestrator:
            return fake

        # Patch the bound coroutine on the singleton. We intentionally touch
        # the module-level oracle_service so the router under test reaches
        # through the real adapter and hits our fake at the orchestrator
        # boundary only.
        orchestrator_patch = patch.object(
            oracle_service, "_get_orchestrator", side_effect=_return_fake,
        )
        analytics_patch = patch.object(
            oracle_service.analytics,
            "store_query_analytics",
            new=AsyncMock(return_value=None),
        )
        orchestrator_patch.start()
        analytics_patch.start()
        # Also reset cached orchestrator so subsequent tests can re-patch.
        oracle_service._orchestrator = None  # noqa: SLF001
        fake._orchestrator_patch = orchestrator_patch  # type: ignore[attr-defined]
        fake._analytics_patch = analytics_patch  # type: ignore[attr-defined]
        return fake

    yield _factory


@pytest.fixture(autouse=True)
def _reset_oracle_service_state():
    """Reset mutable state on the module-level singleton between tests so
    patches from a previous test don't leak."""
    # Snapshot the values we touch.
    original_orchestrator = oracle_service._orchestrator
    original_db_pool = oracle_service._db_pool
    yield
    # Stop any patches installed by the factory.
    patches = (
        getattr(oracle_service, "__wave3_patches__", None) or []
    )
    for p in patches:
        try:
            p.stop()
        except RuntimeError:
            pass
    # Also stop patches that were attached directly to a _FakeOrchestrator
    # (factory path). They store themselves on the fake, not on the service,
    # so we rely on unittest.mock's global registry via patch.stopall.
    patch.stopall()
    oracle_service._orchestrator = original_orchestrator  # noqa: SLF001
    oracle_service._db_pool = original_db_pool  # noqa: SLF001


# ---------------------------------------------------------------------------
# Test 1 — happy path, English query, no user_email
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_service_happy_path_english_anonymous(fake_orchestrator_factory):
    """The real adapter without a user_email must:
    - return success=True
    - forward the orchestrator's answer, sources and collection
    - resolve language to English (no Italian/Indonesian markers in query)
    - mark user_profile=None (no lookup without email)
    - produce a Pydantic-valid response dict (no 422).
    """
    result = _core_result()
    fake_orchestrator_factory(result)

    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/oracle/query",
            json={"query": "What is the minimum capital for PT PMA in Indonesia?"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["answer"] == result.answer
    assert body["collection_used"] == "company_knowledge_hybrid"
    assert body["document_count"] == 3
    assert body["answer_language"] == "en"
    assert body["language_detected"] == "en"
    assert body["user_profile"] is None


# ---------------------------------------------------------------------------
# Test 2 — Italian query exercises the language detector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_service_italian_query_detected_as_it(fake_orchestrator_factory):
    """A query rich in Italian markers must be detected as `it` by the real
    LanguageDetectionService (this would silently regress if we kept
    patching process_query)."""
    fake_orchestrator_factory(_core_result())

    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/oracle/query",
            json={
                "query": (
                    "Vorrei aprire una PT PMA: quali sono i documenti necessari "
                    "e quanto costa la pratica?"
                ),
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["answer_language"] == "it"
    assert body["language_detected"] == "it"


# ---------------------------------------------------------------------------
# Test 3 — language_override short-circuits detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_service_language_override_wins(fake_orchestrator_factory):
    """An explicit language_override must be honoured by the real language
    detector even when the query body is English."""
    fake_orchestrator_factory(_core_result())

    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/oracle/query",
            json={
                "query": "What is the minimum capital for PT PMA?",
                "language_override": "id",
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["answer_language"] == "id"
    assert body["language_detected"] == "id"


# ---------------------------------------------------------------------------
# Test 4 — orchestrator reports ambiguity → router surfaces clarification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_service_surfaces_clarification(fake_orchestrator_factory):
    """When the orchestrator flags the query as ambiguous, the real adapter
    must propagate `clarification_needed=True` and the clarification text
    into the router response."""
    result = _core_result(
        is_ambiguous=True,
        clarification_question="Do you mean a local PT or a foreign-owned PT PMA?",
    )
    fake_orchestrator_factory(result)

    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/oracle/query", json={"query": "Start a PT."})

    assert r.status_code == 200
    body = r.json()
    assert body["clarification_needed"] is True
    assert body["clarification_question"] == (
        "Do you mean a local PT or a foreign-owned PT PMA?"
    )


# ---------------------------------------------------------------------------
# Test 5 — `golden` in model_used flips the golden_answer_used flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_service_golden_marker_sets_flag(fake_orchestrator_factory):
    """When the orchestrator returns a model_used containing `golden`, the
    real adapter must set `golden_answer_used=True`. This is the contract
    apps/mouth relies on to badge cached golden answers."""
    result = _core_result(model_used="golden-cache-v1", answer="Cached golden answer")
    fake_orchestrator_factory(result)

    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/oracle/query",
            json={"query": "How much is KITAS extension?"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["golden_answer_used"] is True
    assert body["model_used"] == "golden-cache-v1"
