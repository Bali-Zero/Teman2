"""Shadow retrieval — read-side counterpart to scripts/nlm_shadow_extractor.py.

The extractor (Sprint 2) writes NLMShadowChunk rows into the
``nlm_shadow_hybrid`` Qdrant collection nightly. This module reads them
back at runtime so the agentic orchestrator can serve NLM-grounded claims
in sub-second time without touching the NLM CLI in the hot path.

Activation is opt-in via the ``NLM_SHADOW_RETRIEVAL_ENABLED`` env flag.
When unset, ``search_nlm_shadow_claims()`` short-circuits to an empty
result so no caller gets surprised. This makes the wire-up safe to ship
ahead of the cron extractor populating the collection.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

COLLECTION_NAME = "nlm_shadow_hybrid"

# Domain → typed nb_label filter so the orchestrator can narrow by domain.
# Mirrors apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py
# but kept independent — this module never has to know the registry shape.
_KNOWN_DOMAINS = frozenset({
    "immigration", "company", "tax", "property",
    "operations", "editorial", "lifestyle",
})

_DEFAULT_TOP_K = 5
_DEFAULT_MIN_CONFIDENCE = 0.6


def is_enabled() -> bool:
    """Check the activation flag.

    The flag is read every call (not cached) so a runtime ``fly secrets
    set`` change takes effect on the next request without redeploy.
    """
    return os.environ.get("NLM_SHADOW_RETRIEVAL_ENABLED", "").lower() in (
        "1", "true", "yes", "on",
    )


async def search_nlm_shadow_claims(
    query_vector: list[float],
    *,
    domain: Optional[str] = None,
    top_k: int = _DEFAULT_TOP_K,
    min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
    qdrant_client: Any = None,
    skip_expired: bool = True,
) -> list[dict[str, Any]]:
    """Search the nlm_shadow_hybrid collection for top-K relevant claims.

    Args:
        query_vector: Pre-computed query embedding (1536 dims, OpenAI
            text-embedding-3-small per the FROZEN model rule).
        domain: Optional ``nb_label`` filter — restrict results to a
            single domain (e.g. ``"immigration"``). When None, search
            across all domains.
        top_k: Maximum results to return (default 5).
        min_confidence: Drop claims whose ``deepseek_confidence`` is
            below this threshold (default 0.6).
        qdrant_client: Injected Qdrant client. When None, the function
            tries to import the canonical singleton from ``backend.core``
            (delayed so unit tests can run without qdrant-client).
        skip_expired: Drop claims whose ``ttl_hours`` window has elapsed
            since ``extracted_at``.

    Returns:
        A list of claim dicts (most relevant first). Each item has:
          - ``claim_text``
          - ``score`` (Qdrant similarity)
          - ``nb_id``, ``nb_label`` (provenance)
          - ``extraction_run_id``, ``extracted_at``
          - ``deepseek_confidence``
          - ``ttl_hours``

    Empty list when:
      - ``NLM_SHADOW_RETRIEVAL_ENABLED`` is not truthy.
      - Qdrant is unreachable / collection missing (logged, not raised).
      - No claims match the filters.
    """
    if not is_enabled():
        return []

    if domain and domain not in _KNOWN_DOMAINS:
        logger.warning("nlm_shadow search: unknown domain %r — ignoring filter", domain)
        domain = None

    client = qdrant_client or _resolve_qdrant_client()
    if client is None:
        logger.info("nlm_shadow: no Qdrant client available — empty result")
        return []

    # Build payload filter — Qdrant FieldCondition syntax. Imports are
    # delayed so this module can be imported in unit tests that mock
    # everything but lack qdrant_client installed.
    try:
        from qdrant_client.http.models import FieldCondition, Filter, MatchValue
    except ImportError as exc:
        logger.warning("nlm_shadow: qdrant_client not installed — empty result (%s)", exc)
        return []

    must = [FieldCondition(key="source", match=MatchValue(value="nlm_shadow"))]
    if domain:
        must.append(FieldCondition(key="nb_label", match=MatchValue(value=domain)))

    try:
        # Some QdrantClient versions are sync, others async — handle both.
        # The agentic orchestrator runs in an event loop, so we await the
        # search call when it returns a coroutine.
        result = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=Filter(must=must),
            limit=top_k * 2,  # over-fetch so we can drop low-confidence and expired
            with_payload=True,
        )
        if hasattr(result, "__await__"):
            result = await result
    except Exception as exc:
        logger.warning("nlm_shadow search failed: %s", exc)
        return []

    out: list[dict[str, Any]] = []
    now = datetime.now(tz=timezone.utc)
    for hit in result or []:
        payload = getattr(hit, "payload", None) or (hit.get("payload") if isinstance(hit, dict) else {})
        if not payload:
            continue
        confidence = float(payload.get("deepseek_confidence", 0.0) or 0.0)
        if confidence < min_confidence:
            continue
        if skip_expired and _is_expired(payload, now):
            continue
        score = getattr(hit, "score", None)
        if score is None and isinstance(hit, dict):
            score = hit.get("score")
        out.append({
            "claim_text": payload.get("claim_text", ""),
            "score": float(score) if score is not None else 0.0,
            "nb_id": payload.get("nb_id", ""),
            "nb_label": payload.get("nb_label", ""),
            "extraction_run_id": payload.get("extraction_run_id", ""),
            "extracted_at": payload.get("extracted_at", ""),
            "deepseek_confidence": confidence,
            "ttl_hours": int(payload.get("ttl_hours", 72)),
        })
        if len(out) >= top_k:
            break
    return out


def _is_expired(payload: dict, now: datetime) -> bool:
    """Return True iff (now - extracted_at) > ttl_hours."""
    extracted = payload.get("extracted_at")
    ttl = int(payload.get("ttl_hours", 72) or 72)
    if not extracted:
        return False  # Old rows without ts: keep, don't drop silently
    try:
        ts = datetime.fromisoformat(extracted)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False
    age_hours = (now - ts).total_seconds() / 3600
    return age_hours > ttl


def _resolve_qdrant_client() -> Any:
    """Lazy-import the canonical Qdrant client singleton if available."""
    try:
        from backend.core import qdrant_db
        getter = getattr(qdrant_db, "get_qdrant_client", None)
        if callable(getter):
            return getter()
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("qdrant_db getter failed: %s", exc)
    return None


__all__ = [
    "COLLECTION_NAME",
    "is_enabled",
    "search_nlm_shadow_claims",
]
