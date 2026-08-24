"""The ten-tool risk-tiered registry (MANDATE.md F5).

Implements research capture §4 (Qwen §4)'s ten tools **verbatim** — exact
names, exact JSON schemas, exact per-tool risk tier and confirmation
nuance. See ../../README.md's "Naming note" for why this package follows
Qwen §4's wire-level shapes literally rather than the MANDATE prose's
dotted-namespace shorthand (``client.lookup``, an ``open_preview``/
``open_commit`` split, ...): lane B4 already ran real empirical
golden-suite evaluations against exactly this name/schema/tier set on the
actual Qwen3-14B model, and this registry stays byte-compatible with that
measured evidence rather than silently disconnecting from it.

Design principles (Qwen §4, verbatim): read tools separate from mutation
tools; one mutation per tool; enums not free text; IDs not names; small
result payloads; no bulk operations; no raw DB access; backend enforces
RBAC/transition-rules/audit; the model never sees full sensitive identifiers
unless necessary; high-risk tools are gated by orchestrator confirmation.

pydantic v2 house style, matching backend/services/client_bot/*.

Author: Claude Sonnet 5 (lane B3 — team-bot tool registry)
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .envelope import (
    CLIENT_ID_PATTERN,
    PRACTICE_ID_PATTERN,
    STAFF_ID_PATTERN,
    TARGET_ID_PATTERN,
    DocumentType,
    Priority,
    PracticeStatus,
    PracticeType,
    ReasonCode,
    ReminderType,
    SourceChannel,
)

__all__ = [
    "TOOL_NAMES",
    "TOOL_REGISTRY",
    "ConfirmPolicy",
    "RiskTier",
    "ToolKind",
    "ToolSpec",
    "get_tool",
]


class RiskTier(StrEnum):
    """Qwen §4 "Tool summary" table risk tiers, verbatim."""

    R0 = "R0"  # read, never confirmed
    R1 = "R1"  # low mutation, no confirm (undo where the CRM supports it)
    R2 = "R2"  # mutation, confirmed ONLY under a named conflict condition
    R3 = "R3"  # high mutation, always confirmed


class ToolKind(StrEnum):
    READ = "read"
    MUTATION = "mutation"


class ConfirmPolicy(StrEnum):
    """Finer-grained than a bool because R2 is genuinely conditional (Qwen
    §4 tool 7's own confirmation-policy prose: "No confirm if practice is
    active and document not received. Confirm if: document already
    received / practice archived-rejected-approved / date far off /
    phrasing ambiguous") — collapsing that to True/False would either lose
    the condition or misrepresent R2 as unconditionally gated like R3.
    """

    NEVER = "never"  # R0
    NO_CONFIRM_UNDO = "no_confirm_undo"  # R1
    CONDITIONAL = "conditional"  # R2
    ALWAYS = "always"  # R3


_TIER_POLICY: dict[RiskTier, ConfirmPolicy] = {
    RiskTier.R0: ConfirmPolicy.NEVER,
    RiskTier.R1: ConfirmPolicy.NO_CONFIRM_UNDO,
    RiskTier.R2: ConfirmPolicy.CONDITIONAL,
    RiskTier.R3: ConfirmPolicy.ALWAYS,
}


class ToolSpec(BaseModel):
    """One entry in the frozen ten-tool registry.

    ``confirm_policy`` is DERIVED from ``risk_tier`` via ``_TIER_POLICY``,
    never set independently — the 1:1 tier<->policy mapping is exactly
    Qwen §4's own table, and encoding it as a second free field would let a
    future edit desync tier from policy silently. The validator below makes
    that impossible; ``confirm_condition`` is the one piece of information
    that genuinely varies per-tool within R2 and is NOT derivable, so it
    stays a real field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Annotated[str, Field(pattern=r"^[a-z][a-z_]*$")]
    kind: ToolKind
    risk_tier: RiskTier
    confirm_policy: ConfirmPolicy
    confirm_condition: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    description: Annotated[str, Field(min_length=1, max_length=500)]
    parameters_schema: dict[str, object]

    @model_validator(mode="after")
    def _tier_constrains_policy_and_kind(self) -> ToolSpec:
        expected_policy = _TIER_POLICY[self.risk_tier]
        if self.confirm_policy != expected_policy:
            raise ValueError(
                f"confirm_policy must be {expected_policy} for risk_tier "
                f"{self.risk_tier} (Qwen §4 tier table)"
            )
        if self.risk_tier == RiskTier.R0 and self.kind != ToolKind.READ:
            raise ValueError("R0 is reserved for read tools")
        if self.risk_tier != RiskTier.R0 and self.kind != ToolKind.MUTATION:
            raise ValueError("R1/R2/R3 are reserved for mutation tools")
        is_conditional = self.confirm_policy == ConfirmPolicy.CONDITIONAL
        if is_conditional and self.confirm_condition is None:
            raise ValueError("confirm_condition is required when confirm_policy is conditional")
        if not is_conditional and self.confirm_condition is not None:
            raise ValueError("confirm_condition must be unset unless confirm_policy is conditional")
        params = self.parameters_schema
        if params.get("additionalProperties") is not False:
            raise ValueError("parameters_schema must set additionalProperties: false (F5)")
        return self


# ---------------------------------------------------------------------------
# `mark_document_received`'s `source` (Qwen §4 tool 7) is a DIFFERENT
# vocabulary from `open_practice`'s `source_channel` (SourceChannel, tool
# 10) — "courier" here has no SourceChannel equivalent, and SourceChannel's
# "meeting" has no equivalent here. Kept separate deliberately; see
# envelope.py's SourceChannel docstring.
# ---------------------------------------------------------------------------
_DOCUMENT_RECEIVED_SOURCES: tuple[str, ...] = (
    "whatsapp",
    "email",
    "portal",
    "in_person",
    "courier",
)


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


# ---------------------------------------------------------------------------
# 1. search_clients — R0
# ---------------------------------------------------------------------------
_SEARCH_CLIENTS = ToolSpec(
    name="search_clients",
    kind=ToolKind.READ,
    risk_tier=RiskTier.R0,
    confirm_policy=ConfirmPolicy.NEVER,
    description=(
        "Read-only. Search clients by name, phone, email, or tax code fragment. "
        "Returns client_id candidates. Use client_id for later tools."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 2,
                "maxLength": 80,
                "description": "Client name, phone fragment, email fragment, or tax code fragment.",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 5, "default": 5},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)

# ---------------------------------------------------------------------------
# 2. get_client — R0
# ---------------------------------------------------------------------------
_GET_CLIENT = ToolSpec(
    name="get_client",
    kind=ToolKind.READ,
    risk_tier=RiskTier.R0,
    confirm_policy=ConfirmPolicy.NEVER,
    description="Read-only. Get one client by client_id.",
    parameters_schema={
        "type": "object",
        "properties": {"client_id": {"type": "string", "pattern": CLIENT_ID_PATTERN}},
        "required": ["client_id"],
        "additionalProperties": False,
    },
)

# ---------------------------------------------------------------------------
# 3. list_practices — R0
# ---------------------------------------------------------------------------
_LIST_PRACTICES = ToolSpec(
    name="list_practices",
    kind=ToolKind.READ,
    risk_tier=RiskTier.R0,
    confirm_policy=ConfirmPolicy.NEVER,
    description=(
        "Read-only. List practices. Filter by client_id, status, assigned_to, "
        "or due_before. Returns max 10 practices."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "client_id": {"type": "string", "pattern": CLIENT_ID_PATTERN},
            "status": {"type": "string", "enum": _enum_values(PracticeStatus)},
            "assigned_to": {"type": "string", "pattern": STAFF_ID_PATTERN},
            "due_before": {"type": "string", "format": "date"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 10},
        },
        "required": [],
        "additionalProperties": False,
    },
)

# ---------------------------------------------------------------------------
# 4. get_practice — R0
# ---------------------------------------------------------------------------
_GET_PRACTICE = ToolSpec(
    name="get_practice",
    kind=ToolKind.READ,
    risk_tier=RiskTier.R0,
    confirm_policy=ConfirmPolicy.NEVER,
    description=(
        "Read-only. Get one practice by practice_id, including document "
        "checklist and status."
    ),
    parameters_schema={
        "type": "object",
        "properties": {"practice_id": {"type": "string", "pattern": PRACTICE_ID_PATTERN}},
        "required": ["practice_id"],
        "additionalProperties": False,
    },
)

# ---------------------------------------------------------------------------
# 5. get_required_documents — R0
# ---------------------------------------------------------------------------
_GET_REQUIRED_DOCUMENTS = ToolSpec(
    name="get_required_documents",
    kind=ToolKind.READ,
    risk_tier=RiskTier.R0,
    confirm_policy=ConfirmPolicy.NEVER,
    description="Read-only. Get required and optional document types for a practice type.",
    parameters_schema={
        "type": "object",
        "properties": {"practice_type": {"type": "string", "enum": _enum_values(PracticeType)}},
        "required": ["practice_type"],
        "additionalProperties": False,
    },
)

# ---------------------------------------------------------------------------
# 6. list_assignable_staff — R0
# ---------------------------------------------------------------------------
_LIST_ASSIGNABLE_STAFF = ToolSpec(
    name="list_assignable_staff",
    kind=ToolKind.READ,
    risk_tier=RiskTier.R0,
    confirm_policy=ConfirmPolicy.NEVER,
    description="Read-only. List staff members eligible for assignment. Returns staff_id values.",
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "maxLength": 60, "description": "Name fragment."},
            "role": {"type": "string", "enum": ["agent", "senior_agent", "manager", "admin"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 10},
        },
        "required": [],
        "additionalProperties": False,
    },
)

# ---------------------------------------------------------------------------
# 7. mark_document_received — R2 (conditional confirm)
# ---------------------------------------------------------------------------
_MARK_DOCUMENT_RECEIVED = ToolSpec(
    name="mark_document_received",
    kind=ToolKind.MUTATION,
    risk_tier=RiskTier.R2,
    confirm_policy=ConfirmPolicy.CONDITIONAL,
    confirm_condition=(
        "No confirm if the practice is active and the document is not already "
        "received. Confirm if: the document is already received; the practice "
        "is archived, rejected, or approved; received_date is far in the "
        "past/future; or user phrasing is ambiguous."
    ),
    description=(
        "Mutation. Mark one document type as received for one practice. Use "
        "only after practice_id is known. One document per call."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "practice_id": {"type": "string", "pattern": PRACTICE_ID_PATTERN},
            "document_type": {"type": "string", "enum": _enum_values(DocumentType)},
            "received_date": {
                "type": "string",
                "format": "date",
                "description": "Optional. Defaults to today if omitted.",
            },
            "source": {"type": "string", "enum": list(_DOCUMENT_RECEIVED_SOURCES)},
        },
        "required": ["practice_id", "document_type", "source"],
        "additionalProperties": False,
    },
)

# ---------------------------------------------------------------------------
# 8. create_reminder — R1 (no confirm, undo)
# ---------------------------------------------------------------------------
_CREATE_REMINDER = ToolSpec(
    name="create_reminder",
    kind=ToolKind.MUTATION,
    risk_tier=RiskTier.R1,
    confirm_policy=ConfirmPolicy.NO_CONFIRM_UNDO,
    description=(
        "Mutation. Create one reminder for a practice or client. Use ISO "
        "date-time for due_at."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "target_type": {"type": "string", "enum": ["practice", "client"]},
            "target_id": {"type": "string", "pattern": TARGET_ID_PATTERN},
            "reminder_type": {"type": "string", "enum": _enum_values(ReminderType)},
            "due_at": {"type": "string", "format": "date-time"},
            "assigned_to": {
                "type": "string",
                "pattern": STAFF_ID_PATTERN,
                "description": "Optional. Defaults to requesting staff member if omitted.",
            },
        },
        "required": ["target_type", "target_id", "reminder_type", "due_at"],
        "additionalProperties": False,
    },
)

# ---------------------------------------------------------------------------
# 9. update_practice_status — R3 (always confirm)
# ---------------------------------------------------------------------------
_UPDATE_PRACTICE_STATUS = ToolSpec(
    name="update_practice_status",
    kind=ToolKind.MUTATION,
    risk_tier=RiskTier.R3,
    confirm_policy=ConfirmPolicy.ALWAYS,
    description=(
        "Mutation, high risk. Change one practice status. Use only after "
        "practice_id is known. Reason code is required."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "practice_id": {"type": "string", "pattern": PRACTICE_ID_PATTERN},
            "new_status": {"type": "string", "enum": _enum_values(PracticeStatus)},
            "reason_code": {"type": "string", "enum": _enum_values(ReasonCode)},
        },
        "required": ["practice_id", "new_status", "reason_code"],
        "additionalProperties": False,
    },
)

# ---------------------------------------------------------------------------
# 10. open_practice — R3 (always confirm)
# ---------------------------------------------------------------------------
_OPEN_PRACTICE = ToolSpec(
    name="open_practice",
    kind=ToolKind.MUTATION,
    risk_tier=RiskTier.R3,
    confirm_policy=ConfirmPolicy.ALWAYS,
    description=(
        "Mutation, high risk. Open one new practice for an existing client. "
        "Use client_id, not client name."
    ),
    parameters_schema={
        "type": "object",
        "properties": {
            "client_id": {"type": "string", "pattern": CLIENT_ID_PATTERN},
            "practice_type": {"type": "string", "enum": _enum_values(PracticeType)},
            "assigned_to": {"type": "string", "pattern": STAFF_ID_PATTERN},
            "priority": {"type": "string", "enum": _enum_values(Priority)},
            "source_channel": {"type": "string", "enum": _enum_values(SourceChannel)},
        },
        "required": ["client_id", "practice_type", "assigned_to", "priority", "source_channel"],
        "additionalProperties": False,
    },
)


TOOL_REGISTRY: tuple[ToolSpec, ...] = (
    _SEARCH_CLIENTS,
    _GET_CLIENT,
    _LIST_PRACTICES,
    _GET_PRACTICE,
    _GET_REQUIRED_DOCUMENTS,
    _LIST_ASSIGNABLE_STAFF,
    _MARK_DOCUMENT_RECEIVED,
    _CREATE_REMINDER,
    _UPDATE_PRACTICE_STATUS,
    _OPEN_PRACTICE,
)

TOOL_NAMES: frozenset[str] = frozenset(spec.name for spec in TOOL_REGISTRY)

_BY_NAME: dict[str, ToolSpec] = {spec.name: spec for spec in TOOL_REGISTRY}


def get_tool(name: str) -> ToolSpec | None:
    """Exact-name lookup only — never a substring/prefix match
    (cicatrix-superscar.md family #3: guard-over-match by substring)."""
    return _BY_NAME.get(name)
