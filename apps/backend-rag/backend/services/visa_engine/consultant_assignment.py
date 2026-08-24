"""``ConsultantAssignmentEvent`` — the Oracle -> CRM consultant-assignment
event, frozen contract C3 (``docs/plans/2026-08-24-visa-oracle-live/contracts/FROZEN.md``).

Implements C3 exactly as frozen by the orchestrator; this module does not
redesign the contract, it types it. A lane wanting a different shape files a
request back to the orchestrator, who re-freezes and re-broadcasts — this
file is not the place to add a field.

**The invariant this event exists to serve** (mandate ``docs/plans/2026-08-24-visa-oracle-live/MANDATE.md``
§1, "the consultant thread"): a visible "Talk to a consultant" control on
EVERY screen — wizard, verdict, checkout, portal — invokable at ANY moment,
including before buying. Self-service is an option, never an obligation.
That is why both ``client_id`` and ``product_version_id`` are nullable: the
control must be emittable by an anonymous visitor who has not yet reached a
verdict.

**Law 2 boundary, absolute and load-bearing here** (FROZEN.md C3, verbatim):
"This event carries no name, phone, email, passport, KTP, or free-text from
the applicant. Identity travels as ``client_id`` only, and only once one
exists. Any lane that finds itself wanting to put a contact detail in this
event has found a design error, not a missing field." Enforced three ways,
deliberately redundant:

1. Every field is a closed type (``UUID``, a closed ``Enum``, or an
   RFC 3339 ``datetime``) — there is no string-typed field a free-text value
   could even be written into.
2. ``extra="forbid"`` rejects any field not in the frozen shape outright, so
   a caller cannot widen the event ad hoc to smuggle a contact detail through
   (e.g. ``name=``, ``phone=``, ``whatsapp=``, ``notes=``).
3. A defense-in-depth guard (:func:`_reject_pii_shaped_field_names`) checks
   the raw input mapping's *key names* against a curated PII-shaped
   vocabulary before Pydantic's own extra-field check even runs, so the
   error a caller sees names Law 2 specifically rather than a generic
   "extra inputs are not permitted".

``consultant_required`` is intentionally **not** a field here — C3 lists
seven fields only. That flag belongs to C2's ``VerdictRoutingIntent`` (the
verdict -> GARUDA-checkout handoff, still blocked on GARUDA's contract
landing on main). This module exposes the equivalent business rule as a
plain Python :pyattr:`ConsultantAssignmentEvent.consultant_required`
*property* — computed, never serialized — so CRM-side routing code has one
place to read it without duplicating the tier rule, while the wire shape
this event actually emits stays exactly the seven frozen fields.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# ---------------------------------------------------------------------------
# Closed vocabularies (C3 wire shape)
# ---------------------------------------------------------------------------


class OriginScreen(str, Enum):
    """Where the "Talk to a consultant" control was invoked from.

    The four values are the mandate's own enumeration of the consultant
    thread's required surfaces (MANDATE.md §1) — the control is a critic-gate
    failure on any screen missing from this list, so this enum is not meant
    to grow casually; a fifth screen surfacing means the product grew a fifth
    screen, and this enum should follow that, not precede it.
    """

    WIZARD = "wizard"
    VERDICT = "verdict"
    CHECKOUT = "checkout"
    PORTAL = "portal"


class ServiceTier(str, Enum):
    """The three service tiers (MANDATE.md §1)."""

    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class EventLocale(str, Enum):
    EN = "en"
    ID = "id"


# ---------------------------------------------------------------------------
# Law 2 defense-in-depth
# ---------------------------------------------------------------------------

# Curated, not a regex sweep: a regex over arbitrary key names is a
# guess at what PII "looks like" (family #3's guard-over-match disease).
# This is a closed list of the exact contact-detail vocabulary the FROZEN.md
# C3 text names, plus their obvious near-synonyms — checked against the
# input mapping's *key names*, never its values (no value on this event can
# be a free string in the first place; see module docstring point 1).
_PII_SHAPED_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "name",
        "full_name",
        "first_name",
        "last_name",
        "applicant_name",
        "phone",
        "phone_number",
        "whatsapp",
        "whatsapp_number",
        "email",
        "email_address",
        "passport",
        "passport_number",
        "ktp",
        "ktp_number",
        "nik",
        "notes",
        "free_text",
        "message",
        "comment",
        "contact",
        "contact_detail",
    }
)


def _reject_pii_shaped_field_names(data: Any) -> Any:
    """``model_validator(mode="before")`` — refuse construction outright if
    the raw input carries a PII-shaped key, before Pydantic's own
    ``extra="forbid"`` check runs.

    Redundant with ``extra="forbid"`` by design (defense-in-depth, not
    dead code): if a future edit ever loosens ``extra`` on this model, this
    guard still fires. Only inspects a plain ``dict`` — anything else
    (already-built kwargs via keyword construction land here as a dict too;
    an already-constructed instance passed to ``model_validate`` does not
    carry arbitrary keys to inspect) is passed through untouched.
    """

    if isinstance(data, dict):
        offending = _PII_SHAPED_FIELD_NAMES.intersection(data.keys())
        if offending:
            raise ValueError(
                "ConsultantAssignmentEvent refuses to serialize: "
                f"PII-shaped field(s) {sorted(offending)!r} are not part of "
                "the frozen C3 contract. Law 2 (SYMBIOSIS.md) — identity "
                "travels as client_id only. This is a design error to fix "
                "at the call site, not a missing field to add here."
            )
    return data


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("requested_at must be timezone-aware UTC")
    return value


# ---------------------------------------------------------------------------
# The event
# ---------------------------------------------------------------------------


class ConsultantAssignmentEvent(BaseModel):
    """C3, verbatim. Seven fields, no more."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_id: UUID
    client_id: UUID | None = None
    requested_at: datetime
    origin_screen: OriginScreen
    tier: ServiceTier
    product_version_id: UUID | None = None
    locale: EventLocale

    _reject_pii_shaped_field_names = model_validator(mode="before")(_reject_pii_shaped_field_names)

    @field_validator("requested_at")
    @classmethod
    def _check_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @property
    def consultant_required(self) -> bool:
        """Derived, never serialized (not one of C3's seven wire fields).

        MANDATE.md §1: T2 — "the client buys online AND the assigned
        consultant always makes contact after purchase ... never a
        fallback"; T3 — "never sold solo ... routes straight to the
        consultant". T1 is self-service and never requires one, though the
        control itself is still always present regardless of tier.
        """

        return self.tier is not ServiceTier.T1
