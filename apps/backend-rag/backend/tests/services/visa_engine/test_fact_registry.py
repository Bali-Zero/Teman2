"""Tests for ``backend.services.visa_engine.fact_registry``.

Covers: the default catalog is seeded 1:1 with ``enums.FactPath`` (43
entries, 40 applicant + 3 derived); ``spec()``/``missing_paths()`` behavior
(the PR1 brief's "required_facts subset-of registry" primitive); commercial
classification exactly matches ``enums.COMMERCIAL_FACT_PATHS``; PII
classification spot-checks per this module's own documented rationale;
duplicate-path construction rejected. PR3 additions at the bottom:
``FactRegistry.derive()`` (wire ``ApplicantFacts`` -> runtime
``FactSnapshot``) and ``canonical_fact_payload()``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from backend.services.visa_engine.ast import KnownFact, UnknownFact
from backend.services.visa_engine.enums import (
    COMMERCIAL_FACT_PATHS,
    DERIVED_FACT_PATHS,
    FactPath,
    FactValueKind,
    PiiClass,
)
from backend.services.visa_engine.errors import FactValidationError
from backend.services.visa_engine.fact_registry import (
    DEFAULT_FACT_REGISTRY,
    FactRegistry,
    FactSpec,
    canonical_fact_payload,
)
from backend.services.visa_engine.models import ApplicantFacts
from backend.tests.services.visa_engine.conftest import GOLD_EFFECTIVE_AT


class TestDefaultCatalogCompleteness:
    def test_every_fact_path_has_a_spec(self) -> None:
        for path in list(FactPath):
            spec = DEFAULT_FACT_REGISTRY.spec(path)
            assert spec.path is path

    def test_catalog_has_exactly_43_entries(self) -> None:
        assert len(DEFAULT_FACT_REGISTRY.all_paths()) == 43

    def test_all_paths_matches_fact_path_enum(self) -> None:
        assert DEFAULT_FACT_REGISTRY.all_paths() == frozenset(FactPath)

    def test_derived_facts_flagged_derived(self) -> None:
        for path in DERIVED_FACT_PATHS:
            assert DEFAULT_FACT_REGISTRY.spec(path).derived is True

    def test_applicant_facts_not_flagged_derived(self) -> None:
        for path in list(FactPath):
            if path in DERIVED_FACT_PATHS:
                continue
            assert DEFAULT_FACT_REGISTRY.spec(path).derived is False


class TestUnknownPathHandling:
    def test_spec_raises_on_unknown_path(self) -> None:
        with pytest.raises(FactValidationError):
            DEFAULT_FACT_REGISTRY.spec("not.a.real.path")

    def test_spec_accepts_string_or_enum(self) -> None:
        by_string = DEFAULT_FACT_REGISTRY.spec("person.birth_date")
        by_enum = DEFAULT_FACT_REGISTRY.spec(FactPath.PERSON_BIRTH_DATE)
        assert by_string is by_enum


class TestMissingPaths:
    def test_missing_paths_empty_for_valid_subset(self) -> None:
        missing = DEFAULT_FACT_REGISTRY.missing_paths(["person.birth_date", "intent.purposes"])
        assert missing == frozenset()

    def test_missing_paths_reports_unknown_entries(self) -> None:
        missing = DEFAULT_FACT_REGISTRY.missing_paths(
            ["person.birth_date", "bogus.field", "another.bogus"]
        )
        assert missing == frozenset({"bogus.field", "another.bogus"})

    def test_missing_paths_empty_iterable(self) -> None:
        assert DEFAULT_FACT_REGISTRY.missing_paths([]) == frozenset()


class TestCommercialClassification:
    def test_commercial_paths_match_enums_constant(self) -> None:
        for path in list(FactPath):
            expected = path in COMMERCIAL_FACT_PATHS
            assert DEFAULT_FACT_REGISTRY.is_commercial(path) is expected

    def test_service_fee_budget_is_commercial(self) -> None:
        assert DEFAULT_FACT_REGISTRY.is_commercial(FactPath.COMMERCIAL_SERVICE_FEE_BUDGET_IDR)

    def test_intent_purposes_is_not_commercial(self) -> None:
        assert not DEFAULT_FACT_REGISTRY.is_commercial(FactPath.INTENT_PURPOSES)


class TestPiiClassification:
    def test_violation_history_is_sensitive(self) -> None:
        spec = DEFAULT_FACT_REGISTRY.spec(FactPath.IMMIGRATION_VIOLATION_HISTORY)
        assert spec.pii_class is PiiClass.SENSITIVE

    def test_investment_capital_is_sensitive(self) -> None:
        spec = DEFAULT_FACT_REGISTRY.spec(FactPath.INVESTMENT_INVESTMENT_CAPITAL_IDR)
        assert spec.pii_class is PiiClass.SENSITIVE

    def test_derived_facts_are_pii_none(self) -> None:
        for path in DERIVED_FACT_PATHS:
            assert DEFAULT_FACT_REGISTRY.spec(path).pii_class is PiiClass.NONE

    def test_process_application_channel_is_pii_none(self) -> None:
        spec = DEFAULT_FACT_REGISTRY.spec(FactPath.PROCESS_APPLICATION_CHANNEL)
        assert spec.pii_class is PiiClass.NONE


class TestValueKind:
    def test_boolean_facts_have_boolean_kind(self) -> None:
        spec = DEFAULT_FACT_REGISTRY.spec(FactPath.WORK_EMPLOYER_IS_INDONESIAN_ENTITY)
        assert spec.kind is FactValueKind.BOOLEAN

    def test_set_valued_facts_have_string_set_kind(self) -> None:
        spec = DEFAULT_FACT_REGISTRY.spec(FactPath.INTENT_PURPOSES)
        assert spec.kind is FactValueKind.STRING_SET

    def test_money_facts_have_integer_kind(self) -> None:
        spec = DEFAULT_FACT_REGISTRY.spec(FactPath.INVESTMENT_PAID_UP_CAPITAL_IDR)
        assert spec.kind is FactValueKind.INTEGER


class TestRegistryImmutability:
    def test_specs_mapping_cannot_be_cleared(self) -> None:
        # Codex finding 9, exact counterexample: `registry._specs.clear()`
        # must be impossible, not merely type-annotated as read-only.
        with pytest.raises(AttributeError):
            DEFAULT_FACT_REGISTRY._specs.clear()  # type: ignore[attr-defined]
        assert len(DEFAULT_FACT_REGISTRY.all_paths()) == 43

    def test_specs_mapping_cannot_be_item_assigned(self) -> None:
        with pytest.raises(TypeError):
            DEFAULT_FACT_REGISTRY._specs[FactPath.PERSON_BIRTH_DATE] = None  # type: ignore[index]


class TestValueFormat:
    """Hotfix (2026-07-18, Gap A/D): the ``value_format`` axis on
    ``FactSpec`` — ``None`` by default, ``"date"``/``"country_code"`` for
    the facts ``compiler.py`` must shape-check beyond bare ``kind``.
    """

    def test_birth_date_has_date_format(self) -> None:
        spec = DEFAULT_FACT_REGISTRY.spec(FactPath.PERSON_BIRTH_DATE)
        assert spec.value_format == "date"

    def test_marital_status_has_no_value_format(self) -> None:
        # Enum-ish free-form STRING facts (already covered by
        # `allowed_values`) get no extra shape check.
        spec = DEFAULT_FACT_REGISTRY.spec(FactPath.PERSON_MARITAL_STATUS)
        assert spec.value_format is None

    def test_employer_country_code_has_country_code_format(self) -> None:
        spec = DEFAULT_FACT_REGISTRY.spec(FactPath.WORK_EMPLOYER_COUNTRY_CODE)
        assert spec.value_format == "country_code"

    def test_nationalities_set_has_country_code_format(self) -> None:
        spec = DEFAULT_FACT_REGISTRY.spec(FactPath.PERSON_NATIONALITIES)
        assert spec.value_format == "country_code"


class TestValueFormatKindConsistency:
    """PR1b item 5: ``value_format`` used to be a purely static hint — a
    future ``FactSpec(kind=INTEGER, value_format="date")`` would silently
    disable ``compiler.py``'s date-shape check instead of failing loud at
    construction, the one place the mismatch is actually introduced.
    """

    def test_date_format_on_integer_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="value_format='date'"):
            FactSpec(
                path=FactPath.INTENT_STAY_DAYS,
                kind=FactValueKind.INTEGER,
                value_type="date",
                derived=False,
                value_format="date",
            )

    def test_date_format_on_string_set_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="value_format='date'"):
            FactSpec(
                path=FactPath.INTENT_PURPOSES,
                kind=FactValueKind.STRING_SET,
                value_type="date_set",
                derived=False,
                value_format="date",
            )

    def test_country_code_format_on_boolean_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="value_format='country_code'"):
            FactSpec(
                path=FactPath.WORK_EMPLOYER_IS_INDONESIAN_ENTITY,
                kind=FactValueKind.BOOLEAN,
                value_type="boolean",
                derived=False,
                value_format="country_code",
            )

    def test_country_code_format_on_integer_kind_rejected(self) -> None:
        with pytest.raises(ValueError, match="value_format='country_code'"):
            FactSpec(
                path=FactPath.INTENT_STAY_DAYS,
                kind=FactValueKind.INTEGER,
                value_type="non_negative_integer",
                derived=False,
                value_format="country_code",
            )

    def test_date_format_on_string_kind_is_innocent(self) -> None:
        spec = FactSpec(
            path=FactPath.PERSON_BIRTH_DATE,
            kind=FactValueKind.STRING,
            value_type="date",
            derived=False,
            value_format="date",
        )
        assert spec.value_format == "date"

    def test_country_code_format_on_string_kind_is_innocent(self) -> None:
        spec = FactSpec(
            path=FactPath.WORK_EMPLOYER_COUNTRY_CODE,
            kind=FactValueKind.STRING,
            value_type="country_code",
            derived=False,
            value_format="country_code",
        )
        assert spec.value_format == "country_code"

    def test_country_code_format_on_string_set_kind_is_innocent(self) -> None:
        spec = FactSpec(
            path=FactPath.PERSON_NATIONALITIES,
            kind=FactValueKind.STRING_SET,
            value_type="country_code_set",
            derived=False,
            value_format="country_code",
        )
        assert spec.value_format == "country_code"

    def test_none_format_always_accepted_regardless_of_kind(self) -> None:
        for kind in list(FactValueKind):
            spec = FactSpec(
                path=FactPath.PERSON_MARITAL_STATUS,
                kind=kind,
                value_type="whatever",
                derived=False,
                value_format=None,
            )
            assert spec.value_format is None

    def test_default_registry_specs_all_construct_cleanly(self) -> None:
        # Every entry in the real catalog satisfies its own invariant — the
        # hotfix's __post_init__ addition must not retroactively break
        # _DEFAULT_SPECS (module import already proves this at collection
        # time; this is the explicit, readable assertion of it).
        assert len(DEFAULT_FACT_REGISTRY.all_paths()) == 43


class TestRegistryConstruction:
    def test_duplicate_spec_path_rejected(self) -> None:
        spec_a = FactSpec(
            path=FactPath.PERSON_BIRTH_DATE,
            kind=FactValueKind.STRING,
            value_type="date",
            derived=False,
        )
        spec_b = FactSpec(
            path=FactPath.PERSON_BIRTH_DATE,
            kind=FactValueKind.STRING,
            value_type="date",
            derived=False,
        )
        with pytest.raises(FactValidationError):
            FactRegistry([spec_a, spec_b])

    def test_custom_registry_is_independent_of_default(self) -> None:
        custom = FactRegistry(
            [
                FactSpec(
                    path=FactPath.PERSON_BIRTH_DATE,
                    kind=FactValueKind.STRING,
                    value_type="date",
                    derived=False,
                )
            ]
        )
        assert custom.all_paths() == frozenset({FactPath.PERSON_BIRTH_DATE})
        assert len(DEFAULT_FACT_REGISTRY.all_paths()) == 43


_UNKNOWN_WIRE = {"status": "UNKNOWN", "reason": "NOT_ASKED"}


def _applicant_facts(overrides: dict[str, Any], *, assessment_id: uuid.UUID | None = None) -> ApplicantFacts:
    """Build an ``ApplicantFacts`` with every one of the 40 paths defaulted
    to UNKNOWN, then override the given wire keys with KNOWN wire values —
    the minimal builder ``derive()``'s tests need (distinct from
    ``conftest.make_applicant_facts``, which is all-UNKNOWN with no override
    knob)."""

    facts: dict[str, object] = {
        "person.birth_date": _UNKNOWN_WIRE,
        "person.nationalities": _UNKNOWN_WIRE,
        "person.marital_status": _UNKNOWN_WIRE,
        "immigration.currently_in_indonesia": _UNKNOWN_WIRE,
        "immigration.current_status_code": _UNKNOWN_WIRE,
        "immigration.current_status_expiry": _UNKNOWN_WIRE,
        "immigration.last_entry_date": _UNKNOWN_WIRE,
        "immigration.overstay_days": _UNKNOWN_WIRE,
        "immigration.violation_history": _UNKNOWN_WIRE,
        "intent.purposes": _UNKNOWN_WIRE,
        "intent.stay_days": _UNKNOWN_WIRE,
        "intent.desired_entry_date": _UNKNOWN_WIRE,
        "intent.entry_pattern": _UNKNOWN_WIRE,
        "intent.requested_product_code": _UNKNOWN_WIRE,
        "work.employer_country_code": _UNKNOWN_WIRE,
        "work.employer_is_indonesian_entity": _UNKNOWN_WIRE,
        "work.serves_indonesian_clients": _UNKNOWN_WIRE,
        "work.indonesia_source_compensation": _UNKNOWN_WIRE,
        "work.indonesian_work_sponsor_confirmed": _UNKNOWN_WIRE,
        "investment.pt_pma_committed": _UNKNOWN_WIRE,
        "investment.investment_capital_idr": _UNKNOWN_WIRE,
        "investment.paid_up_capital_idr": _UNKNOWN_WIRE,
        "investment.proposed_role": _UNKNOWN_WIRE,
        "family.relation_to_sponsor": _UNKNOWN_WIRE,
        "family.sponsor_nationalities": _UNKNOWN_WIRE,
        "family.sponsor_status_code": _UNKNOWN_WIRE,
        "family.marriage_registered": _UNKNOWN_WIRE,
        "family.sponsor_confirmed": _UNKNOWN_WIRE,
        "study.level": _UNKNOWN_WIRE,
        "study.admission_confirmed": _UNKNOWN_WIRE,
        "study.sponsor_confirmed": _UNKNOWN_WIRE,
        "secondhome.bank_deposit_usd": _UNKNOWN_WIRE,
        "secondhome.bank_deposit_at_state_bank": _UNKNOWN_WIRE,
        "secondhome.bank_deposit_in_own_name": _UNKNOWN_WIRE,
        "secondhome.qualifying_property_value_usd": _UNKNOWN_WIRE,
        "secondhome.passive_monthly_income_usd": _UNKNOWN_WIRE,
        "process.application_channel": _UNKNOWN_WIRE,
        "process.wants_onshore_conversion": _UNKNOWN_WIRE,
        "commercial.service_fee_budget_idr": _UNKNOWN_WIRE,
        "commercial.wants_quote": _UNKNOWN_WIRE,
    }
    facts.update(overrides)
    return ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=assessment_id or uuid.uuid4(),
        collected_at=GOLD_EFFECTIVE_AT,
        facts=facts,
    )


class TestDeriveRequiresAwareEffectiveAt:
    """F3 (2-seat review, 2026-07-18): a naive ``effective_at`` is ambiguous
    (which timezone?) and could silently shift the derived age by up to a
    day — ``derive()`` now fails loud instead of guessing.
    """

    def test_naive_effective_at_raises(self) -> None:
        # Guilt: no tzinfo at all.
        naive = datetime(2026, 7, 17, 0, 0, 0)
        with pytest.raises(FactValidationError, match="timezone-aware"):
            DEFAULT_FACT_REGISTRY.derive(_applicant_facts({}), effective_at=naive)

    def test_aware_utc_effective_at_still_works(self) -> None:
        # Innocence: an ordinary aware-UTC effective_at is unaffected.
        snapshot = DEFAULT_FACT_REGISTRY.derive(_applicant_facts({}), effective_at=GOLD_EFFECTIVE_AT)
        assert frozenset(snapshot.values) == frozenset(FactPath)


class TestDeriveWireToRuntime:
    def test_every_one_of_43_paths_present_in_snapshot(self) -> None:
        snapshot = DEFAULT_FACT_REGISTRY.derive(_applicant_facts({}), effective_at=GOLD_EFFECTIVE_AT)
        assert frozenset(snapshot.values) == frozenset(FactPath)

    def test_unknown_wire_fact_becomes_unknown_fact_with_reason(self) -> None:
        snapshot = DEFAULT_FACT_REGISTRY.derive(_applicant_facts({}), effective_at=GOLD_EFFECTIVE_AT)
        stay_days = snapshot.values[FactPath.INTENT_STAY_DAYS]
        assert isinstance(stay_days, UnknownFact)
        assert stay_days.reason.value == "NOT_ASKED"

    def test_known_scalar_wire_fact_becomes_known_fact(self) -> None:
        facts = _applicant_facts({"intent.stay_days": {"status": "KNOWN", "value": 30}})
        snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=GOLD_EFFECTIVE_AT)
        assert snapshot.values[FactPath.INTENT_STAY_DAYS] == KnownFact(value=30)

    def test_known_set_valued_wire_fact_becomes_frozenset(self) -> None:
        facts = _applicant_facts(
            {"intent.purposes": {"status": "KNOWN", "value": ["TOURISM", "STUDY"]}}
        )
        snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=GOLD_EFFECTIVE_AT)
        purposes = snapshot.values[FactPath.INTENT_PURPOSES]
        assert isinstance(purposes, KnownFact)
        assert purposes.value == frozenset({"TOURISM", "STUDY"})

    def test_known_date_wire_fact_stays_iso_string(self) -> None:
        facts = _applicant_facts({"person.birth_date": {"status": "KNOWN", "value": "2000-07-19"}})
        snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=GOLD_EFFECTIVE_AT)
        assert snapshot.values[FactPath.PERSON_BIRTH_DATE] == KnownFact(value="2000-07-19")


class TestDeriveAgeYears:
    def test_age_computed_from_birth_date(self) -> None:
        facts = _applicant_facts({"person.birth_date": {"status": "KNOWN", "value": "2000-07-19"}})
        snapshot = DEFAULT_FACT_REGISTRY.derive(
            facts, effective_at=datetime(2026, 7, 18, tzinfo=timezone.utc)
        )
        # Birthday is 2000-07-19; effective_at is one day BEFORE the 2026
        # birthday, so the applicant has not yet turned 26 -> 25.
        assert snapshot.values[FactPath.DERIVED_AGE_YEARS] == KnownFact(value=25)

    def test_age_rolls_over_on_birthday(self) -> None:
        facts = _applicant_facts({"person.birth_date": {"status": "KNOWN", "value": "2000-07-19"}})
        snapshot = DEFAULT_FACT_REGISTRY.derive(
            facts, effective_at=datetime(2026, 7, 19, tzinfo=timezone.utc)
        )
        assert snapshot.values[FactPath.DERIVED_AGE_YEARS] == KnownFact(value=26)

    def test_age_unknown_when_birth_date_unknown(self) -> None:
        snapshot = DEFAULT_FACT_REGISTRY.derive(_applicant_facts({}), effective_at=GOLD_EFFECTIVE_AT)
        assert isinstance(snapshot.values[FactPath.DERIVED_AGE_YEARS], UnknownFact)

    def test_future_birth_date_yields_unknown_not_definite_age(self) -> None:
        # Guilt (F2, 2-seat review 2026-07-18): a birth_date AFTER
        # effective_at is contradictory evidence — it must never be silently
        # turned into a definite age/minor boolean (e.g. a negative age
        # rolling into "not yet 18" -> is_minor=True would be a wrong
        # DEFINITE answer on a client-facing "zero wrong answers" engine).
        facts = _applicant_facts(
            {"person.birth_date": {"status": "KNOWN", "value": "2027-01-01"}}
        )
        snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=GOLD_EFFECTIVE_AT)
        age = snapshot.values[FactPath.DERIVED_AGE_YEARS]
        is_minor = snapshot.values[FactPath.DERIVED_IS_MINOR]
        assert isinstance(age, UnknownFact)
        assert age.reason.value == "CONFLICTING"
        assert isinstance(is_minor, UnknownFact)

    def test_birth_date_equal_to_reference_date_is_age_zero(self) -> None:
        # Innocence: born exactly ON effective_at's date is NOT "future" —
        # must still resolve to a definite age (0), not UNKNOWN.
        facts = _applicant_facts(
            {"person.birth_date": {"status": "KNOWN", "value": "2026-07-17"}}
        )
        snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=GOLD_EFFECTIVE_AT)
        assert snapshot.values[FactPath.DERIVED_AGE_YEARS] == KnownFact(value=0)

    def test_ordinary_past_birth_date_still_derives_correct_age(self) -> None:
        # Innocence: an unremarkable past birth date is unaffected by the
        # new future-date guard.
        facts = _applicant_facts(
            {"person.birth_date": {"status": "KNOWN", "value": "2000-07-19"}}
        )
        snapshot = DEFAULT_FACT_REGISTRY.derive(
            facts, effective_at=datetime(2026, 7, 18, tzinfo=timezone.utc)
        )
        assert snapshot.values[FactPath.DERIVED_AGE_YEARS] == KnownFact(value=25)


class TestDeriveIsMinor:
    def test_minor_true_under_18(self) -> None:
        facts = _applicant_facts({"person.birth_date": {"status": "KNOWN", "value": "2015-01-01"}})
        snapshot = DEFAULT_FACT_REGISTRY.derive(
            facts, effective_at=datetime(2026, 7, 18, tzinfo=timezone.utc)
        )
        assert snapshot.values[FactPath.DERIVED_IS_MINOR] == KnownFact(value=True)

    def test_minor_false_at_18_or_over(self) -> None:
        facts = _applicant_facts({"person.birth_date": {"status": "KNOWN", "value": "2000-07-19"}})
        snapshot = DEFAULT_FACT_REGISTRY.derive(
            facts, effective_at=datetime(2026, 7, 18, tzinfo=timezone.utc)
        )
        assert snapshot.values[FactPath.DERIVED_IS_MINOR] == KnownFact(value=False)

    def test_minor_unknown_when_birth_date_unknown(self) -> None:
        snapshot = DEFAULT_FACT_REGISTRY.derive(_applicant_facts({}), effective_at=GOLD_EFFECTIVE_AT)
        assert isinstance(snapshot.values[FactPath.DERIVED_IS_MINOR], UnknownFact)


class TestDeriveHasIndonesianCitizenship:
    def test_true_when_id_in_nationalities(self) -> None:
        facts = _applicant_facts(
            {"person.nationalities": {"status": "KNOWN", "value": ["IT", "ID"]}}
        )
        snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=GOLD_EFFECTIVE_AT)
        assert snapshot.values[FactPath.DERIVED_HAS_INDONESIAN_CITIZENSHIP] == KnownFact(value=True)

    def test_false_when_id_absent_from_nationalities(self) -> None:
        facts = _applicant_facts({"person.nationalities": {"status": "KNOWN", "value": ["IT"]}})
        snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=GOLD_EFFECTIVE_AT)
        assert snapshot.values[FactPath.DERIVED_HAS_INDONESIAN_CITIZENSHIP] == KnownFact(
            value=False
        )

    def test_unknown_when_nationalities_unknown(self) -> None:
        snapshot = DEFAULT_FACT_REGISTRY.derive(_applicant_facts({}), effective_at=GOLD_EFFECTIVE_AT)
        assert isinstance(
            snapshot.values[FactPath.DERIVED_HAS_INDONESIAN_CITIZENSHIP], UnknownFact
        )


class TestCanonicalFactPayload:
    def test_keys_are_sorted(self) -> None:
        payload = canonical_fact_payload(_applicant_facts({}))
        assert list(payload.keys()) == sorted(payload.keys())

    def test_covers_all_40_applicant_paths(self) -> None:
        payload = canonical_fact_payload(_applicant_facts({}))
        assert len(payload) == 40

    def test_is_json_serializable(self) -> None:
        import json

        payload = canonical_fact_payload(_applicant_facts({}))
        serialized = json.dumps(payload)
        assert json.loads(serialized) == payload

    def test_deterministic_for_same_input(self) -> None:
        assessment_id = uuid.uuid4()
        facts = _applicant_facts(
            {"intent.stay_days": {"status": "KNOWN", "value": 30}}, assessment_id=assessment_id
        )
        payload_a = canonical_fact_payload(facts)
        payload_b = canonical_fact_payload(facts)
        assert payload_a == payload_b
