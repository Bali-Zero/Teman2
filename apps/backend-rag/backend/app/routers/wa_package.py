"""
WA codex-route package-build endpoint (BOT-V4 S2, D2).

``POST /api/wa-package/build`` — internal-only, RAG process group. Builds
the deterministic ``ContextPackage`` (D1, ``wa_package_builder.py``) for one
WA turn, or reports the query as unbuildable so the caller routes it to the
Gemini leg (spec §2.2, "unclassifiable -> Gemini leg").

Auth: no route-level dependency here by design. ``HybridAuthMiddleware``
(``backend/middleware/hybrid_auth.py``) already fail-closed rejects any
request without a recognized credential (X-API-Key / X-Internal-Key / JWT)
before it reaches this router, and this path is deliberately NOT added to
``PUBLIC_ENDPOINTS`` (``backend/app/auth/public_endpoints.py``). No new auth
scheme is invented here.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.dependencies import get_orchestrator
from backend.services.rag.agentic.query_planner import QueryPlanner
from backend.services.rag.agentic.wa_package_builder import (
    PackageUnbuildable,
    build_context_package,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wa-package", tags=["channels", "wa-broker"])


class WaPackageHistoryMessage(BaseModel):
    role: str
    content: str


class WaPackageBuildRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    history: list[WaPackageHistoryMessage] = Field(default_factory=list, max_length=24)
    thread_epoch: int


class WaPackageBuildResponse(BaseModel):
    """Exactly one of `package` / `unbuildable` is populated.

    HTTP 200 either way: an unbuildable intent is a ROUTE decision for the
    worker (send this row to the Gemini leg), not a server error — see
    ``PackageUnbuildable``'s docstring.
    """

    package: dict[str, Any] | None = None
    unbuildable: str | None = None


@router.post("/build", response_model=WaPackageBuildResponse)
async def build_wa_package(
    request: WaPackageBuildRequest,
    orchestrator: Any = Depends(get_orchestrator),
) -> WaPackageBuildResponse:
    """Build the deterministic context package for one WA codex-route turn."""
    history = [{"role": m.role, "content": m.content} for m in request.history]

    # Domain lookup for the curated-QA gate (D3) is a second, cheap call to
    # the same pure heuristic `build_context_package` runs internally — no
    # I/O, <50ms, deterministic for a given query. Duplicating the plan()
    # call here (rather than threading a precomputed plan through
    # `build_context_package`) keeps the "is this query unbuildable"
    # decision owned by exactly one function — D1's own GREETING /
    # no-collections gate — so the router and the builder can never
    # disagree about what counts as classifiable.
    plan = QueryPlanner().plan(request.query)
    curated_qa_block = await orchestrator.core.curated_qa_grounding_block(
        request.query,
        {"domain": plan.domain.value},
    )

    try:
        package = await build_context_package(
            query=request.query,
            history=history,
            thread_epoch=request.thread_epoch,
            retriever=orchestrator.core.retriever,
            curated_qa_block=curated_qa_block,
        )
    except PackageUnbuildable as exc:
        logger.info("wa_package: unbuildable reason=%s", exc.reason)
        return WaPackageBuildResponse(unbuildable=exc.reason)

    return WaPackageBuildResponse(package=package.to_payload())
