"""GARUDA VOA pilot — intake orchestration (pure, no I/O).

The engine (`eligibility.py` / `safe_clock.py`) does not close its own
inputs: ``screen()`` takes ``days_until_expiry`` as a caller-supplied int
and ``passport_valid_6mo_from_entry`` as a caller-supplied bool, and
``MIN_PASSPORT_VALIDITY_DAYS`` (constants.py) was consumed by nothing
(BUILD-SPEC-SLICE-A-2026-07-27.md §2 trap 3). This module closes that gap
and orchestrates the verdict for the stateless owner preview: derive the two
missing facts from raw dates → ``screen()`` → ``compute_stay()`` → one
combined, auditable result. No I/O, no HTTP.

Field contract (spec §5 — the whole bounded input surface of this preview):
``case_type`` (issuance | extension) · ``nationality`` (ISO-3) ·
``entry_date`` · ``passport_expiry_date`` · ``voa_expiry_date`` (extension
only) · ``extension_already_used`` (bool) · ``purpose`` (enum) ·
``travellers`` (int) · ``self_pay`` (bool). Nothing else — no free-text
field that could carry a name.

Some of ``EligibilityInput``'s SOP §1 criteria have no matching field in
this 9-field wizard (no nationality-eligibility dataset shipped yet, no
interview-only signals like "clean ordinary passport" or "prior
overstay/blacklist" — those are things a human staff member reads off a
document or a conversation, not something this synthetic preview can ask).
This engine therefore gives a PRELIMINARY verdict built only from what it
mechanically can derive; see ``_build_eligibility_input`` for the exact
mapping and the documented defaults for the rest.

Serialization boundary (spec §6, charter — non-negotiable): D-14 is never
serialized. D-10/D-3/D-1 may be serialized only by the authenticated
owner-local preview, never to the read-only historical archive or a public
surface. The archive may carry only the published D-7 Ngurah Rai deadline.
``VoaVerdict`` encodes this provenance split structurally via
``published_filing_deadline`` / ``client_facing_checkpoints`` /
``internal_checkpoints`` so every adapter must select its permitted fields
instead of serializing ``stay_window.checkpoints`` directly.

Issuance-only submission-window gate (owner ruling, 2026-07-27): a VOA is
issued in a few hours, so the issuance rule accepts a request up
to the day BEFORE arrival — counting Bali Zero's systems closed on
Saturday, Sunday, and any Indonesian national holiday / cuti bersama
(`operating_calendar.py`; follow-up ruling, same session). This SUPERSEDES
the charter's blanket "urgent case" exclusion FOR ISSUANCE ONLY — the
bounded 9-field request never had a mechanical "urgent" signal to begin with
(no field in `VoaIntakeRequest` maps to `EligibilityInput.urgent_case`), so
this gate is what actually governs how close to arrival an issuance request
may be submitted. It does NOT touch the extension path: extensions require
an in-person photo/interview (since 29 May 2025) and keep their own runway
gate — now identical to the published D-7 filing deadline itself (owner
ruling 2026-07-27, see `eligibility.screen`) — untouched by this ruling.
``VoaVerdict.submit_by_date`` carries the one date this rule can expose —
Bali Zero's OWN operational commitment, never an immigration
rule — and is ``None`` when it cannot be computed (see
`operating_calendar.last_open_day_before`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from backend.services.garuda_flow import operating_calendar
from backend.services.garuda_flow.constants import (
    MIN_PASSPORT_VALIDITY_DAYS,
    b1_max_total_stay_exceeded,
)
from backend.services.garuda_flow.eligibility import (
    Decision,
    DeclineCode,
    EligibilityInput,
    screen,
)
from backend.services.garuda_flow.safe_clock import (
    SafeCheckpoint,
    StayWindow,
    compute_stay,
    days_until_expiry,
)
from backend.services.visa_check.catalogue import VisaType


class CaseType(str, Enum):
    ISSUANCE = "issuance"
    EXTENSION = "extension"


class Purpose(str, Enum):
    """B1-permitted purposes, distinct from this pilot's eligibility.

    B1 permits tourism, family visits, transit and short business meetings;
    this pilot accepts simple tourism only. Business meetings are also marked
    as a business-purpose exclusion; family purpose is not a traveller group.
    """

    TOURISM = "tourism"
    FAMILY = "family"
    TRANSIT = "transit"
    BUSINESS_MEETING = "business-meeting"


@dataclass(frozen=True)
class VoaIntakeRequest:
    """The whole PII contract (spec §5) — enum/date/bool/ISO-code only."""

    case_type: CaseType
    nationality: str  # ISO-3
    entry_date: date  # actual (issuance) or the original entry (extension)
    passport_expiry_date: date
    purpose: Purpose
    travellers: int
    self_pay: bool
    voa_expiry_date: date | None = None  # required iff case_type == EXTENSION
    extension_already_used: bool = False


@dataclass(frozen=True)
class VoaVerdict:
    """One combined result: eligibility decision + Safe Clock dates.

    ``stay_window.checkpoints`` mixes 1 published-source mark (D-7) with 4
    internal ones (D-14/D-10/D-3/D-1) — see the module docstring. D-14 is
    engine-only; D-10/D-3/D-1 are eligible only for the authenticated
    owner-local preview, never the archive or a public surface. The legacy
    accessor name ``client_facing_checkpoints`` describes provenance; it
    does not authorize a public surface. Use ``published_filing_deadline`` /
    ``client_facing_checkpoints`` / ``internal_checkpoints`` below; never
    read ``stay_window.checkpoints`` directly from a response builder.
    """

    decision: Decision
    decline_reasons: list[str]
    stay_window: StayWindow
    # Parallel to ``decline_reasons`` (same length/order) — the wire-safe
    # machine-code twin. See `eligibility.DeclineCode` docstring: this is
    # the ONLY form of a decline reason an adapter may ever serialize.
    decline_codes: list[str] = field(default_factory=list)
    # Issuance-only (owner ruling 2026-07-27): the last day Bali Zero's own
    # systems are open strictly before `entry_date` — the ONE date this
    # gate may ever expose, and it is Bali Zero's OWN operational
    # commitment, never an immigration deadline. Always `None` for an
    # extension case (untouched by this rule) and for an issuance case
    # whose full last-open-day calculation is outside the materialized
    # operating-calendar coverage (see `_issuance_submission_verdict`).
    submit_by_date: date | None = None

    @property
    def accepted(self) -> bool:
        return self.decision is Decision.ACCEPT

    @property
    def published_filing_deadline(self) -> date:
        """The one externally sourced deadline the engine may expose (D-7)."""
        return self.stay_window.published_filing_deadline

    @property
    def client_facing_checkpoints(self) -> list[SafeCheckpoint]:
        """Legacy name for the published-source D-7 checkpoint."""
        return [c for c in self.stay_window.checkpoints if c.client_facing]

    @property
    def internal_checkpoints(self) -> list[SafeCheckpoint]:
        """Return the engine-internal checkpoints.

        D-14 is never serialized. D-10/D-3/D-1 may be serialized only by the
        authenticated owner-local preview, never to an archive or public surface.
        """
        return [c for c in self.stay_window.checkpoints if not c.client_facing]

    def checkpoint_at(self, label: str) -> date:
        """Absolute date for a Safe-Clock label (e.g. ``"D-10"``)."""
        return next(c.at for c in self.stay_window.checkpoints if c.label == label)


_EXTENSION_LIMIT_REASON = (
    "B1 VOA allows only one extension (30 + 1x30 days) — this would be a "
    "second extension of the same stay; hand off to the ordinary channel"
)

_ARRIVAL_TOO_SOON_REASON = (
    "past our online submission cutoff for this arrival date (Bali Zero "
    "systems closed weekends and Indonesian national holidays/cuti "
    "bersama) — hand off to the manual Bali Zero channel, which is not "
    "bound by this internal preview cutoff"
)

_ARRIVAL_DATE_UNCONFIRMED_REASON = (
    "arrival date is outside the materialized operating calendar coverage — "
    "the internal preview cutoff cannot be "
    "computed without guessing; hand off to a human"
)

_MAX_STAY_EXCEEDED_REASON_TEMPLATE = (
    "printed extension expiry implies a stay beyond the legal B1 maximum "
    "of {max_total_stay_days} days total (arrival day counted as day 1) — "
    "hand off to the ordinary channel"
)


def _issuance_submission_verdict(
    *, entry_date: date, today: date
) -> tuple[date | None, DeclineCode | None, str | None]:
    """Owner ruling (2026-07-27): a VOA is issued in a few hours, so the
    issuance rule accepts a request up to the day BEFORE arrival —
    Bali Zero's systems being closed weekends + Indonesian national
    holidays/cuti bersama (`operating_calendar.py`). Issuance-only; never
    called for an extension case.

    Returns ``(submit_by_date, decline_code, decline_reason)``:

    - ``submit_by_date`` — the last open day strictly before ``entry_date``.
      Bali Zero's OWN operational commitment, never an immigration rule.
      ``None`` only when the full calculation is outside
      ``operating_calendar.COVERAGE_START`` / ``COVERAGE_END``; this routes
      to a human rather than publishing a guessed date.
    - ``decline_code``/``decline_reason`` are both ``None`` when the
      request is still within the window (``today <= submit_by_date``).
    """
    submit_by = operating_calendar.last_open_day_before(entry_date)
    if submit_by is None:
        return None, DeclineCode.ARRIVAL_DATE_UNCONFIRMED, _ARRIVAL_DATE_UNCONFIRMED_REASON
    if today > submit_by:
        return submit_by, DeclineCode.ARRIVAL_TOO_SOON, _ARRIVAL_TOO_SOON_REASON
    return submit_by, None, None


def _build_eligibility_input(request: VoaIntakeRequest, *, today: date) -> EligibilityInput:
    """Map the 9-field intake contract onto ``EligibilityInput``.

    Two derivations close the gap the engine leaves open (spec §2 trap 3):

    - ``passport_valid_6mo_from_entry`` from ``passport_expiry_date`` vs
      ``entry_date`` + ``MIN_PASSPORT_VALIDITY_DAYS``.
    - ``days_until_expiry`` from ``voa_expiry_date`` vs ``today``,
      extension-only (``screen()`` itself already declines a missing value
      on an extension case — see eligibility.py).

    Criteria this wizard cannot mechanically ask (no nationality-eligibility
    dataset yet; "clean ordinary passport" / "prior overstay" are
    interview-only signals) get the ACCEPT-compatible default — a DECLINE
    here always still routes to WhatsApp (SOP amendment, never a bare no),
    and an ACCEPT still goes through the human pilot intake before travel.
    """
    days_left: int | None = None
    if request.case_type is CaseType.EXTENSION and request.voa_expiry_date is not None:
        days_left = days_until_expiry(expiry_date=request.voa_expiry_date, today=today)

    passport_valid = (
        request.passport_expiry_date - request.entry_date
    ).days >= MIN_PASSPORT_VALIDITY_DAYS

    return EligibilityInput(
        nationality_entry_eligible=True,
        simple_tourism=request.purpose is Purpose.TOURISM,
        single_adult_traveler=request.travellers == 1,
        clean_ordinary_passport=True,
        passport_valid_6mo_from_entry=passport_valid,
        self_pay=request.self_pay,
        willing_anonymous_feedback=True,
        is_extension=request.case_type is CaseType.EXTENSION,
        days_until_expiry=days_left,
        family_or_group=request.travellers > 1,
        work_or_business_purpose=request.purpose is Purpose.BUSINESS_MEETING,
    )


def build_verdict(request: VoaIntakeRequest, *, today: date) -> VoaVerdict:
    """Orchestrate the whole VOA verdict: derive → ``screen()`` → ``compute_stay()``.

    Pure — no I/O, no HTTP. ``today`` is caller-supplied (never
    ``date.today()`` internally) so this stays deterministic and
    unit-testable; the router passes the real wall-clock date.
    """
    eligibility_input = _build_eligibility_input(request, today=today)
    result = screen(eligibility_input)

    decision = result.decision
    reasons = list(result.decline_reasons)
    codes = list(result.decline_codes)

    # Computed up front (moved ahead of the layered checks below, 2026-08-23)
    # so the max-total-stay guard can reuse `max_total_days` — the same
    # VISA_META-derived figure the CLI derives locally — instead of
    # re-deriving it a second time.
    printed_expiry = request.voa_expiry_date if request.case_type is CaseType.EXTENSION else None
    stay_window = compute_stay(
        entry_date=request.entry_date,
        visa_type=VisaType.B1,
        printed_expiry=printed_expiry,
    )

    # SOP/catalogue fact (VisaType.B1 extensions=(1, 30)): only ONE extension
    # is possible. `screen()` doesn't know about this — it's a VOA/B1-shape
    # rule, not a generic pilot-intake criterion — so it's layered on here.
    if request.case_type is CaseType.EXTENSION and request.extension_already_used:
        decision = Decision.DECLINE
        reasons.append(_EXTENSION_LIMIT_REASON)
        codes.append(DeclineCode.EXTENSION_ALREADY_USED.value)

    # B1 max-total-stay boundary (`constants.b1_max_total_stay_exceeded`,
    # promoted 2026-08-23 from the owner-local `internal_preview_cli` guard,
    # its sole caller — PR #4685). `screen()` doesn't know about this
    # either — it's a B1/VOA-shape fact from the catalogue, not a generic
    # pilot-intake criterion — so it's layered on here exactly like the
    # extension-limit rule above. The CLI still validates this up front and
    # raises `PreviewInputError` before ever calling `build_verdict()`, so
    # this branch is unreachable for it (its behaviour is unchanged); THIS
    # is the never-a-bare-error form for any caller — e.g. a future public
    # funnel — that must always DECLINE + WhatsApp-handoff rather than
    # reject the request outright.
    if (
        request.case_type is CaseType.EXTENSION
        and request.voa_expiry_date is not None
        and b1_max_total_stay_exceeded(
            (request.voa_expiry_date - request.entry_date).days,
            stay_window.max_total_days,
        )
    ):
        decision = Decision.DECLINE
        reasons.append(
            _MAX_STAY_EXCEEDED_REASON_TEMPLATE.format(
                max_total_stay_days=stay_window.max_total_days
            )
        )
        codes.append(DeclineCode.EXTENSION_EXCEEDS_MAX_STAY.value)

    # Issuance-only submission-window gate (owner ruling 2026-07-27) — see
    # `_issuance_submission_verdict` and the module docstring. `screen()`
    # doesn't know about this either — it's a B1 operational rule,
    # not a generic pilot-intake criterion — so it's layered on here,
    # exactly like the extension-limit rule above. Never runs for an
    # extension case.
    submit_by_date: date | None = None
    if request.case_type is CaseType.ISSUANCE:
        submit_by_date, issuance_code, issuance_reason = _issuance_submission_verdict(
            entry_date=request.entry_date, today=today
        )
        if issuance_code is not None:
            decision = Decision.DECLINE
            reasons.append(issuance_reason)  # type: ignore[arg-type]
            codes.append(issuance_code.value)

    return VoaVerdict(
        decision=decision,
        decline_reasons=reasons,
        stay_window=stay_window,
        decline_codes=codes,
        submit_by_date=submit_by_date,
    )


__all__ = [
    "CaseType",
    "Purpose",
    "VoaIntakeRequest",
    "VoaVerdict",
    "build_verdict",
]
