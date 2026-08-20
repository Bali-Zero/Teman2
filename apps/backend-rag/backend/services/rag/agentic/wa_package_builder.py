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

import copy
import hashlib
import json
import logging
from dataclasses import dataclass, field
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
from backend.services.rag.agentic.wa_dlp import redact_package_fields

logger = logging.getLogger(__name__)

# Package hygiene caps (spec §2.2 hygiene). Enforced with a LOG line on every
# drop/truncation — a silent cap reads downstream as "the complete set"
# (scar family #2, W97: three tools once printed a truncated [:40] slice
# that four separate audits mistook for the full list).
_MAX_CHUNKS = 8
_MAX_CHUNK_CHARS = 4000
_CHUNKS_PER_COLLECTION_LIMIT = 3

# History hygiene (S2 cross-family review, findings 3+8): the builder OWNS
# its payload allowlist, so history entries are rebuilt to exactly
# {"role", "content"} — a caller-supplied extra key (phone, crm_id, ...)
# is dropped, never forwarded. Content is capped at the WA message ceiling.
_MAX_HISTORY_ROLE_CHARS = 32
_MAX_HISTORY_CONTENT_CHARS = 4096

# pricing_block per-field allowlist (S2 cross-family review, finding 2):
# PricingService.search_service() returns contact_info (WhatsApp number,
# wa.me link), disclaimers and raw catalogue entries with internal
# annotations (_sub_block). Only these fields may cross into the package —
# "no phone" is part of the spec's allowlist contract.
_PRICING_ENTRY_FIELDS: tuple[str, ...] = (
    "key",
    "name",
    "price",
    "tier_range",
    "duration",
    "validity",
    "notes",
)

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
    # DLP reversal map (G-P3), placeholder -> original PII value. Populated
    # ONLY when `build_context_package(dlp=True)` redacted this package's
    # history/chunks; empty otherwise. Deliberately EXCLUDED from
    # `_canonical_wire`/`__post_init__`'s hash domain, from `to_payload()`
    # and from `wire_text()` — it is not part of the 7-key allowlist and
    # must never enter the wire package, the package_hash inputs, or a log
    # line (spec: "never leaves Fly"). `repr=False` so an accidental
    # `logger.debug(package)`/`repr(package)` cannot print original PII.
    reversal_map: dict[str, str] = field(default_factory=dict, repr=False, compare=False)
    # Wire snapshot, sealed at construction (Codex S2 re-verdict r6,
    # finding 2): `frozen=True` freezes the field BINDINGS only — the
    # nested lists/dicts stay mutable, so serializing them lazily would let
    # `pkg.history[-1]["content"] = ...` between build and offer divorce
    # the wire bytes from package_hash. Serializing ONCE here, and
    # verifying the hash against the snapshot in __post_init__, makes the
    # pair immutable together for the object's whole life.
    _wire: str = field(init=False, repr=False, compare=False, default="")

    def __post_init__(self) -> None:
        wire = _canonical_wire(
            {
                "history": self.history,
                "chunks": self.chunks,
                "pricing_block": self.pricing_block,
                "persona_digest": self.persona_digest,
                "evidence_inputs": self.evidence_inputs,
                "thread_epoch": self.thread_epoch,
            }
        )
        digest = hashlib.sha256(wire.encode("utf-8")).hexdigest()
        if digest != self.package_hash:
            raise ValueError(
                "package_hash does not cover this package's wire bytes "
                "(hash/wire integrity is sealed at construction)"
            )
        object.__setattr__(self, "_wire", wire)

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the exact 7-key allowlist. No extras, ever.

        Returns a DEEP COPY (S2 cross-family review, finding 5):
        `frozen=True` freezes the field BINDINGS, not the mutable
        lists/dicts inside them — handing out the internal references
        would let a caller mutate content after `package_hash` was
        computed, silently divorcing the payload from its own hash.

        NOT the broker wire format: this 7-key view INCLUDES package_hash,
        so its serialization can never equal the bytes the hash covers —
        offering `json.dumps(to_payload())` as broker_jobs.package makes
        every broker-side hash verification fail by construction (Codex S2
        re-verdict r5, finding 1). The envelope the broker receives and
        verifies is ``wire_text()``; the hash travels beside it.
        """
        return copy.deepcopy(
            {
                "history": self.history,
                "chunks": self.chunks,
                "pricing_block": self.pricing_block,
                "persona_digest": self.persona_digest,
                "evidence_inputs": self.evidence_inputs,
                "thread_epoch": self.thread_epoch,
                "package_hash": self.package_hash,
            }
        )

    def wire_text(self) -> str:
        """The EXACT bytes offered to the broker as broker_jobs.package —
        and, verbatim, the bytes ``package_hash`` covers.

        One serializer (``_canonical_wire``) produces both this string and
        the string ``_package_hash`` digests, so the hash domain and the
        wire bytes cannot drift apart (Codex S2 re-verdict r5, finding 1:
        the 7-field ``to_payload()`` serialization inevitably differed from
        the 6-field hash domain — a broker recomputing sha256 over the
        received bytes rejected every healthy package). Returns the
        SNAPSHOT sealed in ``__post_init__`` (r6, finding 2): a post-build
        mutation of the nested lists/dicts can no longer change what goes
        on the wire, so the hash verified at construction stays true. The
        transport stores this as TEXT (migration 272) precisely so these
        bytes survive offer->claim untouched: ``sha256(wire_text()) ==
        package_hash`` holds end to end.
        """
        return self._wire


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
        # fallback_to_plain=False is LOAD-BEARING for the zero-LLM criterion
        # (S2 cross-family review, finding 1): SearchService.hybrid_search's
        # default error fallback is self.search(), which runs Gemini query
        # expansion. With False it re-raises instead, and this except block
        # is the whole degradation — no LLM is reachable from this call.
        result = await retriever.hybrid_search(
            query=query,
            user_level=_SEARCH_USER_LEVEL,
            limit=_CHUNKS_PER_COLLECTION_LIMIT,
            collection_override=collection,
            fallback_to_plain=False,
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


def _sanitize_history(history: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    """Rebuild history to EXACTLY {"role", "content"} entries + the current turn.

    S2 cross-family review, findings 3, 4 and 8:
      - extra keys on a caller-supplied entry (phone, crm_id, ...) are
        DROPPED, never forwarded — the builder owns its allowlist at
        runtime, not just in a type annotation;
      - role/content are capped (a type annotation bounds nothing) with the
        drop LOGGED (W97);
      - the CURRENT query is appended as the final user turn, so the
        generator receives the question it must answer and `package_hash`
        distinguishes two different questions over identical history.
    """
    sanitized: list[dict[str, str]] = []
    dropped_keys = 0
    truncated = 0
    for entry in history:
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role", ""))[:_MAX_HISTORY_ROLE_CHARS]
        content = str(entry.get("content", ""))
        if len(content) > _MAX_HISTORY_CONTENT_CHARS:
            content = content[:_MAX_HISTORY_CONTENT_CHARS]
            truncated += 1
        dropped_keys += len(set(entry.keys()) - {"role", "content"})
        sanitized.append({"role": role, "content": content})
    if dropped_keys:
        logger.info(
            "wa_package_builder: dropped %d non-allowlisted history key(s)",
            dropped_keys,
        )
    if truncated:
        logger.info(
            "wa_package_builder: truncated %d history content(s) over the %d-char cap",
            truncated,
            _MAX_HISTORY_CONTENT_CHARS,
        )
    sanitized.append({"role": "user", "content": query[:_MAX_HISTORY_CONTENT_CHARS]})
    return sanitized


def _sanitize_pricing_block(raw: Any) -> dict[str, Any] | None:
    """Reduce PricingService.search_service() output to the per-field allowlist.

    Keeps: `search_query` and, per category, each entry filtered to
    `_PRICING_ENTRY_FIELDS`. Drops by construction: `contact_info` (WhatsApp
    number + wa.me link), `disclaimer`, `official_notice`, error/suggestion
    prose, and the internal `_sub_block` annotation (S2 cross-family
    review, finding 2). Returns None when nothing price-shaped survives.

    The wire (measured on `PricingService.search_service`, and pinned by the
    real-service contract test in `test_wa_package_builder.py` — S2 re-verdict
    round, W114) carries per-category values in TWO shapes:
      - 2026 data: `{service_name: entry_dict}` — a dict keyed by the public
        service name (`filtered_results[category_name] = items` on the dict
        path of the scorer);
      - legacy list fixtures: `[entry_dict, ...]`.
    A dict whose values are dicts is a service map, never a single entry —
    the earlier draft read it as one entry and silently dropped every real
    2026 match (Codex re-verdict, blocker).
    """
    if not isinstance(raw, dict):
        return None
    results = raw.get("results")
    if not isinstance(results, dict) or not results:
        return None

    def _filter_entry(entry: Any) -> dict[str, Any] | None:
        if not isinstance(entry, dict):
            return None
        kept = {k: entry[k] for k in _PRICING_ENTRY_FIELDS if k in entry}
        return kept or None

    clean_results: dict[str, Any] = {}
    dropped_categories = 0
    for category, items in results.items():
        if isinstance(items, list):
            kept_items = [e for e in (_filter_entry(item) for item in items) if e]
            if kept_items:
                clean_results[str(category)] = kept_items
                continue
        elif isinstance(items, dict):
            kept_services = {}
            for service_name, entry in items.items():
                kept_entry = _filter_entry(entry)
                if kept_entry:
                    kept_services[str(service_name)] = kept_entry
            if kept_services:
                clean_results[str(category)] = kept_services
                continue
        dropped_categories += 1
    if dropped_categories:
        logger.info(
            "wa_package_builder: dropped %d pricing categor(ies) with no allowlisted entries",
            dropped_categories,
        )
    if not clean_results:
        return None
    return {"search_query": str(raw.get("search_query", "")), "results": clean_results}


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


def _canonical_wire(payload: dict[str, Any]) -> str:
    """The ONE serializer for the broker envelope — used by BOTH
    ``ContextPackage.wire_text()`` and ``_package_hash``, so the bytes on
    the wire and the bytes under the digest are the same function's output
    by construction (Codex S2 re-verdict r5, finding 1). `sort_keys=True`
    makes it independent of dict insertion order; compact `separators` plus
    `ensure_ascii=False` keep it deterministic for identical content."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _package_hash(
    history: list[dict[str, str]],
    chunks: list[dict[str, Any]],
    pricing_block: dict[str, Any] | None,
    persona_digest: str,
    evidence_inputs: dict[str, Any],
    thread_epoch: int,
) -> str:
    """Content-addressed sha256 hex digest over the 6 non-hash fields —
    digested over exactly ``_canonical_wire`` of them, i.e. exactly the
    string ``wire_text()`` later emits."""
    payload = {
        "history": history,
        "chunks": chunks,
        "pricing_block": pricing_block,
        "persona_digest": persona_digest,
        "evidence_inputs": evidence_inputs,
        "thread_epoch": thread_epoch,
    }
    return hashlib.sha256(_canonical_wire(payload).encode("utf-8")).hexdigest()


async def build_context_package(
    *,
    query: str,
    history: list[dict[str, str]],
    thread_epoch: int,
    retriever: Any,
    curated_qa_block: str = "",
    dlp: bool = False,
) -> ContextPackage:
    """Build the deterministic context package for the WA codex-route leg.

    Zero LLM calls anywhere in this function or its helpers (S2 acceptance
    criterion, spec §2.2) — see `test_codex_package_builder_invokes_zero_llms`.

    Args:
        query: The user's raw message text. Appended to the payload history
            as the final user turn (and therefore hashed) — the generator
            must receive the question it is answering, and two different
            questions over identical history must never share a
            `package_hash` (S2 cross-family review, finding 4).
        history: Up to 12 turns of `{"role", "content"}` conversation
            history (spec §2.2 "12-turn history") — SANITIZED here to
            exactly those two keys with capped lengths, extras dropped and
            logged (S2 cross-family review, findings 3+8).
        thread_epoch: The caller's monotonic thread-epoch counter, frozen
            into the package and re-verified unchanged at finalization
            (spec §2.3).
        retriever: A `SearchService`-shaped object exposing `hybrid_search`
            (see `_search_collection_chunks`).
        curated_qa_block: Pre-gated curated-QA evidence text, or "" for
            none. MUST come from `OrchestratorCore.curated_qa_grounding_block`
            (D3) — this function trusts the caller's domain/staleness gating
            and never re-derives it.
        dlp: G-P3 DLP gate. When True, every `history[i]["content"]`,
            `chunks[i]["text"]` AND `pricing_block["search_query"]` (M1 —
            the pricing lookup's own echo of the customer's raw query) is
            redacted (`wa_dlp.redact_package_fields`) BEFORE
            `evidence_inputs`/`package_hash` are computed, so the sealed
            package and its hash cover only the REDACTED content.
            `evidence_inputs["dlp"]` records whether this build asked for
            redaction, inside the hash domain. The codex-bound build path
            passes True; the Gemini leg never calls this function with
            dlp=True (default False preserves existing callers unchanged).

    Raises:
        PackageUnbuildable: the deterministic domain gate could not classify
            this query into a non-empty collection set (GREETING domain, or
            any domain plan whose `collections` list is empty). The caller
            routes the row to the Gemini leg instead of borrowing an LLM
            planner into this path.
        PackageUnbuildable("dlp_error"): the DLP redaction step raised
            (detector exception, or the fail-closed overflow guard when a
            single package would need more than `wa_dlp.MAX_PLACEHOLDERS`
            distinct redacted values) — fail-closed, never a partially
            redacted package (spec G-P3 rule 7).
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

    retrieved: list[dict[str, Any]] = []
    for collection in ordered_collections:
        retrieved.extend(await _search_collection_chunks(retriever, collection, query))
    # Deterministic total order BEFORE the cap (S2 cross-family review,
    # finding 6): QueryPlanner merges cross-domain collections through a
    # set, whose iteration order varies per process (PYTHONHASHSEED) — two
    # workers building the same turn must not disagree on which chunks
    # survive the cap, their order, or the resulting package_hash. Sorting
    # by (-score, collection, text) removes collection-arrival order from
    # the outcome entirely. The curated_qa chunk stays pinned first.
    retrieved.sort(key=lambda c: (-float(c["score"]), c["collection"], c["text"]))
    chunks.extend(retrieved)

    chunks = _cap_chunks(chunks)

    pricing_block: dict[str, Any] | None = None
    if has_pricing_intent(query):
        pricing_block = _sanitize_pricing_block(get_pricing_service().search_service(query))

    payload_history = _sanitize_history(history, query)

    # G-P3 DLP gate — runs AFTER chunks are capped and history sanitized,
    # BEFORE evidence_inputs/package_hash are computed: everything hashed
    # and sealed below is the REDACTED content, never the original (spec
    # rule: "package_hash computed over the REDACTED content"). Fail-closed
    # by construction — ANY exception from the redact step (detector bug,
    # or wa_dlp's own >MAX_PLACEHOLDERS overflow guard) becomes
    # PackageUnbuildable so the row falls off to the Gemini leg instead of
    # shipping a partially-redacted or unredacted package.
    #
    # M1 (Kimi adversarial review, verified): `pricing_block["search_query"]`
    # is the customer's RAW query, verbatim (pricing_service.py sets it from
    # the same `query` argument `_sanitize_pricing_block` keeps untouched) —
    # without threading it through the SAME redaction state as history, a
    # NIK in the query would be redacted in `history[-1]["content"]` but
    # ship unredacted a few keys over in `pricing_block.search_query`, into
    # both the wire and the hash. Passed into `redact_package_fields` so it
    # shares dedup/placeholder-numbering with the history copy of the same
    # string, then spliced back before hashing.
    reversal_map: dict[str, str] = {}
    if dlp:
        pricing_search_query = (
            pricing_block.get("search_query") if pricing_block is not None else None
        )
        try:
            dlp_result = redact_package_fields(payload_history, chunks, pricing_search_query)
        except Exception as exc:
            logger.info(
                "wa_package_builder: dlp redaction failed error=%s",
                type(exc).__name__,
            )
            raise PackageUnbuildable(reason="dlp_error") from exc
        payload_history = dlp_result.history
        chunks = dlp_result.chunks
        reversal_map = dlp_result.reversal_map
        if pricing_block is not None:
            pricing_block = {**pricing_block, "search_query": dlp_result.search_query}

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
        # Kimi-7 (MINOR): inside the hash domain by design — a future
        # caller that forgets `dlp=True` produces a package distinguishable
        # downstream (evidence_inputs is what finalize/consumers read out
        # of the sealed wire) instead of one indistinguishable from a
        # properly-redacted build.
        "dlp": dlp,
    }

    package_hash = _package_hash(
        history=payload_history,
        chunks=chunks,
        pricing_block=pricing_block,
        persona_digest=persona_digest,
        evidence_inputs=evidence_inputs,
        thread_epoch=thread_epoch,
    )

    return ContextPackage(
        history=payload_history,
        chunks=chunks,
        pricing_block=pricing_block,
        persona_digest=persona_digest,
        evidence_inputs=evidence_inputs,
        thread_epoch=thread_epoch,
        package_hash=package_hash,
        reversal_map=reversal_map,
    )
