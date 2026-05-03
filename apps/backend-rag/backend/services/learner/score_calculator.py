"""Composite score + percentile normalization (§10.1).

    composite = 0.35 * norm(reach)
              + 0.25 * engagement_rate
              + 0.25 * leads_per_1k_impressions
              + 0.15 * save_rate

- ``norm(reach)`` = percentile rank of this post's reach within the last
  90d on the same platform, squashed to [0,1].
- ``engagement_rate`` = (likes + comments + shares) / impressions (clamped to [0,1]).
- ``leads_per_1k_impressions`` = leads_attributed / impressions * 1000 (clamped to [0,1]).
- ``save_rate`` = saves / impressions (clamped to [0,1]).

When impressions is missing or zero, the denominators are treated as None and
the corresponding term contributes 0 to the composite. The returned
:class:`CompositeScore` flags which terms were synthesized-from-missing so the
Learner can decide whether the score is trustworthy (``complete=True`` only
when all four inputs were measurable).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.services.measurer.base import (
    METRIC_COMMENTS,
    METRIC_IMPRESSIONS,
    METRIC_LEADS_ATTRIBUTED,
    METRIC_LIKES,
    METRIC_REACH,
    METRIC_SAVES,
    METRIC_SHARES,
)
from backend.services.war_room.models import Platform

# Weights (must sum to 1.0)
W_REACH = 0.35
W_ENGAGEMENT = 0.25
W_LEADS_PER_1K = 0.25
W_SAVE_RATE = 0.15


@dataclass
class ScoreInputs:
    reach: float | None = None
    impressions: float | None = None
    likes: float | None = None
    comments: float | None = None
    shares: float | None = None
    saves: float | None = None
    leads_attributed: float | None = None


@dataclass
class CompositeScore:
    value: float             # final composite 0..1
    norm_reach: float        # percentile-normalized reach 0..1
    engagement_rate: float   # clamped 0..1
    leads_per_1k: float      # clamped 0..1 (leads / impressions * 1000)
    save_rate: float         # clamped 0..1
    complete: bool           # True iff all four terms were derived from real data
    missing_terms: list[str] = field(default_factory=list)
    platform: Platform | None = None


def _clamp_01(x: float) -> float:
    if x < 0:
        return 0.0
    if x > 1:
        return 1.0
    return x


def _percentile_rank(value: float, distribution: list[float]) -> float:
    """Fraction of ``distribution`` that is <= value, in [0, 1].

    With < 3 historical points, returns 0.5 (no trustworthy signal — we'd
    rather treat new posts as median than amplify noise).
    """
    if value is None:
        return 0.0
    if len(distribution) < 3:
        return 0.5
    total = len(distribution)
    below_or_equal = sum(1 for v in distribution if v <= value)
    return below_or_equal / total


class ScoreCalculator:
    """Build a :class:`CompositeScore` from inputs + historical distribution."""

    def calculate(
        self,
        *,
        inputs: ScoreInputs,
        reach_distribution_90d: list[float],
        platform: Platform | None = None,
    ) -> CompositeScore:
        missing: list[str] = []

        # 1. norm(reach)
        if inputs.reach is None:
            missing.append(METRIC_REACH)
            norm_reach = 0.0
        else:
            norm_reach = _percentile_rank(
                float(inputs.reach),
                [float(x) for x in reach_distribution_90d],
            )

        # 2. engagement_rate
        if inputs.impressions is None or inputs.impressions <= 0:
            missing.append(METRIC_IMPRESSIONS)
            engagement = 0.0
        else:
            numer = (
                (inputs.likes or 0.0)
                + (inputs.comments or 0.0)
                + (inputs.shares or 0.0)
            )
            engagement = _clamp_01(numer / float(inputs.impressions))
            if inputs.likes is None:
                missing.append(METRIC_LIKES)
            if inputs.comments is None:
                missing.append(METRIC_COMMENTS)
            if inputs.shares is None:
                missing.append(METRIC_SHARES)

        # 3. leads per 1k impressions
        if (
            inputs.impressions is None
            or inputs.impressions <= 0
            or inputs.leads_attributed is None
        ):
            if inputs.leads_attributed is None:
                missing.append(METRIC_LEADS_ATTRIBUTED)
            leads_per_1k = 0.0
        else:
            leads_per_1k = _clamp_01(
                (float(inputs.leads_attributed) / float(inputs.impressions)) * 1000
            )

        # 4. save rate
        if (
            inputs.impressions is None
            or inputs.impressions <= 0
            or inputs.saves is None
        ):
            if inputs.saves is None:
                missing.append(METRIC_SAVES)
            save_rate = 0.0
        else:
            save_rate = _clamp_01(
                float(inputs.saves) / float(inputs.impressions)
            )

        composite = (
            W_REACH * norm_reach
            + W_ENGAGEMENT * engagement
            + W_LEADS_PER_1K * leads_per_1k
            + W_SAVE_RATE * save_rate
        )

        return CompositeScore(
            value=_clamp_01(composite),
            norm_reach=norm_reach,
            engagement_rate=engagement,
            leads_per_1k=leads_per_1k,
            save_rate=save_rate,
            complete=not missing,
            missing_terms=missing,
            platform=platform,
        )
