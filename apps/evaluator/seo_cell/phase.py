"""SEO Cell lifecycle phases.

Extends cell-core's native Phase enum (EMBRIONE..ANZIANO) with a
pre_natal marker. pre_natal is NOT a cell_core phase — it's a
learning-lock flag evaluated at the cell-level before dispatching to
the reasoner/actor. When pre_natal=True, the cell behaves in
sense-only mode regardless of its age.

This decouples maturation (cell_core.lifecycle.Maturation) from
learning readiness, which is a domain-specific gate: we don't unlock
the Bayesian calibrator just because N days passed — we also need
enough GSC query volume and at least a few website-sourced leads to
have any signal to calibrate on.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from cell_core.types import Phase


@dataclass(frozen=True)
class SEOPhase:
    """Composite phase: native Phase + pre_natal learning-lock."""

    native: Phase
    pre_natal: bool

    @property
    def can_learn(self) -> bool:
        """True when the Bayesian calibrator + LLM rerank are allowed.

        pre_natal overrides any native phase — a 60-day-old cell still
        in pre_natal (not enough GSC signal) cannot learn yet.
        """
        return not self.pre_natal

    @property
    def can_act(self) -> bool:
        """True when actors can execute LOW/MED-tier changes.

        pre_natal is strictly sense-only. HIGH/CRITICAL always go
        through review_handler.py regardless of phase (Sprint 2+).
        """
        return not self.pre_natal

    @property
    def label(self) -> str:
        return f"pre_natal[{self.native.value}]" if self.pre_natal else self.native.value


def is_pre_natal(
    *,
    gsc_query_count: int,
    website_organic_lead_count: int,
    birth_date: datetime,
    min_gsc_queries: int,
    min_leads: int,
    min_age_days: int,
    now: datetime | None = None,
) -> bool:
    """Evaluate pre_natal unlock gate (AND of three conditions).

    All three must be satisfied to exit pre_natal:
      - gsc_query_count >= min_gsc_queries
      - website_organic_lead_count >= min_leads
      - age_days >= min_age_days

    Returns True if cell is STILL pre_natal (i.e., gate NOT passed).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if birth_date.tzinfo is None:
        birth_date = birth_date.replace(tzinfo=timezone.utc)
    age_days = (now - birth_date).days
    gate_passed = (
        gsc_query_count >= min_gsc_queries
        and website_organic_lead_count >= min_leads
        and age_days >= min_age_days
    )
    return not gate_passed


PhaseDecision = Literal["pre_natal_continue", "graduate"]
