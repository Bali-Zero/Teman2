"""SEOThinker — proposes SEO actions from sensor readings.

In pre_natal the thinker is strictly observational: aggregates sensor
readings, records signal density, and proposes `action="none"` so the
actor never executes changes. This lets the cell accumulate GSC and
lead history until the unlock gate passes.

Post-graduation (Sprint 3+) this class gains:
  - daily: LLM rerank of candidate actions (Tier 1 = Ollama, Tier 2 =
    Gemini, Tier 3 = Claude for HIGH/CRITICAL)
  - weekly: Bayesian calibrator updates genome weights
    (pattern.name='seo_scoring_weights'), NO council 4-LLM voting.

Sprint 1 behavior is intentionally minimal — see decision memo for
v2.1 rationale (Council 4-LLM eliminated as theater on microscopic
signal).
"""
from __future__ import annotations

import json
import logging
from typing import Any, TYPE_CHECKING

from cell_core.lifecycle import Maturation
from cell_core.types import HomeostaticState, Proposal, SensorReading

from apps.evaluator.seo_cell import config
from apps.evaluator.seo_cell.bayesian_calibrator import (
    DEFAULT_WEIGHTS,
    PATTERN_ID,
    SENSOR_NAMES,
)
from apps.evaluator.seo_cell.phase import SEOPhase, is_pre_natal

if TYPE_CHECKING:
    from cell_core.genome import Genome

logger = logging.getLogger("seo_cell.thinker")


class SEOThinker:
    """Aggregates sensor readings; in pre_natal returns no-op proposal."""

    def __init__(self) -> None:
        # Snapshot of last readings for external inspection (actor, tests).
        self._last_readings: list[SensorReading] = []
        self._last_phase: SEOPhase | None = None

    def current_weights(
        self,
        *,
        genome: "Genome",
        cell_name: str = "seo-guardian",
    ) -> dict[str, float]:
        """Read calibrated sensor weights from the genome, or defaults.

        The Bayesian calibrator is the only writer of this pattern (see
        :mod:`apps.evaluator.seo_cell.bayesian_calibrator`). The thinker
        reads on every pulse where scoring is needed. Missing or
        malformed rows fall back to :data:`DEFAULT_WEIGHTS` — the cell
        never hard-fails because of a bad genome row.
        """
        rows = genome.get_active(
            cell=cell_name, entry_type="pattern", limit=50,
        )
        for row in rows:
            if row.get("id") != PATTERN_ID:
                continue
            procedure = row.get("procedure") or ""
            try:
                parsed = json.loads(procedure)
            except (TypeError, ValueError):
                logger.warning(
                    "[thinker] %s procedure is not JSON — using defaults",
                    PATTERN_ID,
                )
                return dict(DEFAULT_WEIGHTS)
            if not isinstance(parsed, dict):
                return dict(DEFAULT_WEIGHTS)
            # Require the exact 6-sensor contract; reject partial rows.
            if set(parsed.keys()) != set(SENSOR_NAMES):
                logger.warning(
                    "[thinker] %s missing sensors — using defaults", PATTERN_ID,
                )
                return dict(DEFAULT_WEIGHTS)
            try:
                weights = {k: float(parsed[k]) for k in SENSOR_NAMES}
            except (TypeError, ValueError):
                return dict(DEFAULT_WEIGHTS)
            total = sum(weights.values())
            if total <= 0:
                return dict(DEFAULT_WEIGHTS)
            # Re-normalise defensively so a drifted pattern still sums to 1.
            return {k: v / total for k, v in weights.items()}
        return dict(DEFAULT_WEIGHTS)

    def current_phase(
        self,
        readings: list[SensorReading],
        state: HomeostaticState,
    ) -> SEOPhase:
        """Derive composite phase from native maturation + pre_natal gate.

        Native phase is computed from the immutable birth_date via a
        fresh Maturation instance (cheap — just age-in-days arithmetic).
        The PulseLoop owns its own Maturation for `can_act` gating; we
        just need the Phase value here, which is a deterministic
        function of birth_date.
        """
        native = Maturation(birth_date=config.cell_birth_date()).phase

        gsc_query_count = 0
        for r in readings:
            if r.sensor_name == "gsc" and isinstance(r.value, dict):
                gsc_query_count = int(r.value.get("query_count", 0))
                break

        # website_organic lead count comes from CRM via a future sensor
        # (Sprint 2 — lead_attribution_sensor). Until then the memory
        # context carries a rolling count written by the actor on every
        # pulse, starting at 0.
        lead_count = 0  # pessimistic default; pre_natal stays locked

        pre_natal = is_pre_natal(
            gsc_query_count=gsc_query_count,
            website_organic_lead_count=lead_count,
            birth_date=config.cell_birth_date(),
            min_gsc_queries=config.PRE_NATAL_MIN_GSC_QUERIES,
            min_leads=config.PRE_NATAL_MIN_WEBSITE_ORGANIC_LEADS,
            min_age_days=config.PRE_NATAL_MIN_AGE_DAYS,
        )
        return SEOPhase(native=native, pre_natal=pre_natal)

    async def think(
        self,
        readings: list[SensorReading],
        state: HomeostaticState,
        memory_context: dict[str, Any],
    ) -> Proposal:
        self._last_readings = readings
        phase = self.current_phase(readings, state)
        self._last_phase = phase

        green = sum(1 for r in readings if r.status == "green")
        yellow = sum(1 for r in readings if r.status == "yellow")
        red = sum(1 for r in readings if r.status == "red")

        reason = (
            f"phase={phase.label}; sensors green={green} yellow={yellow} red={red}"
        )

        if phase.pre_natal:
            logger.info("[seo_cell] pre_natal → no-op: %s", reason)
            return Proposal(
                action="none",
                reason=f"pre_natal gate not passed — {reason}",
                confidence=1.0,
                tier_used=0,
                cost_usd=0.0,
            )

        # Post-graduation path — NOT IMPLEMENTED in Sprint 1. Falls back
        # to no-op with a distinct reason so operators see we entered
        # the "should-act" branch but scaffolding is incomplete.
        logger.warning(
            "[seo_cell] graduated but think() not implemented — returning no-op"
        )
        return Proposal(
            action="none",
            reason=f"sprint1_stub_graduated — {reason}",
            confidence=0.0,
            tier_used=0,
            cost_usd=0.0,
        )
