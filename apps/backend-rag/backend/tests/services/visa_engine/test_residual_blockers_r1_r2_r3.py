"""Fix-round verification pass residual blockers (R1/R2/R3):

R1: set-operator (`intersects`/`contains_all`) `values` members were never
type-checked against the fact's element type — only the container shape
(frozenset vs scalar) was checked. An int/bool member on a str-typed set
fact must be rejected, naming the offending member. `in`/`not_in`/`between`
member-level checks are re-asserted here too (already covered by the
existing per-member literal loop, but the coordinator asked for explicit
coverage).

R2: `date.fromisoformat` (Python 3.11) accepts non-canonical forms —
compact `YYYYMMDD` and ISO week-dates `YYYY-Www-D` — that then compare
LEXICOGRAPHICALLY WRONG against the canonical `YYYY-MM-DD` strings stored
in FactSnapshot. Every date-typed-fact literal must also match
`^\\d{4}-\\d{2}-\\d{2}$` before being accepted.

R3: `_validate_uri` accepted raw whitespace/control characters inside an
otherwise scheme-valid URI (e.g. `urn:bad value`). Must require an RFC
3986 scheme prefix AND reject any embedded whitespace/control character,
while keeping urn:/mailto:/http(s) forms passing.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.services.visa_engine.compiler import CompiledRulePack, compile_rule_pack
from backend.services.visa_engine.errors import RulePackCompilationError
from backend.services.visa_engine.fact_registry import FactRegistry
from backend.services.visa_engine.models import RulePack, SourceRecord

from ._builders import single_rule_envelope, source_record


def _compile(when: dict, *, required_facts: list[str]) -> CompiledRulePack:
    envelope = single_rule_envelope(when=when, required_facts=required_facts)
    pack = RulePack(**envelope)
    return compile_rule_pack(pack, fact_registry=FactRegistry())


class TestR1SetOperatorMemberTyping:
    def test_intersects_int_member_on_str_set_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "intersects", "fact": "intent.purposes", "values": [1]},
                required_facts=["intent.purposes"],
            )

    def test_contains_all_int_member_on_str_set_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "contains_all", "fact": "intent.purposes", "values": [1]},
                required_facts=["intent.purposes"],
            )

    def test_intersects_bool_member_on_str_set_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "intersects", "fact": "intent.purposes", "values": [True]},
                required_facts=["intent.purposes"],
            )

    def test_intersects_all_str_members_still_accepted(self) -> None:
        compiled = _compile(
            {
                "op": "intersects",
                "fact": "intent.purposes",
                "values": ["TOURISM", "BUSINESS_MEETINGS"],
            },
            required_facts=["intent.purposes"],
        )
        assert compiled.rules[0].when.values == ("TOURISM", "BUSINESS_MEETINGS")

    def test_intersects_mixed_valid_and_invalid_members_rejected_naming_offender(self) -> None:
        with pytest.raises(RulePackCompilationError, match=r"1"):
            _compile(
                {"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM", 1]},
                required_facts=["intent.purposes"],
            )

    def test_in_bool_member_on_int_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "in", "fact": "intent.stay_days", "values": [True, 20]},
                required_facts=["intent.stay_days"],
            )

    def test_between_mixed_type_bounds_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "between", "fact": "intent.stay_days", "lower": 1, "upper": "30"},
                required_facts=["intent.stay_days"],
            )


class TestR2CanonicalDateForm:
    def test_compact_date_form_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {
                    "op": "gt",
                    "fact": "immigration.current_status_expiry",
                    "value": "20260101",
                },
                required_facts=["immigration.current_status_expiry"],
            )

    def test_iso_week_date_form_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {
                    "op": "gt",
                    "fact": "immigration.current_status_expiry",
                    "value": "2026-W01-1",
                },
                required_facts=["immigration.current_status_expiry"],
            )

    def test_canonical_date_form_accepted(self) -> None:
        compiled = _compile(
            {
                "op": "gt",
                "fact": "immigration.current_status_expiry",
                "value": "2026-01-01",
            },
            required_facts=["immigration.current_status_expiry"],
        )
        assert compiled.rules[0].when.value == "2026-01-01"

    def test_compact_date_rejected_inside_in_condition(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {
                    "op": "in",
                    "fact": "immigration.current_status_expiry",
                    "values": ["2026-01-01", "20260102"],
                },
                required_facts=["immigration.current_status_expiry"],
            )

    def test_week_date_rejected_inside_between_bounds(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {
                    "op": "between",
                    "fact": "immigration.current_status_expiry",
                    "lower": "2026-01-01",
                    "upper": "2026-W01-1",
                },
                required_facts=["immigration.current_status_expiry"],
            )


class TestR3UriRfc3986SchemeAndControlChars:
    def _record_with_url(self, url: str) -> SourceRecord:
        return SourceRecord(**source_record(canonical_url=url))

    def test_urn_with_raw_space_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._record_with_url("urn:bad value")

    def test_urn_isbn_accepted(self) -> None:
        record = self._record_with_url("urn:isbn:9780140328721")
        assert record.canonical_url == "urn:isbn:9780140328721"

    def test_mailto_accepted(self) -> None:
        record = self._record_with_url("mailto:a@b.com")
        assert record.canonical_url == "mailto:a@b.com"

    def test_https_accepted(self) -> None:
        record = self._record_with_url("https://example.com/source")
        assert record.canonical_url == "https://example.com/source"

    def test_uri_with_tab_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._record_with_url("https://example.com/\tsource")

    def test_uri_with_newline_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._record_with_url("https://example.com/\nsource")
