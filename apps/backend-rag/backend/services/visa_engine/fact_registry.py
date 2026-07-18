"""The closed fact vocabulary + the applicant-facts -> evaluation-snapshot step.

Two representations of a "fact" exist in this package, deliberately kept
distinct:

* The **wire format** (``backend.services.visa_engine.models.ApplicantFacts``)
  mirrors the JSON Schema contract 1:1 — each fact is either
  ``{"status": "UNKNOWN", "reason": ...}`` or a status/value pair typed per
  path (``KnownBoolean``, ``KnownDate``, ...).
* The **runtime snapshot** (this module's :class:`KnownFact`/:class:`UnknownFact`
  + :class:`FactSnapshot`) is what the AST evaluator (``ast.py``) actually
  reads: a flat ``Mapping[str, KnownFact | UnknownFact]`` covering both the
  35 applicant-supplied paths *and* the 3 derived paths
  (``derived.age_years``, ``derived.is_minor``,
  ``derived.has_indonesian_citizenship``), with dates canonicalized to ISO
  strings (so ``lt``/``lte``/``gt``/``gte`` work as plain string comparison)
  and set-valued facts canonicalized to ``frozenset[str]``.

:class:`FactRegistry` is the single source of truth for "what fact paths
exist, what shape are they, are they derived, and can a RANKING-stage rule
reference them" (``commercial_only``) — the compiler (``compiler.py``)
depends on this to reject rule packs that reference unregistered paths or
smuggle a legal fact into a commercial ranking rule.

Pure module: no I/O. The only reference to
``backend.services.visa_engine.models.ApplicantFacts`` is deferred
(``TYPE_CHECKING``-only) to avoid a runtime import cycle — ``models.py``
imports ``ApplicantFactPath``/``UnknownReason`` from *this* module, so this
module must not import ``models.py`` at runtime.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.services.visa_engine.errors import FactValidationError

if TYPE_CHECKING:  # pragma: no cover - import-cycle avoidance only
    from backend.services.visa_engine.models import ApplicantFacts

logger = logging.getLogger(__name__)

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
"""A JSON-safe value: what :func:`canonical_fact_payload` returns members of."""


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
class FactSpec:
    """The registry entry for one fact path.

    ``value_type`` is the fact's *logical* type, used by the compiler
    (``compiler.py``) to validate condition literals and operator/fact-shape
    compatibility — it is one of ``bool``, ``int``, ``str``, ``date``, or
    ``frozenset`` (set-valued facts). Note this is the LOGICAL type, not
    necessarily the exact Python runtime type stored in
    :class:`FactSnapshot`: a ``date`` fact is still stored there as a
    canonicalized ISO-8601 *string* (so ``lt``/``lte``/``gt``/``gte`` work
    via plain string comparison) — ``value_type=date`` exists precisely so
    the compiler can distinguish "this string must be a valid ISO date
    literal" from a plain opaque ``str`` fact (e.g. ``person.marital_status``),
    which has no such constraint.
    """

    path: str
    value_type: type
    derived: bool
    dependencies: frozenset[str]
    commercial_only: bool


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


def _spec(
    path: ApplicantFactPath | DerivedFactPath,
    *,
    value_type: type,
    derived: bool = False,
    dependencies: frozenset[str] = frozenset(),
    commercial_only: bool = False,
) -> FactSpec:
    return FactSpec(
        path=path.value,
        value_type=value_type,
        derived=derived,
        dependencies=dependencies,
        commercial_only=commercial_only,
    )


DEFAULT_FACT_SPECS: tuple[FactSpec, ...] = (
    _spec(ApplicantFactPath.PERSON_BIRTH_DATE, value_type=date),
    _spec(ApplicantFactPath.PERSON_NATIONALITIES, value_type=frozenset),
    _spec(ApplicantFactPath.PERSON_MARITAL_STATUS, value_type=str),
    _spec(ApplicantFactPath.IMMIGRATION_CURRENTLY_IN_INDONESIA, value_type=bool),
    _spec(ApplicantFactPath.IMMIGRATION_CURRENT_STATUS_CODE, value_type=str),
    _spec(ApplicantFactPath.IMMIGRATION_CURRENT_STATUS_EXPIRY, value_type=date),
    _spec(ApplicantFactPath.IMMIGRATION_LAST_ENTRY_DATE, value_type=date),
    _spec(ApplicantFactPath.IMMIGRATION_OVERSTAY_DAYS, value_type=int),
    _spec(ApplicantFactPath.IMMIGRATION_VIOLATION_HISTORY, value_type=frozenset),
    _spec(ApplicantFactPath.INTENT_PURPOSES, value_type=frozenset),
    _spec(ApplicantFactPath.INTENT_STAY_DAYS, value_type=int),
    _spec(ApplicantFactPath.INTENT_DESIRED_ENTRY_DATE, value_type=date),
    _spec(ApplicantFactPath.INTENT_ENTRY_PATTERN, value_type=str),
    _spec(ApplicantFactPath.INTENT_REQUESTED_PRODUCT_CODE, value_type=str),
    _spec(ApplicantFactPath.WORK_EMPLOYER_COUNTRY_CODE, value_type=str),
    _spec(ApplicantFactPath.WORK_EMPLOYER_IS_INDONESIAN_ENTITY, value_type=bool),
    _spec(ApplicantFactPath.WORK_SERVES_INDONESIAN_CLIENTS, value_type=bool),
    _spec(ApplicantFactPath.WORK_INDONESIA_SOURCE_COMPENSATION, value_type=bool),
    _spec(ApplicantFactPath.WORK_INDONESIAN_WORK_SPONSOR_CONFIRMED, value_type=bool),
    _spec(ApplicantFactPath.INVESTMENT_PT_PMA_COMMITTED, value_type=bool),
    _spec(ApplicantFactPath.INVESTMENT_INVESTMENT_CAPITAL_IDR, value_type=int),
    _spec(ApplicantFactPath.INVESTMENT_PAID_UP_CAPITAL_IDR, value_type=int),
    _spec(ApplicantFactPath.INVESTMENT_PROPOSED_ROLE, value_type=str),
    _spec(ApplicantFactPath.FAMILY_RELATION_TO_SPONSOR, value_type=str),
    _spec(ApplicantFactPath.FAMILY_SPONSOR_NATIONALITIES, value_type=frozenset),
    _spec(ApplicantFactPath.FAMILY_SPONSOR_STATUS_CODE, value_type=str),
    _spec(ApplicantFactPath.FAMILY_MARRIAGE_REGISTERED, value_type=bool),
    _spec(ApplicantFactPath.FAMILY_SPONSOR_CONFIRMED, value_type=bool),
    _spec(ApplicantFactPath.STUDY_LEVEL, value_type=str),
    _spec(ApplicantFactPath.STUDY_ADMISSION_CONFIRMED, value_type=bool),
    _spec(ApplicantFactPath.STUDY_SPONSOR_CONFIRMED, value_type=bool),
    _spec(ApplicantFactPath.PROCESS_APPLICATION_CHANNEL, value_type=str),
    _spec(ApplicantFactPath.PROCESS_WANTS_ONSHORE_CONVERSION, value_type=bool),
    _spec(
        ApplicantFactPath.COMMERCIAL_SERVICE_FEE_BUDGET_IDR,
        value_type=int,
        commercial_only=True,
    ),
    _spec(ApplicantFactPath.COMMERCIAL_WANTS_QUOTE, value_type=bool, commercial_only=True),
    _spec(
        DerivedFactPath.AGE_YEARS,
        value_type=int,
        derived=True,
        dependencies=frozenset({ApplicantFactPath.PERSON_BIRTH_DATE.value}),
    ),
    _spec(
        DerivedFactPath.IS_MINOR,
        value_type=bool,
        derived=True,
        dependencies=frozenset({ApplicantFactPath.PERSON_BIRTH_DATE.value}),
    ),
    _spec(
        DerivedFactPath.HAS_INDONESIAN_CITIZENSHIP,
        value_type=bool,
        derived=True,
        dependencies=frozenset({ApplicantFactPath.PERSON_NATIONALITIES.value}),
    ),
)

_INDONESIA_COUNTRY_CODE = "ID"
_MINOR_AGE_THRESHOLD = 18


class FactRegistry:
    """The closed catalog of fact paths + the applicant-facts -> snapshot step."""

    def __init__(self, specs: Iterable[FactSpec] | None = None) -> None:
        chosen = tuple(specs) if specs is not None else DEFAULT_FACT_SPECS
        self._specs: dict[str, FactSpec] = {s.path: s for s in chosen}

    def spec(self, path: str) -> FactSpec:
        """Return the :class:`FactSpec` for ``path``.

        Raises :class:`FactValidationError` if ``path`` is not registered in
        *this* registry instance (a registry may be constructed with a
        deliberately reduced set of specs, e.g. in tests).
        """

        try:
            return self._specs[path]
        except KeyError as exc:
            raise FactValidationError(f"unregistered fact path: {path!r}") from exc

    def known_paths(self) -> frozenset[str]:
        """All fact paths registered in this instance."""

        return frozenset(self._specs)

    def derive(
        self,
        facts: ApplicantFacts,
        *,
        effective_at: datetime,
    ) -> FactSnapshot:
        """Turn a validated ``ApplicantFacts`` wire object into a
        :class:`FactSnapshot` ready for AST evaluation.

        Canonicalizes dates to ISO-8601 strings, set-valued facts to
        ``frozenset[str]``, and computes the 3 derived facts.
        """

        raw = facts.facts.model_dump(by_alias=True, mode="json")
        values: dict[str, KnownFact | UnknownFact] = {
            path: self._wire_to_runtime(path, wire_fact) for path, wire_fact in raw.items()
        }

        values[DerivedFactPath.AGE_YEARS.value] = self._derive_age_years(values, effective_at)
        values[DerivedFactPath.IS_MINOR.value] = self._derive_is_minor(values, effective_at)
        values[DerivedFactPath.HAS_INDONESIAN_CITIZENSHIP.value] = (
            self._derive_has_indonesian_citizenship(values)
        )

        return FactSnapshot(values=MappingProxyType(values))

    def _wire_to_runtime(
        self, path: str, wire_fact: Mapping[str, object]
    ) -> KnownFact | UnknownFact:
        if wire_fact["status"] == "UNKNOWN":
            return UnknownFact(reason=UnknownReason(wire_fact["reason"]))

        value = wire_fact["value"]
        spec = self._specs.get(path)
        if spec is not None and spec.value_type is frozenset:
            value = frozenset(value)  # type: ignore[arg-type]
        return KnownFact(value=value)

    @staticmethod
    def _derive_age_years(
        values: Mapping[str, KnownFact | UnknownFact],
        effective_at: datetime,
    ) -> KnownFact | UnknownFact:
        birth = values[ApplicantFactPath.PERSON_BIRTH_DATE.value]
        if isinstance(birth, UnknownFact):
            return UnknownFact(reason=birth.reason)

        birth_date = date.fromisoformat(str(birth.value))
        reference_date = (
            effective_at.astimezone(timezone.utc).date()
            if effective_at.tzinfo is not None
            else effective_at.date()
        )
        years = (
            reference_date.year
            - birth_date.year
            - ((reference_date.month, reference_date.day) < (birth_date.month, birth_date.day))
        )
        return KnownFact(value=years)

    @classmethod
    def _derive_is_minor(
        cls,
        values: Mapping[str, KnownFact | UnknownFact],
        effective_at: datetime,
    ) -> KnownFact | UnknownFact:
        age = cls._derive_age_years(values, effective_at)
        if isinstance(age, UnknownFact):
            return UnknownFact(reason=age.reason)
        return KnownFact(value=bool(age.value < _MINOR_AGE_THRESHOLD))

    @staticmethod
    def _derive_has_indonesian_citizenship(
        values: Mapping[str, KnownFact | UnknownFact],
    ) -> KnownFact | UnknownFact:
        nationalities = values[ApplicantFactPath.PERSON_NATIONALITIES.value]
        if isinstance(nationalities, UnknownFact):
            return UnknownFact(reason=nationalities.reason)
        return KnownFact(value=_INDONESIA_COUNTRY_CODE in nationalities.value)


def canonical_fact_payload(facts: ApplicantFacts) -> dict[str, JsonValue]:
    """A deterministic, sorted-key, ``json.dumps``-serializable view of
    ``facts.facts``.

    Used upstream (PR2+) as the input to the facts HMAC fingerprint. Pure
    function: same input always yields the same, key-sorted output. Returns
    a **plain** ``dict`` — not a ``types.MappingProxyType`` — because the
    latter is not JSON-serializable (``json.dumps(MappingProxyType(...))``
    raises ``TypeError``), which would defeat the "fingerprint this over the
    wire" purpose the function exists for.
    """

    raw = facts.facts.model_dump(by_alias=True, mode="json")
    return dict(sorted(raw.items()))


def __getattr__(name: str) -> object:
    """PEP 562 lazy module attribute.

    ``ApplicantFacts`` is intentionally never imported at module-load time
    (see the module docstring: it would reintroduce the
    ``fact_registry -> models -> ast -> fact_registry`` import cycle). That
    also means it is invisible to ``typing.get_type_hints()``, which
    resolves the ``"ApplicantFacts"`` forward-reference string used in
    :meth:`FactRegistry.derive`/:func:`canonical_fact_payload` by evaluating
    it against this module's *real* ``__globals__`` dict — a bare
    ``__getattr__`` hook is NOT consulted by that ``eval()`` (it only fires
    for ``module.attr``-style access), so the forward ref stays unresolved
    until something actually triggers this hook at least once.

    Accessing ``backend.services.visa_engine.fact_registry.ApplicantFacts``
    (directly, or via ``getattr(fact_registry, "ApplicantFacts")``) performs
    the deferred import *and* caches the real class into this module's
    namespace, so any ``get_type_hints()`` call made *after* that first
    access resolves correctly.
    """

    if name == "ApplicantFacts":
        from backend.services.visa_engine.models import ApplicantFacts as _ApplicantFacts

        globals()[name] = _ApplicantFacts
        return _ApplicantFacts
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
