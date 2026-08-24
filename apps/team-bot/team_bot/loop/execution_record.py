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

Author: Claude Sonnet 5 (lane B3 — team-bot confirmation state machine)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from team_bot.registry import TOOL_NAMES

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
