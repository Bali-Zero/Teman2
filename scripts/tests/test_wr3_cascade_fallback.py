"""Cascade fallback tests — Q9 panel-flagged missing test (Codex catch).

Verifies the Tier 1 → Tier 2 cascade engages on the right error types
(BudgetExceededError, NOT generic Exception). Generic crashes do NOT cascade,
they raise (no ack, replays).
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
    dispatch_agent,
)


@pytest.fixture(scope="module")
def contracts():
    return load_contracts()


@pytest.mark.asyncio
async def test_generic_exception_does_not_cascade(contracts) -> None:
    """Network error / segfault / etc. MUST raise — no cascade.

    Cascade is reserved for KNOWN exhaust signals (budget). Random errors
    should bubble up so the supervisor doesn't ack the outbox row.
    """
    with patch(
        "wr3_dispatch_agent._dispatch_claude_sdk",
        new=AsyncMock(side_effect=RuntimeError("connection reset")),
    ), patch(
        "wr3_dispatch_agent._dispatch_gemini_cli", new=AsyncMock()
    ) as cascade:
        with pytest.raises(RuntimeError):
            await dispatch_agent(
                contracts, "wr3-script-editor", "prompt", episode_id="ep"
            )
        cascade.assert_not_awaited()


@pytest.mark.asyncio
async def test_budget_exceeded_engages_cascade_on_hot_path(contracts) -> None:
    fake = DispatchResult(
        agent="wr3-script-editor",
        cost_usd_estimated=0.0,
        duration_ms=1000,
        cascade_tier=2,
        raw_output="cascade-success",
    )
    with patch(
        "wr3_dispatch_agent._dispatch_claude_sdk",
        new=AsyncMock(side_effect=BudgetExceededError("claude exceed")),
    ), patch(
        "wr3_dispatch_agent._dispatch_gemini_cli",
        new=AsyncMock(return_value=fake),
    ) as cascade:
        result = await dispatch_agent(
            contracts, "wr3-script-editor", "prompt", episode_id="ep"
        )
        assert result.cascade_tier == 2
        cascade.assert_awaited_once()


@pytest.mark.asyncio
async def test_cascade_reason_recorded(contracts) -> None:
    fake = DispatchResult(
        agent="wr3-script-editor",
        cost_usd_estimated=0.0,
        duration_ms=1000,
        cascade_tier=2,
        raw_output="ok",
        cascade_reason="claude_budget_exceeded",
    )
    with patch(
        "wr3_dispatch_agent._dispatch_claude_sdk",
        new=AsyncMock(side_effect=BudgetExceededError("claude exceed")),
    ), patch(
        "wr3_dispatch_agent._dispatch_gemini_cli",
        new=AsyncMock(return_value=fake),
    ):
        result = await dispatch_agent(
            contracts, "wr3-script-editor", "prompt", episode_id="ep"
        )
        assert result.cascade_reason == "claude_budget_exceeded"


@pytest.mark.asyncio
async def test_audio_producer_is_core_cascades(contracts) -> None:
    """audio-asset-producer is core, non-gate — verify it cascades on budget."""
    fake = DispatchResult(
        agent="wr3-audio-asset-producer",
        cost_usd_estimated=0.0,
        duration_ms=500,
        cascade_tier=2,
        raw_output="ok",
    )
    with patch(
        "wr3_dispatch_agent._dispatch_claude_sdk",
        new=AsyncMock(side_effect=BudgetExceededError("audio budget exceed")),
    ), patch(
        "wr3_dispatch_agent._dispatch_gemini_cli",
        new=AsyncMock(return_value=fake),
    ) as cascade:
        result = await dispatch_agent(
            contracts, "wr3-audio-asset-producer", "prompt", episode_id="ep"
        )
        assert result.cascade_tier == 2
        cascade.assert_awaited_once()


@pytest.mark.asyncio
async def test_fallback_tier_does_not_cascade(contracts) -> None:
    """b-roll-curator is FALLBACK tier — no cascade on budget."""
    with patch(
        "wr3_dispatch_agent._dispatch_claude_sdk",
        new=AsyncMock(side_effect=BudgetExceededError("fallback budget")),
    ), patch(
        "wr3_dispatch_agent._dispatch_gemini_cli", new=AsyncMock()
    ) as cascade:
        with pytest.raises(CascadeExhaustedError):
            await dispatch_agent(
                contracts, "wr3-b-roll-curator", "prompt", episode_id="ep"
            )
        cascade.assert_not_awaited()
