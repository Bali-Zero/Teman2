"""E33 Second Home — client case lifecycle model (CRM).

Extends the existing practice/journey/compliance machinery for the E33
Second Home visa vertical; it does NOT replace it:

- The coarse CRM practice status still flows through
  ``practice_state_machine.py`` (inquiry → … → completed). This module models
  the E33-specific *case* stages that live underneath an ``on_process``
  practice, mirroring that file's validated-transition pattern.
- Compliance deadlines computed here (the Day-90 guarantee-proof gate and the
  annual maintenance recurrence) are emitted as
  ``backend.services.compliance.predictive_engine.ComplianceForecast`` objects,
  so the existing ``AlertsEngine`` (dedup → ``compliance_alerts`` → dispatcher)
  carries persistence, i18n and delivery. No parallel alert framework.
- Expiry-driven E33 renewals are covered by the existing
  ``PredictiveComplianceEngine`` via the ``e33_second_home_renewal`` rule in
  ``renewal_rules.py`` — deliberately not duplicated here.

NO-CUSTODY SOP (owner decision 2026-07-23, non-negotiable)
-----------------------------------------------------------
Bali Zero NEVER holds, routes, or observes client funds. The USD 130,000
own-name BUMN-bank deposit (or the USD 1,000,000 qualifying property) is
placed and kept by the CLIENT. This model therefore stores EVIDENCE
REFERENCES ONLY: document ids, issuing party, dates, filing confirmations.
It must never store account numbers, balances, amounts, IBANs or any other
financial-instrument detail — ``EvidenceRef`` has no such fields by design
and its free-form ``metadata`` dict is rejected by
:func:`validate_evidence_metadata` if custody-flavoured keys appear.
PII is kept minimal per UU PDP: a case links to the CRM client by id only;
names/passports stay in the CRM client record.

Dependents (E31B/E31E/E31H/E31J) are PENDING official confirmation
(letter 006, ``research/secondhome/e33-letter-response-tracker.md``): the
relationship is modelled, but the allowed codes live in the configurable
``DEFAULT_DEPENDENT_CODES`` constant — never hardcoded in logic.

ITAP_EVAL is modelled but gated behind ``E33_ITAP_EVAL_ENABLED = False``:
ITAP conversion marketing is forbidden until the written letter-006 Q7
reply arrives (owner decision 2026-07-23).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any

from backend.services.compliance.predictive_engine import ComplianceForecast
from backend.services.compliance.priority_scorer import calculate_priority

logger = logging.getLogger(__name__)


# ── Stages ────────────────────────────────────────────────────────────────────


class E33Stage(str, Enum):
    """Lifecycle stages of an E33 Second Home case."""

    FIT_MEMO = "fit_memo"  # free fit assessment (owner decision: FREE)
    BANK_PRECHECK = "bank_precheck"  # BUMN bank pre-check of deposit route
    APPLICATION = "application"  # visa application dossier
    PAYMENT = "payment"  # PNBP/service payment step
    VISA_ISSUED = "visa_issued"  # visa granted, pre-entry
    ENTRY = "entry"  # client entered Indonesia
    ITAS_ACTIVE = "itas_active"  # ITAS (stay permit) activated
    GUARANTEE_PROOF_DUE = "guarantee_proof_due"  # 90-day evidence gate open
    ANNUAL_MAINTENANCE = "annual_maintenance"  # gate cleared; yearly upkeep
    RENEWAL = "renewal"  # permit renewal in progress
    EPO = "epo"  # Exit Permit Only — terminal
    STATUS_CHANGE = "status_change"  # moved to another permit — terminal
    ITAP_EVAL = "itap_eval"  # ITAP evaluation (gated, see E33_ITAP_EVAL_ENABLED)


class GuaranteeBasis(str, Enum):
    """Which qualifying-guarantee route the case uses.

    Mid-permit basis switch (deposit ↔ property) is BELUM_DIATUR_PUBLIK in
    the E33 fact registry — a basis change mid-permit is therefore NOT a
    normal transition and must go through STATUS_CHANGE handling instead.
    """

    DEPOSIT = "deposit"  # USD 130,000 own-name at a BUMN state bank
    PROPERTY = "property"  # USD 1,000,000 qualifying completed strata title


# Forward transitions. Back-edges allow one-step correction only.
VALID_TRANSITIONS: dict[E33Stage, set[E33Stage]] = {
    E33Stage.FIT_MEMO: {E33Stage.BANK_PRECHECK},
    E33Stage.BANK_PRECHECK: {E33Stage.APPLICATION, E33Stage.FIT_MEMO},
    E33Stage.APPLICATION: {E33Stage.PAYMENT, E33Stage.BANK_PRECHECK},
    E33Stage.PAYMENT: {E33Stage.VISA_ISSUED, E33Stage.APPLICATION},
    E33Stage.VISA_ISSUED: {E33Stage.ENTRY},
    E33Stage.ENTRY: {E33Stage.ITAS_ACTIVE},
    E33Stage.ITAS_ACTIVE: {
        E33Stage.GUARANTEE_PROOF_DUE,
        E33Stage.EPO,
        E33Stage.STATUS_CHANGE,
        E33Stage.ITAP_EVAL,
    },
    E33Stage.GUARANTEE_PROOF_DUE: {
        E33Stage.ANNUAL_MAINTENANCE,
        E33Stage.EPO,
        E33Stage.STATUS_CHANGE,
    },
    E33Stage.ANNUAL_MAINTENANCE: {
        E33Stage.RENEWAL,
        E33Stage.EPO,
        E33Stage.STATUS_CHANGE,
        E33Stage.ITAP_EVAL,
    },
    E33Stage.RENEWAL: {E33Stage.ITAS_ACTIVE},
    E33Stage.EPO: set(),  # terminal
    E33Stage.STATUS_CHANGE: set(),  # terminal
    E33Stage.ITAP_EVAL: {E33Stage.STATUS_CHANGE},
}

TERMINAL_STAGES: frozenset[E33Stage] = frozenset({E33Stage.EPO, E33Stage.STATUS_CHANGE})

# Stages in which the ITAS is live (post-entry, pre-terminal).
ACTIVE_PERMIT_STAGES: frozenset[E33Stage] = frozenset(
    {E33Stage.ITAS_ACTIVE, E33Stage.GUARANTEE_PROOF_DUE, E33Stage.ANNUAL_MAINTENANCE}
)

# ITAP conversion marketing is forbidden until the written letter-006 Q7
# reply (owner decision 2026-07-23). Flip to True only after that reply.
E33_ITAP_EVAL_ENABLED: bool = False


class E33InvalidTransitionError(Exception):
    """Raised when an E33 case stage transition is not allowed."""

    def __init__(self, from_stage: E33Stage, to_stage: E33Stage, reason: str = "") -> None:
        self.from_stage = from_stage
        self.to_stage = to_stage
        self.reason = reason
        msg = f"Invalid E33 transition: {from_stage.value} → {to_stage.value}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


def validate_transition(
    from_stage: E33Stage,
    to_stage: E33Stage,
    *,
    itap_eval_enabled: bool = E33_ITAP_EVAL_ENABLED,
) -> bool:
    """Validate an E33 case stage transition.

    Mirrors ``practice_state_machine.validate_transition``: same-stage is a
    no-op, unknown/terminal states and missing edges raise.

    Raises:
        E33InvalidTransitionError: If the transition is not allowed.
    """
    if from_stage == to_stage:
        return True
    allowed = VALID_TRANSITIONS.get(from_stage, set())
    if to_stage not in allowed:
        raise E33InvalidTransitionError(
            from_stage,
            to_stage,
            f"allowed transitions from '{from_stage.value}': {sorted(s.value for s in allowed)}",
        )
    if to_stage == E33Stage.ITAP_EVAL and not itap_eval_enabled:
        raise E33InvalidTransitionError(
            from_stage,
            to_stage,
            "ITAP evaluation is gated until the letter-006 Q7 written reply",
        )
    logger.debug("E33 transition validated: %s → %s", from_stage.value, to_stage.value)
    return True


# ── Dependents (codes pending official confirmation — configurable) ───────────

# Candidate dependent codes from the E33 research corner, PENDING official
# confirmation (letter 006). Overridable per-call; never hardcoded in logic.
DEFAULT_DEPENDENT_CODES: tuple[str, ...] = ("E31B", "E31E", "E31H", "E31J")


class UnknownDependentCodeError(ValueError):
    """Raised when a dependent code is not in the allowed set."""


@dataclass(frozen=True)
class DependentLink:
    """Link from a principal E33 case to a dependent (spouse/child/parent).

    ``code`` is the dependent visa code (candidate values in
    ``DEFAULT_DEPENDENT_CODES``, pending official confirmation).
    ``client_id`` references the CRM client record — no PII is copied here.
    """

    code: str
    client_id: int
    relationship: str  # "spouse" | "child" | "parent" | free text until confirmed


def validate_dependent_code(
    code: str,
    *,
    allowed: tuple[str, ...] = DEFAULT_DEPENDENT_CODES,
) -> str:
    """Validate a dependent code against the allowed (configurable) set."""
    if code not in allowed:
        raise UnknownDependentCodeError(
            f"Unknown dependent code {code!r}; allowed: {allowed}. "
            "Codes are pending official confirmation — extend "
            "DEFAULT_DEPENDENT_CODES only after the letter-006 reply."
        )
    return code


# ── Evidence (no-custody) ─────────────────────────────────────────────────────


class EvidenceKind(str, Enum):
    """Evidence categories. All are REFERENCES, never financial data."""

    BANK_CONFIRMATION = "bank_confirmation"  # bank letter confirming the deposit exists
    PROPERTY_TITLE = "property_title"  # proof of the qualifying property
    IMMIGRATION_FILING = "immigration_filing"  # proof submitted to Immigration
    IMMIGRATION_RECEIPT = "immigration_receipt"  # Immigration acknowledgement
    OTHER = "other"


# Keys that would turn an evidence record into custody data. Normalized
# (lower-cased, separators stripped) before matching.
FORBIDDEN_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "accountnumber",
        "account",
        "balance",
        "amount",
        "iban",
        "swift",
        "nomorrekening",
        "norekening",
        "norek",
        "saldo",
        "jumlah",
    }
)


class CustodyViolationError(ValueError):
    """Raised when evidence metadata would breach the no-custody SOP."""


def _normalize_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch.isalnum())


def validate_evidence_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Reject evidence metadata that would breach the no-custody SOP.

    Bali Zero never holds or observes client funds: account numbers,
    balances and amounts are forbidden in case evidence. Only document
    references, dates and confirmations may be stored.
    """
    for key in metadata:
        if _normalize_key(str(key)) in FORBIDDEN_METADATA_KEYS:
            raise CustodyViolationError(
                f"Evidence metadata key {key!r} breaches the no-custody SOP: "
                "store document references and dates only, never account "
                "numbers, balances or amounts."
            )
    return metadata


@dataclass(frozen=True)
class EvidenceRef:
    """Reference to a piece of guarantee evidence — metadata only.

    ``document_ref`` is a pointer to the CRM/Drive document (id or path),
    never the document content and never financial-instrument data.
    """

    evidence_id: str
    kind: EvidenceKind
    document_ref: str  # CRM document id / Drive file id — never account data
    issued_date: date | None = None  # when the bank/notary issued the proof
    filed_date: date | None = None  # when it was filed to Immigration
    confirmed_by: str | None = None  # team member who verified the reference
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_evidence_metadata(self.metadata)


# ── Day-90 guarantee gate + annual maintenance ────────────────────────────────

# The qualifying guarantee must be evidenced to Immigration within 90 days
# of entry/ITAS and MAINTAINED for the permit validity.
GUARANTEE_PROOF_WINDOW_DAYS: int = 90
# Alert schedule: days AFTER the anchor (entry/ITAS date) at which alerts
# fire — Day 30 / 60 / 75, i.e. 60 / 30 / 15 days before the deadline.
GUARANTEE_ALERT_DAYS_AFTER: tuple[int, ...] = (30, 60, 75)
# Annual maintenance: re-confirm the guarantee is maintained each ITAS
# anniversary; alerts start this many days before it.
ANNUAL_MAINTENANCE_ALERT_DAYS_BEFORE: int = 60

# Severity mapping aligned with AlertSeverity (info > 60d, warning ≤ 60d,
# urgent ≤ 30d, critical ≤ 7d or overdue). Values are the strings
# AlertsEngine._urgency_to_severity passes through unchanged.
_SEVERITY_INFO = "info"
_SEVERITY_WARNING = "warning"
_SEVERITY_URGENT = "urgent"
_SEVERITY_CRITICAL = "critical"

# matched_rule_id values carried into ComplianceForecast.compliance_item_ref
# (stable → AlertsEngine dedup/promotion works across the Day 30/60/75 run).
RULE_ID_GUARANTEE_PROOF = "e33_guarantee_proof_90d"
RULE_ID_ANNUAL_MAINTENANCE = "e33_annual_maintenance"

# document_type values — mapped to the "guarantee_proof" template category in
# alerts_engine._DOCTYPE_TO_CATEGORY.
DOCTYPE_GUARANTEE = "e33_guarantee"
DOCTYPE_MAINTENANCE = "e33_maintenance"


def severity_for_days_until(days_until: int) -> str:
    """Map days-until-deadline to an alert severity string."""
    if days_until < 0 or days_until <= 7:
        return _SEVERITY_CRITICAL
    if days_until <= 30:
        return _SEVERITY_URGENT
    if days_until <= 60:
        return _SEVERITY_WARNING
    return _SEVERITY_INFO


@dataclass(frozen=True)
class GuaranteeMilestone:
    """One alert milestone of the Day-90 guarantee gate."""

    day_after_anchor: int  # e.g. 30
    at: date  # absolute calendar date the alert fires
    days_until_deadline: int  # days remaining on that date (e.g. 60)


def compute_guarantee_deadline(anchor: date) -> date:
    """Deadline = anchor (entry/ITAS date) + GUARANTEE_PROOF_WINDOW_DAYS."""
    return anchor + timedelta(days=GUARANTEE_PROOF_WINDOW_DAYS)


def guarantee_alert_schedule(
    anchor: date,
    *,
    alert_days: tuple[int, ...] = GUARANTEE_ALERT_DAYS_AFTER,
) -> list[GuaranteeMilestone]:
    """Compute the Day 30/60/75 alert schedule for the guarantee gate."""
    return [
        GuaranteeMilestone(
            day_after_anchor=d,
            at=anchor + timedelta(days=d),
            days_until_deadline=GUARANTEE_PROOF_WINDOW_DAYS - d,
        )
        for d in alert_days
    ]


def next_itas_anniversary(itas_date: date, *, today: date) -> date:
    """Next yearly ITAS anniversary on or after ``today`` (Feb-29 safe)."""

    def _shift(years: int) -> date:
        try:
            return itas_date.replace(year=itas_date.year + years)
        except ValueError:  # Feb 29 → Feb 28 in non-leap years
            return itas_date.replace(year=itas_date.year + years, day=28)

    years = max(1, today.year - itas_date.year)
    anniv = _shift(years)
    while anniv < today:
        years += 1
        anniv = _shift(years)
    return anniv


# ── Case ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StageTransition:
    """One recorded stage change (append-only history entry)."""

    from_stage: E33Stage | None  # None for the initial stage
    to_stage: E33Stage
    at: datetime
    actor: str | None = None
    note: str | None = None


@dataclass
class E33Case:
    """An E33 Second Home client case.

    Links to the CRM by ids only (PII-minimal per UU PDP): ``client_id`` is
    the CRM client, ``practice_id`` the coarse CRM practice whose status
    still follows ``practice_state_machine``. ``owner`` is the assigned team
    member (same ``assigned_to`` semantics as practices).
    """

    case_id: str
    client_id: int
    basis: GuaranteeBasis
    stage: E33Stage = E33Stage.FIT_MEMO
    practice_id: int | None = None
    owner: str | None = None
    entry_date: date | None = None
    itas_date: date | None = None
    dependent_code: str | None = None  # set when THIS case is a dependent
    principal_case_id: str | None = None  # set when THIS case is a dependent
    dependents: list[DependentLink] = field(default_factory=list)
    evidence: list[EvidenceRef] = field(default_factory=list)
    history: list[StageTransition] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

    # ── Stage machine ────────────────────────────────────────────────────

    def advance(
        self,
        to_stage: E33Stage,
        *,
        at: datetime,
        actor: str | None = None,
        note: str | None = None,
        occurred_on: date | None = None,
        itap_eval_enabled: bool = E33_ITAP_EVAL_ENABLED,
    ) -> StageTransition:
        """Move the case to a new stage, recording history and key dates.

        ``occurred_on`` pins the legal date of ENTRY / ITAS_ACTIVE events
        (defaults to ``at.date()``) — it anchors the Day-90 computation.
        """
        validate_transition(self.stage, to_stage, itap_eval_enabled=itap_eval_enabled)
        transition = StageTransition(
            from_stage=self.stage, to_stage=to_stage, at=at, actor=actor, note=note
        )
        self.history.append(transition)
        self.stage = to_stage
        if to_stage == E33Stage.ENTRY:
            self.entry_date = occurred_on or at.date()
        elif to_stage == E33Stage.ITAS_ACTIVE:
            self.itas_date = occurred_on or at.date()
        logger.info("E33 case %s: %s → %s", self.case_id, transition.from_stage, to_stage.value)
        return transition

    # ── Evidence ─────────────────────────────────────────────────────────

    def add_evidence(self, evidence: EvidenceRef) -> None:
        """Attach an evidence reference (no-custody validated at build)."""
        self.evidence.append(evidence)
        logger.info(
            "E33 case %s: evidence %s (%s) attached",
            self.case_id,
            evidence.evidence_id,
            evidence.kind.value,
        )

    @property
    def guarantee_basis_evidence_complete(self) -> bool:
        """Basis proof exists: bank confirmation (deposit) or title (property)."""
        if self.basis == GuaranteeBasis.DEPOSIT:
            return any(e.kind == EvidenceKind.BANK_CONFIRMATION for e in self.evidence)
        return any(e.kind == EvidenceKind.PROPERTY_TITLE for e in self.evidence)

    @property
    def guarantee_proof_filed(self) -> bool:
        """The guarantee proof has been filed to Immigration."""
        return any(
            e.kind == EvidenceKind.IMMIGRATION_FILING and e.filed_date is not None
            for e in self.evidence
        )

    @property
    def guarantee_evidence_complete(self) -> bool:
        """Basis proof collected AND filed to Immigration."""
        return self.guarantee_basis_evidence_complete and self.guarantee_proof_filed

    # ── Day-90 gate ──────────────────────────────────────────────────────

    @property
    def guarantee_anchor(self) -> date | None:
        """Anchor date for the 90-day gate: ITAS date preferred, entry fallback."""
        return self.itas_date or self.entry_date

    @property
    def guarantee_deadline(self) -> date | None:
        """Day-90 deadline, or None before entry/ITAS."""
        anchor = self.guarantee_anchor
        return compute_guarantee_deadline(anchor) if anchor else None

    # ── StayGuard hook ───────────────────────────────────────────────────

    @property
    def stayguard_eligible(self) -> bool:
        """StayGuard (annual monitoring retainer) eligibility flag.

        Owner decision: StayGuard launches only after this tracker exists and
        is offered to E33 clients whose permit is live AND whose Day-90
        guarantee evidence is complete (ITAS_ACTIVE-or-later with the basis
        proof filed to Immigration). Pure computation — no pricing, no
        sending; the commercial offer is a separate follow-up.
        """
        return self.stage in ACTIVE_PERMIT_STAGES and self.guarantee_evidence_complete

    # ── Forecasts (AlertsEngine integration) ─────────────────────────────

    def build_case_forecasts(self, *, today: date) -> list[ComplianceForecast]:
        """Build compliance forecasts for this case as of ``today``.

        Emits at most:
        - one Day-90 guarantee-proof forecast, once the first alert milestone
          (Day 30 after anchor) is reached, while the proof is unfiled;
        - one annual-maintenance forecast when inside the pre-anniversary
          alert window, once the gate is cleared.

        Returns ``ComplianceForecast`` objects ready for
        ``AlertsEngine.generate_alerts`` — dedup keys are stable across runs
        (``compliance_item_ref`` is constant per item), so severity promotion
        carries the Day 30 → 60 → 75 escalation.
        """
        forecasts: list[ComplianceForecast] = []
        if self.stage in TERMINAL_STAGES:
            return forecasts

        guarantee_fc = self._build_guarantee_forecast(today=today)
        if guarantee_fc is not None:
            forecasts.append(guarantee_fc)

        maintenance_fc = self._build_maintenance_forecast(today=today)
        if maintenance_fc is not None:
            forecasts.append(maintenance_fc)

        return forecasts

    def _build_guarantee_forecast(self, *, today: date) -> ComplianceForecast | None:
        anchor = self.guarantee_anchor
        if anchor is None or self.guarantee_proof_filed:
            return None
        if self.stage not in ACTIVE_PERMIT_STAGES:
            return None
        deadline = compute_guarantee_deadline(anchor)
        first_alert_day = min(GUARANTEE_ALERT_DAYS_AFTER)
        days_until = (deadline - today).days
        if (today - anchor).days < first_alert_day and days_until >= 0:
            return None  # before the Day-30 milestone — nothing to alert yet

        urgency = severity_for_days_until(days_until)
        priority = calculate_priority(
            days_until_action=days_until,
            estimated_revenue_idr=None,
            complexity=2.0,
        )
        if self.basis == GuaranteeBasis.DEPOSIT:
            required_docs = [
                "bank_confirmation_letter_bumn",
                "immigration_filing_receipt",
            ]
        else:
            required_docs = [
                "property_title_proof",
                "immigration_filing_receipt",
            ]
        return ComplianceForecast(
            client_id=self.client_id,
            client_name="",  # PII-minimal: name resolved downstream from CRM
            assigned_to=self.owner,
            document_type=DOCTYPE_GUARANTEE,
            current_visa_type="E33",
            expiry_date=deadline,
            days_until_expiry=days_until,
            matched_rule_id=RULE_ID_GUARANTEE_PROOF,
            processing_days=0,
            lead_time_start=anchor,
            recommended_action_by=anchor + timedelta(days=min(GUARANTEE_ALERT_DAYS_AFTER)),
            days_until_action=days_until,
            estimated_revenue_idr=None,
            renewal_pricing_key=None,
            priority_score=priority.score,
            urgency_level=urgency,
            required_docs=required_docs,
            has_active_renewal_practice=False,
            notes=(
                "E33 Day-90 gate: guarantee proof must be evidenced to "
                "Immigration within 90 days of entry/ITAS and maintained for "
                "the permit validity."
            ),
        )

    def _build_maintenance_forecast(self, *, today: date) -> ComplianceForecast | None:
        if self.stage != E33Stage.ANNUAL_MAINTENANCE or self.itas_date is None:
            return None
        anniversary = next_itas_anniversary(self.itas_date, today=today)
        days_until = (anniversary - today).days
        if days_until > ANNUAL_MAINTENANCE_ALERT_DAYS_BEFORE:
            return None

        urgency = severity_for_days_until(days_until)
        priority = calculate_priority(
            days_until_action=days_until,
            estimated_revenue_idr=None,
            complexity=1.5,
        )
        return ComplianceForecast(
            client_id=self.client_id,
            client_name="",
            assigned_to=self.owner,
            document_type=DOCTYPE_MAINTENANCE,
            current_visa_type="E33",
            expiry_date=anniversary,
            days_until_expiry=days_until,
            matched_rule_id=RULE_ID_ANNUAL_MAINTENANCE,
            processing_days=0,
            lead_time_start=anniversary - timedelta(days=ANNUAL_MAINTENANCE_ALERT_DAYS_BEFORE),
            recommended_action_by=anniversary
            - timedelta(days=ANNUAL_MAINTENANCE_ALERT_DAYS_BEFORE),
            days_until_action=days_until,
            estimated_revenue_idr=None,
            renewal_pricing_key=None,
            priority_score=priority.score,
            urgency_level=urgency,
            required_docs=[
                "fresh_bank_confirmation_or_property_title",
                "current_itas_card",
            ],
            has_active_renewal_practice=False,
            notes=(
                "E33 annual maintenance: re-confirm the qualifying guarantee "
                "(deposit/property) is still maintained at the ITAS anniversary."
            ),
        )


__all__ = [
    "ACTIVE_PERMIT_STAGES",
    "ANNUAL_MAINTENANCE_ALERT_DAYS_BEFORE",
    "DEFAULT_DEPENDENT_CODES",
    "DOCTYPE_GUARANTEE",
    "DOCTYPE_MAINTENANCE",
    "E33_ITAP_EVAL_ENABLED",
    "FORBIDDEN_METADATA_KEYS",
    "GUARANTEE_ALERT_DAYS_AFTER",
    "GUARANTEE_PROOF_WINDOW_DAYS",
    "RULE_ID_ANNUAL_MAINTENANCE",
    "RULE_ID_GUARANTEE_PROOF",
    "TERMINAL_STAGES",
    "VALID_TRANSITIONS",
    "CustodyViolationError",
    "DependentLink",
    "E33Case",
    "E33InvalidTransitionError",
    "E33Stage",
    "EvidenceKind",
    "EvidenceRef",
    "GuaranteeBasis",
    "GuaranteeMilestone",
    "StageTransition",
    "UnknownDependentCodeError",
    "compute_guarantee_deadline",
    "guarantee_alert_schedule",
    "next_itas_anniversary",
    "severity_for_days_until",
    "validate_dependent_code",
    "validate_evidence_metadata",
    "validate_transition",
]
