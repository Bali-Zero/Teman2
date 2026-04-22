"""Ahrefs snapshot — DR + backlinks + SOV + AI citations.

**Known limitation (2026-04-22):** the current Ahrefs MCP subscription
returns "Insufficient plan" (-32001) for all site-explorer-* and
brand-radar-* endpoints. This sensor returns zero placeholders with
`source_status="plan_insufficient"` so the baseline file is transparent
about the gap.

Upgrade path (outside SOTA scope):
  - Ahrefs plan upgrade to include Site Explorer + Brand Radar API units
  - OR switch to an alternative free tier (Moz, Ubersuggest)
  - OR derive proxies from GSC (for organic/backlinks) + manual NotebookLM
    research for AI citation patterns

Once the plan is upgraded, replace the `zero_fallback` call in `fetch()`
with actual MCP tool invocations. The shape of the returned dict is
stable — consumers (baseline_builder, M13 weekly report) won't need to
change.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def fetch_ahrefs_snapshot(timeout_sec: int = 30) -> dict[str, Any]:
    """Pull Ahrefs DR + backlinks + SOV + AI citations.

    Currently returns zeros with `source_status="plan_insufficient"`.
    See module docstring for upgrade path.
    """
    logger.info(
        "Ahrefs snapshot: plan insufficient — returning zeros. "
        "Upgrade plan or wire alternative to get real values."
    )
    return _zero_fallback("plan_insufficient")


def _zero_fallback(reason: str) -> dict[str, Any]:
    return {
        "domain_rating": 0,
        "backlinks_count": 0,
        "sov_pct": 0.0,
        "ai_citations_30d": 0,
        "source_status": reason,
    }
