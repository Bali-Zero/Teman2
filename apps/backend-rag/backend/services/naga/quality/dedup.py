"""Fuzzy deduplication for Naga claims.

Uses trigram-based similarity on claim_text to detect near-duplicate claims
across sessions. When a duplicate is found:

1. The newer claim gets claim_status='duplicate' and duplicate_of_id set
2. A naga_claim_transitions record is created (type='duplicate')
3. The original claim is NOT modified

Similarity is computed in Python using a fast character-trigram Jaccard
coefficient, avoiding the need for pg_trgm extension on Fly.io PostgreSQL.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trigram similarity (pure Python, no pg_trgm needed)
# ---------------------------------------------------------------------------

_SIMILARITY_THRESHOLD = 0.85


def _trigrams(text: str) -> set[str]:
    """Generate character trigrams from text.

    Pads with spaces like PostgreSQL pg_trgm for compatibility.
    """
    padded = f"  {text.lower().strip()}  "
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def trigram_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity of character trigrams.

    Returns a value in [0, 1] where 1.0 means identical trigram sets.
    """
    if not a or not b:
        return 0.0

    tg_a = _trigrams(a)
    tg_b = _trigrams(b)

    intersection = len(tg_a & tg_b)
    union = len(tg_a | tg_b)

    return intersection / union if union > 0 else 0.0


def similarity_hash(text: str) -> str:
    """Generate a hash from sorted trigrams for fast pre-filtering.

    Claims sharing the same similarity_hash are likely duplicates.
    This is a coarse filter — actual similarity check follows.
    """
    # Use first 200 chars, normalized
    normalized = text[:200].lower().strip()
    # Hash the sorted trigram set
    tg = sorted(_trigrams(normalized))
    combined = "".join(tg[:20])  # Use first 20 trigrams for hash
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Dedup on single claim (called during persist)
# ---------------------------------------------------------------------------


async def find_duplicate(
    conn: Any,
    claim_text: str,
    domain: str,
    exclude_claim_id: str | None = None,
    threshold: float = _SIMILARITY_THRESHOLD,
) -> dict | None:
    """Find an existing active claim that is a near-duplicate.

    Searches within the same domain, comparing against active claims only.
    Uses a two-pass strategy:
    1. Fetch candidates from the same domain (limited to recent 500)
    2. Compute trigram similarity in Python

    Args:
        conn: asyncpg connection.
        claim_text: Text of the new claim.
        domain: Domain to search within.
        exclude_claim_id: UUID to exclude (the claim itself).
        threshold: Similarity threshold [0, 1].

    Returns:
        Dict with {id, claim_text, similarity} of the best match, or None.
    """
    # Fetch recent active claims in the same domain
    query = """
        SELECT id, claim_text
        FROM naga_claims
        WHERE domain = $1
          AND claim_status = 'active'
          AND ($2::uuid IS NULL OR id != $2)
        ORDER BY created_at DESC
        LIMIT 500
    """
    exclude_uuid = uuid.UUID(exclude_claim_id) if exclude_claim_id else None
    rows = await conn.fetch(query, domain, exclude_uuid)

    best_match: dict | None = None
    best_sim = 0.0

    for row in rows:
        sim = trigram_similarity(claim_text, row["claim_text"])
        if sim >= threshold and sim > best_sim:
            best_sim = sim
            best_match = {
                "id": str(row["id"]),
                "claim_text": row["claim_text"],
                "similarity": round(sim, 4),
            }

    return best_match


async def mark_as_duplicate(
    conn: Any,
    claim_id: str,
    duplicate_of_id: str,
    similarity: float,
) -> None:
    """Mark a claim as duplicate and create a transition record.

    Args:
        conn: asyncpg connection.
        claim_id: UUID of the duplicate claim.
        duplicate_of_id: UUID of the canonical claim.
        similarity: Measured similarity score.
    """
    await conn.execute(
        """
        UPDATE naga_claims
        SET claim_status = 'duplicate',
            duplicate_of_id = $2
        WHERE id = $1
        """,
        uuid.UUID(claim_id),
        uuid.UUID(duplicate_of_id),
    )

    await conn.execute(
        """
        INSERT INTO naga_claim_transitions (
            from_claim_id, to_claim_id, transition_type, reason, detected_by
        ) VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (from_claim_id, to_claim_id, transition_type) DO NOTHING
        """,
        uuid.UUID(claim_id),
        uuid.UUID(duplicate_of_id),
        "duplicate",
        f"trigram_similarity={similarity:.4f}",
        "naga_dedup_v1",
    )

    logger.info(
        "Marked claim %s as duplicate of %s (sim=%.4f)",
        claim_id[:8],
        duplicate_of_id[:8],
        similarity,
    )


# ---------------------------------------------------------------------------
# Batch dedup — scan all active claims for duplicates
# ---------------------------------------------------------------------------


async def batch_dedup(
    pool: Any,
    threshold: float = _SIMILARITY_THRESHOLD,
) -> int:
    """Scan all active claims and mark duplicates.

    Groups by domain, then checks each claim against earlier claims.
    The older claim (by created_at) is always the canonical one.

    Args:
        pool: asyncpg connection pool.
        threshold: Similarity threshold.

    Returns:
        Number of claims marked as duplicate.
    """
    marked = 0

    async with pool.acquire() as conn:
        domains = await conn.fetch("""
            SELECT DISTINCT domain FROM naga_claims
            WHERE claim_status = 'active'
        """)

        for domain_row in domains:
            domain = domain_row["domain"]

            # Fetch all active claims in this domain, oldest first
            claims = await conn.fetch("""
                SELECT id, claim_text, created_at
                FROM naga_claims
                WHERE domain = $1 AND claim_status = 'active'
                ORDER BY created_at ASC
            """, domain)

            # Compare each claim against all earlier claims
            canonical: list[dict] = []
            for claim in claims:
                claim_id = str(claim["id"])
                text = claim["claim_text"]

                # Check against all canonical claims so far
                best_match = None
                best_sim = 0.0
                for canon in canonical:
                    sim = trigram_similarity(text, canon["text"])
                    if sim >= threshold and sim > best_sim:
                        best_sim = sim
                        best_match = canon

                if best_match:
                    await mark_as_duplicate(
                        conn, claim_id, best_match["id"], best_sim,
                    )
                    marked += 1
                else:
                    # This claim is canonical
                    canonical.append({"id": claim_id, "text": text})

            logger.info(
                "Dedup domain=%s: %d claims, %d canonical, %d duplicates",
                domain,
                len(claims),
                len(canonical),
                len(claims) - len(canonical),
            )

    logger.info("Batch dedup complete: %d claims marked as duplicate", marked)
    return marked
