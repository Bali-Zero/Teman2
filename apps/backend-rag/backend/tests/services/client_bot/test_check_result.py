"""CheckOutcome's own two invariants — see its module docstring for why
each is a defect a check module must never be able to construct.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import pytest

from backend.services.client_bot.policy.check_result import CheckOutcome
from backend.services.client_bot.policy.types import GateReason, GateVerdict


def test_construct_normal_terminal_outcome() -> None:
    outcome = CheckOutcome(verdict=GateVerdict.ABSTAIN, reason=GateReason.MODEL_ABSTAINED)
    assert outcome.verdict == GateVerdict.ABSTAIN
    assert outcome.reason_detail is None


def test_allow_verdict_is_rejected() -> None:
    with pytest.raises(ValueError, match="ALLOW"):
        CheckOutcome(verdict=GateVerdict.ALLOW, reason=GateReason.MODEL_ABSTAINED)


def test_passed_all_checks_reason_is_rejected() -> None:
    with pytest.raises(ValueError, match="PASSED_ALL_CHECKS"):
        CheckOutcome(verdict=GateVerdict.HANDOFF, reason=GateReason.PASSED_ALL_CHECKS)


def test_is_frozen() -> None:
    outcome = CheckOutcome(verdict=GateVerdict.DROP, reason=GateReason.HUMAN_TAKEOVER_ACTIVE)
    with pytest.raises(AttributeError):
        outcome.reason_detail = "mutated"  # type: ignore[misc]
