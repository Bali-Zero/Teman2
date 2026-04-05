"""Naga DB persistence — saves sessions, sources, and claims to PostgreSQL.

Called by the orchestrator after each research completes.
Uses asyncpg directly (no ORM) following the project pattern.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date, timedelta
from typing import Any

import asyncpg

from backend.core.claims.models import ClaimRecord
from backend.services.naga.quality.claim_scorer import compute_quality_score

logger = logging.getLogger(__name__)


async def save_session(
    pool: asyncpg.Pool,
    state: dict[str, Any],
) -> str | None:
    """Persist a completed research session + sources + claims.

    Returns the session UUID or None on failure.
    """
    session_id = str(uuid.uuid4())

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # 1. Insert session
                await conn.execute(
                    """
                    INSERT INTO naga_sessions (
                        id, query, tier, domain, mode, channel,
                        trusted_mode, status,
                        duration_ms, iterations, search_calls,
                        sources_found, claims_extracted, avg_confidence,
                        report_markdown, report_drive_path,
                        action_items, evidence_map_uri,
                        sub_questions, url_history,
                        langgraph_thread_id, completed_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6,
                        $7, $8,
                        $9, $10, $11,
                        $12, $13, $14,
                        $15, $16,
                        $17::jsonb, $18,
                        $19::jsonb, $20,
                        $21, NOW()
                    )
                    """,
                    uuid.UUID(session_id),
                    state.get("query", ""),
                    state.get("tier", "flash"),
                    state.get("domain", "general"),
                    state.get("mode", "oneshot"),
                    state.get("channel", ""),
                    False,  # trusted_mode
                    state.get("status", "completed"),
                    state.get("duration_ms", 0),
                    state.get("iteration", 0),
                    state.get("search_calls_used", 0),
                    len(state.get("search_results", [])),
                    state.get("claims_extracted", 0),
                    state.get("avg_confidence", 0.0),
                    state.get("report_markdown", ""),
                    "",  # report_drive_path
                    "[]",  # action_items jsonb
                    state.get("evidence_map_uri", ""),
                    "[]",  # sub_questions jsonb
                    state.get("url_history", []),
                    "",  # langgraph_thread_id
                )

                # 2. Insert sources
                search_results = state.get("search_results", [])
                source_id_map: dict[str, str] = {}  # url -> source uuid

                for sr in search_results:
                    url = sr.get("url", "")
                    if not url:
                        continue
                    src_id = str(uuid.uuid4())
                    source_id_map[url] = src_id

                    content_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
                    domain_str = ""
                    if url.startswith("http"):
                        from urllib.parse import urlparse
                        domain_str = urlparse(url).netloc

                    await conn.execute(
                        """
                        INSERT INTO naga_sources (
                            id, session_id, url, title, domain,
                            source_type, credibility_score, content_hash
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (url, session_id) DO NOTHING
                        """,
                        uuid.UUID(src_id),
                        uuid.UUID(session_id),
                        url,
                        sr.get("title", ""),
                        domain_str,
                        sr.get("source_type", "web"),
                        sr.get("relevance_score", 0.0),
                        content_hash,
                    )

                # 3. Insert claims with quality scoring
                claims_data: list[ClaimRecord] = state.get("_claims", [])
                domain_str = state.get("domain", "general")
                today = date.today()

                for claim in claims_data:
                    claim_id = str(uuid.uuid4())
                    claim_key = hashlib.sha256(
                        claim.claim_text[:200].lower().strip().encode()
                    ).hexdigest()[:32]

                    # Compute quality score at insertion time
                    cross_ref = len(claim.source_ids)
                    cred_scores = _collect_credibility_scores(
                        claim.source_ids, search_results, source_id_map, conn,
                    )
                    quality = compute_quality_score(
                        valid_as_of=today,
                        domain=domain_str,
                        cross_ref_count=cross_ref,
                        verification_level=claim.confidence_class,
                        credibility_scores=cred_scores,
                    )

                    # Set expiry: 30 days for visa/immigration, 90 days otherwise
                    expiry_days = 30 if domain_str in ("visa", "immigration") else 90
                    expires_at = today + timedelta(days=expiry_days)

                    await conn.execute(
                        """
                        INSERT INTO naga_claims (
                            id, session_id, claim_text, claim_key,
                            domain, verification_level, confidence,
                            cross_ref_count, review_status,
                            valid_as_of, expires_at,
                            quality_score, claim_status
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        """,
                        uuid.UUID(claim_id),
                        uuid.UUID(session_id),
                        claim.claim_text[:2000],
                        claim_key,
                        domain_str,
                        claim.confidence_class,
                        claim.confidence_score,
                        cross_ref,
                        "auto_extracted",  # Human review gate
                        today,
                        expires_at,
                        quality,
                        "active",
                    )

                    # 4. Link claim to sources via naga_claim_evidence
                    for src_ref in claim.source_ids:
                        # src_ref might be "s0", "s1" etc — map to actual source URL
                        try:
                            idx = int(src_ref.replace("s", ""))
                            if idx < len(search_results):
                                src_url = search_results[idx].get("url", "")
                                src_uuid = source_id_map.get(src_url)
                                if src_uuid:
                                    await conn.execute(
                                        """
                                        INSERT INTO naga_claim_evidence (
                                            claim_id, source_id, relation, extraction_method
                                        ) VALUES ($1, $2, $3, $4)
                                        ON CONFLICT (claim_id, source_id, relation) DO NOTHING
                                        """,
                                        uuid.UUID(claim_id),
                                        uuid.UUID(src_uuid),
                                        "supports",
                                        "naga_v1",
                                    )
                        except (ValueError, IndexError):
                            pass

        logger.info(
            "Naga persisted: session=%s sources=%d claims=%d",
            session_id[:8],
            len(source_id_map),
            len(claims_data),
        )
        return session_id

    except Exception as e:
        logger.error("Naga persist failed: %s", e, exc_info=True)
        return None


def _collect_credibility_scores(
    source_ids: list[str],
    search_results: list[dict],
    source_id_map: dict[str, str],
    conn: Any,
) -> list[float]:
    """Extract credibility scores for a claim's source references.

    Source IDs are "s0", "s1" etc — indexes into search_results.
    We pull relevance_score as a proxy for credibility since the actual
    naga_sources.credibility_score is the same value (set during insert).
    """
    scores: list[float] = []
    for src_ref in source_ids:
        try:
            idx = int(src_ref.replace("s", ""))
            if idx < len(search_results):
                score = search_results[idx].get("relevance_score", 0.5)
                scores.append(float(score))
        except (ValueError, IndexError):
            pass
    return scores
