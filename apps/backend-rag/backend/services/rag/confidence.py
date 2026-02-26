"""
Dynamic Confidence Scoring for KG LangGraph Workflows

Multi-factor confidence calculation replacing the simplistic 3-tier system.
Factors: chain count, entity confidence, relationship strength, multi-source
corroboration, data recency, and intent clarity.

Pure computation module — no DB queries, no side effects.

Author: Nuzantara Team
Date: 2026-02-09
Reference: memory/langgraph-kg-evolution-plan.md (Phase 2)
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

# ============================================================================
# Constants
# ============================================================================

RELATIONSHIP_WEIGHTS: dict[str, float] = {
    "REQUIRES": 1.0,
    "ENABLES": 0.8,
    "PART_OF": 0.5,
    "REFERENCES": 0.3,
}

RECENCY_HALF_LIFE_DAYS = 180  # 6-month exponential decay

CONFIDENCE_HIGH = 0.80
CONFIDENCE_MEDIUM = 0.55
CONFIDENCE_LOW = 0.35

# Composite weights (sum = 1.0)
WEIGHT_CHAIN_BASE = 0.30
WEIGHT_ENTITY_CONFIDENCE = 0.20
WEIGHT_RELATIONSHIP_STRENGTH = 0.20
WEIGHT_MULTI_SOURCE = 0.15
WEIGHT_RECENCY = 0.10
WEIGHT_INTENT_CLARITY = 0.05


# ============================================================================
# Dataclass
# ============================================================================


@dataclass
class ConfidenceBreakdown:
    """Detailed breakdown of a confidence score."""

    overall: float = 0.0

    # Individual factor scores (0.0 - 1.0)
    chain_base: float = 0.0
    entity_confidence_avg: float = 0.0
    relationship_strength_avg: float = 0.0
    multi_source_bonus: float = 0.0
    recency_score: float = 0.5
    intent_clarity_bonus: float = 0.0

    # Multi-source details
    unique_source_count: int = 0
    unique_sources: list[str] = field(default_factory=list)

    # Warning
    warning_level: str = "very_low"
    warning_message: str = ""


# ============================================================================
# Factor Functions
# ============================================================================


def calculate_chain_base_score(chains_count: int) -> float:
    """5-tier chain count score."""
    if chains_count <= 0:
        return 0.0
    if chains_count <= 2:
        return 0.4
    if chains_count <= 5:
        return 0.6
    if chains_count <= 10:
        return 0.8
    return 1.0


def calculate_relationship_strength(chains: list[list[dict]]) -> float:
    """Weighted average of relationship types across all chain elements."""
    weights = []
    for chain in chains:
        for element in chain:
            rel_type = element.get("relationship_type", "")
            weights.append(RELATIONSHIP_WEIGHTS.get(rel_type, 0.3))
    if not weights:
        return 0.0
    return sum(weights) / len(weights)


def calculate_recency_score(chain_elements: list[dict]) -> float:
    """
    Exponential decay from timestamps in chain elements.

    Looks for 'target_created_at' or 'edge_created_at'.
    Returns 0.5 (neutral) if no timestamps found.
    """
    now = datetime.now(timezone.utc)
    scores = []

    for element in chain_elements:
        for key in ("target_created_at", "edge_created_at"):
            ts = element.get(key)
            if ts is None:
                continue
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except (ValueError, TypeError):
                    continue
            if not isinstance(ts, datetime):
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_days = max(0, (now - ts).days)
            decay = math.exp(-0.693 * age_days / RECENCY_HALF_LIFE_DAYS)
            scores.append(decay)

    if not scores:
        return 0.5  # neutral when no timestamps
    return sum(scores) / len(scores)


def calculate_multi_source_bonus(
    chain_elements: list[dict],
) -> tuple[float, int, list[str]]:
    """
    Bonus for evidence from multiple independent sources.

    Looks for 'edge_source_collection' and 'target_source_collection'.
    Returns (bonus, count, source_names).
    """
    sources: set[str] = set()
    for element in chain_elements:
        for key in ("edge_source_collection", "target_source_collection"):
            val = element.get(key)
            if val:
                sources.add(val)

    source_list = sorted(sources)
    count = len(source_list)

    if count >= 3:
        bonus = 0.15
    elif count == 2:
        bonus = 0.10
    else:
        bonus = 0.0

    return bonus, count, source_list


# ============================================================================
# Main Entry Points
# ============================================================================


def calculate_dynamic_confidence(
    state: dict,
    enriched_chains: list[list[dict]] | None = None,
) -> ConfidenceBreakdown:
    """
    Main confidence calculation combining all factors.

    Args:
        state: KGAgentState dict
        enriched_chains: Optional pre-enriched chains (with source_collection,
                         created_at fields). Falls back to state chains.

    Returns:
        ConfidenceBreakdown with overall score and per-factor details
    """
    chains = enriched_chains or state.get("relationship_chains", [])
    chains_count = len(chains)

    # Flatten chain elements for element-level analysis
    all_elements: list[dict] = []
    for chain in chains:
        all_elements.extend(chain)

    # Factor 1: Chain base
    chain_base = calculate_chain_base_score(chains_count)

    # Factor 2: Entity confidence average
    confidence_scores = state.get("confidence_scores", {})
    if confidence_scores:
        entity_conf_avg = sum(confidence_scores.values()) / len(confidence_scores)
    else:
        entity_conf_avg = 0.0

    # Factor 3: Relationship strength
    rel_strength = calculate_relationship_strength(chains)

    # Factor 4: Multi-source bonus
    ms_bonus, ms_count, ms_sources = calculate_multi_source_bonus(all_elements)

    # Factor 5: Recency
    recency = calculate_recency_score(all_elements)

    # Factor 6: Intent clarity
    intent = state.get("intent")
    intent_bonus = 1.0 if intent and intent != "general" else 0.0

    # Weighted composite
    overall = (
        WEIGHT_CHAIN_BASE * chain_base
        + WEIGHT_ENTITY_CONFIDENCE * entity_conf_avg
        + WEIGHT_RELATIONSHIP_STRENGTH * rel_strength
        + WEIGHT_MULTI_SOURCE * ms_bonus
        + WEIGHT_RECENCY * recency
        + WEIGHT_INTENT_CLARITY * intent_bonus
    )
    overall = round(min(1.0, max(0.0, overall)), 4)

    warning_level, warning_message = get_confidence_warning(overall)

    return ConfidenceBreakdown(
        overall=overall,
        chain_base=round(chain_base, 4),
        entity_confidence_avg=round(entity_conf_avg, 4),
        relationship_strength_avg=round(rel_strength, 4),
        multi_source_bonus=round(ms_bonus, 4),
        recency_score=round(recency, 4),
        intent_clarity_bonus=round(intent_bonus, 4),
        unique_source_count=ms_count,
        unique_sources=ms_sources,
        warning_level=warning_level,
        warning_message=warning_message,
    )


def get_confidence_warning(confidence: float) -> tuple[str, str]:
    """Map confidence score to warning level and message."""
    if confidence >= CONFIDENCE_HIGH:
        return "high", "High confidence — backed by multiple graph paths."
    if confidence >= CONFIDENCE_MEDIUM:
        return "medium", "Moderate confidence — verify details with official sources."
    if confidence >= CONFIDENCE_LOW:
        return "low", "Low confidence — recommend professional consultation before acting."
    return "very_low", "Very low confidence — insufficient evidence; seek professional advice."


def calculate_subgraph_confidence(
    workflow_source: str,
    steps_count: int,
    has_db_validation: bool,
    unique_sources: int,
) -> ConfidenceBreakdown:
    """
    Confidence score for domain-specific subgraphs.

    Replaces hardcoded 0.85/0.9 values with a dynamic calculation
    based on the subgraph's own characteristics.

    Args:
        workflow_source: Subgraph name (e.g. "company_subgraph")
        steps_count: Number of workflow steps produced
        has_db_validation: Whether subgraph queried DB for validation
        unique_sources: Number of unique data sources used

    Returns:
        ConfidenceBreakdown
    """
    # Subgraphs use hardcoded domain knowledge, so chain_base is always solid
    chain_base = min(1.0, 0.5 + steps_count * 0.1)

    # DB validation adds entity confidence
    entity_conf = 0.8 if has_db_validation else 0.5

    # Subgraphs encode strong REQUIRES relationships
    rel_strength = 0.9

    # Multi-source bonus
    if unique_sources >= 3:
        ms_bonus = 0.15
    elif unique_sources == 2:
        ms_bonus = 0.10
    else:
        ms_bonus = 0.0

    # Hardcoded knowledge is not time-sensitive
    recency = 0.7

    # Subgraphs are always domain-specific → clear intent
    intent_bonus = 1.0

    overall = (
        WEIGHT_CHAIN_BASE * chain_base
        + WEIGHT_ENTITY_CONFIDENCE * entity_conf
        + WEIGHT_RELATIONSHIP_STRENGTH * rel_strength
        + WEIGHT_MULTI_SOURCE * ms_bonus
        + WEIGHT_RECENCY * recency
        + WEIGHT_INTENT_CLARITY * intent_bonus
    )
    overall = round(min(1.0, max(0.0, overall)), 4)

    warning_level, warning_message = get_confidence_warning(overall)

    return ConfidenceBreakdown(
        overall=overall,
        chain_base=round(chain_base, 4),
        entity_confidence_avg=round(entity_conf, 4),
        relationship_strength_avg=round(rel_strength, 4),
        multi_source_bonus=round(ms_bonus, 4),
        recency_score=round(recency, 4),
        intent_clarity_bonus=round(intent_bonus, 4),
        unique_source_count=unique_sources,
        unique_sources=[workflow_source],
        warning_level=warning_level,
        warning_message=warning_message,
    )
