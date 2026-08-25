"""Per-member memory — the frozen data shapes (owner directive #1 §3, relayed
by the orchestrator in ``/tmp/due-bot-directive-1.md``, integrated into
``docs/plans/2026-08-25-due-bot-live/MANDATE.md`` by
``dd23aab94``).

Directive verbatim: "Tre strati nello state store locale (sqlite Mini,
replicato Pro — la memoria sopravvive al failover): (1) Profilo stabile:
ruolo/RBAC, lingua preferita per membro, formato risposte, orari. (2)
Episodica: clienti/pratiche toccati di recente, richieste recenti — i
riferimenti anaforici ... risolvono da qui. (3) Pattern appresi: abitudini
ricorrenti -> proattivita personalizzata."

**The PII boundary is the constraint this whole package is built around**
(team lead's framing, verbatim: "the central design constraint"). Every
model below is typed so that a cleartext client name, phone number,
passport/KTP/NPWP number, or raw chat message CANNOT enter it — not "the
caller is expected not to put PII here", but the field shapes themselves
reject it:

- Members are addressed by ``principal_id`` (F7's opaque, non-PII token —
  ``team_bot.confirmation.models.PRINCIPAL_ID_PATTERN``), never a phone
  number or name. This module never stores a raw WhatsApp number.
- Clients/practices touched are addressed by ``target_id``
  (``CL-...``/``PR-...``, ``team_bot.registry.envelope.TARGET_ID_PATTERN``),
  never a client's ``full_name``.
- "Recent requests" are stored as a closed ``IntentCategory`` enum, never
  the request's literal text — this is the one place this package departs
  from the literal directive wording ("richieste recenti") on purpose:
  storing the raw chat message would make client PII (a name, a phone
  number typed into a WhatsApp reply, a passport number) a persistence
  concern for the FIRST time in this lane's design, and Law 2's output
  frontier (CLAUDE.md §14) applies to persisted memory exactly as it does
  to logs. A category answers "what kind of thing was this" — enough for
  anaphora resolution ("e per l'altro cliente?" resolves from the target_id
  history, not from remembered prose) — without ever giving the model a
  transcript of what was said.
- "Learned patterns" are a closed, snake_case ``pattern_key`` vocabulary
  (same shape as ``team_bot.registry.envelope.ToolError.code``), never a
  free-text description of the habit.

This module carries only the DATA shape. Storage/CAS behavior lives in
``store.py``; the ~200-token render lives in ``card.py``; the "dimentica X"
parser lives in ``forget_input.py``.

Author: Claude Sonnet 5 (lane B8 — per-member memory)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from team_bot.confirmation.models import PRINCIPAL_ID_PATTERN
from team_bot.confirmation.outcomes import Locale
from team_bot.registry.envelope import TARGET_ID_PATTERN

__all__ = [
    "PATTERN_KEY_PATTERN",
    "WORKING_HOURS_PATTERN",
    "EpisodicEvent",
    "IntentCategory",
    "LearnedPattern",
    "Locale",
    "MemberProfile",
    "ResponseFormat",
    "StaffRole",
    "TargetType",
]

# Same closed vocabulary `list_assignable_staff` (registry/tools.py) already
# uses for its `role` filter — reused verbatim rather than a second copy
# that could drift.
class StaffRole(StrEnum):
    AGENT = "agent"
    SENIOR_AGENT = "senior_agent"
    MANAGER = "manager"
    ADMIN = "admin"


class ResponseFormat(StrEnum):
    """How this member likes replies shaped. Two values only, deliberately
    narrow — extend when a real second axis is measured, not speculatively."""

    CONCISE = "concise"
    DETAILED = "detailed"


class TargetType(StrEnum):
    """Same two values `create_reminder`'s `target_type` (registry/tools.py)
    already uses — an episodic event's target is always a client or a
    practice, never anything else."""

    CLIENT = "client"
    PRACTICE = "practice"


class IntentCategory(StrEnum):
    """What KIND of thing touched this target — never the literal request
    text (see module docstring). Closed vocabulary; a category an event
    does not fit is ``OTHER``, never a new ad-hoc string threaded through
    from model output."""

    LOOKUP = "lookup"
    STATUS_CHECK = "status_check"
    DOCUMENT_UPDATE = "document_update"
    REMINDER = "reminder"
    MUTATION = "mutation"
    DIGEST = "digest"
    OTHER = "other"


WORKING_HOURS_PATTERN = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"

# Same shape as `team_bot.registry.envelope.ToolError.code` — snake_case,
# closed-ish (open vocabulary in principle, but never a smuggled sentence:
# a pattern_key is a LABEL for a recurring shape, not a description).
PATTERN_KEY_PATTERN = r"^[a-z][a-z0-9_]{1,63}$"

_MAX_OBSERVATION_COUNT = 100_000


class MemberProfile(BaseModel):
    """Layer 1 — stable. One row per ``principal_id``, last-write-wins.

    RBAC (``role``) is carried here for the card render only — this is NOT
    the authorization boundary. F7's own text is explicit ("the model
    cannot supply actor or scope; CRM routes independently enforce
    assigned_to") and `team_crm_tools.py` already establishes the pattern
    this profile does not override: scope comes from the server-resolved
    identity at call time, never from a cached memory row. If this row and
    a live RBAC lookup ever disagree, the live lookup wins — this field
    exists so the card can say "you're an agent" without a second DB
    round-trip, not to gate anything.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    principal_id: Annotated[str, Field(pattern=PRINCIPAL_ID_PATTERN)]
    role: StaffRole
    preferred_language: Locale
    response_format: ResponseFormat = ResponseFormat.CONCISE
    working_hours_start: Annotated[str, Field(pattern=WORKING_HOURS_PATTERN)] | None = None
    working_hours_end: Annotated[str, Field(pattern=WORKING_HOURS_PATTERN)] | None = None
    updated_at: datetime


class EpisodicEvent(BaseModel):
    """Layer 2 — one "this member touched this target" fact.

    Never carries the request text — see module docstring. Bounded
    retention is `store.py`'s job (a fixed count per principal), not this
    model's; this type is a read-only snapshot of one row.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    principal_id: Annotated[str, Field(pattern=PRINCIPAL_ID_PATTERN)]
    target_type: TargetType
    target_id: Annotated[str, Field(pattern=TARGET_ID_PATTERN)]
    intent_category: IntentCategory
    tool_name: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    occurred_at: datetime

    @model_validator(mode="after")
    def _target_type_matches_target_id_prefix(self) -> EpisodicEvent:
        expected_prefix = "CL-" if self.target_type == TargetType.CLIENT else "PR-"
        if not self.target_id.startswith(expected_prefix):
            raise ValueError(
                f"target_id {self.target_id!r} does not match target_type "
                f"{self.target_type.value!r} (expected prefix {expected_prefix!r})"
            )
        return self


class LearnedPattern(BaseModel):
    """Layer 3 — one recurring-habit counter for one member.

    ``observation_count`` only ever increments (``store.py``'s
    ``record_pattern_signal``) — this type is a read-only snapshot, never
    constructed with a count the store did not itself compute.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    principal_id: Annotated[str, Field(pattern=PRINCIPAL_ID_PATTERN)]
    pattern_key: Annotated[str, Field(pattern=PATTERN_KEY_PATTERN)]
    observation_count: Annotated[int, Field(ge=1, le=_MAX_OBSERVATION_COUNT)]
    first_observed_at: datetime
    last_observed_at: datetime

    @model_validator(mode="after")
    def _last_not_before_first(self) -> LearnedPattern:
        if self.last_observed_at < self.first_observed_at:
            raise ValueError("last_observed_at cannot precede first_observed_at")
        return self
