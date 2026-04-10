"""Tier-based reasoning framework — tries cheapest tier first.

All LLM invocations via subprocess (SYMBIOSIS Law #1: CLI-only).
Each organ configures its own tiers and commands.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from cell_core.types import Proposal

logger = logging.getLogger("cell_core.reasoner")


@dataclass
class TierConfig:
    """Configuration for one reasoning tier."""
    tier: int
    name: str
    command: list[str]
    max_cost_usd: float
    timeout_seconds: float


class ReasonerFramework:
    """Tier-based escalation. Tries cheapest tier first."""

    def __init__(self, tiers: list[TierConfig], allowlist: list[str]) -> None:
        self._tiers = sorted(tiers, key=lambda t: t.max_cost_usd)
        self._allowlist = set(allowlist) | {"none"}

    async def reason(
        self,
        situation: str,
        context: dict[str, Any],
    ) -> Proposal:
        """Escalate through tiers until one produces a valid proposal."""
        for tier_cfg in self._tiers:
            try:
                proposal = await self._try_tier(tier_cfg, situation, context)
                if proposal is not None:
                    return proposal
            except Exception as e:
                logger.warning(f"Tier {tier_cfg.name} failed: {e}")
                continue

        # All tiers failed — return safe default
        return Proposal(
            action="none",
            reason="All reasoning tiers failed",
            confidence=0.0,
            tier_used=-1,
        )

    async def _try_tier(
        self,
        tier_cfg: TierConfig,
        situation: str,
        context: dict[str, Any],
    ) -> Proposal | None:
        """Run one tier. Returns Proposal or None if tier fails."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *tier_cfg.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=tier_cfg.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Tier {tier_cfg.name} timed out after {tier_cfg.timeout_seconds}s")
            return None

        if proc.returncode != 0:
            logger.warning(f"Tier {tier_cfg.name} exited with code {proc.returncode}")
            return None

        output = stdout.decode().strip()
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            # Try to extract JSON from output (LLMs sometimes wrap in markdown)
            import re
            match = re.search(r'\{[^{}]+\}', output)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.warning(f"Tier {tier_cfg.name}: no valid JSON in output")
                    return None
            else:
                logger.warning(f"Tier {tier_cfg.name}: no valid JSON in output")
                return None

        action = data.get("action", "none")
        if action not in self._allowlist:
            logger.warning(f"Tier {tier_cfg.name}: action '{action}' not in allowlist")
            action = "none"

        return Proposal(
            action=action,
            reason=data.get("reason", ""),
            confidence=float(data.get("confidence", 0.0)),
            tier_used=tier_cfg.tier,
            cost_usd=tier_cfg.max_cost_usd,
        )
