"""ExecutionRecord — the ONLY proof that a tool executed this turn.

Added in response to the fenced cross-family refuter's finding (relayed by
the orchestrator): ``ActionClaimGate.evaluate``'s original ``execution_ok:
bool`` parameter established nothing. A bare Python ``bool`` type hint is
not runtime-validated by a plain staticmethod call — passing the STRING
``"false"`` is truthy and silently ALLOWs, and even a genuine ``bool`` had
no provenance: nothing tied it to an actual tool having actually run, for
THIS turn, successfully.

``ExecutionRecord`` fixes both problems by construction: it can only be
built by the two places execution actually happens —
``confirmation/store.py``'s ``execute()`` reaching ``EXECUTED`` (R2/R3,
F6), or a direct un-gated R1 tool call (``ExecutionSource.DIRECT_R1``) —
and its ``ok``/``executed_at``/``tool_name`` fields are real pydantic
fields, not a caller-asserted flag. The absence of a record (``None``) is
now the ONLY way to represent "nothing executed" — there is no truthy/falsy
string to smuggle past a type check.

Orchestrator follow-up (same day, from my own report naming the gap): this
type establishes "a tool existed" (registry membership) but originally
said nothing about WHICH KIND of tool — nothing stopped constructing a
record for an R0 READ tool via ``ExecutionSource.DIRECT_R1``, which by
this architecture's own convention only ever wraps an R1 MUTATION tool
executed directly. ``_tool_is_a_mutation`` closes that: the tool named
must be a ``ToolKind.MUTATION`` per the F5 registry, not merely registered.
Still does NOT establish "belongs to THIS turn" (no turn/conversation
identifier on the type — a caller-discipline invariant, not yet a
structural one; no live caller exists to test this against) or "matches
what the reply specifically describes" (moot in ``compose_reply``'s
primary-control path, which renders directly from this record's own
fields rather than comparing to free text; a real but narrow residual gap
in ``claim_gate.py``'s defense-in-depth ALLOW branch, not fixed here —
closing it would mean parsing free text for which tool it claims, which is
the unbounded-arms-race anti-pattern the orchestrator's claim_gate ruling
already named).

Author: Claude Sonnet 5 (lane B3 — team-bot confirmation state machine)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from team_bot.registry import TOOL_NAMES, ToolKind, get_tool

__all__ = ["ExecutionRecord", "ExecutionSource"]


class ExecutionSource(StrEnum):
    """Where this execution actually happened — the two, and only two,
    places a tool call can reach the CRM in this architecture."""

    DIRECT_R1 = "direct_r1"  # an R1 (no_confirm_undo) tool executed directly, no PendingAction
    PENDING_ACTION = "pending_action"  # an R2/R3 tool executed via F6's PendingAction reaching EXECUTED


class ExecutionRecord(BaseModel):
    """Proof, not assertion. Frozen — constructed once by whichever
    executor actually ran the tool, never mutated after."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: Annotated[str, Field(min_length=1, max_length=128)]
    ok: bool
    source: ExecutionSource
    executed_at: datetime
    result_ref: Annotated[str, Field(min_length=1, max_length=64)] | None = None

    @model_validator(mode="after")
    def _tool_name_is_registered(self) -> ExecutionRecord:
        if self.tool_name not in TOOL_NAMES:
            raise ValueError(f"tool_name {self.tool_name!r} is not in the F5 registry")
        return self

    @model_validator(mode="after")
    def _tool_is_a_mutation(self) -> ExecutionRecord:
        # Runs after _tool_name_is_registered (pydantic v2 runs "after"
        # validators in declaration order) so get_tool() is guaranteed a
        # hit here, never None. An ExecutionRecord proves a MUTATION
        # occurred — an R0 read tool has nothing to "execute" in this
        # sense and is never the subject of a completion claim in the
        # first place.
        spec = get_tool(self.tool_name)
        assert spec is not None  # narrows for mypy/readers; see comment above
        if spec.kind is not ToolKind.MUTATION:
            raise ValueError(
                f"tool_name {self.tool_name!r} is a {spec.kind.value} tool — "
                "ExecutionRecord only represents a mutation's execution"
            )
        return self
