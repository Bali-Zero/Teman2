"""Tests for cost ceiling enforcement — Symbiosis Law 7 (Numeri prima).

Verifies that wr3_dispatch_agent.dispatch_agent() routes BudgetExceededError
per Symbiosis precedence:
  - GATE agent (design-architect, pre-render-gatekeeper) → HardHaltException
  - HOT PATH core agent → cascade to Gemini Tier 2
  - Scheduled/fallback agent → CascadeExhaustedError (no cascade for non-core)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wr3_contracts import load_contracts  # noqa: E402
from wr3_dispatch_agent import (  # noqa: E402
    BudgetExceededError,
    CascadeExhaustedError,
    DispatchResult,
    HardHaltException,
    dispatch_agent,
)


@pytest.fixture(scope="module")
def contracts():
    return load_contracts()


@pytest.mark.asyncio
async def test_gate_budget_exceeded_raises_hard_halt(contracts) -> None:
    """design-architect is a GATE — budget exhaust must HALT (no cascade)."""
    with patch(
        "wr3_dispatch_agent._dispatch_claude_sdk",
        new=AsyncMock(side_effect=BudgetExceededError("simulated gate exceed")),
    ), patch(
        "wr3_dispatch_agent.telegram_p0", new=AsyncMock()
    ) as p0:
        with pytest.raises(HardHaltException):
            await dispatch_agent(
                contracts, "wr3-design-architect", "prompt", episode_id="ep-test"
            )
        p0.assert_awaited_once()


@pytest.mark.asyncio
async def test_pre_render_gatekeeper_is_gate(contracts) -> None:
    """pre-render-gatekeeper is the OTHER gate — same HARD HALT rule."""
    with patch(
        "wr3_dispatch_agent._dispatch_claude_sdk",
        new=AsyncMock(side_effect=BudgetExceededError("gatekeeper exceed")),
    ), patch(
        "wr3_dispatch_agent.telegram_p0", new=AsyncMock()
    ):
        with pytest.raises(HardHaltException):
            await dispatch_agent(
                contracts, "wr3-pre-render-gatekeeper", "prompt", episode_id="ep-test"
            )


@pytest.mark.asyncio
async def test_hot_path_budget_exceeded_cascades_to_gemini(contracts) -> None:
    """script-editor is core, non-gate → cascade Tier 2 Gemini."""
    fake = DispatchResult(
        agent="wr3-script-editor",
        cost_usd_estimated=0.0,
        duration_ms=1200,
        cascade_tier=2,
        raw_output="cascaded output",
        cascade_reason="claude_budget_exceeded",
    )
    with patch(
        "wr3_dispatch_agent._dispatch_claude_sdk",
        new=AsyncMock(side_effect=BudgetExceededError("simulated")),
    ), patch(
        "wr3_dispatch_agent._dispatch_gemini_cli",
        new=AsyncMock(return_value=fake),
    ) as cascade:
        result = await dispatch_agent(
            contracts, "wr3-script-editor", "prompt", episode_id="ep-test"
        )
        assert result.cascade_tier == 2
        cascade.assert_awaited_once()


@pytest.mark.asyncio
async def test_scheduled_agent_no_cascade(contracts) -> None:
    """reflexion-synth is scheduled tier — no cascade, returns CascadeExhausted."""
    with patch(
        "wr3_dispatch_agent._dispatch_claude_sdk",
        new=AsyncMock(side_effect=BudgetExceededError("scheduled exceed")),
    ):
        with pytest.raises(CascadeExhaustedError, match="non-core"):
            await dispatch_agent(
                contracts, "wr3-reflexion-synth", "prompt", episode_id="ep-test"
            )


@pytest.mark.asyncio
async def test_cascade_chain_exhaustion_telegram_p0(contracts) -> None:
    """When both Claude AND Gemini exhausted → telegram_p0 fires + raise."""
    with patch(
        "wr3_dispatch_agent._dispatch_claude_sdk",
        new=AsyncMock(side_effect=BudgetExceededError("claude exceed")),
    ), patch(
        "wr3_dispatch_agent._dispatch_gemini_cli",
        new=AsyncMock(side_effect=CascadeExhaustedError("gemini also exhausted")),
    ), patch(
        "wr3_dispatch_agent.telegram_p0", new=AsyncMock()
    ) as p0:
        with pytest.raises(CascadeExhaustedError):
            await dispatch_agent(
                contracts, "wr3-script-editor", "prompt", episode_id="ep-test"
            )
        p0.assert_awaited_once()


@pytest.mark.asyncio
async def test_successful_dispatch_no_cascade(contracts) -> None:
    fake = DispatchResult(
        agent="wr3-script-editor",
        cost_usd_estimated=0.11,
        duration_ms=8000,
        cascade_tier=1,
        raw_output="all good",
    )
    with patch(
        "wr3_dispatch_agent._dispatch_claude_sdk",
        new=AsyncMock(return_value=fake),
    ) as primary:
        result = await dispatch_agent(
            contracts, "wr3-script-editor", "prompt", episode_id="ep-ok"
        )
        assert result.cascade_tier == 1
        primary.assert_awaited_once()
