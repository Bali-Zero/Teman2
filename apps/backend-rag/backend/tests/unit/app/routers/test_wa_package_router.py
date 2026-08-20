"""BOT-V4 S2 (D2/D4): the wa-package router — thin wiring test.

The deterministic pipeline itself (domain gate, retrieval, caps, hashing) is
covered exhaustively in
`backend/tests/unit/services/rag/agentic/test_wa_package_builder.py`. This
file only proves the router's OWN jobs: (1) it acquires the retriever and
calls the D3 curated-QA wrapper off the injected orchestrator, never a
new/duplicated dependency; (2) it translates `PackageUnbuildable` into the
`{"unbuildable": reason}` HTTP-200 shape instead of letting the exception
propagate as a 500 — an unbuildable intent is a ROUTE decision for the
worker, not a server error; (3) S2 cross-family review round: the
`require_internal_caller` scope gate (finding 7 — fail-closed, guilt AND
innocence, plus the armed-check that the route actually carries it: a
dependency that exists but is not wired is suspended, not alive — scar
family #2); (4) transport bounds on history entries (finding 8 — an
annotation caps nothing, `Field(max_length=...)` does); (5) the GREETING
cost guard (finding 9 — no embedding+Qdrant spend on a query the builder is
about to declare unbuildable).
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError

from backend.app.routers.wa_package import (
    WaPackageBuildRequest,
    WaPackageBuildResponse,
    build_wa_package,
    require_internal_caller,
    router,
)


class FakeRetriever:
    async def hybrid_search(
        self,
        *,
        query: str,
        user_level: int,
        limit: int,
        collection_override: str,
        fallback_to_plain: bool = True,
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


def _request_with_user(user: Any) -> SimpleNamespace:
    """The middleware contract this router reads: `request.state.user`
    (set by HybridAuthMiddleware after a successful authentication)."""
    return SimpleNamespace(state=SimpleNamespace(user=user))


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
        assert response.package_wire
        assert response.package_hash
        # S2 adversarial gate round 2, finding 1: the top-level evidence_inputs
        # copy was struck — an unsealed copy can diverge from the sealed one
        # inside package_wire. Consumers parse evidence_inputs OUT OF the wire.
        assert not hasattr(response, "evidence_inputs")
        # reversal_map (G-P3) is admissible where evidence_inputs was not:
        # it is NOT a copy of sealed content (nothing to diverge from — its
        # whole purpose is to stay OUTSIDE the sealed wire), it travels only
        # build->leg on localhost within Fly, and the router logs nothing of
        # it. Any OTHER new field here still needs this test changed on
        # purpose, with its own rationale.
        assert set(WaPackageBuildResponse.model_fields) == {
            "package_wire",
            "package_hash",
            "unbuildable",
            "reversal_map",
        }

        # Load-bearing: package_hash must cover package_wire's EXACT bytes
        # (mirrors _package_hash/_canonical_wire in wa_package_builder.py —
        # sha256 hex digest over the wire text, no prefix).
        recomputed_hash = hashlib.sha256(response.package_wire.encode("utf-8")).hexdigest()
        assert recomputed_hash == response.package_hash

        # The wire excludes package_hash by design (the hash covers the
        # other 6 fields only — hashing a payload that includes its own
        # hash would be circular).
        wire_payload = json.loads(response.package_wire)
        assert "package_hash" not in wire_payload
        assert set(wire_payload.keys()) == {
            "history",
            "chunks",
            "pricing_block",
            "persona_digest",
            "evidence_inputs",
            "thread_epoch",
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

        assert response.package_wire is None
        assert response.unbuildable == "greeting_domain"

    async def test_greeting_query_never_spends_the_curated_qa_lookup(self) -> None:
        """finding 9 (GUILT): a GREETING query is about to be declared
        unbuildable by the builder's own gate — the router must not pay an
        embedding + a Qdrant search for it first. The visa test above is the
        innocence pair (a buildable domain DOES get the lookup)."""
        orchestrator = FakeOrchestrator()
        request = WaPackageBuildRequest(query="ciao!", history=[], thread_epoch=0)

        await build_wa_package(request, orchestrator=orchestrator)

        assert orchestrator.core.curated_qa_calls == []


class TestRequireInternalCaller:
    """finding 7: authentication is not authorization — any portal JWT
    passes HybridAuthMiddleware, but only the middleware's `internal`
    service identity (X-Internal-Key) or an `admin` may drive this
    internal builder."""

    def test_portal_user_role_is_refused_403(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            require_internal_caller(_request_with_user({"role": "user", "sub": "someone"}))
        assert exc_info.value.status_code == 403

    def test_missing_state_user_is_refused_403_fail_closed(self) -> None:
        """Middleware disabled / unexpected wiring must FAIL CLOSED — a
        missing identity is a refusal, never a pass."""
        with pytest.raises(HTTPException) as exc_info:
            require_internal_caller(SimpleNamespace(state=SimpleNamespace()))
        assert exc_info.value.status_code == 403

    def test_non_dict_user_is_refused_403(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            require_internal_caller(_request_with_user("internal"))
        assert exc_info.value.status_code == 403

    def test_internal_and_admin_roles_pass(self) -> None:
        assert require_internal_caller(_request_with_user({"role": "internal"})) is None
        assert require_internal_caller(_request_with_user({"role": "admin"})) is None

    def test_the_build_route_actually_carries_the_dependency(self) -> None:
        """Armed-check (scar family #2, esiste ≠ armato): a correct guard
        that no route declares protects nothing. The /build route must list
        `require_internal_caller` among its dependencies."""
        build_routes = [
            r
            for r in router.routes
            if isinstance(r, APIRoute) and r.path == "/api/wa-package/build"
        ]
        assert build_routes, "expected the /api/wa-package/build route to exist"
        deps = [d.dependency for d in build_routes[0].dependencies]
        assert require_internal_caller in deps


class TestTransportBounds:
    """finding 8: the history entry fields are bounded at the transport —
    `Field(max_length=...)`, because a bare annotation validates nothing."""

    def test_oversized_history_content_is_rejected_422(self) -> None:
        with pytest.raises(ValidationError):
            WaPackageBuildRequest(
                query="What documents do I need for a KITAS?",
                history=[{"role": "user", "content": "x" * 5000}],
                thread_epoch=0,
            )

    def test_oversized_history_role_is_rejected_422(self) -> None:
        with pytest.raises(ValidationError):
            WaPackageBuildRequest(
                query="What documents do I need for a KITAS?",
                history=[{"role": "r" * 64, "content": "hello"}],
                thread_epoch=0,
            )

    def test_content_at_the_ceiling_is_accepted(self) -> None:
        request = WaPackageBuildRequest(
            query="What documents do I need for a KITAS?",
            history=[{"role": "user", "content": "x" * 4096}],
            thread_epoch=0,
        )
        assert len(request.history) == 1
