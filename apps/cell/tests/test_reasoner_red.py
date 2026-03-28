"""Empirical test: verify the SlowReasoner activates correctly on RED health.

These tests make REAL LLM calls (no mocks).
Run with: PYTHONPATH=. pytest tests/test_reasoner_red.py -v -s
The -s flag shows LLM output in real time for debugging.
"""
import os

import pytest

from cell.core.dna_interpreter import DNAInterpreter
from cell.slow.reasoner import SlowReasoner

# Actions the reasoner may legitimately propose for a RED/degraded backend
VALID_ACTIONS = {"restart_service", "alert_human", "read_logs", "alert_silent", "none"}


@pytest.mark.asyncio
async def test_reasoner_proposes_action_on_red() -> None:
    """On RED health the reasoner must propose a sensible action."""
    reasoner = SlowReasoner(gemini_api_key=os.environ.get("GOOGLE_API_KEY", ""))
    interpreter = DNAInterpreter()

    proposal = await reasoner.think(
        health_status="red",
        response_time_ms=30_000,
        error_message="Connection refused",
        recent_history=[{"health_status": "red", "pulse_number": i, "response_time_ms": 30_000} for i in range(5)],
        budget_spent=0.5,
        budget_limit=10.0,
    )

    print(f"\n[RED] tier={proposal.tier_used} action={proposal.action} confidence={proposal.confidence:.2f}")
    print(f"[RED] reason: {proposal.reason}")

    assert proposal.action in ("restart_service", "alert_human", "read_logs", "alert_silent"), (
        f"Expected an actionable response on RED, got: {proposal.action!r}"
    )
    assert proposal.confidence >= 0.6, (
        f"Expected confidence >= 0.6 on RED, got: {proposal.confidence}"
    )
    assert proposal.tier_used in (-1, 0, 1), (
        f"Expected tier 0 (Qwen) or 1 (Gemini) or -1 (pattern), got: {proposal.tier_used}"
    )

    validation = interpreter.validate(
        action_name=proposal.action,
        budget_spent=0.5,
        budget_limit=10.0,
        confidence=proposal.confidence,
    )
    # Must either be approved or explicitly blocked with a stated rule
    assert validation.approved or validation.rule_violated is not None, (
        "Validation returned neither approved nor a violated rule"
    )
    print(f"[RED] validation: approved={validation.approved} rule={validation.rule_violated}")


@pytest.mark.asyncio
async def test_reasoner_no_action_on_green() -> None:
    """On GREEN health the reasoner must NOT propose disruptive actions."""
    reasoner = SlowReasoner(gemini_api_key=os.environ.get("GOOGLE_API_KEY", ""))

    proposal = await reasoner.think(
        health_status="green",
        response_time_ms=300,
        error_message="",
        recent_history=[],
        budget_spent=0.0,
        budget_limit=10.0,
    )

    print(f"\n[GREEN] tier={proposal.tier_used} action={proposal.action} confidence={proposal.confidence:.2f}")
    print(f"[GREEN] reason: {proposal.reason}")

    assert proposal.action == "none", (
        f"Expected 'none' on GREEN health, got: {proposal.action!r}"
    )
