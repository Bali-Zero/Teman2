"""Auto-expiry and cross-referencing for Naga claims.

Provides two batch operations:

1. **expire_stale_claims**: Marks claims past their expires_at date as
   claim_status='expired'. Does NOT delete them.

2. **cross_reference_claims**: Finds claims from different sessions that
   corroborate each other (same domain, high similarity, different session).
   Links them via naga_claim_transitions type='corroborates' and optionally
   boosts quality_score of the corroborated claim.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from backend.services.naga.quality.dedup import trigram_similarity

logger = logging.getLogger(__name__)

# Cross-reference threshold is lower than dedup — we want to catch
# claims that say similar things, not just exact duplicates
_CROSS_REF_SIMILARITY_THRESHOLD = 0.70

# Quality boost when a claim is corroborated by another session
_CORROBORATION_BOOST = 0.10


# ---------------------------------------------------------------------------
# Auto-expiry
# ---------------------------------------------------------------------------


async def expire_stale_claims(
    pool: Any,
    reference_date: date | None = None,
) -> int:
    """Mark claims past their expires_at as expired.

    Only affects claims with claim_status='active' and expires_at <= today.
    Sets claim_status='expired' and expired_at=NOW().

    Args:
        pool: asyncpg connection pool.
        reference_date: Override for testing.

    Returns:
        Number of claims expired.
    """
    ref = reference_date or date.today()

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE naga_claims
            SET claim_status = 'expired',
                expired_at = NOW()
            WHERE claim_status = 'active'
              AND expires_at IS NOT NULL
              AND expires_at <= $1
            """,
            ref,
        )

    # Parse "UPDATE N" from result string
    count = int(result.split()[-1]) if result else 0
    logger.info("Expired %d stale claims (reference_date=%s)", count, ref)
    return count


# ---------------------------------------------------------------------------
# Cross-referencing
# ---------------------------------------------------------------------------


async def cross_reference_claims(
    pool: Any,
    threshold: float = _CROSS_REF_SIMILARITY_THRESHOLD,
    boost: float = _CORROBORATION_BOOST,
) -> int:
    """Find corroborating claims across sessions and link them.

    For each active claim, checks if claims from OTHER sessions say
    the same thing. When found:
    1. Creates a naga_claim_transitions record (type='corroborates')
    2. Boosts quality_score of the older (canonical) claim
    3. Increments cross_ref_count on the older claim

    Args:
        pool: asyncpg connection pool.
        threshold: Similarity threshold for corroboration.
        boost: Quality score boost per corroboration (capped at 1.0).

    Returns:
        Number of new corroboration links created.
    """
    links_created = 0

    async with pool.acquire() as conn:
        domains = await conn.fetch("""
            SELECT DISTINCT domain FROM naga_claims
            WHERE claim_status = 'active'
        """)

        for domain_row in domains:
            domain = domain_row["domain"]

            claims = await conn.fetch("""
                SELECT id, session_id, claim_text, quality_score, cross_ref_count
                FROM naga_claims
                WHERE domain = $1 AND claim_status = 'active'
                ORDER BY created_at ASC
            """, domain)

            # Check existing transitions to avoid re-processing
            existing = set()
            transitions = await conn.fetch("""
                SELECT from_claim_id, to_claim_id
                FROM naga_claim_transitions
                WHERE transition_type = 'corroborates'
            """)
            for t in transitions:
                existing.add((str(t["from_claim_id"]), str(t["to_claim_id"])))

            # Compare each pair from different sessions
            for i, newer in enumerate(claims):
                for j in range(i):
                    older = claims[j]

                    # Must be from different sessions
                    if newer["session_id"] == older["session_id"]:
                        continue

                    pair_key = (str(newer["id"]), str(older["id"]))
                    if pair_key in existing:
                        continue

                    sim = trigram_similarity(
                        newer["claim_text"], older["claim_text"],
                    )
                    if sim < threshold:
                        continue

                    # Create corroboration link
                    await conn.execute(
                        """
                        INSERT INTO naga_claim_transitions (
                            from_claim_id, to_claim_id,
                            transition_type, reason, detected_by
                        ) VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (from_claim_id, to_claim_id, transition_type) DO NOTHING
                        """,
                        newer["id"],
                        older["id"],
                        "corroborates",
                        f"cross_session_similarity={sim:.4f}",
                        "naga_xref_v1",
                    )

                    # Boost quality_score and cross_ref_count on the older claim
                    current_quality = float(older["quality_score"] or 0.0)
                    new_quality = min(1.0, current_quality + boost)
                    current_xref = int(older["cross_ref_count"] or 0)

                    await conn.execute(
                        """
                        UPDATE naga_claims
                        SET quality_score = $2,
                            cross_ref_count = $3
                        WHERE id = $1
                        """,
                        older["id"],
                        new_quality,
                        current_xref + 1,
                    )

                    links_created += 1
                    existing.add(pair_key)

            logger.info(
                "Cross-ref domain=%s: %d claims, %d new links",
                domain,
                len(claims),
                links_created,
            )

    logger.info("Cross-reference complete: %d new corroboration links", links_created)
    return links_created
