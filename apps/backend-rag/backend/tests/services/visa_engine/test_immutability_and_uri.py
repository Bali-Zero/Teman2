"""F9 (deep immutability) + F10 (URI validation scheme-only) regression
coverage.

Process note: unlike every other finding in this fix round, F9's list->tuple
conversion and F10's URI-validator fix were implemented in the same edit
pass as F7 (strict primitives) rather than behind their own dedicated
RED test first — both were verified non-regressive via the full existing
suite immediately afterwards (no prior test asserted list-vs-tuple typing
or exercised a schemeless-authority URI), but that is a narrower guarantee
than "this exact behavior was proven absent beforehand". This file closes
that gap with dedicated, currently-passing regression tests.
"""

from __future__ import annotations

import typing

import pytest
from pydantic import ValidationError

from backend.services.visa_engine.ast import AllCondition, InCondition, KnownCondition
from backend.services.visa_engine.compiler import CompiledRule, CompiledRulePack
from backend.services.visa_engine.models import Rule, SourceRecord, VisaProductVersion

from ._builders import minimal_valid_envelope, product, source_record


class TestAstTupleImmutability:
    def test_all_condition_args_is_a_tuple(self) -> None:
        cond = AllCondition(op="all", args=[{"op": "known", "fact": "intent.stay_days"}])
        assert isinstance(cond.args, tuple)

    def test_in_condition_values_is_a_tuple(self) -> None:
        cond = InCondition(op="in", fact="intent.stay_days", values=[10, 20])
        assert isinstance(cond.values, tuple)

    def test_condition_model_is_frozen(self) -> None:
        cond = KnownCondition(op="known", fact="intent.stay_days")
        with pytest.raises(ValidationError):
            cond.fact = "commercial.wants_quote"  # type: ignore[misc]


class TestModelTupleImmutability:
    def test_rule_required_facts_is_a_tuple(self) -> None:
        envelope = minimal_valid_envelope()
        rule_dict = envelope["payload"]["rules"][0]
        r = Rule(**rule_dict)
        assert isinstance(r.required_facts, tuple)
        with pytest.raises(AttributeError):
            r.required_facts.append("x")  # type: ignore[attr-defined]

    def test_visa_product_version_covered_purposes_is_a_tuple(self) -> None:
        prod_dict = product(source_id="00000000-0000-0000-0000-000000000000")
        prod = VisaProductVersion(**prod_dict)
        assert isinstance(prod.covered_purposes, tuple)

    def test_source_record_locators_is_a_tuple(self) -> None:
        src_dict = source_record()
        src = SourceRecord(**src_dict)
        assert isinstance(src.locators, tuple)

    def test_rule_itself_is_frozen(self) -> None:
        envelope = minimal_valid_envelope()
        r = Rule(**envelope["payload"]["rules"][0])
        with pytest.raises(ValidationError):
            r.priority = 999  # type: ignore[misc]


class TestCompiledStructuresHaveNoMutableLeaks:
    """F9: verify CompiledRule/CompiledRulePack (already frozen dataclasses)
    declare only immutable container types for their collection fields —
    no bare list/set/dict. ``compiler.py`` uses
    ``from __future__ import annotations``, so raw ``dataclasses.fields()``
    types are unresolved strings; ``typing.get_type_hints`` resolves them to
    real (generic-alias) type objects, same mechanism as F12."""

    _MUTABLE_CONTAINERS = (list, set, dict)

    def test_compiled_rule_has_no_list_set_dict_fields(self) -> None:
        hints = typing.get_type_hints(CompiledRule)
        for name, hint in hints.items():
            origin = typing.get_origin(hint)
            assert origin not in self._MUTABLE_CONTAINERS, (
                f"CompiledRule.{name} has a mutable container type: {hint!r}"
            )

    def test_compiled_rule_pack_has_no_list_set_dict_fields(self) -> None:
        hints = typing.get_type_hints(CompiledRulePack)
        for name, hint in hints.items():
            origin = typing.get_origin(hint)
            assert origin not in self._MUTABLE_CONTAINERS, (
                f"CompiledRulePack.{name} has a mutable container type: {hint!r}"
            )


class TestUriValidationSchemeOnly:
    """F10: only a scheme is required (RFC 3986 absolute-URI) — NOT a
    netloc. urn:/mailto: forms (no authority component) must pass."""

    def _record_with_url(self, url: str) -> SourceRecord:
        return SourceRecord(**source_record(canonical_url=url))

    def test_urn_uri_accepted(self) -> None:
        record = self._record_with_url("urn:isbn:0451450523")
        assert record.canonical_url == "urn:isbn:0451450523"

    def test_mailto_uri_accepted(self) -> None:
        record = self._record_with_url("mailto:someone@example.com")
        assert record.canonical_url == "mailto:someone@example.com"

    def test_ordinary_https_uri_still_accepted(self) -> None:
        record = self._record_with_url("https://example.com/source")
        assert record.canonical_url == "https://example.com/source"

    def test_schemeless_string_still_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._record_with_url("not-a-uri-at-all")
