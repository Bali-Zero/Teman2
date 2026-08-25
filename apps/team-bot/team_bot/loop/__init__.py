"""The team-bot typed tool loop's shared decision/gate types.

``ToolDecision`` is the schema this lane shares with B4's serving contract
(MANDATE.md "Lanes": "B3/B4 share only the ToolDecision schema and the
serving endpoint contract"). ``ActionClaimGate`` closes the gc-015 defect
class (B4b empirical finding — see claim_gate.py's module docstring).

``turn_plan`` and ``loop_detector`` implement owner directive #1 §2's
amendment to F4/F5 ("one tool per turn" applies only to mutations; reads
chain freely, MAX_STEPS raised, with a loop detector and a budget) as a
type split ON TOP OF ``ToolDecision`` — that module is unchanged.
"""

from __future__ import annotations

from .claim_gate import ActionClaimGate, ActionClaimVerdict, ClaimGateDecision
from .execution_record import ExecutionRecord, ExecutionSource
from .loop_detector import DEFAULT_CONSECUTIVE_REPEAT_THRESHOLD, LoopDetectorVerdict, detect_stuck_loop
from .tool_decision import ProposedToolCall, ToolDecision
from .turn_plan import (
    ABSOLUTE_MAX_READ_STEPS,
    FinalAnswer,
    MutationDecision,
    ReadPlan,
    ReadStep,
    ReadStepOutcome,
    ReadStepResult,
    StepClassification,
    UnknownToolError,
    classify_step,
    try_append_read_step,
)

__all__ = [
    "ABSOLUTE_MAX_READ_STEPS",
    "DEFAULT_CONSECUTIVE_REPEAT_THRESHOLD",
    "ActionClaimGate",
    "ActionClaimVerdict",
    "ClaimGateDecision",
    "ExecutionRecord",
    "ExecutionSource",
    "FinalAnswer",
    "LoopDetectorVerdict",
    "MutationDecision",
    "ProposedToolCall",
    "ReadPlan",
    "ReadStep",
    "ReadStepOutcome",
    "ReadStepResult",
    "StepClassification",
    "ToolDecision",
    "UnknownToolError",
    "classify_step",
    "detect_stuck_loop",
    "try_append_read_step",
]
