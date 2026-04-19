"""SEOActor — executes SEO proposals under tier + phase guards.

Tier policy (decision memo v2.1):
  LOW       — autonomous (schema injection, meta description refresh,
              canonical fix — via gemini_seo_optimizer.py)
  MED       — autonomous → newsroom queue (new article drafts)
  HIGH      — review_handler.py SLA worker (Telegram approve/reject)
  CRITICAL  — review_handler.py + mandatory Zero approval

Pre-natal override: regardless of tier, no action executes while
SEOPhase.pre_natal is True. The actor records the refused intent to
STM so the thinker can learn the action would have fired (Sprint 3
backfill measurement).

Sprint 1 behavior: act() accepts only `action="none"`; anything else
is logged + refused. No integration yet with gemini_seo_optimizer or
review_handler.
"""
from __future__ import annotations

import logging
from typing import Any

from cell_core.types import Proposal

from apps.evaluator.seo_cell.phase import SEOPhase

logger = logging.getLogger("seo_cell.actor")

# Sprint 1 whitelist — only no-op. Sprint 2 adds `publish_schema`,
# `refresh_meta`, `queue_article_draft`, `request_review`.
_ALLOWED_ACTIONS: frozenset[str] = frozenset({"none"})


class SEOActor:
    """Executes vetted proposals; refuses everything in pre_natal."""

    def __init__(self) -> None:
        self._current_phase: SEOPhase | None = None
        self._refused_intents: list[dict[str, Any]] = []

    def set_phase(self, phase: SEOPhase) -> None:
        """Called by the PulseLoop wrapper before act() (mirrors sentinel
        pattern). Keeps actor stateless vs PulseLoop."""
        self._current_phase = phase

    def can_execute(self, action_name: str) -> bool:
        return action_name in _ALLOWED_ACTIONS

    async def act(self, proposal: Proposal) -> str:
        if proposal.action == "none":
            return "no_action"

        if self._current_phase is None or self._current_phase.pre_natal:
            self._refused_intents.append(
                {
                    "action": proposal.action,
                    "reason": proposal.reason,
                    "phase": (
                        self._current_phase.label
                        if self._current_phase
                        else "unknown"
                    ),
                }
            )
            logger.info(
                "[seo_cell] refused %s — pre_natal or unset phase",
                proposal.action,
            )
            return "refused_pre_natal"

        if not self.can_execute(proposal.action):
            logger.warning(
                "[seo_cell] action %s not in sprint1 whitelist — refusing",
                proposal.action,
            )
            return "refused_not_implemented"

        # Unreachable in Sprint 1 (whitelist is just {"none"}).
        return "ok"
