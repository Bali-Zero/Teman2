"""
WA codex-route context package builder (BOT-V4 S2, D1).

Deterministic pipeline (spec §2.2,
research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md):
    intent/domain gate -> domain->collection map (QueryPlanner, pure
    heuristic) -> hybrid dense+sparse search per collection -> curated-QA
    injection (pre-gated by the caller via
    OrchestratorCore.curated_qa_grounding_block, D3) -> PricingTool
    resolution on pricing intent -> persona digest -> frozen evidence
    inputs -> content-addressed package_hash.

S2 acceptance criterion (spec §2.2): "the codex-route package builder
invokes zero LLMs" — this module MUST NOT import `backend.llm` (directly,
in its own new code) or call any LLM client. Verified at runtime by
`test_codex_package_builder_invokes_zero_llms` (monkeypatched tripwires)
AND statically (an AST/source scan for a `backend.llm` import in this
file's own source).

Unclassifiable intent (GREETING domain, or a domain plan whose collection
list is empty) raises `PackageUnbuildable` — the caller (the wa_package
router) routes that row to the Gemini leg rather than borrowing an LLM
planner into the codex path (spec §2.2, "unclassifiable -> Gemini leg").

Allowlist schema (spec §2.2, Codex M22/CR1): `ContextPackage.to_payload()`
serializes EXACTLY 7 fields — `history`, `chunks`, `pricing_block`,
`persona_digest`, `evidence_inputs`, `thread_epoch`, `package_hash`. No
phone, no `wa:` subject, no CRM fields, no source paths.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from backend.prompts.channel_overlays import CHANNEL_CONFIGS
from backend.prompts.zantara_core import (
    CITATION_RULES,
    GREETING_RULES,
    LANGUAGE_PROTOCOL,
)
from backend.services.misc.pricing_intent import has_pricing_intent
from backend.services.pricing.pricing_service import get_pricing_service
from backend.services.rag.agentic._abstain_policy import build_abstain_policy
from backend.services.rag.agentic.query_plan import QueryDomain
from backend.services.rag.agentic.query_planner import QueryPlanner
from backend.services.rag.agentic.reasoning_utils import calculate_evidence_score

logger = logging.getLogger(__name__)

# Package hygiene caps (spec §2.2 hygiene). Enforced with a LOG line on every
# drop/truncation — a silent cap reads downstream as "the complete set"
# (scar family #2, W97: three tools once printed a truncated [:40] slice
# that four separate audits mistook for the full list).
_MAX_CHUNKS = 8
_MAX_CHUNK_CHARS = 4000
_CHUNKS_PER_COLLECTION_LIMIT = 3

# Fixed, documented access level for this deterministic, unauthenticated WA
# path — matches `VectorSearchTool.__init__`'s own default (tools.py:89),
# the closest existing analog for "no elevated tier, anonymous caller".
_SEARCH_USER_LEVEL = 1

# Persona digest: a MINIMAL, deterministic set of the existing SSOT prompt
# sections from backend/prompts/zantara_core.py (the sole prompt SSOT per
# apps/backend-rag/CLAUDE.md "Prompt Architecture") — chosen because they
# most directly constrain HOW a WA reply gets written (language selection,
# citation discipline, greeting handling). Deliberately excluded: the
# creator/team personas, the master template, and the internal-monologue /
# escalation / crash-protocol sections — those are orchestration-only
# (deciding what tools to call, how to escalate) and irrelevant to a
# downstream text generator that receives an already-built evidence
# package and just has to write the reply.
_PERSONA_SECTIONS: tuple[str, ...] = (LANGUAGE_PROTOCOL, CITATION_RULES, GREETING_RULES)


class PackageUnbuildable(Exception):
    """The deterministic pipeline cannot build a package for this query.

    The caller (the wa_package router) treats this as a ROUTE decision, not
    an error: the whole row goes to the Gemini leg, never an LLM-borrowed
    fallback inside the codex path (spec §2.2).
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ContextPackage:
    """The deterministic context package for the codex-route WA generation leg.

    Allowlist schema (spec §2.2) — EXACTLY these 7 fields serialize via
    `to_payload()`. Adding an 8th field to this dataclass does NOT
    automatically leak it into the wire payload: `to_payload()` builds the
    dict literally (never `dataclasses.asdict()` plus extras), so the
    allowlist is enforced by construction, not by convention.
    """

    history: list[dict[str, str]]
    chunks: list[dict[str, Any]]
    pricing_block: dict[str, Any] | None
    persona_digest: str
    evidence_inputs: dict[str, Any]
    thread_epoch: int
    package_hash: str

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the exact 7-key allowlist. No extras, ever."""
        return {
            "history": self.history,
            "chunks": self.chunks,
            "pricing_block": self.pricing_block,
            "persona_digest": self.persona_digest,
            "evidence_inputs": self.evidence_inputs,
            "thread_epoch": self.thread_epoch,
            "package_hash": self.package_hash,
        }


def _build_persona_digest(channel: str = "whatsapp") -> str:
    """Deterministic persona digest assembled ONLY from imported prompt SSOT.

    No new persona prose is authored here — every fragment originates in
    `backend/prompts/zantara_core.py` or, for the channel-specific tail,
    `backend/prompts/channel_overlays.py` (the sole channel-constraint SSOT).
    """
    parts = [text.strip() for text in _PERSONA_SECTIONS if text and text.strip()]
    channel_config = CHANNEL_CONFIGS.get(channel)
    if channel_config and channel_config.extra_instructions:
        parts.append(channel_config.extra_instructions.strip())
    return "\n\n".join(parts)


async def _search_collection_chunks(
    retriever: Any,
    collection: str,
    query: str,
) -> list[dict[str, Any]]:
    """One collection's chunks, in the allowlisted `{collection, text, score}` shape.

    Dispatch choice (documented per the D1 contract): `tools.py`'s
    `VectorSearchTool.execute` picks between `hybrid_search_with_reranking`
    / `search_with_reranking` / plain `search` based on retriever capability
    and a global `enable_hybrid_search` feature flag, running all target
    collections in a `TaskGroup`. This pipeline queries a FIXED, already
    domain-ranked collection list from `QueryPlanner` — there is no LLM tool
    call choosing among them and no reranking loop — so the simpler,
    spec-permitted branch is used instead: a plain
    `retriever.hybrid_search(..., collection_override=collection)` call per
    collection (true dense+sparse RRF fusion — "hybrid dense+sparse search"
    per spec §2.2 — as opposed to `search_collection`, which is dense-only
    and reserved for the always-small curated_qa lookup).
    """
    try:
        result = await retriever.hybrid_search(
            query=query,
            user_level=_SEARCH_USER_LEVEL,
            limit=_CHUNKS_PER_COLLECTION_LIMIT,
            collection_override=collection,
        )
    except Exception:
        logger.warning(
            "wa_package_builder: hybrid_search failed for collection=%s",
            collection,
            exc_info=True,
        )
        return []

    if not isinstance(result, dict):
        return []

    chunks: list[dict[str, Any]] = []
    for hit in result.get("results", []):
        if not isinstance(hit, dict):
            continue
        text = hit.get("text")
        if not text:
            continue
        chunks.append(
            {
                "collection": collection,
                "text": text,
                "score": hit.get("score", 0.0),
            },
        )
    return chunks


def _cap_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enforce the chunk-count and per-chunk-length hygiene caps, LOGGING every drop."""
    capped: list[dict[str, Any]] = []
    truncated_count = 0
    for chunk in chunks:
        text = chunk["text"]
        if len(text) > _MAX_CHUNK_CHARS:
            text = text[:_MAX_CHUNK_CHARS]
            truncated_count += 1
        capped.append({**chunk, "text": text})

    dropped_count = max(0, len(capped) - _MAX_CHUNKS)
    if dropped_count:
        logger.info(
            "wa_package_builder: dropping %d/%d chunks over the %d-chunk cap",
            dropped_count,
            len(capped),
            _MAX_CHUNKS,
        )
    if truncated_count:
        logger.info(
            "wa_package_builder: truncated %d chunk(s) over the %d-char cap",
            truncated_count,
            _MAX_CHUNK_CHARS,
        )
    return capped[:_MAX_CHUNKS]


def _package_hash(
    history: list[dict[str, str]],
    chunks: list[dict[str, Any]],
    pricing_block: dict[str, Any] | None,
    persona_digest: str,
    evidence_inputs: dict[str, Any],
    thread_epoch: int,
) -> str:
    """Content-addressed sha256 hex digest over the 6 non-hash fields.

    `sort_keys=True` makes the digest independent of dict insertion order;
    the compact `separators` plus `ensure_ascii=False` keep the
    serialization deterministic for identical logical content.
    """
    payload = {
        "history": history,
        "chunks": chunks,
        "pricing_block": pricing_block,
        "persona_digest": persona_digest,
        "evidence_inputs": evidence_inputs,
        "thread_epoch": thread_epoch,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


async def build_context_package(
    *,
    query: str,
    history: list[dict[str, str]],
    thread_epoch: int,
    retriever: Any,
    curated_qa_block: str = "",
) -> ContextPackage:
    """Build the deterministic context package for the WA codex-route leg.

    Zero LLM calls anywhere in this function or its helpers (S2 acceptance
    criterion, spec §2.2) — see `test_codex_package_builder_invokes_zero_llms`.

    Args:
        query: The user's raw message text.
        history: Up to 12 turns of `{"role", "content"}` conversation
            history (spec §2.2 "12-turn history") — passed through verbatim,
            this function does not truncate or otherwise validate it.
        thread_epoch: The caller's monotonic thread-epoch counter, frozen
            into the package and re-verified unchanged at finalization
            (spec §2.3).
        retriever: A `SearchService`-shaped object exposing `hybrid_search`
            (see `_search_collection_chunks`).
        curated_qa_block: Pre-gated curated-QA evidence text, or "" for
            none. MUST come from `OrchestratorCore.curated_qa_grounding_block`
            (D3) — this function trusts the caller's domain/staleness gating
            and never re-derives it.

    Raises:
        PackageUnbuildable: the deterministic domain gate could not classify
            this query into a non-empty collection set (GREETING domain, or
            any domain plan whose `collections` list is empty). The caller
            routes the row to the Gemini leg instead of borrowing an LLM
            planner into this path.
    """
    plan = QueryPlanner().plan(query)

    if plan.domain == QueryDomain.GREETING:
        raise PackageUnbuildable(reason="greeting_domain")
    if not plan.collections:
        raise PackageUnbuildable(reason="no_collections")

    # Dedup collections while preserving QueryPlanner's priority order.
    seen_collections: set[str] = set()
    ordered_collections: list[str] = []
    for collection in plan.collections:
        if collection not in seen_collections:
            seen_collections.add(collection)
            ordered_collections.append(collection)

    chunks: list[dict[str, Any]] = []
    if curated_qa_block:
        chunks.append({"collection": "curated_qa", "text": curated_qa_block, "score": 1.0})

    for collection in ordered_collections:
        chunks.extend(await _search_collection_chunks(retriever, collection, query))

    chunks = _cap_chunks(chunks)

    pricing_block: dict[str, Any] | None = None
    if has_pricing_intent(query):
        pricing_block = get_pricing_service().search_service(query)

    persona_digest = _build_persona_digest()

    # Evidence inputs are FROZEN here — finalization (spec §2.3) reads these
    # fields, it never recomputes them against a possibly-drifted retrieval.
    abstain_policy = build_abstain_policy(query)
    evidence_score = calculate_evidence_score(
        sources=[{"score": chunk["score"]} for chunk in chunks],
        context_gathered=[chunk["text"] for chunk in chunks],
        query=query,
    )
    evidence_inputs: dict[str, Any] = {
        "evidence_score": evidence_score,
        "context_length": len(chunks),
        "domain": plan.domain.value,
        "label_threshold": abstain_policy.label_threshold,
        "abstain": abstain_policy.label_abstains(evidence_score),
    }

    package_hash = _package_hash(
        history=history,
        chunks=chunks,
        pricing_block=pricing_block,
        persona_digest=persona_digest,
        evidence_inputs=evidence_inputs,
        thread_epoch=thread_epoch,
    )

    return ContextPackage(
        history=history,
        chunks=chunks,
        pricing_block=pricing_block,
        persona_digest=persona_digest,
        evidence_inputs=evidence_inputs,
        thread_epoch=thread_epoch,
        package_hash=package_hash,
    )
