"""Data models for the Curiosity Loop pipeline.

# Organo: graph-engine/curiosity → models shared across orchestrator, grader, store
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class ProposalType(StrEnum):
    """Type of KG mutation proposed."""
    NODE = "node"
    EDGE = "edge"
    PROPERTY = "property"


class ProposalStatus(StrEnum):
    """State machine for proposals."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    AUTO_EXPIRED = "auto_expired"


class Tier(StrEnum):
    """Research tier classification."""
    SIMPLE = "tier1_simple"
    MEDIUM = "tier2_medium"
    COMPLEX = "tier3_complex"


@dataclass
class GapTopic:
    """A single gap topic from coverage_matrix.json."""
    domain: str
    topic: str
    freshness: str = "GAP"  # FRESH | AGING | STALE | GAP
    follow_up_queries: list[str] = field(default_factory=list)
    severity: float = 1.0  # 1.0 = GAP, 0.7 = STALE, 0.3 = AGING
    last_proposed_at: str | None = None


@dataclass
class ResearchEvidence:
    """Evidence gathered from a research dispatch."""
    content: str = ""
    source_url: str = ""
    source_type: str = ""  # "ollama" | "gemini" | "exa" | "nlm" | "hyde"
    citations: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GradeResult:
    """Validation result from CuriosityGrader."""
    score: float = 0.0
    decision: str = "abstain"  # "propose" | "more_research" | "abstain"
    reason: str = ""


@dataclass
class KGProposal:
    """A proposal to enrich the Knowledge Graph.

    NEVER applied directly — requires Zero approval via kg-propose CLI.
    """
    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    gap_id: str = ""
    domain: str = ""
    proposal_type: ProposalType = ProposalType.NODE
    tier: Tier = Tier.SIMPLE

    # Node proposal
    node_label: str = ""
    node_type: str = ""
    node_properties: dict[str, Any] = field(default_factory=dict)

    # Edge proposal
    source_entity_id: str = ""
    target_entity_id: str = ""
    relationship_type: str = ""
    edge_properties: dict[str, Any] = field(default_factory=dict)

    # Property proposal
    target_entity_id_prop: str = ""
    property_key: str = ""
    property_value: Any = None

    # Validation
    evidence_sources: list[dict[str, Any]] = field(default_factory=list)
    self_rag_score: float = 0.0
    research_method: str = ""

    # State
    status: ProposalStatus = ProposalStatus.PENDING
    approved_by: str = ""
    approved_at: str = ""
    applied_at: str = ""
    rejection_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CycleResult:
    """Summary of a single Curiosity Loop cycle."""
    gaps_scanned: int = 0
    proposals_created: int = 0
    proposals_by_tier: dict[str, int] = field(default_factory=dict)
    proposals_by_domain: dict[str, int] = field(default_factory=dict)
    skipped_dedup: int = 0
    skipped_blacklisted: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
