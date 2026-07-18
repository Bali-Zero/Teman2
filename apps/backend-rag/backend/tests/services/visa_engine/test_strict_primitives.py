"""F7: no bool-from-string, no int-from-float coercion anywhere in the wire
models or AST literals. Wire field names accept ONLY the schema's aliases,
not the python attribute names (populate_by_name off where aliases exist).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.services.visa_engine.ast import EqCondition
from backend.services.visa_engine.models import ApplicantFacts, TimeRange

from ._builders import applicant_facts_envelope


class TestAstScalarStrictness:
    """Note: whether "true" (a string) is a *valid fact-type match* for a
    bool-typed fact is the compiler's job (F1, `type(value) is bool` check
    against `FactSpec.value_type`) — Scalar itself is a bare `bool | int |
    str` union with no fact linkage, and a string IS a legitimate Scalar
    (e.g. an enum-like value for a str-typed fact). What belongs here is
    strictly the union's own coercion behavior: does a float silently
    become an int, does an int silently become a bool, etc."""

    def test_eq_condition_accepts_real_bool(self) -> None:
        cond = EqCondition(op="eq", fact="immigration.currently_in_indonesia", value=True)
        assert cond.value is True

    def test_int_like_scalar_rejects_float(self) -> None:
        # 2.0 must not silently become int 2 inside the bool|int|str Scalar union.
        with pytest.raises(ValidationError):
            EqCondition(op="eq", fact="intent.stay_days", value=2.0)

    def test_scalar_still_accepts_a_real_string(self) -> None:
        """Strictness must not break the legitimate str member of Scalar."""

        cond = EqCondition(op="eq", fact="person.marital_status", value="MARRIED")
        assert cond.value == "MARRIED"

    def test_int_scalar_rejects_bool_via_isinstance_leak(self) -> None:
        """`bool` is an `int` subclass in Python — a StrictInt member must
        not accidentally accept a bool positionally meant for the bool
        member (exercised here by asserting the round-tripped type is
        exactly int, never bool, when a real int is given)."""

        cond = EqCondition(op="eq", fact="intent.stay_days", value=5)
        assert type(cond.value) is int


class TestModelPrimitiveStrictness:
    def test_known_boolean_rejects_string_false(self) -> None:
        payload = applicant_facts_envelope(
            **{"immigration.currently_in_indonesia": {"status": "KNOWN", "value": "false"}}
        )
        with pytest.raises(ValidationError):
            ApplicantFacts(**payload)

    def test_known_non_negative_integer_rejects_float(self) -> None:
        payload = applicant_facts_envelope(
            **{"intent.stay_days": {"status": "KNOWN", "value": 14.0}}
        )
        with pytest.raises(ValidationError):
            ApplicantFacts(**payload)

    def test_known_boolean_accepts_real_bool(self) -> None:
        payload = applicant_facts_envelope(
            **{"immigration.currently_in_indonesia": {"status": "KNOWN", "value": True}}
        )
        facts = ApplicantFacts(**payload)
        assert facts.facts.immigration_currently_in_indonesia.value is True

    def test_known_non_negative_integer_accepts_real_int(self) -> None:
        payload = applicant_facts_envelope(**{"intent.stay_days": {"status": "KNOWN", "value": 14}})
        facts = ApplicantFacts(**payload)
        assert facts.facts.intent_stay_days.value == 14

    def test_uuid_and_date_fields_still_accept_iso_strings(self) -> None:
        """Strictness must be scoped to bool/int/str primitives — UUID and
        date fields are still validated (and MUST still accept) their JSON
        string wire representation."""

        payload = applicant_facts_envelope(
            **{"person.birth_date": {"status": "KNOWN", "value": "1990-05-12"}}
        )
        facts = ApplicantFacts(**payload)
        assert str(facts.assessment_id)  # UUID field accepted a string
        assert facts.facts.person_birth_date.value.isoformat() == "1990-05-12"


class TestAliasOnlyWireNames:
    def test_time_range_rejects_python_attribute_name(self) -> None:
        """`from_` is the Python attribute name for the wire key `from` —
        with populate_by_name off, constructing via the python name (rather
        than the alias) must fail, not silently succeed."""

        with pytest.raises(ValidationError):
            TimeRange(from_="2026-01-01T00:00:00Z", to=None)

    def test_time_range_accepts_wire_alias(self) -> None:
        tr = TimeRange(**{"from": "2026-01-01T00:00:00Z", "to": None})
        assert tr.from_ == "2026-01-01T00:00:00Z"

    def test_applicant_facts_data_rejects_python_attribute_name(self) -> None:
        payload = applicant_facts_envelope()
        # Swap one alias key for its python-attribute-name equivalent.
        payload["facts"]["person_birth_date"] = payload["facts"].pop("person.birth_date")
        with pytest.raises(ValidationError):
            ApplicantFacts(**payload)
