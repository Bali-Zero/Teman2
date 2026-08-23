"""
WA codex-route package-build endpoint (BOT-V4 S2, D2).

``POST /api/wa-package/build`` — internal-only, RAG process group. Builds
the deterministic ``ContextPackage`` (D1, ``wa_package_builder.py``) for one
WA turn, or reports the query as unbuildable so the caller routes it to the
Gemini leg (spec §2.2, "unclassifiable -> Gemini leg").

Auth: two layers, neither invented here (S2 cross-family review, finding 7).
``HybridAuthMiddleware`` (``backend/middleware/hybrid_auth.py``) fail-closed
rejects any request without a recognized credential before it reaches this
router, and this path is deliberately NOT in ``PUBLIC_ENDPOINTS``. On top of
that, ``require_internal_caller`` below enforces the per-endpoint SCOPE the
middleware alone cannot: authentication is not authorization, and a portal
user's valid JWT must not be able to drive this internal builder (embedding
+ Qdrant cost on every call). Only the middleware's ``internal`` service
identity (X-Internal-Key) or an ``admin`` may call it.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.dependencies import get_orchestrator
from backend.services.rag.agentic.query_plan import QueryDomain
from backend.services.rag.agentic.query_planner import QueryPlanner
from backend.services.rag.agentic.wa_package_builder import (
    PackageUnbuildable,
    build_context_package,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wa-package", tags=["channels", "wa-broker"])


def require_internal_caller(request: Request) -> None:
    """Per-endpoint scope on top of HybridAuthMiddleware's authentication.

    The middleware stores the authenticated identity on ``request.state.user``
    (``hybrid_auth.py``: X-Internal-Key -> role "internal"). Fail-closed: a
    missing/unshaped state (middleware disabled, unexpected wiring) is a 403,
    never a pass.
    """
    user = getattr(request.state, "user", None)
    role = user.get("role") if isinstance(user, dict) else None
    if role not in ("internal", "admin"):
        raise HTTPException(status_code=403, detail="internal callers only")


class WaPackageHistoryMessage(BaseModel):
    # Bounded at the transport (S2 cross-family review, finding 8): an
    # annotation caps nothing — 24 unbounded contents would be parsed,
    # hashed and re-serialized in full. 4096 matches the WA message ceiling.
    role: str = Field(..., max_length=32)
    content: str = Field(..., max_length=4096)


class WaPackageBuildRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4096)
    history: list[WaPackageHistoryMessage] = Field(default_factory=list, max_length=24)
    thread_epoch: int
    # G-P3 DLP gate: redact history/chunks free-text fields before the
    # package is sealed. Default False preserves the pre-G-P3 contract for
    # any other caller; the codex-bound leg (the only caller today, see
    # wa_codex_leg.py) sends True.
    dlp: bool = False


class WaPackageBuildResponse(BaseModel):
    """Exactly one of `package_wire` / `unbuildable` is populated.

    HTTP 200 either way: an unbuildable intent is a ROUTE decision for the
    worker (send this row to the Gemini leg), not a server error — see
    ``PackageUnbuildable``'s docstring.

    ``package_wire`` is the SEALED ENVELOPE — verbatim the bytes
    ``package_hash`` covers (``ContextPackage.wire_text()``), which is what
    ``offer_job`` must store and the broker verifies. The earlier draft
    returned ``to_payload()`` here, whose own docstring says it is NOT the
    wire format (its 7-key view includes package_hash itself): a consumer
    re-serializing that dict would produce bytes the hash does not cover
    and every broker-side verification would reject a valid package.
    EXACTLY one representation of the sealed fact crosses this contract —
    the wire plus its hash, nothing else. An earlier draft also returned a
    top-level ``evidence_inputs`` copy; the S2 adversarial gate (round 2)
    struck it: an unsealed copy can diverge from the sealed one inside the
    wire and steer the consumer's frozen-evidence abstain verdict with
    values the hash never covered. Consumers parse evidence_inputs OUT OF
    the wire.

    ``reversal_map`` (G-P3) travels ALONGSIDE the sealed wire, never inside
    it: placeholder -> original PII value, populated only when the request
    asked for ``dlp=True`` and the package actually redacted something.
    Absent (None) on every unbuildable response and on any dlp=False build.
    The caller is trusted to keep this local and never persist/log it (see
    `wa_codex_leg._attempt`, the only caller today) — this endpoint does
    not log it either.
    """

    package_wire: str | None = None
    package_hash: str | None = None
    unbuildable: str | None = None
    reversal_map: dict[str, str] | None = None


@router.post(
    "/build",
    response_model=WaPackageBuildResponse,
    dependencies=[Depends(require_internal_caller)],
)
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

    # Cost guard, not a routing decision (S2 cross-family review, finding
    # 9): a GREETING query is about to be declared unbuildable by D1's own
    # gate — prefetching curated-QA for it would spend an embedding + a
    # Qdrant search per "ciao". Same pure function, same query, so this can
    # never disagree with the builder's verdict; the builder still OWNS
    # the unbuildable decision.
    curated_qa_block = ""
    if plan.domain is not QueryDomain.GREETING:
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
            dlp=request.dlp,
        )
    except PackageUnbuildable as exc:
        logger.info("wa_package: unbuildable reason=%s", exc.reason)
        return WaPackageBuildResponse(unbuildable=exc.reason)

    return WaPackageBuildResponse(
        package_wire=package.wire_text(),
        package_hash=package.package_hash,
        reversal_map=package.reversal_map or None,
    )
