"""Legacy-to-canonical adapters for Research OS v1.0.0 (Work Packet 04, Deliverable 4).

Scope of this package (see the package docstrings of each module for the
per-kind detail): additive adapters that read a legacy record from an
existing domain system and produce a `research_os` canonical contract
object, alongside an explicit, structured loss report -- never a silent
field drop. Nothing here mutates or reads from any existing domain model;
this package only ADDS a new consumer of legacy data shapes that are passed
in as plain mappings by whatever caller eventually wires up a real read path
(none exists yet -- see `shadow.py`).

This first slice covers the Magazine `ops_intents`/`ops_receipts` action
chain only (`ActionItem`, `ActionIntent`, `OperationalReceipt`). It
deliberately excludes `ExecutionAttempt` and `ApprovalReceipt` -- see
`action_intent_adapter.py`'s module docstring for why.
"""

from __future__ import annotations
