"""detect_stuck_loop — the read/search chain's loop guard (owner directive
#1 §2: "catene multi-step libere ... con loop-detector e budget").

Cicatrix-superscar family #3 ("guard-over-match / gemello UNDER-match" —
``.claude/rules/cicatrix-superscar.md``) applies to a loop detector exactly
as it applies to a text pattern: an OVER-match aborts a legitimate
multi-step lookup, and an UNDER-match lets a genuinely stuck model burn the
whole step budget re-asking the same question with nothing to show for it.
The team lead's own worked example of the innocent case: "the same client
looked up twice for two different practices" — ``get_client(client_id=...)``
called with the IDENTICAL ``client_id`` argument both times, by
construction, once in the context of practice A and again later for
practice B. That repeat is completely ordinary and must never be flagged.

The detector below is deliberately NARROW: it flags a read chain as stuck
ONLY when the identical ``(tool_name, raw_arguments)`` pair occupies the
CONSECUTIVE TAIL of the chain, at least ``consecutive_repeat_threshold``
steps deep. It does not scan the whole chain's history for a repeat at any
distance, and it does not attempt to detect longer alternating cycles
(A, B, A, B, ...). Both would risk exactly the innocent case above — the
"same client, two practices" pattern is very likely to put the SAME
``get_client`` call twice in the chain, just with an unrelated call (e.g.
``get_practice`` for the other practice) in between, so it is never a
CONSECUTIVE repeat and a consecutive-only rule leaves it alone by
construction, not by a special case carved out for it.

This is the narrowest guard that still catches the concrete failure mode
it exists for: a 14B model that re-issues the exact same call because it
did not understand — or could not use — the tool's own result, over and
over, with no distinguishable progress between attempts. Widening this
further without a fresh guilty+innocence pair to justify it would repeat
the exact mistake ``claim_gate.py``'s own docstring already catalogues one
layer down (the STATUS CHANGE section: an unbounded arms race of pattern
widening is the anti-pattern, not the fix).

Author: Claude Sonnet 5 (lane B3 — team-bot tool registry, directive #1 §2)
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .turn_plan import ReadPlan

__all__ = ["DEFAULT_CONSECUTIVE_REPEAT_THRESHOLD", "LoopDetectorVerdict", "detect_stuck_loop"]

# Below this many consecutive identical calls, "repeated" and "stuck" are
# not yet distinguishable — a single retry after a transient tool error, or
# even one deliberate re-check, is ordinary and must not trip this guard.
# Three in a row with byte-identical arguments has no ordinary explanation
# left: the model asked the CRM the exact same question a third time having
# already seen the answer (or the error) twice with nothing changed.
DEFAULT_CONSECUTIVE_REPEAT_THRESHOLD = 3


class LoopDetectorVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stuck: bool
    reason: Annotated[str, Field(min_length=1, max_length=300)]


def detect_stuck_loop(
    plan: ReadPlan,
    *,
    consecutive_repeat_threshold: int = DEFAULT_CONSECUTIVE_REPEAT_THRESHOLD,
) -> LoopDetectorVerdict:
    """Intended to be called after appending each new step to ``plan``.
    Looks ONLY at the tail — the ``consecutive_repeat_threshold`` most
    recent steps — never the whole chain's history, so a repeat the model
    already moved past (broken by a different call in between, at any
    earlier point in the chain) never counts against it.
    """
    if consecutive_repeat_threshold < 2:
        raise ValueError("consecutive_repeat_threshold must be at least 2 (one real repeat)")

    steps = plan.steps
    if len(steps) < consecutive_repeat_threshold:
        return LoopDetectorVerdict(
            stuck=False,
            reason=(
                f"chain has {len(steps)} step(s), fewer than the "
                f"{consecutive_repeat_threshold}-repeat threshold"
            ),
        )

    tail = steps[-consecutive_repeat_threshold:]
    signature = (tail[0].call.tool_name, tail[0].call.raw_arguments)
    if all((step.call.tool_name, step.call.raw_arguments) == signature for step in tail):
        return LoopDetectorVerdict(
            stuck=True,
            reason=(
                f"the last {consecutive_repeat_threshold} steps all called {signature[0]!r} "
                "with byte-identical arguments — no progress between attempts"
            ),
        )
    return LoopDetectorVerdict(
        stuck=False,
        reason="the tail of the chain is not a run of consecutive identical calls",
    )
