"""Deterministic, I/O-free finalization contract for user-visible RAG results.

The orchestration layer owns transport and analytics scheduling. This module
only classifies a result's producer and stamps additive metadata on the one
public ``CoreResult`` schema. It deliberately does not grade, rewrite, or
recompute answers, abstention decisions, confidence, or sources.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.rag.agentic.schema import (
    AnalyticsReceiptStatus,
    CoreResult,
    EvidenceProvenance,
    FinalizationStatus,
    ProducerOrigin,
    TrustedBypassReason,
)

_FINALIZATION_STAMP = object()

_QUERY_GATE_MODELS = frozenset(
    {
        "security-gate",
        "greeting-gate",
        "casual-gate",
        "identity-gate",
        "clarification-gate",
        "out_of_domain-gate",
    }
)
_EVIDENCE_PROVENANCE_BY_ORIGIN = {
    ProducerOrigin.FAQ_CACHE: EvidenceProvenance.FAQ_CACHE,
    ProducerOrigin.SEMANTIC_CACHE: EvidenceProvenance.SEMANTIC_CACHE,
    ProducerOrigin.MULTI_AGENT_COORDINATOR: EvidenceProvenance.MULTI_AGENT_COORDINATOR,
    ProducerOrigin.SPECIALIZED_SERVICE_ROUTER: EvidenceProvenance.SPECIALIZED_SERVICE_ROUTER,
    ProducerOrigin.KNOWLEDGE_GRAPH: EvidenceProvenance.KNOWLEDGE_GRAPH,
    ProducerOrigin.REACT_PIPELINE: EvidenceProvenance.REACT_PIPELINE,
}
_EVIDENCE_IDENTITY_FIELDS = (
    "source",
    "title",
    "collection",
    "url",
    "source_url",
    "id",
    "doc_id",
    "document_id",
    "chunk_id",
)
_PLACEHOLDER_VALUES = frozenset(
    {"", "-", "n/a", "na", "none", "null", "placeholder", "unknown", "unspecified"}
)


@dataclass(frozen=True, slots=True)
class FinalizationContext:
    """Internal producer attribution carried across the shared wrapper."""

    result: CoreResult
    producer_origin: ProducerOrigin
    trusted_bypass_reason: TrustedBypassReason | None = None
    analytics_receipt: AnalyticsReceiptStatus | None = None


@dataclass(frozen=True, slots=True)
class _FinalizationMetadataSnapshot:
    """Canonical public metadata protected by the private identity seal."""

    finalization_status: FinalizationStatus | None
    producer_origin: ProducerOrigin | None
    evidence_provenance: EvidenceProvenance | None
    trusted_bypass_reason: TrustedBypassReason | None
    analytics_receipt: AnalyticsReceiptStatus | None


@dataclass(frozen=True, slots=True)
class _FinalizationDecisionSnapshot:
    """Only result inputs that can change the deterministic classification."""

    model_used: str
    route_used: str
    cache_hit: bool
    tools_called: tuple[str, ...]
    has_valid_evidence: bool


@dataclass(frozen=True, slots=True)
class _FinalizationSeal:
    """Identity-bound canonical snapshot; clones cannot inherit authority."""

    token: object
    owner_id: int
    metadata: _FinalizationMetadataSnapshot
    decisions: _FinalizationDecisionSnapshot


def _normalized_text(value: object) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def _normalized_tools(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(sorted({_normalized_text(tool) for tool in value if isinstance(tool, str)}))


def _metadata_snapshot(result: CoreResult) -> _FinalizationMetadataSnapshot:
    return _FinalizationMetadataSnapshot(
        finalization_status=result.finalization_status,
        producer_origin=result.producer_origin,
        evidence_provenance=result.evidence_provenance,
        trusted_bypass_reason=result.trusted_bypass_reason,
        analytics_receipt=result.analytics_receipt,
    )


def _decision_snapshot(result: CoreResult) -> _FinalizationDecisionSnapshot:
    return _FinalizationDecisionSnapshot(
        model_used=_normalized_text(result.model_used),
        route_used=_normalized_text(result.route_used),
        cache_hit=result.cache_hit is True,
        tools_called=_normalized_tools(result.tools_called),
        has_valid_evidence=_has_valid_evidence(result.sources),
    )


def _attribution_inputs(
    snapshot: _FinalizationDecisionSnapshot,
) -> tuple[str, str, bool, tuple[str, ...]]:
    return (
        snapshot.model_used,
        snapshot.route_used,
        snapshot.cache_hit,
        snapshot.tools_called,
    )


def _owned_seal(result: CoreResult) -> _FinalizationSeal | None:
    seal = result._finalization_stamp
    if (
        isinstance(seal, _FinalizationSeal)
        and seal.token is _FINALIZATION_STAMP
        and seal.owner_id == id(result)
    ):
        return seal
    return None


def _restore_metadata(
    result: CoreResult,
    snapshot: _FinalizationMetadataSnapshot,
) -> None:
    result.finalization_status = snapshot.finalization_status
    result.producer_origin = snapshot.producer_origin
    result.evidence_provenance = snapshot.evidence_provenance
    result.trusted_bypass_reason = snapshot.trusted_bypass_reason
    result.analytics_receipt = snapshot.analytics_receipt


def _metadata_matches_snapshot(
    result: CoreResult,
    snapshot: _FinalizationMetadataSnapshot,
) -> bool:
    """Require the exact canonical enum objects, not StrEnum-equal strings."""
    return (
        result.finalization_status is snapshot.finalization_status
        and result.producer_origin is snapshot.producer_origin
        and result.evidence_provenance is snapshot.evidence_provenance
        and result.trusted_bypass_reason is snapshot.trusted_bypass_reason
        and result.analytics_receipt is snapshot.analytics_receipt
    )


def is_canonically_finalized(result: CoreResult) -> bool:
    """Return whether identity, decisions, and public metadata all match."""
    seal = _owned_seal(result)
    return (
        seal is not None
        and _metadata_matches_snapshot(result, seal.metadata)
        and seal.decisions == _decision_snapshot(result)
    )


def _has_valid_evidence(sources: object) -> bool:
    """Recognize existing source shapes without normalizing or rewriting them."""
    if not isinstance(sources, list):
        return False
    for source in sources:
        if not isinstance(source, dict) or not source:
            continue
        for field in _EVIDENCE_IDENTITY_FIELDS:
            value = source.get(field)
            if isinstance(value, str):
                if value.strip().lower() not in _PLACEHOLDER_VALUES:
                    return True
            elif isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return True
    return False


def classify_result_origin(
    result: CoreResult,
) -> tuple[ProducerOrigin, TrustedBypassReason | None]:
    """Return the closed producer attribution for a ``CoreResult``."""
    model_used = _normalized_text(result.model_used)
    route_used = _normalized_text(result.route_used)
    tools_called = set(_normalized_tools(result.tools_called))

    if model_used in _QUERY_GATE_MODELS:
        return ProducerOrigin.QUERY_GATE, TrustedBypassReason.DETERMINISTIC_QUERY_GATE
    if model_used == "faq_cache":
        return ProducerOrigin.FAQ_CACHE, None
    if result.cache_hit is True or model_used == "cache":
        return ProducerOrigin.SEMANTIC_CACHE, None
    if model_used == "multi-agent-coordinator":
        return ProducerOrigin.MULTI_AGENT_COORDINATOR, None
    if model_used in {"kg_langgraph", "knowledge-graph"} or route_used == "kg_fast_path":
        return ProducerOrigin.KNOWLEDGE_GRAPH, None
    if tools_called.intersection(
        {"autonomous_research", "cross_oracle_synthesis", "client_journey"}
    ) or model_used in {
        "specialized-router",
        "autonomous-research",
        "client-journey",
    }:
        return ProducerOrigin.SPECIALIZED_SERVICE_ROUTER, None
    if route_used == "react":
        return ProducerOrigin.REACT_PIPELINE, None
    return ProducerOrigin.UNKNOWN, None


def finalize_core_result(
    result: CoreResult,
    *,
    producer_origin: ProducerOrigin,
    trusted_bypass_reason: TrustedBypassReason | None,
    analytics_receipt: AnalyticsReceiptStatus,
) -> CoreResult:
    """Stamp the shadow contract exactly once without changing response data.

    The function is intentionally idempotent: a second invocation returns the
    byte-equivalent model without reclassification or any I/O. Runtime enum
    checks prevent producers from self-asserting arbitrary trust strings.
    """
    existing_seal = _owned_seal(result)
    decision_snapshot = _decision_snapshot(result)
    if existing_seal is not None and existing_seal.decisions == decision_snapshot:
        # The exact object was finalized already. Public metadata may have been
        # changed afterward, so restore the private canonical snapshot rather
        # than trusting an identity-only early return.
        _restore_metadata(result, existing_seal.metadata)
        return result

    if existing_seal is not None and _attribution_inputs(
        existing_seal.decisions
    ) == _attribution_inputs(decision_snapshot):
        # Once an instance crosses the boundary, producer attribution is
        # authority carried by the private seal. Later changes to routing
        # hints cannot promote the result to a trusted producer or query-gate.
        # Evidence-validity drift is recomputed under the sealed origin.
        producer_origin = existing_seal.metadata.producer_origin
        trusted_bypass_reason = existing_seal.metadata.trusted_bypass_reason
    elif existing_seal is not None:
        # Attribution-input drift after sealing is fail-closed. Public routing
        # hints are not authority to reclassify a previously finalized result.
        producer_origin = ProducerOrigin.UNKNOWN
        trusted_bypass_reason = None

    if not isinstance(producer_origin, ProducerOrigin):
        raise TypeError("producer_origin must be a ProducerOrigin")
    if trusted_bypass_reason is not None and not isinstance(
        trusted_bypass_reason, TrustedBypassReason
    ):
        raise TypeError("trusted_bypass_reason must be a TrustedBypassReason")
    if not isinstance(analytics_receipt, AnalyticsReceiptStatus):
        raise TypeError("analytics_receipt must be an AnalyticsReceiptStatus")
    if trusted_bypass_reason is not None and producer_origin is not ProducerOrigin.QUERY_GATE:
        raise ValueError("trusted bypass is only valid for the allowlisted query-gate origin")

    # Even the internal producer context cannot extend the trusted surface by
    # inventing a new ``*-gate`` model. A new deterministic gate must be added
    # deliberately to the finite allowlist above; until then it is fail-visible.
    if (
        producer_origin is ProducerOrigin.QUERY_GATE
        and trusted_bypass_reason is TrustedBypassReason.DETERMINISTIC_QUERY_GATE
        and (result.model_used or "").strip().lower() not in _QUERY_GATE_MODELS
    ):
        producer_origin = ProducerOrigin.UNKNOWN
        trusted_bypass_reason = None

    has_valid_evidence = decision_snapshot.has_valid_evidence

    # A same-instance decision-input change requires metadata recomputation,
    # but never means the analytics side effect should run again. Preserve the
    # receipt protected by the prior private seal when one exists.
    if existing_seal is not None and existing_seal.metadata.analytics_receipt is not None:
        analytics_receipt = existing_seal.metadata.analytics_receipt

    # Every public field is recomputed.  A producer/user payload can prefill
    # these fields, but cannot create the private identity stamp above.
    result.producer_origin = producer_origin
    result.evidence_provenance = (
        _EVIDENCE_PROVENANCE_BY_ORIGIN.get(producer_origin) if has_valid_evidence else None
    )
    result.trusted_bypass_reason = trusted_bypass_reason
    result.analytics_receipt = analytics_receipt
    result.finalization_status = (
        FinalizationStatus.SHADOW_INCOMPLETE
        if producer_origin is ProducerOrigin.UNKNOWN
        or (not has_valid_evidence and trusted_bypass_reason is None)
        else FinalizationStatus.SHADOW_RECORDED
    )
    result._finalization_stamp = _FinalizationSeal(
        token=_FINALIZATION_STAMP,
        owner_id=id(result),
        metadata=_metadata_snapshot(result),
        decisions=_decision_snapshot(result),
    )
    return result
