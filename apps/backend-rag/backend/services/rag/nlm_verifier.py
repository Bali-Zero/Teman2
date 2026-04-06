"""
NLM Async Verification Service

Fire-and-forget background task that verifies Zantara's response against NLM.
NOT in the hot path — runs after response is sent to the user.

Trigger: critical domain queries (visa, tax, legal) with evidence score 0.15-0.60.
Rate limit: max 10/hour via Redis (works across workers).
Timeout: 30s per NLM call.
"""

import asyncio
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Critical domains that warrant NLM verification
CRITICAL_DOMAINS: frozenset[str] = frozenset({"visa", "tax", "legal", "immigration"})

# Evidence score window for verification (CAUTIOUS range)
EVIDENCE_MIN: float = 0.15
EVIDENCE_MAX: float = 0.60

# NLM notebook IDs by domain
DOMAIN_NOTEBOOK_MAP: dict[str, str] = {
    "visa": "cff93ab0-813a-42f2-a8de-36987e724271",        # NB-2
    "immigration": "cff93ab0-813a-42f2-a8de-36987e724271",  # NB-2
    "tax": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",         # NB-4
    "legal": "933509f9-1561-403d-bd44-4a7a67a36df2",        # NB-3
}

# Redis rate-limit key and max calls per hour
RATE_KEY: str = "nlm_verify:rate_count"
RATE_LIMIT: int = 10
RATE_TTL: int = 3600  # 1 hour in seconds

# NLM call timeout (seconds) — tight budget, fire-and-forget
NLM_TIMEOUT: int = 30

# ---------------------------------------------------------------------------
# NLM bridge import — graceful degradation if monorepo root not reachable
# ---------------------------------------------------------------------------

_nlm_query_fn: Any = None


def _load_nlm_query() -> Any:
    """Attempt to import nlm_query from the evaluator package.

    Returns the real function if import succeeds, else a no-op stub.
    The import is attempted once and cached in _nlm_query_fn.
    """
    global _nlm_query_fn
    if _nlm_query_fn is not None:
        return _nlm_query_fn

    try:
        import sys
        from pathlib import Path

        # backend/services/rag/nlm_verifier.py → 4 parents → apps/backend-rag
        # → 1 more parent → monorepo root
        monorepo_root = str(Path(__file__).parents[4])
        if monorepo_root not in sys.path:
            sys.path.insert(0, monorepo_root)

        from apps.evaluator.nlm_deep_research.nlm_bridge import nlm_query  # type: ignore

        _nlm_query_fn = nlm_query
        logger.info("nlm_verifier: nlm_query loaded successfully")
    except Exception as exc:  # pragma: no cover
        logger.warning("nlm_verifier: nlm_query unavailable (%s) — verifier disabled", exc)

        def _noop(*args: Any, **kwargs: Any) -> dict:  # type: ignore[misc]
            return {"status": "unavailable", "answer": ""}

        _nlm_query_fn = _noop

    return _nlm_query_fn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def should_verify(
    domain: str,
    evidence_score: float,
    is_greeting: bool,
    is_pricing: bool,
    redis_client: Optional[Any] = None,
) -> bool:
    """Decide whether this response warrants NLM verification.

    Args:
        domain: Classified query domain (e.g. "visa", "tax").
        evidence_score: RAG evidence score for the response (0.0–1.0).
        is_greeting: True when the query is a greeting/small-talk.
        is_pricing: True when the query is a pricing enquiry.
        redis_client: Optional aioredis/redis-py async client for rate limit check.

    Returns:
        True only when all eligibility and rate-limit conditions are met.
    """
    # Fast-path exclusions
    if is_greeting or is_pricing:
        return False

    if domain not in CRITICAL_DOMAINS:
        return False

    if domain not in DOMAIN_NOTEBOOK_MAP:
        return False

    # Evidence must be in the CAUTIOUS range (uncertain, but not garbage)
    if not (EVIDENCE_MIN <= evidence_score <= EVIDENCE_MAX):
        return False

    # Rate-limit check via Redis
    if redis_client is not None:
        try:
            count = await redis_client.get(RATE_KEY)
            if count is not None and int(count) >= RATE_LIMIT:
                logger.debug("nlm_verifier: rate limit reached (%s/%s per hour)", count, RATE_LIMIT)
                return False
        except Exception as exc:
            # Redis unavailable → allow verification (fail-open, but log)
            logger.warning("nlm_verifier: Redis rate-limit check failed (%s), proceeding", exc)

    return True


async def verify_response(
    query: str,
    zantara_answer: str,
    domain: str,
    evidence_score: float,
    db_pool: Optional[Any] = None,
    redis_client: Optional[Any] = None,
) -> None:
    """Run NLM verification for a Zantara response — fire and forget.

    This function MUST NEVER raise an exception.  All errors are caught and
    logged at WARNING level so the main request path is never affected.

    Args:
        query: The user query that produced the response.
        zantara_answer: The answer Zantara returned to the user.
        domain: Classified query domain.
        evidence_score: RAG evidence score.
        db_pool: asyncpg pool for discrepancy logging (optional).
        redis_client: aioredis client for rate limiting (optional).
    """
    try:
        notebook_id = DOMAIN_NOTEBOOK_MAP.get(domain)
        if not notebook_id:
            logger.debug("nlm_verifier: no notebook for domain=%s", domain)
            return

        # Increment rate counter atomically in Redis
        if redis_client is not None:
            try:
                count = await redis_client.incr(RATE_KEY)
                if count == 1:
                    # First increment — set TTL so the key expires after 1 hour
                    await redis_client.expire(RATE_KEY, RATE_TTL)
            except Exception as exc:
                logger.warning("nlm_verifier: Redis incr failed (%s), continuing", exc)

        # Call NLM synchronously inside a thread (subprocess-based)
        nlm_query = _load_nlm_query()
        try:
            result: dict = await asyncio.wait_for(
                asyncio.to_thread(nlm_query, notebook_id, query, None, NLM_TIMEOUT),
                timeout=NLM_TIMEOUT + 5,  # extra buffer for thread overhead
            )
        except asyncio.TimeoutError:
            logger.warning("nlm_verifier: NLM call timed out (domain=%s)", domain)
            return

        nlm_answer: str = result.get("answer", "") or ""
        if not nlm_answer:
            logger.debug("nlm_verifier: NLM returned empty answer (domain=%s)", domain)
            return

        # Compare answers
        discrepancy = _detect_discrepancy(zantara_answer, nlm_answer)
        if discrepancy:
            logger.info(
                "nlm_verifier: discrepancy detected (domain=%s, score=%.2f): %s",
                domain,
                evidence_score,
                discrepancy,
            )
            await _log_discrepancy(
                db_pool,
                query,
                zantara_answer,
                nlm_answer,
                domain,
                evidence_score,
                discrepancy,
            )
        else:
            logger.debug("nlm_verifier: no discrepancy found (domain=%s)", domain)

    except Exception as exc:  # pragma: no cover — must never crash caller
        logger.warning("nlm_verifier: unexpected error (%s)", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _detect_discrepancy(zantara: str, nlm: str) -> Optional[str]:
    """Basic v1 discrepancy detection between two answer strings.

    Checks:
    - Number mismatches: any digit-sequence present in one but not the other.
    - Length disparity: NLM answer is >3× longer than Zantara's (potential omission).

    Args:
        zantara: Zantara's answer text.
        nlm: NLM's answer text.

    Returns:
        Human-readable discrepancy description, or None if no issue found.
    """
    if not zantara or not nlm:
        return None

    zantara_lower = zantara.lower()
    nlm_lower = nlm.lower()

    # Extract all numeric tokens (e.g. "180", "60", "2.5")
    z_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)*\b", zantara_lower))
    n_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)*\b", nlm_lower))

    only_in_zantara = z_numbers - n_numbers
    only_in_nlm = n_numbers - z_numbers

    # Filter trivial single-digit differences (1, 2, 3 … often ordinals)
    significant_threshold = 4  # numbers with 4+ digits are likely meaningful
    zantara_significant = {n for n in only_in_zantara if len(n.replace(",", "").replace(".", "")) >= significant_threshold}
    nlm_significant = {n for n in only_in_nlm if len(n.replace(",", "").replace(".", "")) >= significant_threshold}

    parts: list[str] = []

    if zantara_significant:
        parts.append(f"numbers in Zantara not in NLM: {', '.join(sorted(zantara_significant)[:5])}")
    if nlm_significant:
        parts.append(f"numbers in NLM not in Zantara: {', '.join(sorted(nlm_significant)[:5])}")

    # Length disparity — NLM substantially longer may signal Zantara omitted detail
    if len(nlm) > 3 * max(len(zantara), 1):
        parts.append(
            f"length disparity: zantara={len(zantara)} chars, nlm={len(nlm)} chars"
        )

    return "; ".join(parts) if parts else None


async def _log_discrepancy(
    pool: Optional[Any],
    query: str,
    zantara_answer: str,
    nlm_answer: str,
    domain: str,
    evidence_score: float,
    discrepancy: str,
) -> None:
    """Insert a discrepancy record into nlm_verification_log.

    Args:
        pool: asyncpg connection pool.  If None the log is skipped silently.
        query: Original user query.
        zantara_answer: Zantara's response.
        nlm_answer: NLM's response.
        domain: Query domain.
        evidence_score: RAG evidence score.
        discrepancy: Human-readable discrepancy description.
    """
    if pool is None:
        logger.debug("nlm_verifier: no db_pool — skipping discrepancy log")
        return

    try:
        await pool.execute(
            """
            INSERT INTO nlm_verification_log
                (query, zantara_answer, nlm_answer, domain, evidence_score, discrepancy)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            query,
            zantara_answer,
            nlm_answer,
            domain,
            evidence_score,
            discrepancy,
        )
    except Exception as exc:
        # Table may not exist yet — log and continue
        logger.warning("nlm_verifier: failed to log discrepancy (%s)", exc)
