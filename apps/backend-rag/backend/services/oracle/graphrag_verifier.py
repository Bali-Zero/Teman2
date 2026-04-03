"""ARCH-7: GraphRAG Verification Layer.

Verifies NLM enrichment claims against the local Knowledge Graph.
Catches NLM hallucinations by cross-referencing extracted claims with
KG nodes/edges (REQUIRES, HAS_FEE, HAS_DURATION, ENABLES, etc.).

Scoring:
    HIGH   — KG confirms: 2+ relevant nodes + at least 1 meaningful edge
    MEDIUM — KG is silent: 1 node found OR no meaningful edge
    LOW    — KG contradicts or cannot verify: 0 nodes found

Usage (from orchestrator_core.py — after NLM enrichment merge):

    from backend.services.oracle.graphrag_verifier import GraphRAGVerifier, get_verifier

    verifier = get_verifier(db_pool)
    kg_result = await verifier.verify(nlm_response_text)
    result.kg_verification = {
        "status": kg_result.overall_status,   # HIGH | MEDIUM | LOW
        "score": kg_result.score,             # 0.0–1.0
        "claims_verified": kg_result.claims_verified,
        "claims_total": kg_result.claims_total,
        "evidence": kg_result.evidence[:5],   # top evidence paths
        "hallucination_risk": kg_result.hallucination_risk,  # bool
    }
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Relationship types considered "meaningful" for HIGH classification
STRONG_EDGE_TYPES = frozenset({
    "REQUIRES", "HAS_FEE", "HAS_DURATION", "ENABLES",
    "REQUIRED_FOR", "APPLIES_TO", "AUTHORIZES", "PENALTY_FOR",
})

# Stop words excluded from keyword extraction
_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "in", "to", "for", "is", "are",
    "was", "be", "by", "on", "at", "from", "with", "this", "that", "it",
    "its", "as", "can", "has", "have", "must", "not", "no", "their",
    "which", "will", "does", "do", "if", "also", "only", "all", "any",
    "each", "both", "per", "under", "over", "about", "than", "then",
    "when", "where", "who", "what", "how", "into", "out", "up", "new",
    "following", "required", "need", "needs", "minimum", "maximum",
    "foreign", "indonesia", "indonesian", "company", "work", "working",
})

# Minimum claim length (chars) to bother verifying
MIN_CLAIM_LEN = 40

# Max claims to verify per NLM response (performance cap)
MAX_CLAIMS = 12

# KG query timeout (seconds) — used as per-query hint in caller
KG_TIMEOUT = 3.0

# HIGH threshold: what fraction of claims must be verified HIGH/MEDIUM
HIGH_FRACTION = 0.60
MEDIUM_FRACTION = 0.35

# Contradiction keywords — presence in claim + opposing KG fact → LOW risk
_CONTRADICT_SIGNALS = frozenset({
    "cannot", "not allowed", "prohibited", "forbidden", "illegal",
    "not permitted", "tidak boleh", "dilarang", "tidak diizinkan",
})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ClaimVerification:
    """Verification result for a single extracted claim."""
    text: str
    status: str             # "HIGH" | "MEDIUM" | "LOW"
    nodes_found: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class GraphRAGResult:
    """Aggregated verification result for a full NLM response."""
    overall_status: str           # "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN"
    score: float                  # 0.0–1.0
    claims_verified: int          # claims with HIGH or MEDIUM status
    claims_total: int             # total claims extracted
    evidence: list[str]           # top evidence paths
    hallucination_risk: bool      # True if LOW overall (KG contradicts)
    claim_details: list[ClaimVerification] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------------

def extract_claims_for_verification(text: str, max_claims: int = MAX_CLAIMS) -> list[str]:
    """Extract verifiable sentence-level claims from NLM response text.

    Handles NLM JSON wrapper (value.answer) transparently.
    """
    if not text:
        return []

    # Unwrap NLM JSON envelope if present
    raw = text
    if '"answer"' in text:
        import json as _json
        try:
            parsed = _json.loads(text)
            # Handle {"value": {"answer": ...}} wrapper
            if isinstance(parsed, dict):
                inner = parsed.get("value", parsed)
                raw = inner.get("answer", text) if isinstance(inner, dict) else text
        except Exception:
            # Not valid JSON — treat as plain text
            pass

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+|\n+', raw)
    claims = []
    for sent in sentences:
        # Strip markdown, citations like [1,2], bullets
        clean = re.sub(r'\[[\d,\s]+\]', '', sent)
        clean = re.sub(r'[*_#`]', '', clean)
        clean = clean.strip(' •-–')
        if len(clean) >= MIN_CLAIM_LEN:
            claims.append(clean)
        if len(claims) >= max_claims:
            break

    return claims


def extract_keywords(text: str, min_len: int = 5) -> list[str]:
    """Extract meaningful keywords from a claim for KG lookup."""
    words = re.findall(r'\b[A-Za-z][A-Za-z\-]{3,}\b', text)
    # Also grab Indonesian/technical terms (uppercase abbreviations)
    abbrevs = re.findall(r'\b[A-Z]{2,8}\b', text)
    candidates = [w.lower() for w in words if w.lower() not in _STOP_WORDS and len(w) >= min_len]
    candidates += [a.lower() for a in abbrevs if a not in _STOP_WORDS]
    # Deduplicate preserving order
    seen: set[str] = set()
    result = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result[:8]  # cap at 8 keywords per claim


# ---------------------------------------------------------------------------
# GraphRAG Verifier
# ---------------------------------------------------------------------------

class GraphRAGVerifier:
    """Verifies NLM claims against the Knowledge Graph.

    Requires an asyncpg connection pool (db_pool). If pool is None,
    all verifications return UNKNOWN (graceful degradation).
    """

    def __init__(self, db_pool: Any = None) -> None:
        self.db_pool = db_pool

    async def verify(self, nlm_text: str) -> GraphRAGResult:
        """Verify NLM response text against KG.

        Args:
            nlm_text: Raw NLM response (may be JSON envelope or plain text).

        Returns:
            GraphRAGResult with overall_status, score, evidence.
        """
        if not self.db_pool or not nlm_text:
            return GraphRAGResult(
                overall_status="UNKNOWN",
                score=0.5,
                claims_verified=0,
                claims_total=0,
                evidence=[],
                hallucination_risk=False,
            )

        claims = extract_claims_for_verification(nlm_text)
        if not claims:
            return GraphRAGResult(
                overall_status="UNKNOWN",
                score=0.5,
                claims_verified=0,
                claims_total=0,
                evidence=[],
                hallucination_risk=False,
            )

        claim_results: list[ClaimVerification] = []
        all_evidence: list[str] = []

        for claim in claims:
            cv = await self._verify_claim(claim)
            claim_results.append(cv)
            all_evidence.extend(cv.evidence[:2])

        # Aggregate
        high_count = sum(1 for c in claim_results if c.status == "HIGH")
        medium_count = sum(1 for c in claim_results if c.status == "MEDIUM")
        low_count = sum(1 for c in claim_results if c.status == "LOW")
        total = len(claim_results)

        verified = high_count + medium_count
        fraction = verified / total if total > 0 else 0.0

        if fraction >= HIGH_FRACTION and high_count > 0:
            overall = "HIGH"
            score = 0.75 + 0.25 * (high_count / total)
        elif fraction >= MEDIUM_FRACTION:
            overall = "MEDIUM"
            score = 0.40 + 0.35 * fraction
        else:
            overall = "LOW"
            score = 0.15 * fraction

        hallucination_risk = overall == "LOW" or (low_count > total * 0.5)

        logger.info(
            "GraphRAG verify: overall=%s score=%.2f claims=%d H=%d M=%d L=%d",
            overall, score, total, high_count, medium_count, low_count,
        )

        return GraphRAGResult(
            overall_status=overall,
            score=round(score, 3),
            claims_verified=verified,
            claims_total=total,
            evidence=list(dict.fromkeys(all_evidence))[:10],  # dedup, top 10
            hallucination_risk=hallucination_risk,
            claim_details=claim_results,
        )

    async def _verify_claim(self, claim: str) -> ClaimVerification:
        """Verify a single claim against KG."""
        keywords = extract_keywords(claim)
        if not keywords:
            return ClaimVerification(text=claim, status="LOW")

        nodes_found: list[str] = []
        evidence: list[str] = []

        try:
            async with self.db_pool.acquire() as conn:
                # Find nodes matching any keyword
                for keyword in keywords[:5]:
                    rows = await conn.fetch(
                        """
                        SELECT entity_id, name, entity_type
                        FROM kg_nodes
                        WHERE LOWER(name) LIKE $1
                        LIMIT 3
                        """,
                        f"%{keyword}%",
                    )
                    for row in rows:
                        node_name = row["name"]
                        if node_name not in nodes_found:
                            nodes_found.append(node_name)

                if not nodes_found:
                    return ClaimVerification(text=claim, status="LOW", nodes_found=[])

                # Look for strong edges between found nodes
                node_names_lower = [n.lower() for n in nodes_found[:6]]
                edge_rows = await conn.fetch(
                    """
                    SELECT n1.name as src, e.relationship_type, n2.name as tgt
                    FROM kg_edges e
                    JOIN kg_nodes n1 ON e.source_entity_id = n1.entity_id
                    JOIN kg_nodes n2 ON e.target_entity_id = n2.entity_id
                    WHERE (LOWER(n1.name) = ANY($1) OR LOWER(n2.name) = ANY($1))
                      AND e.relationship_type = ANY($2)
                    LIMIT 5
                    """,
                    node_names_lower,
                    list(STRONG_EDGE_TYPES),
                )
                for row in edge_rows:
                    path = f"{row['src']} → {row['relationship_type']} → {row['tgt']}"
                    if path not in evidence:
                        evidence.append(path)

        except Exception as exc:
            logger.debug("GraphRAG KG query error for claim: %s", exc)
            return ClaimVerification(text=claim, status="MEDIUM", nodes_found=nodes_found)

        # Classify
        if len(nodes_found) >= 2 and len(evidence) >= 1:
            status = "HIGH"
        elif len(nodes_found) >= 1:
            status = "MEDIUM"
        else:
            status = "LOW"

        return ClaimVerification(
            text=claim,
            status=status,
            nodes_found=nodes_found[:5],
            evidence=evidence,
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_verifier: Optional[GraphRAGVerifier] = None


def get_verifier(db_pool: Any = None) -> GraphRAGVerifier:
    """Return module-level GraphRAGVerifier singleton.

    If db_pool is provided on first call, it is stored. Subsequent calls
    with db_pool=None reuse the existing instance.
    """
    global _verifier
    if _verifier is None or (db_pool is not None and _verifier.db_pool is None):
        _verifier = GraphRAGVerifier(db_pool=db_pool)
    return _verifier


def reset_verifier() -> None:
    """Reset singleton (test use only)."""
    global _verifier
    _verifier = None
