"""FactRegistry: the closed-catalog lookup + applicant-facts -> evaluation-snapshot step.

Two representations of a "fact" exist in this package, deliberately kept
distinct:

* The **wire format** (``backend.services.visa_engine.models.ApplicantFacts``)
  mirrors the JSON Schema contract 1:1 — each fact is either
  ``{"status": "UNKNOWN", "reason": ...}`` or a status/value pair typed per
  path (``KnownBoolean``, ``KnownDate``, ...).
* The **runtime snapshot** (:class:`~backend.services.visa_engine._types.KnownFact`/
  :class:`~backend.services.visa_engine._types.UnknownFact` +
  :class:`~backend.services.visa_engine._types.FactSnapshot`) is what the AST
  evaluator (``ast.py``) actually reads: a flat
  ``Mapping[str, KnownFact | UnknownFact]`` covering both the 35
  applicant-supplied paths *and* the 3 derived paths (``derived.age_years``,
  ``derived.is_minor``, ``derived.has_indonesian_citizenship``), with dates
  canonicalized to ISO strings (so ``lt``/``lte``/``gt``/``gte`` work as
  plain string comparison) and set-valued facts canonicalized to
  ``frozenset[str]``.

The closed fact-path vocabulary (``UnknownReason``, ``ApplicantFactPath``,
``DerivedFactPath``, ``FactPath``) and the two runtime fact wrappers
(``KnownFact``, ``UnknownFact``, ``FactSnapshot``) live in the
dependency-free leaf module ``_types.py`` — ``models.py`` and ``ast.py``
import them from there directly, so neither needs to import this module at
runtime (this breaks the ``models -> fact_registry -> models`` /
``models -> ast -> fact_registry -> models`` import cycles CodeQL's
``py/unsafe-cyclic-import`` flagged). This module re-exports every one of
those names unchanged for backward compatibility —
``from backend.services.visa_engine.fact_registry import ApplicantFactPath``
keeps working exactly as before.

:class:`FactRegistry` is the single source of truth for "what fact paths
exist, what shape are they, are they derived, and can a RANKING-stage rule
reference them" (``commercial_only``) — the compiler (``compiler.py``)
depends on this to reject rule packs that reference unregistered paths or
smuggle a legal fact into a commercial ranking rule.

Pure module: no I/O. The only reference to
``backend.services.visa_engine.models.ApplicantFacts`` is deferred
(``TYPE_CHECKING``-only) to avoid a runtime import cycle — this is now a
single non-cyclic edge (``fact_registry -> models``, nothing points back)
since ``models.py`` no longer imports anything from this module.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.services.visa_engine._types import (
    ApplicantFactPath,
    DerivedFactPath,
    FactSnapshot,
    KnownFact,
    UnknownFact,
    UnknownReason,
)
from backend.services.visa_engine._types import FactPath as FactPath  # explicit re-export (F401)
from backend.services.visa_engine.errors import FactValidationError

if TYPE_CHECKING:  # pragma: no cover - import-cycle avoidance only
    from backend.services.visa_engine.models import ApplicantFacts

logger = logging.getLogger(__name__)

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
"""A JSON-safe value: what :func:`canonical_fact_payload` returns members of."""

# Re-exported unchanged from ``_types.py`` (see module docstring) so every
# existing ``from backend.services.visa_engine.fact_registry import X``
# keeps resolving: UnknownReason, ApplicantFactPath, DerivedFactPath,
# FactPath, KnownFact, UnknownFact, FactSnapshot.


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
    (see the module docstring: ``models.py`` imports ``ApplicantFacts`` from
    ``pydantic``-model definitions living in the very module this
    ``TYPE_CHECKING``-only reference points at — importing it eagerly here
    would force ``models.py`` to be fully initialized before this module
    finishes loading, which is fragile even though it's no longer a true
    cycle post-``_types.py`` extraction). That also means it is invisible to
    ``typing.get_type_hints()``, which
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
