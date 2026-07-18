"""Tests for ``backend.services.visa_engine.fact_registry``.

Covers: the default catalog is seeded 1:1 with ``enums.FactPath`` (38
entries, 35 applicant + 3 derived); ``spec()``/``missing_paths()`` behavior
(the PR1 brief's "required_facts subset-of registry" primitive); commercial
classification exactly matches ``enums.COMMERCIAL_FACT_PATHS``; PII
classification spot-checks per this module's own documented rationale;
duplicate-path construction rejected.
"""

from __future__ import annotations

import pytest

from backend.services.visa_engine.enums import (
    COMMERCIAL_FACT_PATHS,
    DERIVED_FACT_PATHS,
    FactPath,
    FactValueKind,
    PiiClass,
)
from backend.services.visa_engine.errors import FactValidationError
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY, FactRegistry, FactSpec


class TestDefaultCatalogCompleteness:
    def test_every_fact_path_has_a_spec(self) -> None:
        for path in list(FactPath):
            spec = DEFAULT_FACT_REGISTRY.spec(path)
            assert spec.path is path

    def test_catalog_has_exactly_38_entries(self) -> None:
        assert len(DEFAULT_FACT_REGISTRY.all_paths()) == 38

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
        assert len(DEFAULT_FACT_REGISTRY.all_paths()) == 38

    def test_specs_mapping_cannot_be_item_assigned(self) -> None:
        with pytest.raises(TypeError):
            DEFAULT_FACT_REGISTRY._specs[FactPath.PERSON_BIRTH_DATE] = None  # type: ignore[index]


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
        assert len(DEFAULT_FACT_REGISTRY.all_paths()) == 38
