"""BOT-V4 S2 (D2/D4): the wa-package router — thin wiring test.

The deterministic pipeline itself (domain gate, retrieval, caps, hashing) is
covered exhaustively in
`backend/tests/unit/services/rag/agentic/test_wa_package_builder.py`. This
file only proves the router's OWN two jobs: (1) it acquires the retriever
and calls the D3 curated-QA wrapper off the injected orchestrator, never a
new/duplicated dependency; (2) it translates `PackageUnbuildable` into the
`{"unbuildable": reason}` HTTP-200 shape instead of letting the exception
propagate as a 500 — an unbuildable intent is a ROUTE decision for the
worker, not a server error.
"""

from __future__ import annotations

from typing import Any

from backend.app.routers.wa_package import (
    WaPackageBuildRequest,
    build_wa_package,
)


class FakeRetriever:
    async def hybrid_search(
        self,
        *,
        query: str,
        user_level: int,
        limit: int,
        collection_override: str,
    ) -> dict[str, Any]:
        return {
            "query": query,
            "results": [
                {"id": "d1", "text": "KITAS requires a sponsor letter.", "score": 0.7},
            ],
            "collection": collection_override,
        }


class FakeCore:
    def __init__(self) -> None:
        self.retriever = FakeRetriever()
        self.curated_qa_calls: list[tuple[str, dict[str, Any] | None]] = []

    async def curated_qa_grounding_block(
        self,
        query: str,
        extracted_entities: dict[str, Any] | None = None,
    ) -> str:
        self.curated_qa_calls.append((query, extracted_entities))
        return ""


class FakeOrchestrator:
    def __init__(self) -> None:
        self.core = FakeCore()


class TestBuildWaPackageRoute:
    async def test_visa_query_returns_package_with_full_allowlist(self) -> None:
        orchestrator = FakeOrchestrator()
        request = WaPackageBuildRequest(
            query="What documents do I need for a KITAS work permit?",
            history=[],
            thread_epoch=0,
        )

        response = await build_wa_package(request, orchestrator=orchestrator)

        assert response.unbuildable is None
        assert response.package is not None
        assert set(response.package.keys()) == {
            "history",
            "chunks",
            "pricing_block",
            "persona_digest",
            "evidence_inputs",
            "thread_epoch",
            "package_hash",
        }
        # The router calls the D3 wrapper off the SAME orchestrator.core it
        # got via Depends(get_orchestrator) — never a second/new retriever.
        assert orchestrator.core.curated_qa_calls
        assert orchestrator.core.curated_qa_calls[0][0] == request.query
        assert orchestrator.core.curated_qa_calls[0][1] == {"domain": "visa"}

    async def test_greeting_query_returns_unbuildable_not_an_error(self) -> None:
        orchestrator = FakeOrchestrator()
        request = WaPackageBuildRequest(query="ciao!", history=[], thread_epoch=0)

        response = await build_wa_package(request, orchestrator=orchestrator)

        assert response.package is None
        assert response.unbuildable == "greeting_domain"
