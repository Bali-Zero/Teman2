"""Naga research engine configuration.

Defines tier budgets (flash / deep / exhaustive), convergence thresholds,
per-channel TTLs, and domain-credibility source weights.

Uses plain dataclasses to stay lightweight — no Pydantic dependency.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_SOURCE_WEIGHTS_PATH = Path(__file__).resolve().parent / "source_weights.json"


@dataclass(frozen=True, slots=True)
class TierBudget:
    """Resource budget for a single research tier."""

    max_searches: int
    max_gemini_sources: int
    max_iterations: int
    default_ttl_seconds: int


def _default_tier_budgets() -> Dict[str, TierBudget]:
    """Build the canonical tier-budget mapping."""
    return {
        "flash": TierBudget(
            max_searches=3,
            max_gemini_sources=0,
            max_iterations=1,
            default_ttl_seconds=15,
        ),
        "deep": TierBudget(
            max_searches=25,
            max_gemini_sources=20,
            max_iterations=3,
            default_ttl_seconds=300,
        ),
        "exhaustive": TierBudget(
            max_searches=80,
            max_gemini_sources=50,
            max_iterations=5,
            default_ttl_seconds=1800,
        ),
    }


def _default_channel_ttls() -> Dict[str, int]:
    """Per-channel TTL overrides (seconds)."""
    return {
        "telegram": 30,
        "web_chat": 60,
        "claude_code": 1800,
        "openclaw": 1800,
        "api": 3600,
        "cron": 3600,
    }


@dataclass
class NagaConfig:
    """Top-level configuration for the Naga research engine.

    Attributes:
        tier_budgets: Resource budgets keyed by tier name.
        convergence_coverage_threshold: Stop iterating when claim coverage >= this.
        convergence_novelty_threshold: Stop iterating when novelty drops below this.
        source_score_min: Discard sources scoring below this credibility floor.
        channel_ttls: Per-channel TTL overrides in seconds.
    """

    tier_budgets: Dict[str, TierBudget] = field(default_factory=_default_tier_budgets)
    convergence_coverage_threshold: float = 0.80
    convergence_novelty_threshold: float = 0.10
    source_score_min: float = 0.30
    channel_ttls: Dict[str, int] = field(default_factory=_default_channel_ttls)

    # ------------------------------------------------------------------
    # Source weights
    # ------------------------------------------------------------------

    def load_source_weights(self, path: Path | None = None) -> Dict[str, Any]:
        """Load domain-credibility weights from the bundled JSON file.

        Args:
            path: Optional override for the JSON file location.

        Returns:
            Parsed dict with keys ``default``, ``domain_overrides``,
            ``freshness_weights``.

        Raises:
            FileNotFoundError: If the weights file cannot be located.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        target = path or _SOURCE_WEIGHTS_PATH
        logger.debug("Loading source weights from %s", target)
        data: Dict[str, Any] = json.loads(target.read_text(encoding="utf-8"))
        return data
