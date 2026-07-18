"""FactRegistry: spec()/derive()/canonical_fact_payload behavior."""

from __future__ import annotations

import json
import typing
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone

import pytest

from backend.services.visa_engine import fact_registry
from backend.services.visa_engine.errors import FactValidationError
from backend.services.visa_engine.fact_registry import (
    DEFAULT_FACT_SPECS,
    ApplicantFactPath,
    DerivedFactPath,
    FactRegistry,
    FactSpec,
    KnownFact,
    UnknownFact,
    canonical_fact_payload,
)
from backend.services.visa_engine.models import ApplicantFacts

from ._builders import applicant_facts_envelope


def test_default_registry_covers_every_applicant_and_derived_path() -> None:
    registry = FactRegistry()
    known = registry.known_paths()
    for path in ApplicantFactPath:
        assert path.value in known
    for path in DerivedFactPath:
        assert path.value in known
    assert len(known) == 35 + 3


def test_spec_raises_fact_validation_error_for_unregistered_path() -> None:
    registry = FactRegistry()
    with pytest.raises(FactValidationError):
        registry.spec("not.a.real.path")


def test_custom_registry_can_omit_paths() -> None:
    """FactRegistry is injectable — a caller can build one with a subset of
    specs, which is exactly what the compiler tests exploit."""

    reduced = FactRegistry(specs=[s for s in DEFAULT_FACT_SPECS if s.path != "study.level"])
    with pytest.raises(FactValidationError):
        reduced.spec("study.level")
    # everything else still resolves fine
    assert reduced.spec("intent.stay_days").value_type is int


def test_commercial_only_flag_set_for_exactly_the_two_commercial_facts() -> None:
    commercial_paths = {s.path for s in DEFAULT_FACT_SPECS if s.commercial_only}
    assert commercial_paths == {
        "commercial.service_fee_budget_idr",
        "commercial.wants_quote",
    }


def test_derive_computes_age_years_is_minor_and_citizenship() -> None:
    registry = FactRegistry()
    payload = applicant_facts_envelope(
        **{
            "person.birth_date": {"status": "KNOWN", "value": "2010-08-01"},
            "person.nationalities": {"status": "KNOWN", "value": ["ID", "US"]},
        }
    )
    facts = ApplicantFacts(**payload)

    snapshot = registry.derive(facts, effective_at=datetime(2026, 7, 18, tzinfo=timezone.utc))

    age = snapshot.values["derived.age_years"]
    is_minor = snapshot.values["derived.is_minor"]
    citizenship = snapshot.values["derived.has_indonesian_citizenship"]

    assert isinstance(age, KnownFact) and age.value == 15
    assert isinstance(is_minor, KnownFact) and is_minor.value is True
    assert isinstance(citizenship, KnownFact) and citizenship.value is True


def test_derive_age_years_birthday_not_yet_reached_this_year() -> None:
    registry = FactRegistry()
    payload = applicant_facts_envelope(
        **{"person.birth_date": {"status": "KNOWN", "value": "1990-12-31"}}
    )
    facts = ApplicantFacts(**payload)
    snapshot = registry.derive(facts, effective_at=datetime(2026, 7, 18, tzinfo=timezone.utc))
    age = snapshot.values["derived.age_years"]
    assert isinstance(age, KnownFact)
    assert age.value == 35  # birthday not yet reached in 2026


def test_derive_propagates_unknown_reason_for_derived_facts() -> None:
    registry = FactRegistry()
    payload = applicant_facts_envelope()  # birth_date/nationalities default to UNKNOWN{NOT_ASKED}
    facts = ApplicantFacts(**payload)
    snapshot = registry.derive(facts, effective_at=datetime(2026, 7, 18, tzinfo=timezone.utc))

    age = snapshot.values["derived.age_years"]
    is_minor = snapshot.values["derived.is_minor"]
    citizenship = snapshot.values["derived.has_indonesian_citizenship"]

    assert isinstance(age, UnknownFact)
    assert isinstance(is_minor, UnknownFact)
    assert isinstance(citizenship, UnknownFact)


def test_derive_canonicalizes_country_set_to_frozenset() -> None:
    registry = FactRegistry()
    payload = applicant_facts_envelope(
        **{"person.nationalities": {"status": "KNOWN", "value": ["US", "GB"]}}
    )
    facts = ApplicantFacts(**payload)
    snapshot = registry.derive(facts, effective_at=datetime(2026, 7, 18, tzinfo=timezone.utc))
    nationalities = snapshot.values["person.nationalities"]
    assert isinstance(nationalities, KnownFact)
    assert nationalities.value == frozenset({"US", "GB"})


def test_derive_covers_every_applicant_and_derived_path_in_snapshot() -> None:
    registry = FactRegistry()
    facts = ApplicantFacts(**applicant_facts_envelope())
    snapshot = registry.derive(facts, effective_at=datetime(2026, 7, 18, tzinfo=timezone.utc))
    for path in ApplicantFactPath:
        assert path.value in snapshot.values
    for path in DerivedFactPath:
        assert path.value in snapshot.values


def test_canonical_fact_payload_is_deterministic_and_sorted() -> None:
    payload = applicant_facts_envelope(**{"intent.stay_days": {"status": "KNOWN", "value": 14}})
    facts = ApplicantFacts(**payload)

    result = canonical_fact_payload(facts)
    keys = list(result.keys())
    assert keys == sorted(keys)
    assert result["intent.stay_days"] == {"status": "KNOWN", "value": 14}

    # Deterministic: calling again yields an equal payload.
    result2 = canonical_fact_payload(facts)
    assert result == result2


def test_canonical_fact_payload_is_a_plain_dict_not_a_mapping_proxy() -> None:
    """F11: MappingProxyType is NOT json.dumps-serializable — the function
    must return a plain dict."""

    facts = ApplicantFacts(**applicant_facts_envelope())
    result = canonical_fact_payload(facts)
    assert type(result) is dict


def test_canonical_fact_payload_round_trips_through_real_json_dumps() -> None:
    """F11 regression: must survive the REAL json.dumps (no dict()-wrapping
    workaround in the test — that would mask a MappingProxyType bug)."""

    payload = applicant_facts_envelope(
        **{
            "intent.stay_days": {"status": "KNOWN", "value": 14},
            "person.nationalities": {"status": "KNOWN", "value": ["US", "GB"]},
        }
    )
    facts = ApplicantFacts(**payload)
    result = canonical_fact_payload(facts)

    serialized = json.dumps(result)
    reloaded = json.loads(serialized)
    assert reloaded["intent.stay_days"] == {"status": "KNOWN", "value": 14}
    assert reloaded["person.nationalities"] == {"status": "KNOWN", "value": ["US", "GB"]}


def test_fact_spec_is_frozen_dataclass() -> None:
    spec = FactSpec(
        path="x.y", value_type=int, derived=False, dependencies=frozenset(), commercial_only=False
    )
    with pytest.raises(FrozenInstanceError, match="cannot assign to field"):
        spec.path = "changed"  # type: ignore[misc]


def test_date_typed_facts_have_date_value_type() -> None:
    """F1 prerequisite: date facts must be distinguishable from plain str
    facts in the registry, so the compiler can require literal values to be
    valid ISO date strings only for these paths."""

    registry = FactRegistry()
    date_paths = {
        "person.birth_date",
        "immigration.current_status_expiry",
        "immigration.last_entry_date",
        "intent.desired_entry_date",
    }
    for path in date_paths:
        assert registry.spec(path).value_type is date

    # A plain enum-like string fact must NOT be typed as date.
    assert registry.spec("person.marital_status").value_type is str


class TestGetTypeHintsRegression:
    """F12: PEP 562 module __getattr__ must let typing.get_type_hints()
    resolve the "ApplicantFacts" forward reference used in
    FactRegistry.derive()/canonical_fact_payload() signatures.

    Mechanism note (verified empirically, not assumed): a bare module-level
    __getattr__ is NOT consulted by get_type_hints()'s internal eval() call
    (that hook only fires for `module.attr` access) — so the forward ref
    resolves only AFTER something has triggered `fact_registry.ApplicantFacts`
    at least once, populating the module's real __dict__. Both tests below
    perform that trigger explicitly, which is the realistic, correct scope of
    what PEP 562 offers here (see fact_registry.py's __getattr__ docstring).
    """

    def test_getattr_lazily_imports_and_returns_the_real_class(self) -> None:
        real_class = fact_registry.ApplicantFacts
        assert real_class is ApplicantFacts

    def test_getattr_raises_attribute_error_for_unknown_names(self) -> None:
        with pytest.raises(AttributeError):
            fact_registry.this_name_does_not_exist  # noqa: B018

    def test_get_type_hints_resolves_after_lazy_trigger(self) -> None:
        _ = fact_registry.ApplicantFacts  # trigger PEP 562 population

        hints = typing.get_type_hints(FactRegistry.derive)
        assert hints["facts"] is ApplicantFacts

        payload_hints = typing.get_type_hints(canonical_fact_payload)
        assert payload_hints["facts"] is ApplicantFacts
