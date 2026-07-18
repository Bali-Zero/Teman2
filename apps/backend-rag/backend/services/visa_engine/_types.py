"""Dependency-free leaf types shared by ``fact_registry.py``, ``ast.py``, and
``models.py``.

This module exists purely to break the import cycle CodeQL's
``py/unsafe-cyclic-import`` flags on the "real" module graph: ``models.py``
needs ``ApplicantFactPath``/``FactPath``/``UnknownReason``, ``ast.py`` needs
``FactPath``/``FactSnapshot``/``UnknownFact`` — and all of those previously
lived in ``fact_registry.py``, which itself needs (at type-check time)
``models.ApplicantFacts``. That combination is a real cycle:
``models -> fact_registry -> models`` and
``models -> ast -> fact_registry -> models``.

Moving the closed fact-path vocabulary and the two runtime fact wrappers
here means neither ``models.py`` nor ``ast.py`` needs to import
``fact_registry`` at all, so the remaining ``fact_registry -> models``
edge (``TYPE_CHECKING``-only, in ``fact_registry.py``) is a single directed
edge with nothing pointing back — no longer part of any cycle.

``fact_registry.py`` re-exports every name defined here (backward-compat:
any existing ``from backend.services.visa_engine.fact_registry import X``
keeps working unchanged) and additionally owns ``FactSpec``/
``FactRegistry``/``DEFAULT_FACT_SPECS``/``canonical_fact_payload`` — none of
which ``models.py`` or ``ast.py`` need, so they stay there rather than move
here.

Pure module: stdlib only. MUST NOT import ``models``, ``ast``,
``fact_registry``, or ``compiler`` — any such import re-creates the cycle
this module exists to remove.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class UnknownReason(str, Enum):
    """Why a fact is ``UNKNOWN`` — matches ``$defs.UnknownFact.reason`` in the
    JSON Schema contract exactly (5 members, no silent 6th "other")."""

    NOT_ASKED = "NOT_ASKED"
    NOT_PROVIDED = "NOT_PROVIDED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTING = "CONFLICTING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ApplicantFactPath(str, Enum):
    """The 35 fact paths an applicant (or intake flow) can supply.

    Matches ``$defs.ApplicantFactPath`` in the JSON Schema contract exactly —
    same 35 members, same order, same dotted-string values.
    """

    PERSON_BIRTH_DATE = "person.birth_date"
    PERSON_NATIONALITIES = "person.nationalities"
    PERSON_MARITAL_STATUS = "person.marital_status"
    IMMIGRATION_CURRENTLY_IN_INDONESIA = "immigration.currently_in_indonesia"
    IMMIGRATION_CURRENT_STATUS_CODE = "immigration.current_status_code"
    IMMIGRATION_CURRENT_STATUS_EXPIRY = "immigration.current_status_expiry"
    IMMIGRATION_LAST_ENTRY_DATE = "immigration.last_entry_date"
    IMMIGRATION_OVERSTAY_DAYS = "immigration.overstay_days"
    IMMIGRATION_VIOLATION_HISTORY = "immigration.violation_history"
    INTENT_PURPOSES = "intent.purposes"
    INTENT_STAY_DAYS = "intent.stay_days"
    INTENT_DESIRED_ENTRY_DATE = "intent.desired_entry_date"
    INTENT_ENTRY_PATTERN = "intent.entry_pattern"
    INTENT_REQUESTED_PRODUCT_CODE = "intent.requested_product_code"
    WORK_EMPLOYER_COUNTRY_CODE = "work.employer_country_code"
    WORK_EMPLOYER_IS_INDONESIAN_ENTITY = "work.employer_is_indonesian_entity"
    WORK_SERVES_INDONESIAN_CLIENTS = "work.serves_indonesian_clients"
    WORK_INDONESIA_SOURCE_COMPENSATION = "work.indonesia_source_compensation"
    WORK_INDONESIAN_WORK_SPONSOR_CONFIRMED = "work.indonesian_work_sponsor_confirmed"
    INVESTMENT_PT_PMA_COMMITTED = "investment.pt_pma_committed"
    INVESTMENT_INVESTMENT_CAPITAL_IDR = "investment.investment_capital_idr"
    INVESTMENT_PAID_UP_CAPITAL_IDR = "investment.paid_up_capital_idr"
    INVESTMENT_PROPOSED_ROLE = "investment.proposed_role"
    FAMILY_RELATION_TO_SPONSOR = "family.relation_to_sponsor"
    FAMILY_SPONSOR_NATIONALITIES = "family.sponsor_nationalities"
    FAMILY_SPONSOR_STATUS_CODE = "family.sponsor_status_code"
    FAMILY_MARRIAGE_REGISTERED = "family.marriage_registered"
    FAMILY_SPONSOR_CONFIRMED = "family.sponsor_confirmed"
    STUDY_LEVEL = "study.level"
    STUDY_ADMISSION_CONFIRMED = "study.admission_confirmed"
    STUDY_SPONSOR_CONFIRMED = "study.sponsor_confirmed"
    PROCESS_APPLICATION_CHANNEL = "process.application_channel"
    PROCESS_WANTS_ONSHORE_CONVERSION = "process.wants_onshore_conversion"
    COMMERCIAL_SERVICE_FEE_BUDGET_IDR = "commercial.service_fee_budget_idr"
    COMMERCIAL_WANTS_QUOTE = "commercial.wants_quote"


class DerivedFactPath(str, Enum):
    """The 3 facts the engine computes itself — never supplied by an applicant.

    Matches the ``derived.*`` half of ``$defs.FactPath`` exactly.
    """

    AGE_YEARS = "derived.age_years"
    IS_MINOR = "derived.is_minor"
    HAS_INDONESIAN_CITIZENSHIP = "derived.has_indonesian_citizenship"


FactPath = ApplicantFactPath | DerivedFactPath
"""Every valid fact path a condition (``ast.py``) may reference —
matches ``$defs.FactPath`` (``oneOf`` [ApplicantFactPath, derived.*])."""


@dataclass(frozen=True)
class KnownFact:
    """Runtime representation of a fact whose value is known.

    ``value`` is already canonicalized: dates are ISO-8601 strings, sets are
    ``frozenset[str]``, everything else is the bare ``bool``/``int``/``str``.
    """

    value: object


@dataclass(frozen=True)
class UnknownFact:
    """Runtime representation of a fact whose value is unknown."""

    reason: UnknownReason


@dataclass(frozen=True)
class FactSnapshot:
    """The full set of facts (applicant-supplied + derived) for one evaluation."""

    values: Mapping[str, KnownFact | UnknownFact]
