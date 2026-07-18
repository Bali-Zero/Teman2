"""Core engine enums for the Visa Engine v2.

These five enums are the closed vocabularies referenced across every other
module in ``backend.services.visa_engine`` (ast, models, compiler, and, in
later PRs, evaluator/service/flags). Kept dependency-free on purpose so
every other module in the package can import from here without risking an
import cycle.

Pure module: no I/O, no third-party imports beyond the stdlib ``enum``.
"""

from __future__ import annotations

from enum import Enum


class TruthValue(str, Enum):
    """Three-valued (strong Kleene) logic result of a condition evaluation."""

    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


class DecisionState(str, Enum):
    """The exactly-one-of-five global outcome of an evaluation."""

    NEEDS_INPUT = "NEEDS_INPUT"
    SUPPORTED_CANDIDATES = "SUPPORTED_CANDIDATES"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    NO_SUPPORTED_PATH = "NO_SUPPORTED_PATH"
    TEMPORARILY_UNAVAILABLE = "TEMPORARILY_UNAVAILABLE"


class RuleStage(str, Enum):
    """The four strictly ordered rule stages.

    Declaration order matches the spec's public API listing (section 1)
    verbatim — it is NOT the processing/evaluation order. For that, use
    :data:`STAGE_ORDER` (or the ``.order`` property below).
    """

    HARD_FILTER = "HARD_FILTER"
    ELIGIBILITY = "ELIGIBILITY"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    RANKING = "RANKING"

    @property
    def order(self) -> int:
        """Semantic processing order per §4.2/§4.5: ``HARD_FILTER`` runs
        first, then ``HUMAN_REVIEW``, then ``ELIGIBILITY``, then (globally,
        only on ``SUPPORTED`` products) ``RANKING``. NOT the same as
        declaration order or alphabetical ``.value`` order — sorting by
        ``.value`` would put ``ELIGIBILITY`` before ``HARD_FILTER``, which
        is wrong."""

        return STAGE_ORDER[self]


STAGE_ORDER: dict[RuleStage, int] = {
    RuleStage.HARD_FILTER: 0,
    RuleStage.HUMAN_REVIEW: 1,
    RuleStage.ELIGIBILITY: 2,
    RuleStage.RANKING: 3,
}


class EngineMode(str, Enum):
    """Per-surface rollout mode."""

    OFF = "OFF"
    SHADOW = "SHADOW"
    ENFORCE = "ENFORCE"


class EngineSurface(str, Enum):
    """The API/consumer surfaces the engine can be gated on independently."""

    CLOCK = "CLOCK"
    MATCH = "MATCH"
    RECOMMEND = "RECOMMEND"
    CATALOG = "CATALOG"
    CHAT_CONTEXT = "CHAT_CONTEXT"
    HANDOFF = "HANDOFF"
