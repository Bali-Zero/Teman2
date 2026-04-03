"""Source credibility scorer for Naga research engine.

Assigns a combined ``[0, 1]`` score to each :class:`SearchResult` using three
weighted signals:

* **Credibility** (40 %) -- domain reputation from ``source_weights.json``
* **Freshness**   (25 %) -- recency of the publication date
* **Relevance**   (35 %) -- per-source relevance provided by search agents

Resolution order for credibility:

1. Exact domain match in ``domain_overrides``
2. URL domain ends with ``.go.id`` -> ``"gov"`` default
3. ``source_type`` key in defaults
4. ``"unknown"`` fallback
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any
from urllib.parse import urlparse

from backend.services.naga.config import NagaConfig
from backend.services.naga.search_agents.base import SearchResult

logger = logging.getLogger(__name__)

# Weights for the combined formula
_W_CREDIBILITY = 0.40
_W_FRESHNESS = 0.25
_W_RELEVANCE = 0.35


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _extract_domain(url: str) -> str:
    """Return the bare hostname from *url* (e.g. ``"pajak.go.id"``)."""
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _credibility_score(
    url: str,
    source_type: str | None,
    weights: dict[str, Any],
) -> float:
    """Resolve credibility for a single source.

    Resolution:
        1. Exact match in ``domain_overrides``
        2. Domain ends with ``.go.id`` -> ``defaults["gov"]``
        3. ``source_type`` in ``defaults``
        4. ``defaults["unknown"]``
    """
    defaults: dict[str, float] = weights.get("default", {})
    overrides: dict[str, float] = weights.get("domain_overrides", {})

    domain = _extract_domain(url)

    # 1. Exact domain override
    if domain in overrides:
        return float(overrides[domain])

    # 2. .go.id fallback
    if domain.endswith(".go.id"):
        return float(defaults.get("gov", 0.5))

    # 3. source_type default
    if source_type and source_type in defaults:
        return float(defaults[source_type])

    # 4. Unknown fallback
    return float(defaults.get("unknown", 0.3))


def _freshness_score(freshness_date: date | None) -> float:
    """Map publication date to a freshness signal in ``[0, 1]``.

    * No date        -> 0.5 (neutral)
    * <= 30 days     -> 1.0
    * <= 365 days    -> 0.7
    * <= 1095 days   -> 0.5
    * Older          -> 0.3
    """
    if freshness_date is None:
        return 0.5

    age_days = (date.today() - freshness_date).days

    if age_days <= 30:
        return 1.0
    if age_days <= 365:
        return 0.7
    if age_days <= 1095:
        return 0.5
    return 0.3


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def score_source(
    source: SearchResult,
    relevance: float = 0.5,
    config: NagaConfig | None = None,
) -> float:
    """Score a source ``[0, 1]`` using credibility + freshness + relevance.

    Args:
        source: A search result to evaluate.
        relevance: External relevance signal in ``[0, 1]``.  Defaults to 0.5
            when not provided.
        config: Optional :class:`NagaConfig` -- a default instance is created
            when ``None``.

    Returns:
        Combined score in ``[0, 1]``.
    """
    cfg = config or NagaConfig()
    weights = cfg.load_source_weights()

    cred = _credibility_score(source.url, source.source_type, weights)
    fresh = _freshness_score(source.freshness_date)

    combined = (
        cred * _W_CREDIBILITY
        + fresh * _W_FRESHNESS
        + relevance * _W_RELEVANCE
    )
    # Clamp to [0, 1] defensively
    return max(0.0, min(1.0, combined))


def score_sources(
    sources: list[SearchResult],
    relevances: dict[str, float] | None = None,
    config: NagaConfig | None = None,
) -> list[SearchResult]:
    """Score, filter, and sort a list of search results.

    For each source:

    1. Resolve the relevance from *relevances* dict (keyed by URL), falling
       back to the source's own ``relevance_score``.
    2. Compute the combined score via :func:`score_source`.
    3. Store the score in ``metadata["source_score"]``.
    4. Discard sources below ``config.source_score_min``.
    5. Sort descending by score.

    Args:
        sources: Raw search results from agents.
        relevances: Optional URL -> relevance mapping that overrides
            each source's ``relevance_score``.
        config: Optional :class:`NagaConfig`.

    Returns:
        Filtered and sorted list of :class:`SearchResult` with
        ``metadata["source_score"]`` populated.
    """
    if not sources:
        return []

    cfg = config or NagaConfig()
    weights = cfg.load_source_weights()
    threshold = cfg.source_score_min
    relevances = relevances or {}

    scored: list[SearchResult] = []

    for src in sources:
        rel = relevances.get(src.url, src.relevance_score)
        cred = _credibility_score(src.url, src.source_type, weights)
        fresh = _freshness_score(src.freshness_date)

        combined = max(0.0, min(1.0,
            cred * _W_CREDIBILITY
            + fresh * _W_FRESHNESS
            + rel * _W_RELEVANCE
        ))

        if combined < threshold:
            logger.debug(
                "Filtering source %s (score=%.3f < threshold=%.2f)",
                src.url,
                combined,
                threshold,
            )
            continue

        src.metadata["source_score"] = combined
        scored.append(src)

    scored.sort(key=lambda r: r.metadata["source_score"], reverse=True)
    logger.info(
        "Scored %d sources: %d passed threshold %.2f",
        len(sources),
        len(scored),
        threshold,
    )
    return scored
