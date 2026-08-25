"""CheckOutcome — the shared return shape every ``policy/*_check.py`` module
uses to report a terminal failure.

Not part of the frozen contract (``types.py``) — this is an internal
plumbing type for wiring one of the 11 ordered checks into
``final_gate.py``, not a shape any provider or caller outside this package
ever sees. ``FinalDecision`` (the real, frozen, externally-visible output)
is assembled by ``final_gate.py`` itself, once, from whichever check's
``CheckOutcome`` stopped the sequence — see its module docstring for why
checks return this instead of a partially-built ``FinalDecision`` (every
check would otherwise need to thread ``decision_id``/``request_id``/
``evaluated_at`` through, for no benefit).

The ``None``-means-pass convention (a check function returns ``CheckOutcome
| None``) mirrors the check functions themselves reading as "stop here" vs.
"continue to the next check" — the same shape ``model_validator`` failures
use in this codebase (raise to stop, return normally to continue).

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.client_bot.policy.types import GateReason, GateVerdict

__all__ = ["CheckOutcome"]


@dataclass(frozen=True)
class CheckOutcome:
    """A terminal, non-ALLOW verdict+reason from one ordered check.

    Never carries ``rendered_text`` — no check module in this package (all
    of which stop the sequence, i.e. never produce ALLOW) is in the
    business of building outbound text; only ``final_gate.py``'s own
    check-10/11 rendering step does that, after every earlier check has
    already passed.
    """

    verdict: GateVerdict
    reason: GateReason
    reason_detail: str | None = None

    def __post_init__(self) -> None:
        if self.verdict == GateVerdict.ALLOW:
            raise ValueError(
                "CheckOutcome must never carry GateVerdict.ALLOW — an ALLOW is the "
                "ABSENCE of any check stopping the sequence (None), not a value a "
                "check module returns"
            )
        if self.reason == GateReason.PASSED_ALL_CHECKS:
            raise ValueError(
                "CheckOutcome must never carry GateReason.PASSED_ALL_CHECKS — that "
                "reason belongs only to the terminal ALLOW FinalDecision final_gate.py "
                "assembles itself when no check module returned an outcome at all"
            )
