"""Typed fact catalog: fact path -> value kind / allowed values / PII class.

Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` §1 (module layout, ``fact_registry.py``) and §2
(``ApplicantFacts.facts`` — the 35 collected paths + the 3 ``derived.*``
paths this catalog also carries).

Why this exists alongside ``enums.FactPath``: ``FactPath`` is the *closed
vocabulary* (which strings are legal fact paths at all — enforced by the
type system wherever a ``Condition.fact`` or ``Rule.required_facts`` entry
is parsed). This module is the *catalog of metadata about each of those
paths* — what shape its value takes, whether it is PII and at what
sensitivity tier, and whether it is a commercial (never legally
dispositive) fact. ``compiler.py`` reads this catalog to enforce two of the
spec's compiler-only invariants: "no ``commercial.*`` fact in a legal-stage
rule" and "fact-path-specific literal types" (an ``eq`` against a boolean
fact must carry a boolean literal, etc.).

PR1 scope note: the spec's own ``fact_registry.py`` snippet additionally
declares ``FactRegistry.derive(facts: ApplicantFacts, *, effective_at) ->
FactSnapshot`` and a ``FactSnapshot``/``KnownFact``/``UnknownFact`` runtime
shape. That is the *evaluator's* fact-resolution step (turning a raw
``ApplicantFacts`` payload into the typed snapshot ``ast.evaluate_condition``
would consume) — deliberately deferred to PR3 alongside the evaluator itself
(the task brief scopes PR1's ``fact_registry.py`` to "typed fact catalog ...
validation that a RulePack's required_facts subset-of registry", not fact
derivation). ``ApplicantFacts`` itself is not modelled in PR1 for the same
reason — see ``models.py``'s module docstring.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from backend.services.visa_engine.enums import (
    COMMERCIAL_FACT_PATHS,
    FactPath,
    FactValueKind,
    PiiClass,
)
from backend.services.visa_engine.errors import FactValidationError


@dataclass(frozen=True, slots=True)
class FactSpec:
    """Metadata for exactly one fact path (spec §1 ``fact_registry.py``, extended).

    Extends the spec's ``(path, value_type, derived, dependencies,
    commercial_only)`` dataclass with ``kind`` (a coarse, closed shape used
    for structural literal-type checking — see module docstring) and
    ``pii_class`` (the task's explicit "PII class" requirement, not itself
    named in the spec text; see ``enums.PiiClass``'s docstring for the
    resolution). ``value_type`` stays as a free-text human label (e.g.
    ``"date"``, ``"money_idr"``, ``"country_code"``) purely for
    documentation/tooling — ``kind`` is what compiler.py actually branches on.
    """

    path: FactPath
    kind: FactValueKind
    value_type: str
    derived: bool
    dependencies: frozenset[FactPath] = field(default_factory=frozenset)
    commercial_only: bool = False
    pii_class: PiiClass = PiiClass.NONE
    allowed_values: frozenset[str] | None = None


def _spec(
    path: FactPath,
    kind: FactValueKind,
    value_type: str,
    *,
    derived: bool = False,
    dependencies: frozenset[FactPath] = frozenset(),
    pii_class: PiiClass = PiiClass.PERSONAL,
    allowed_values: frozenset[str] | None = None,
) -> FactSpec:
    return FactSpec(
        path=path,
        kind=kind,
        value_type=value_type,
        derived=derived,
        dependencies=dependencies,
        commercial_only=path in COMMERCIAL_FACT_PATHS,
        pii_class=pii_class,
        allowed_values=allowed_values,
    )


#: Default catalog seeded 1:1 from spec §2 ``ApplicantFacts.facts.properties``
#: (35 entries) plus the 3 ``derived.*`` paths from spec §2 ``FactPath``.
#: PII classification rationale: immigration status/violation history and
#: investment capital amounts are SENSITIVE (UU PDP heightened-treatment
#: analogues per CLAUDE.md §14 — closest to "criminal"/"financial" data in
#: this domain); ``process.*``/``commercial.*``/``derived.*`` are NONE
#: (operational metadata or computed, not raw personal data); everything
#: else defaults to PERSONAL.
_DEFAULT_SPECS: tuple[FactSpec, ...] = (
    _spec(FactPath.PERSON_BIRTH_DATE, FactValueKind.STRING, "date"),
    _spec(FactPath.PERSON_NATIONALITIES, FactValueKind.STRING_SET, "country_code_set"),
    _spec(
        FactPath.PERSON_MARITAL_STATUS,
        FactValueKind.STRING,
        "marital_status_enum",
        allowed_values=frozenset({"SINGLE", "MARRIED", "DIVORCED", "WIDOWED", "OTHER"}),
    ),
    _spec(
        FactPath.IMMIGRATION_CURRENTLY_IN_INDONESIA,
        FactValueKind.BOOLEAN,
        "boolean",
        pii_class=PiiClass.SENSITIVE,
    ),
    _spec(
        FactPath.IMMIGRATION_CURRENT_STATUS_CODE,
        FactValueKind.STRING,
        "product_code",
        pii_class=PiiClass.SENSITIVE,
    ),
    _spec(
        FactPath.IMMIGRATION_CURRENT_STATUS_EXPIRY,
        FactValueKind.STRING,
        "date",
        pii_class=PiiClass.SENSITIVE,
    ),
    _spec(
        FactPath.IMMIGRATION_LAST_ENTRY_DATE,
        FactValueKind.STRING,
        "date",
        pii_class=PiiClass.SENSITIVE,
    ),
    _spec(
        FactPath.IMMIGRATION_OVERSTAY_DAYS,
        FactValueKind.INTEGER,
        "non_negative_integer",
        pii_class=PiiClass.SENSITIVE,
    ),
    _spec(
        FactPath.IMMIGRATION_VIOLATION_HISTORY,
        FactValueKind.STRING_SET,
        "violation_type_set",
        pii_class=PiiClass.SENSITIVE,
        allowed_values=frozenset(
            {"OVERSTAY", "DEPORTATION", "BLACKLIST", "IMMIGRATION_INVESTIGATION", "OTHER"}
        ),
    ),
    _spec(
        FactPath.INTENT_PURPOSES,
        FactValueKind.STRING_SET,
        "visa_purpose_set",
        allowed_values=frozenset(
            {
                "TOURISM",
                "BUSINESS_MEETINGS",
                "INVESTMENT",
                "EMPLOYMENT",
                "REMOTE_WORK",
                "FAMILY",
                "STUDY",
                "RETIREMENT",
                "SECOND_HOME",
                "TRANSIT",
                "MEDICAL",
                "OTHER",
            }
        ),
    ),
    _spec(FactPath.INTENT_STAY_DAYS, FactValueKind.INTEGER, "non_negative_integer"),
    _spec(FactPath.INTENT_DESIRED_ENTRY_DATE, FactValueKind.STRING, "date"),
    _spec(
        FactPath.INTENT_ENTRY_PATTERN,
        FactValueKind.STRING,
        "entry_pattern_enum",
        allowed_values=frozenset({"SINGLE", "MULTIPLE"}),
    ),
    _spec(FactPath.INTENT_REQUESTED_PRODUCT_CODE, FactValueKind.STRING, "product_code"),
    _spec(FactPath.WORK_EMPLOYER_COUNTRY_CODE, FactValueKind.STRING, "country_code"),
    _spec(FactPath.WORK_EMPLOYER_IS_INDONESIAN_ENTITY, FactValueKind.BOOLEAN, "boolean"),
    _spec(FactPath.WORK_SERVES_INDONESIAN_CLIENTS, FactValueKind.BOOLEAN, "boolean"),
    _spec(FactPath.WORK_INDONESIA_SOURCE_COMPENSATION, FactValueKind.BOOLEAN, "boolean"),
    _spec(FactPath.WORK_INDONESIAN_WORK_SPONSOR_CONFIRMED, FactValueKind.BOOLEAN, "boolean"),
    _spec(FactPath.INVESTMENT_PT_PMA_COMMITTED, FactValueKind.BOOLEAN, "boolean"),
    _spec(
        FactPath.INVESTMENT_INVESTMENT_CAPITAL_IDR,
        FactValueKind.INTEGER,
        "money_idr",
        pii_class=PiiClass.SENSITIVE,
    ),
    _spec(
        FactPath.INVESTMENT_PAID_UP_CAPITAL_IDR,
        FactValueKind.INTEGER,
        "money_idr",
        pii_class=PiiClass.SENSITIVE,
    ),
    _spec(
        FactPath.INVESTMENT_PROPOSED_ROLE,
        FactValueKind.STRING,
        "proposed_role_enum",
        allowed_values=frozenset(
            {
                "SHAREHOLDER_DIRECTOR",
                "SHAREHOLDER_COMMISSIONER",
                "EMPLOYEE",
                "NO_OPERATIONAL_ROLE",
                "OTHER",
            }
        ),
    ),
    _spec(
        FactPath.FAMILY_RELATION_TO_SPONSOR,
        FactValueKind.STRING,
        "relation_enum",
        allowed_values=frozenset({"SPOUSE", "CHILD", "PARENT", "DEPENDENT", "OTHER"}),
    ),
    _spec(FactPath.FAMILY_SPONSOR_NATIONALITIES, FactValueKind.STRING_SET, "country_code_set"),
    _spec(FactPath.FAMILY_SPONSOR_STATUS_CODE, FactValueKind.STRING, "product_code"),
    _spec(FactPath.FAMILY_MARRIAGE_REGISTERED, FactValueKind.BOOLEAN, "boolean"),
    _spec(FactPath.FAMILY_SPONSOR_CONFIRMED, FactValueKind.BOOLEAN, "boolean"),
    _spec(
        FactPath.STUDY_LEVEL,
        FactValueKind.STRING,
        "study_level_enum",
        allowed_values=frozenset(
            {
                "PRIMARY",
                "SECONDARY",
                "VOCATIONAL",
                "UNDERGRADUATE",
                "POSTGRADUATE",
                "RESEARCH",
                "OTHER",
            }
        ),
    ),
    _spec(FactPath.STUDY_ADMISSION_CONFIRMED, FactValueKind.BOOLEAN, "boolean"),
    _spec(FactPath.STUDY_SPONSOR_CONFIRMED, FactValueKind.BOOLEAN, "boolean"),
    _spec(
        FactPath.PROCESS_APPLICATION_CHANNEL,
        FactValueKind.STRING,
        "application_channel_enum",
        pii_class=PiiClass.NONE,
        allowed_values=frozenset({"OFFSHORE", "ONSHORE_CONVERSION", "STATUS_BRIDGING"}),
    ),
    _spec(
        FactPath.PROCESS_WANTS_ONSHORE_CONVERSION,
        FactValueKind.BOOLEAN,
        "boolean",
        pii_class=PiiClass.NONE,
    ),
    _spec(
        FactPath.COMMERCIAL_SERVICE_FEE_BUDGET_IDR,
        FactValueKind.INTEGER,
        "money_idr",
        pii_class=PiiClass.NONE,
    ),
    _spec(
        FactPath.COMMERCIAL_WANTS_QUOTE,
        FactValueKind.BOOLEAN,
        "boolean",
        pii_class=PiiClass.NONE,
    ),
    _spec(
        FactPath.DERIVED_AGE_YEARS,
        FactValueKind.INTEGER,
        "non_negative_integer",
        derived=True,
        dependencies=frozenset({FactPath.PERSON_BIRTH_DATE}),
        pii_class=PiiClass.NONE,
    ),
    _spec(
        FactPath.DERIVED_IS_MINOR,
        FactValueKind.BOOLEAN,
        "boolean",
        derived=True,
        dependencies=frozenset({FactPath.PERSON_BIRTH_DATE}),
        pii_class=PiiClass.NONE,
    ),
    _spec(
        FactPath.DERIVED_HAS_INDONESIAN_CITIZENSHIP,
        FactValueKind.BOOLEAN,
        "boolean",
        derived=True,
        dependencies=frozenset({FactPath.PERSON_NATIONALITIES}),
        pii_class=PiiClass.NONE,
    ),
)


class FactRegistry:
    """A typed catalog of every fact path the engine may reference.

    Frozen at construction: the default registry (``FactRegistry()``) is
    seeded from ``_DEFAULT_SPECS`` above, one entry per ``enums.FactPath``
    member (verified by ``test_fact_registry.py``). A caller may pass a
    narrower/different mapping (e.g. a future engine version's registry) —
    ``compiler.py`` always takes a ``FactRegistry`` as an explicit parameter
    rather than importing a module-level singleton, so PR2+ can swap it.
    """

    def __init__(self, specs: Iterable[FactSpec] | None = None) -> None:
        source = specs if specs is not None else _DEFAULT_SPECS
        by_path: dict[FactPath, FactSpec] = {}
        for spec in source:
            if spec.path in by_path:
                raise FactValidationError(f"duplicate fact spec for path {spec.path!r}")
            by_path[spec.path] = spec
        self._specs: Mapping[FactPath, FactSpec] = by_path

    def spec(self, path: FactPath | str) -> FactSpec:
        """Return the ``FactSpec`` for ``path``, or raise ``FactValidationError``."""
        try:
            key = path if isinstance(path, FactPath) else FactPath(path)
            return self._specs[key]
        except (KeyError, ValueError) as exc:
            raise FactValidationError(f"unknown fact path: {path!r}") from exc

    def all_paths(self) -> frozenset[FactPath]:
        return frozenset(self._specs)

    def is_commercial(self, path: FactPath | str) -> bool:
        return self.spec(path).commercial_only

    def missing_paths(self, candidate_paths: Iterable[FactPath | str]) -> frozenset[str]:
        """Return the subset of ``candidate_paths`` NOT present in this registry.

        Empty result means every path is a subset of the registry — the
        exact compiler invariant the PR1 brief names: "validation that a
        RulePack's required_facts subset-of registry".
        """
        known = self.all_paths()
        missing: set[str] = set()
        for raw in candidate_paths:
            try:
                path = FactPath(raw) if not isinstance(raw, FactPath) else raw
            except ValueError:
                missing.add(str(raw))
                continue
            if path not in known:
                missing.add(str(raw))
        return frozenset(missing)


#: Module-level default instance for convenience callers (compiler.py's own
#: default parameter, tests). Not a hidden global authority — every function
#: that consumes a registry takes one as an explicit argument.
DEFAULT_FACT_REGISTRY = FactRegistry()
