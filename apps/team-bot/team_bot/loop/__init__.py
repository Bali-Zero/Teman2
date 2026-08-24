"""The team-bot typed tool loop's shared decision/gate types.

``ToolDecision`` is the schema this lane shares with B4's serving contract
(MANDATE.md "Lanes": "B3/B4 share only the ToolDecision schema and the
serving endpoint contract"). ``ActionClaimGate`` closes the gc-015 defect
class (B4b empirical finding — see claim_gate.py's module docstring).
"""

from __future__ import annotations

from .claim_gate import ActionClaimGate, ActionClaimVerdict, ClaimGateDecision
from .tool_decision import ProposedToolCall, ToolDecision

__all__ = [
    "ActionClaimGate",
    "ActionClaimVerdict",
    "ClaimGateDecision",
    "ProposedToolCall",
    "ToolDecision",
]
