"""Curiosity Orchestrator — transforms gaps into validated KG proposals.

# Organo: graph-engine/curiosity → produce CycleResult + kg_proposals → consuma gap_detector + coverage_matrix

Pipeline: scan gaps → prioritize → classify tier → dispatch research →
          validate (CuriosityGrader) → propose (NEVER direct KG write)

SYMBIOSIS Pilastro 6: "La curiosità guidata da gap su knowledge graph
non è stata studiata da nessuno. Stiamo inventando."

Legge 5 enforced: proposals go to kg_proposals table ONLY.
Legge 7 enforced: every cycle produces metrics (gaps_scanned, proposals_created, density_delta).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from nuzantara_graph.curiosity.dispatchers.complex import ComplexDispatcher
from nuzantara_graph.curiosity.dispatchers.medium import MediumDispatcher
from nuzantara_graph.curiosity.dispatchers.simple import SimpleDispatcher
from nuzantara_graph.curiosity.grader import CuriosityGrader
from nuzantara_graph.curiosity.models import (
    CycleResult,
    GapTopic,
    KGProposal,
    ProposalType,
    ResearchEvidence,
    Tier,
)
from nuzantara_graph.curiosity.proposals import KGProposalStore

logger = logging.getLogger(__name__)

# Safety limits
MAX_GAPS_PER_CYCLE = 20
CRITICAL_DOMAINS = {"immigration", "tax", "legal", "company", "property", "visa"}
CROSS_DOMAIN_KEYWORDS = {"vs", "versus", "compared", "conversion", "transfer", "between"}

# Domain priority weights (higher = more important for business)
DOMAIN_PRIORITY = {
    "immigration": 1.0,
    "company": 0.9,
    "tax": 0.9,
    "property": 0.8,
    "operations": 0.7,
    "editorial": 0.4,
    "lifestyle": 0.3,
}

# Freshness severity mapping
FRESHNESS_SEVERITY = {
    "GAP": 1.0,
    "STALE": 0.7,
    "AGING": 0.3,
    "FRESH": 0.0,
}


class CuriosityOrchestrator:
    """Transforms knowledge gaps into validated KG proposals.

    Cycle:
    1. Load gaps from coverage_matrix.json
    2. Prioritize by severity × domain_importance
    3. Classify tier (simple/medium/complex)
    4. Dispatch research per tier
    5. Grade evidence (CuriosityGrader)
    6. Create proposals in kg_proposals (NEVER direct KG write)
    7. Return CycleResult with metrics
    """

    def __init__(
        self,
        proposal_store: KGProposalStore,
        coverage_matrix_path: str = "",
        redis_client: Any = None,
    ) -> None:
        self.store = proposal_store
        self.coverage_matrix_path = coverage_matrix_path
        self.grader = CuriosityGrader()
        self.simple = SimpleDispatcher()
        self.medium = MediumDispatcher()
        self.complex = ComplexDispatcher(redis_client=redis_client)

    async def run_cycle(self, max_gaps: int = MAX_GAPS_PER_CYCLE) -> CycleResult:
        """Run a single curiosity cycle.

        Args:
            max_gaps: Maximum gaps to process (default 20, safety limit).

        Returns:
            CycleResult with metrics.
        """
        start = time.monotonic()
        result = CycleResult()

        # 1. Load gaps
        gaps = self._load_gaps()
        result.gaps_scanned = len(gaps)

        if not gaps:
            logger.info("curiosity_cycle: no gaps found")
            result.duration_seconds = time.monotonic() - start
            return result

        # 2. Prioritize
        prioritized = self._prioritize(gaps)[:max_gaps]

        # 3. Process each gap
        for gap in prioritized:
            try:
                created = await self._process_gap(gap, result)
                if not created:
                    continue
            except Exception as e:
                logger.error("curiosity_cycle: error processing gap '%s': %s", gap.topic[:30], e)
                result.errors += 1

        # 4. Expire stale proposals
        try:
            await self.store.expire_stale()
        except Exception as e:
            logger.warning("curiosity_cycle: expire_stale failed: %s", e)

        result.duration_seconds = time.monotonic() - start

        logger.info(
            "curiosity_cycle_complete: gaps=%d proposals=%d errors=%d duration=%.1fs",
            result.gaps_scanned,
            result.proposals_created,
            result.errors,
            result.duration_seconds,
        )

        return result

    async def _process_gap(self, gap: GapTopic, result: CycleResult) -> bool:
        """Process a single gap: dispatch → grade → propose.

        Returns True if a proposal was created.
        """
        gap_id = f"{gap.domain}:{gap.topic}"

        # Dedup check
        if await self.store.is_duplicate(gap_id, gap.domain):
            result.skipped_dedup += 1
            logger.debug("curiosity: skip dedup '%s'", gap.topic[:30])
            return False

        # Blacklist check
        if await self.store.is_blacklisted(gap_id):
            result.skipped_blacklisted += 1
            logger.debug("curiosity: skip blacklisted '%s'", gap.topic[:30])
            return False

        # Classify tier
        tier = self.classify_tier(gap)

        # Dispatch research
        evidence = await self._dispatch(gap, tier)

        # Grade evidence
        grade = self.grader.grade(
            gap_topic=gap.topic,
            domain=gap.domain,
            evidence=evidence,
        )

        if grade.decision != "propose":
            logger.info(
                "curiosity: not proposing '%s': %s (score=%.2f)",
                gap.topic[:30], grade.decision, grade.score,
            )
            return False

        # Build proposal
        proposal = self._build_proposal(gap, evidence, grade, tier)
        await self.store.save(proposal)

        # Update result metrics
        result.proposals_created += 1
        result.proposals_by_tier[tier.value] = result.proposals_by_tier.get(tier.value, 0) + 1
        result.proposals_by_domain[gap.domain] = result.proposals_by_domain.get(gap.domain, 0) + 1

        return True

    def _load_gaps(self) -> list[GapTopic]:
        """Load gap topics from coverage_matrix.json."""
        path = Path(self.coverage_matrix_path)
        if not path.exists():
            logger.warning("curiosity: coverage_matrix not found at %s", path)
            return []

        try:
            with open(path) as f:
                matrix = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("curiosity: failed to load coverage_matrix: %s", e)
            return []

        gaps: list[GapTopic] = []
        for domain, data in matrix.items():
            if domain.startswith("_"):
                continue  # Skip metadata fields

            coverage = data.get("coverage", {})
            for topic, freshness in coverage.items():
                severity = FRESHNESS_SEVERITY.get(freshness, 0.0)
                if severity > 0.0:  # Only non-FRESH topics
                    gaps.append(
                        GapTopic(
                            domain=domain,
                            topic=topic,
                            freshness=freshness,
                            severity=severity,
                        )
                    )

        logger.info("curiosity: loaded %d gap topics from coverage_matrix", len(gaps))
        return gaps

    def _prioritize(self, gaps: list[GapTopic]) -> list[GapTopic]:
        """Prioritize gaps by severity × domain_importance.

        Higher score = process first.
        """
        def priority_score(gap: GapTopic) -> float:
            domain_weight = DOMAIN_PRIORITY.get(gap.domain, 0.5)
            return gap.severity * domain_weight

        return sorted(gaps, key=priority_score, reverse=True)

    def classify_tier(self, gap: GapTopic) -> Tier:
        """Classify gap into research tier.

        Tier 1 (Simple): Specific regulatory topics in critical domains
        Tier 2 (Medium): Cross-domain topics or topics needing expansion
        Tier 3 (Complex): Novel topics with no existing KG coverage
        """
        topic_lower = gap.topic.lower()

        # Cross-domain keywords → tier 2
        if any(kw in topic_lower for kw in CROSS_DOMAIN_KEYWORDS):
            return Tier.MEDIUM

        # Critical domain + specific (not broad) → tier 1
        if gap.domain in CRITICAL_DOMAINS:
            # Broad topics (contain "overview", "general", "all", "comprehensive") → tier 2
            broad_keywords = {"overview", "general", "all ", "comprehensive", "complete guide"}
            if any(kw in topic_lower for kw in broad_keywords):
                return Tier.MEDIUM
            return Tier.SIMPLE

        # Non-critical domains → tier 2 (need more research)
        if gap.domain in {"editorial", "lifestyle"}:
            return Tier.MEDIUM

        return Tier.SIMPLE

    async def _dispatch(self, gap: GapTopic, tier: Tier) -> list[ResearchEvidence]:
        """Dispatch research to appropriate tier."""
        try:
            if tier == Tier.SIMPLE:
                return await self.simple.dispatch(
                    topic=gap.topic,
                    domain=gap.domain,
                    follow_up_queries=gap.follow_up_queries,
                )
            elif tier == Tier.MEDIUM:
                return await self.medium.dispatch(
                    topic=gap.topic,
                    domain=gap.domain,
                    follow_up_queries=gap.follow_up_queries,
                )
            elif tier == Tier.COMPLEX:
                return await self.complex.dispatch(
                    topic=gap.topic,
                    domain=gap.domain,
                    follow_up_queries=gap.follow_up_queries,
                )
        except Exception as e:
            logger.error("curiosity_dispatch: failed tier=%s gap='%s': %s", tier, gap.topic[:30], e)

        return []

    def _build_proposal(
        self,
        gap: GapTopic,
        evidence: list[ResearchEvidence],
        grade: Any,
        tier: Tier,
    ) -> KGProposal:
        """Build a KG proposal from graded evidence."""
        gap_id = f"{gap.domain}:{gap.topic}"

        # Merge evidence into a single content blob
        merged_content = "\n\n".join(e.content for e in evidence if e.content)
        all_citations = []
        for e in evidence:
            all_citations.extend(e.citations)

        evidence_sources = [
            {
                "content": e.content[:500],
                "source_type": e.source_type,
                "citations": e.citations,
                "confidence": e.confidence,
            }
            for e in evidence
        ]

        # Determine proposal type based on content
        # Default: node proposal (enrich domain knowledge)
        return KGProposal(
            gap_id=gap_id,
            domain=gap.domain,
            proposal_type=ProposalType.NODE,
            tier=tier,
            node_label=gap.topic,
            node_type=gap.domain.capitalize(),
            node_properties={
                "description": merged_content[:1000],
                "gap_origin": True,
                "citations": all_citations[:10],
                "freshness": gap.freshness,
            },
            evidence_sources=evidence_sources,
            self_rag_score=grade.score,
            research_method=f"curiosity_{tier.value}",
            metadata={
                "grade_reason": grade.reason,
                "grade_decision": grade.decision,
            },
        )
