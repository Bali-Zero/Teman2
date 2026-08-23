"""Typed fact catalog: fact path -> value kind / allowed values / PII class.

Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` §1 (module layout, ``fact_registry.py``) and §2
(``ApplicantFacts.facts`` — the 44 collected paths + the 4 ``derived.*``
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

PR3 addition: ``FactRegistry.derive(facts: ApplicantFacts, *, effective_at)
-> FactSnapshot`` — the evaluator's fact-resolution step, turning a raw
``ApplicantFacts`` wire payload into the typed snapshot
``ast.evaluate_condition`` consumes, plus ``canonical_fact_payload()`` (a
deterministic, sorted-key view of ``ApplicantFacts.facts`` for future
fingerprinting). ``FactSnapshot``/``KnownFact``/``UnknownFact`` themselves
live in ``ast.py``, not here — see that module's docstring for the
import-cycle rationale (``fact_registry.py`` needing ``models.ApplicantFacts``
directly, post the PR3 ``models.py`` FactPath-import redirect, would recreate
a cycle if ``FactSnapshot`` also lived here and ``ast.py`` needed it back).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from types import MappingProxyType
from typing import Literal, TypeAlias

from backend.services.visa_engine.ast import FactSnapshot, KnownFact, UnknownFact
from backend.services.visa_engine.enums import (
    COMMERCIAL_FACT_PATHS,
    FactPath,
    FactValueKind,
    PiiClass,
    UnknownReason,
)
from backend.services.visa_engine.errors import FactValidationError
from backend.services.visa_engine.models import ApplicantFacts

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
"""A JSON-safe value — what :func:`canonical_fact_payload` returns members of."""

_INDONESIA_COUNTRY_CODE = "ID"
_MINOR_AGE_THRESHOLD = 18

#: ``derived.has_active_stay_permit`` grounding, side 1 of 2 (2026-08-23,
#: extended 2026-08-24 with a 9th, synthesized value — see below):
#: the exact 8 option keys ``apps/mouth``'s ``current_status_code`` question
#: offers today (the only values the live frontend can ever send as KNOWN —
#: an "other" answer is filtered to UNKNOWN client-side, see that question's
#: ``fact-mapper.ts`` mapper). None of them is an ITAS/ITAP-class residence
#: permit: A1/C1/C2/C6 are catalog ``SHORT_STAY`` visa-index product codes
#: (confirmed 2026-08-23 against the active production pack,
#: ``contracts/packs/rulepack-prod-007.source.json``), and ``ITK_*`` names
#: Izin Tinggal KUNJUNGAN (Visit Stay Permit) — structurally distinct in
#: Indonesian immigration law from Izin Tinggal Terbatas/Tetap (ITAS/ITAP,
#: "kunjungan" = visit, "terbatas"/"tetap" = limited/permanent stay), never
#: the residence-class permit this fact asks about. Grounded, not guessed;
#: kept a separate frozenset (not derived from the enum registry) because it
#: describes an EXTERNAL taxonomy fact about these specific strings, not a
#: FactPath-level closed vocabulary.
#:
#: ``NO_STAY_PERMIT`` (added 2026-08-24, P0 offshore-reachability fix,
#: team-lead funnel-cost review) is NOT one of the 8 real option keys above
#: and is never offered as a UI choice — it is a synthesized sentinel
#: ``apps/mouth``'s ``fact-mapper.ts`` emits directly when an OFFSHORE
#: applicant answers the (already-existing) ``holds_stay_permit`` question
#: "no", instead of asking the granular ``current_status_code`` question a
#: second time for a fact its own answer already fully determines. This is
#: not a guess: it is the literal, honest translation of what the applicant
#: told us, distinct from every real document-derived code, and it belongs
#: in this frozenset (not `_STAY_PERMIT_STATUS_CODE_SHAPE`) for the exact
#: same reason a real visit-class code does — it is definitively NOT a
#: residence permit, so no need to consult expiry either. See
#: ``flow.ts::computeNextNode``'s offshore branch for the frontend routing
#: that produces it, and the funnel-cost measurement in PR #4727 for why
#: this exists instead of unconditionally asking the full onshore chain.
_VISIT_CLASS_STATUS_CODES: frozenset[str] = frozenset(
    {
        "A1",
        "C1",
        "C2",
        "C6",
        "ITK_FROM_BVK",
        "ITK_FROM_VISIT_C",
        "ITK_FROM_VISIT_D",
        "ITK_PERALIHAN",
        "NO_STAY_PERMIT",
    }
)

#: ``derived.has_active_stay_permit`` grounding, side 2 of 2: the SHAPE of a
#: LIMITED_STAY/PERMANENT_STAY (ITAS/ITAP-class) product code in the current
#: catalog. Verified 2026-08-23 against every product in the active pack
#: (``rulepack-prod-007.source.json``): all 12 ``LIMITED_STAY`` codes
#: (E23/E23U/E23V, E28A/B/C/D/F, E30/A/B/E/F, E31A-J, E33/A/B/C/E/F/G) match
#: this shape and no ``SHORT_STAY``/``MULTIPLE_ENTRY``/``OTHER``-category
#: code does. This is a catalog-derived HEURISTIC on the string's shape, not
#: a Pasal-level regulatory citation — the current interview can never send
#: a value that matches it (no E-series code is an offered
#: ``current_status_code`` option), so this pattern is dormant until a
#: richer interview or a direct API caller supplies one. If a future
#: catalog ever breaks the "E-prefix means LIMITED_STAY/PERMANENT_STAY"
#: convention, this pattern must be revisited — it is not a closed
#: enumeration and cannot detect its own staleness.
_STAY_PERMIT_STATUS_CODE_SHAPE = re.compile(r"^E\d+[A-Z]?$")


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
    #: Hotfix (2026-07-18, Gap A/D): a structural shape ``compiler.py`` can
    #: check a condition literal against, independent of ``kind``/
    #: ``allowed_values``. ``kind`` alone cannot distinguish a free-form
    #: STRING fact from a date-shaped one (``person.birth_date``) or a
    #: country-code-shaped one (``work.employer_country_code``) — both are
    #: ``FactValueKind.STRING`` (or, for a set of country codes,
    #: ``STRING_SET``), so a bare kind check let ``"20260101"`` or ``"USA"``
    #: (3 letters) compile clean. ``None`` means "no extra shape check"
    #: (e.g. free-form/enum-ish strings already covered by
    #: ``allowed_values``, or facts of other kinds).
    value_format: Literal["date", "country_code"] | None = None

    def __post_init__(self) -> None:
        """PR1b item 5 (Codex finding on hotfix #2739): ``value_format`` was
        purely a static hint with nothing enforcing it agrees with ``kind`` —
        a future registry entry with e.g. ``kind=INTEGER,
        value_format="date"`` would silently disable
        ``compiler.py``'s date-shape check (``_check_date_literal_shape`` is
        only reached for a ``str`` literal, per
        ``_check_single_literal_against_kind``'s ``isinstance(value, str)``
        guard) instead of failing loud at the one place — ``FactSpec``
        construction — where the mismatch is actually introduced.

        ``"date"`` requires ``kind=STRING`` (a date is always a single
        string value, never a set). ``"country_code"`` requires
        ``kind=STRING`` (a lone country code, e.g.
        ``work.employer_country_code``) or ``kind=STRING_SET`` (a set of
        them, e.g. ``person.nationalities``) — both shapes are legitimate in
        the default catalog. ``None`` is always fine, regardless of
        ``kind``: it means "no extra shape check", never a claim about what
        the kind *should* be.
        """
        if self.value_format == "date" and self.kind is not FactValueKind.STRING:
            raise ValueError(
                f"fact {self.path!r}: value_format='date' requires kind=STRING, "
                f"got kind={self.kind.value}"
            )
        if self.value_format == "country_code" and self.kind not in (
            FactValueKind.STRING,
            FactValueKind.STRING_SET,
        ):
            raise ValueError(
                f"fact {self.path!r}: value_format='country_code' requires "
                f"kind=STRING or kind=STRING_SET, got kind={self.kind.value}"
            )


def _spec(
    path: FactPath,
    kind: FactValueKind,
    value_type: str,
    *,
    derived: bool = False,
    dependencies: frozenset[FactPath] = frozenset(),
    pii_class: PiiClass = PiiClass.PERSONAL,
    allowed_values: frozenset[str] | None = None,
    value_format: Literal["date", "country_code"] | None = None,
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
        value_format=value_format,
    )


#: Default catalog seeded 1:1 from spec §2 ``ApplicantFacts.facts.properties``
#: (35 entries) plus the 3 ``derived.*`` paths from spec §2 ``FactPath``,
#: plus the 5 ``secondhome.*`` paths added for the E33 Second Home vertical
#: (2026-07-23, bank-route owner scope), plus ``sponsor.type`` added so the
#: interview can ask who the sponsor is (2026-08-10), plus the two
#: ``family.stepchild_*`` evidence paths, ``family.sponsor_permit_basis``
#: and ``derived.has_active_stay_permit`` (2026-08-23, three owner rulings)
#: — 48 entries total.
#: PII classification rationale: immigration status/violation history and
#: investment capital amounts are SENSITIVE (UU PDP heightened-treatment
#: analogues per CLAUDE.md §14 — closest to "criminal"/"financial" data in
#: this domain); ``process.*``/``commercial.*``/``derived.*`` are NONE
#: (operational metadata or computed, not raw personal data); everything
#: else defaults to PERSONAL.
_DEFAULT_SPECS: tuple[FactSpec, ...] = (
    _spec(FactPath.PERSON_BIRTH_DATE, FactValueKind.STRING, "date", value_format="date"),
    _spec(
        FactPath.PERSON_NATIONALITIES,
        FactValueKind.STRING_SET,
        "country_code_set",
        value_format="country_code",
    ),
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
        value_format="date",
    ),
    _spec(
        FactPath.IMMIGRATION_LAST_ENTRY_DATE,
        FactValueKind.STRING,
        "date",
        pii_class=PiiClass.SENSITIVE,
        value_format="date",
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
    _spec(
        FactPath.INTENT_DESIRED_ENTRY_DATE, FactValueKind.STRING, "date", value_format="date"
    ),
    _spec(
        FactPath.INTENT_ENTRY_PATTERN,
        FactValueKind.STRING,
        "entry_pattern_enum",
        allowed_values=frozenset({"SINGLE", "MULTIPLE"}),
    ),
    _spec(FactPath.INTENT_REQUESTED_PRODUCT_CODE, FactValueKind.STRING, "product_code"),
    _spec(
        FactPath.WORK_EMPLOYER_COUNTRY_CODE,
        FactValueKind.STRING,
        "country_code",
        value_format="country_code",
    ),
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
        # STEPCHILD added 2026-08-23 (RelationType.STEPCHILD — see that
        # enum member's docstring for the owner ruling + regulatory ground).
        allowed_values=frozenset(
            {"SPOUSE", "CHILD", "PARENT", "SIBLING", "DEPENDENT", "STEPCHILD", "OTHER"}
        ),
    ),
    _spec(
        FactPath.FAMILY_SPONSOR_NATIONALITIES,
        FactValueKind.STRING_SET,
        "country_code_set",
        value_format="country_code",
    ),
    _spec(FactPath.FAMILY_SPONSOR_STATUS_CODE, FactValueKind.STRING, "product_code"),
    _spec(FactPath.FAMILY_MARRIAGE_REGISTERED, FactValueKind.BOOLEAN, "boolean"),
    # sponsor.type — allowed_values mirror enums.SponsorType exactly. They are
    # spelled out rather than derived so that adding a member to the enum is a
    # deliberate two-line change here as well: a silently-widened fact is how a
    # rule starts accepting a value no product was ever written for.
    _spec(
        FactPath.SPONSOR_TYPE,
        FactValueKind.STRING,
        "sponsor_type_enum",
        allowed_values=frozenset(
            {"NONE", "INDIVIDUAL", "EMPLOYER", "EDUCATION", "INVESTMENT", "GOVERNMENT"}
        ),
    ),
    _spec(FactPath.FAMILY_SPONSOR_CONFIRMED, FactValueKind.BOOLEAN, "boolean"),
    # family.stepchild_* — evidence for RelationType.STEPCHILD (2026-08-23
    # owner ruling: "figliastro = figlio del coniuge, serve akta nikah +
    # akta lahir"). Modeled exactly like the two specs immediately above
    # (FAMILY_MARRIAGE_REGISTERED / FAMILY_SPONSOR_CONFIRMED): a plain
    # BOOLEAN, PERSONAL pii_class (the default — this is family-document
    # confirmation, not the SENSITIVE tier reserved for immigration
    # violation/financial data per CLAUDE.md §14), no allowed_values (a
    # boolean's only legal literals are true/false). Booleans, not a
    # document-upload/URL type, because — same as ``family.sponsor_
    # confirmed`` — the engine only ever needs to know THAT the evidence was
    # confirmed, never to store or re-render the document itself.
    _spec(FactPath.FAMILY_STEPCHILD_MARRIAGE_CERTIFICATE_CONFIRMED, FactValueKind.BOOLEAN, "boolean"),
    _spec(FactPath.FAMILY_STEPCHILD_BIRTH_CERTIFICATE_CONFIRMED, FactValueKind.BOOLEAN, "boolean"),
    # family.sponsor_permit_basis — allowed_values mirror enums.SponsorPermitBasis
    # exactly, same "spelled out rather than derived" rationale as sponsor.type
    # below: widening the enum without a matching two-line change here would
    # silently let a rule accept a value no product was ever written for.
    _spec(
        FactPath.FAMILY_SPONSOR_PERMIT_BASIS,
        FactValueKind.STRING,
        "sponsor_permit_basis_enum",
        allowed_values=frozenset(
            {
                "EXPERT",
                "WORKER",
                "MARITIME_CREW",
                "CLERGY",
                "FOREIGN_INVESTMENT",
                "SCIENTIFIC_RESEARCH",
                "EDUCATION",
                "FAMILY_REUNIFICATION",
                "REPATRIATION",
                "SECOND_HOME",
                "MEDICAL_TREATMENT",
                "WORKING_HOLIDAY",
                "OTHER",
            }
        ),
    ),
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
    # secondhome.* — E33 Second Home vertical (2026-07-23, bank-route scope).
    # USD amounts are SENSITIVE (financial data, same UU PDP rationale as the
    # IDR investment capital facts); the placement/holder booleans are
    # PERSONAL (they describe the applicant's banking arrangement, not an
    # amount). No BSI/sharia or split-deposit variant facts exist by design:
    # both are FORBIDDEN claims until the official letters are answered (see
    # research/secondhome/README.md), so the vocabulary cannot express them.
    _spec(
        FactPath.SECONDHOME_BANK_DEPOSIT_USD,
        FactValueKind.INTEGER,
        "money_usd",
        pii_class=PiiClass.SENSITIVE,
    ),
    _spec(
        FactPath.SECONDHOME_BANK_DEPOSIT_AT_STATE_BANK,
        FactValueKind.BOOLEAN,
        "boolean",
    ),
    _spec(
        FactPath.SECONDHOME_BANK_DEPOSIT_IN_OWN_NAME,
        FactValueKind.BOOLEAN,
        "boolean",
    ),
    _spec(
        FactPath.SECONDHOME_QUALIFYING_PROPERTY_VALUE_USD,
        FactValueKind.INTEGER,
        "money_usd",
        pii_class=PiiClass.SENSITIVE,
    ),
    _spec(
        FactPath.SECONDHOME_PASSIVE_MONTHLY_INCOME_USD,
        FactValueKind.INTEGER,
        "money_usd",
        pii_class=PiiClass.SENSITIVE,
    ),
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
    _spec(
        FactPath.DERIVED_HAS_ACTIVE_STAY_PERMIT,
        FactValueKind.BOOLEAN,
        "boolean",
        derived=True,
        dependencies=frozenset(
            {FactPath.IMMIGRATION_CURRENT_STATUS_CODE, FactPath.IMMIGRATION_CURRENT_STATUS_EXPIRY}
        ),
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
        #: ``MappingProxyType``, not a plain ``dict`` (Codex finding 9): a
        #: ``dict``-typed attribute is only immutable at the type-checker
        #: level — ``registry._specs.clear()`` would silently empty a live
        #: registry at runtime. The proxy makes that call raise instead.
        self._specs: Mapping[FactPath, FactSpec] = MappingProxyType(by_path)

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

    def derive(self, facts: ApplicantFacts, *, effective_at: datetime) -> FactSnapshot:
        """Turn a validated ``ApplicantFacts`` wire object into a
        :class:`~backend.services.visa_engine.ast.FactSnapshot` ready for
        ``ast.evaluate_condition``.

        Canonicalizes dates to ISO-8601 strings (already the wire shape —
        ``KnownDate.value`` is an ``IsoDate`` string), ``STRING_SET``-kind
        facts to ``frozenset[str]``, and computes the 4 ``derived.*`` facts
        (``age_years``, ``is_minor``, ``has_indonesian_citizenship``,
        ``has_active_stay_permit``).
        """

        if effective_at.tzinfo is None:
            raise FactValidationError(
                "effective_at must be timezone-aware (UTC); a naive datetime is "
                "ambiguous and would silently change the derived age by up to a day."
            )

        raw = facts.facts.model_dump(by_alias=True, mode="json")
        values: dict[FactPath, KnownFact | UnknownFact] = {
            FactPath(path): self._wire_to_runtime(path, wire_fact)
            for path, wire_fact in raw.items()
        }

        values[FactPath.DERIVED_AGE_YEARS] = self._derive_age_years(values, effective_at)
        values[FactPath.DERIVED_IS_MINOR] = self._derive_is_minor(values, effective_at)
        values[FactPath.DERIVED_HAS_INDONESIAN_CITIZENSHIP] = (
            self._derive_has_indonesian_citizenship(values)
        )
        values[FactPath.DERIVED_HAS_ACTIVE_STAY_PERMIT] = self._derive_has_active_stay_permit(
            values, effective_at
        )

        return FactSnapshot(values=MappingProxyType(values))

    def _wire_to_runtime(self, path: str, wire_fact: Mapping[str, object]) -> KnownFact | UnknownFact:
        if wire_fact["status"] == "UNKNOWN":
            return UnknownFact(reason=UnknownReason(wire_fact["reason"]))

        value = wire_fact["value"]
        spec = self._specs.get(FactPath(path))
        if spec is not None and spec.kind is FactValueKind.STRING_SET:
            value = frozenset(value)  # type: ignore[arg-type]
        return KnownFact(value=value)

    @staticmethod
    def _derive_age_years(
        values: Mapping[FactPath, KnownFact | UnknownFact],
        effective_at: datetime,
    ) -> KnownFact | UnknownFact:
        birth = values[FactPath.PERSON_BIRTH_DATE]
        if isinstance(birth, UnknownFact):
            return UnknownFact(reason=birth.reason)

        birth_date = date.fromisoformat(str(birth.value))
        reference_date = effective_at.astimezone(timezone.utc).date()
        if birth_date > reference_date:
            # A birth date after the evaluation instant is logically impossible;
            # never turn contradictory evidence into a definite legal age/minor
            # boolean — fail closed to UNKNOWN (2-seat review F2, 2026-07-18).
            return UnknownFact(reason=UnknownReason.CONFLICTING)
        years = (
            reference_date.year
            - birth_date.year
            - ((reference_date.month, reference_date.day) < (birth_date.month, birth_date.day))
        )
        return KnownFact(value=years)

    @classmethod
    def _derive_is_minor(
        cls,
        values: Mapping[FactPath, KnownFact | UnknownFact],
        effective_at: datetime,
    ) -> KnownFact | UnknownFact:
        age = cls._derive_age_years(values, effective_at)
        if isinstance(age, UnknownFact):
            return UnknownFact(reason=age.reason)
        return KnownFact(value=bool(age.value < _MINOR_AGE_THRESHOLD))

    @staticmethod
    def _derive_has_indonesian_citizenship(
        values: Mapping[FactPath, KnownFact | UnknownFact],
    ) -> KnownFact | UnknownFact:
        nationalities = values[FactPath.PERSON_NATIONALITIES]
        if isinstance(nationalities, UnknownFact):
            return UnknownFact(reason=nationalities.reason)
        return KnownFact(value=_INDONESIA_COUNTRY_CODE in nationalities.value)

    @staticmethod
    def _derive_has_active_stay_permit(
        values: Mapping[FactPath, KnownFact | UnknownFact],
        effective_at: datetime,
    ) -> KnownFact | UnknownFact:
        """Owner ruling (2026-08-23): an applicant WITH an active KITAS is
        excluded from D12. See the module-level ``_VISIT_CLASS_STATUS_CODES``
        / ``_STAY_PERMIT_STATUS_CODE_SHAPE`` constants for the two-sided
        grounding this classification rests on.

        Tri-state safety is the whole point of this method (CRITICAL per the
        mandate that added it): if EITHER
        ``immigration.current_status_code`` or
        ``immigration.current_status_expiry`` is UNKNOWN, or the code cannot
        be classified either way, the result is UNKNOWN — never a guessed
        ``False``. A guessed ``False`` here would read as "definitely has no
        active permit" and would wrongly ADMIT such an applicant to D12,
        which is exactly the failure mode a fail-closed engine must not
        produce. An EXPIRED permit is a real, tested, POSITIVE ``False`` —
        the owner explicitly ruled that person CAN apply — computed the same
        inclusive-boundary way as ``_derive_age_years``'s own reference-date
        comparison (a permit expiring exactly on ``effective_at``'s date is
        still active that day).
        """

        code = values[FactPath.IMMIGRATION_CURRENT_STATUS_CODE]
        if isinstance(code, UnknownFact):
            return UnknownFact(reason=code.reason)

        code_value = str(code.value)
        if code_value in _VISIT_CLASS_STATUS_CODES:
            # A visit-class code is definitively not a residence permit,
            # regardless of its own expiry — no need to consult
            # IMMIGRATION_CURRENT_STATUS_EXPIRY at all.
            return KnownFact(value=False)
        if not _STAY_PERMIT_STATUS_CODE_SHAPE.match(code_value):
            # Neither a recognized visit-class code nor shaped like a
            # LIMITED_STAY/PERMANENT_STAY product code — genuinely
            # ungrounded (could be a typo, a legacy code, or a real permit
            # class this registry does not yet recognize). Surface that as
            # UNKNOWN rather than guessing either direction.
            return UnknownFact(reason=UnknownReason.UNVERIFIED)

        expiry = values[FactPath.IMMIGRATION_CURRENT_STATUS_EXPIRY]
        if isinstance(expiry, UnknownFact):
            # The code looks like a stay permit but its validity cannot be
            # confirmed — stay UNKNOWN, never coerce to False.
            return UnknownFact(reason=expiry.reason)

        expiry_date = date.fromisoformat(str(expiry.value))
        reference_date = effective_at.astimezone(timezone.utc).date()
        return KnownFact(value=expiry_date >= reference_date)


def canonical_fact_payload(facts: ApplicantFacts) -> dict[str, JsonValue]:
    """A deterministic, sorted-key, ``json.dumps``-serializable view of
    ``facts.facts``.

    Intended for a future facts HMAC fingerprint (``models.Fingerprint``).
    Pure function: same input always yields the same, key-sorted output.
    Returns a **plain** ``dict`` — not a ``types.MappingProxyType`` — because
    the latter is not JSON-serializable (``json.dumps(MappingProxyType(...))``
    raises ``TypeError``), which would defeat the "fingerprint this over the
    wire" purpose the function exists for.
    """

    raw = facts.facts.model_dump(by_alias=True, mode="json")
    return dict(sorted(raw.items()))


#: Module-level default instance for convenience callers (compiler.py's own
#: default parameter, tests). Not a hidden global authority — every function
#: that consumes a registry takes one as an explicit argument.
DEFAULT_FACT_REGISTRY = FactRegistry()
