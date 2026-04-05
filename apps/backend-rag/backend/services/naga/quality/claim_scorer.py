"""Claim quality scorer — composite score for ranking and lifecycle.

Computes a quality_score in [0, 1] from three signals:

    quality = freshness_decay × source_reliability × verification_boost

Where:
    - freshness_decay: exponential decay based on days since valid_as_of
    - source_reliability: weighted credibility of backing sources
    - verification_boost: multiplier based on verification_level

This score is SEPARATE from the extraction-time ``confidence`` score.
Confidence measures how certain we are the claim was correctly extracted.
Quality measures how useful/trustworthy the claim is RIGHT NOW.
"""

from __future__ import annotations

import logging
import math
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Freshness decay — exponential half-life model
# ---------------------------------------------------------------------------

# Half-life in days: after this many days, freshness = 0.5
_HALF_LIFE_DEFAULT = 90
_HALF_LIFE_VISA = 30  # visa/immigration changes fast

_FAST_DECAY_DOMAINS = frozenset({"visa", "immigration"})


def freshness_decay(
    valid_as_of: date | None,
    domain: str = "general",
    reference_date: date | None = None,
) -> float:
    """Compute freshness score in [0, 1] using exponential decay.

    Args:
        valid_as_of: Date the claim was valid as of.
        domain: Claim domain — visa/immigration use shorter half-life.
        reference_date: Override for "today" (useful in tests).

    Returns:
        Freshness score. 1.0 = brand new, 0.5 = half-life reached.
    """
    if valid_as_of is None:
        return 0.5  # unknown age = neutral

    ref = reference_date or date.today()
    age_days = max(0, (ref - valid_as_of).days)

    half_life = _HALF_LIFE_VISA if domain in _FAST_DECAY_DOMAINS else _HALF_LIFE_DEFAULT

    # Exponential decay: 2^(-age/half_life)
    return math.pow(2, -age_days / half_life)


# ---------------------------------------------------------------------------
# Source reliability
# ---------------------------------------------------------------------------


def source_reliability(
    cross_ref_count: int,
    credibility_scores: list[float] | None = None,
) -> float:
    """Compute source reliability in [0, 1].

    Combines:
    - Cross-reference count (more sources = more reliable, saturates at 5)
    - Average credibility of backing sources (if available)

    Args:
        cross_ref_count: Number of distinct sources backing the claim.
        credibility_scores: Optional list of credibility scores from sources.

    Returns:
        Reliability score in [0, 1].
    """
    # Corroboration factor: saturates at 5 sources
    corroboration = min(1.0, cross_ref_count / 5) if cross_ref_count > 0 else 0.2

    if credibility_scores:
        avg_cred = sum(credibility_scores) / len(credibility_scores)
    else:
        avg_cred = 0.5  # unknown credibility = neutral

    # Weighted blend: 60% corroboration, 40% credibility
    return 0.6 * corroboration + 0.4 * avg_cred


# ---------------------------------------------------------------------------
# Verification boost
# ---------------------------------------------------------------------------

_VERIFICATION_BOOST: dict[str, float] = {
    "VERIFIED": 1.0,
    "PROVISIONAL": 0.75,
    "LOW": 0.5,
}


def verification_boost(verification_level: str | None) -> float:
    """Map verification_level to a multiplier in [0.5, 1.0]."""
    return _VERIFICATION_BOOST.get(verification_level or "", 0.5)


# ---------------------------------------------------------------------------
# Composite quality score
# ---------------------------------------------------------------------------


def compute_quality_score(
    valid_as_of: date | None,
    domain: str,
    cross_ref_count: int,
    verification_level: str | None,
    credibility_scores: list[float] | None = None,
    reference_date: date | None = None,
) -> float:
    """Compute composite quality score in [0, 1].

    quality = freshness × reliability × verification_boost

    Args:
        valid_as_of: Date the claim was extracted/valid.
        domain: Claim domain.
        cross_ref_count: Number of backing sources.
        verification_level: VERIFIED / PROVISIONAL / LOW.
        credibility_scores: Optional source credibility scores.
        reference_date: Override for testing.

    Returns:
        Quality score rounded to 4 decimals.
    """
    f = freshness_decay(valid_as_of, domain, reference_date)
    r = source_reliability(cross_ref_count, credibility_scores)
    v = verification_boost(verification_level)

    score = f * r * v
    return round(min(1.0, max(0.0, score)), 4)


# ---------------------------------------------------------------------------
# Batch rescore — update quality_score for all active claims
# ---------------------------------------------------------------------------


async def batch_rescore(pool: Any, reference_date: date | None = None) -> int:
    """Recompute quality_score for all active claims in the DB.

    Reads each claim's valid_as_of, domain, cross_ref_count,
    verification_level, and average source credibility, then updates
    quality_score in place.

    Args:
        pool: asyncpg connection pool.
        reference_date: Override for testing.

    Returns:
        Number of claims rescored.
    """
    ref = reference_date or date.today()

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                c.id,
                c.valid_as_of,
                c.domain,
                c.cross_ref_count,
                c.verification_level,
                COALESCE(
                    ARRAY_AGG(s.credibility_score) FILTER (WHERE s.credibility_score IS NOT NULL),
                    ARRAY[]::float[]
                ) AS cred_scores
            FROM naga_claims c
            LEFT JOIN naga_claim_evidence ce ON ce.claim_id = c.id
            LEFT JOIN naga_sources s ON s.id = ce.source_id
            WHERE c.claim_status = 'active'
            GROUP BY c.id
        """)

        updated = 0
        for row in rows:
            cred_list = list(row["cred_scores"]) if row["cred_scores"] else []
            score = compute_quality_score(
                valid_as_of=row["valid_as_of"],
                domain=row["domain"] or "general",
                cross_ref_count=row["cross_ref_count"] or 0,
                verification_level=row["verification_level"],
                credibility_scores=cred_list,
                reference_date=ref,
            )
            await conn.execute(
                "UPDATE naga_claims SET quality_score = $1 WHERE id = $2",
                score,
                row["id"],
            )
            updated += 1

    logger.info("Batch rescore: updated %d claims", updated)
    return updated
