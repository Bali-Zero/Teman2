"""E31-B01: a no-path decision caused by a GLOBAL hard filter lists only the
global causes, not other products' exclusions.

The defect: ``evaluate`` aggregated the exclusion reasons of every purpose-
feasible EXCLUDED product. A GLOBAL hard filter excludes every product, so the
list also carried the PRODUCTS-scoped filters of the products the applicant was
never shopping for (a Calling Visa passport holder asking for a spouse visa was
also told "must be under 18"). The cure takes "global" from the pack's own
marking (``rule.scope``), not from a list of codes; these tests read the same
marking back from the pack, so none of the expectations is a hard-coded code
list that could drift from the pack.

Acceptance is measured on the ACTIVE seq-29 pack; seq-28 (read-only, still on
disk) is the guilt witness because seq-29's E31E scoping already removed the
spouse leak, so on seq-29 alone the spouse cases cannot tell fixed from broken.
The remaining product-scoped leak on seq-29 (minor PARENT with sponsor not
confirmed) is the live witness.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import gold_coverage_eval
from backend.scripts.visa_engine.compile_pack import load_rule_pack_payload, wrap_as_unsigned_pack
from backend.scripts.visa_engine.gold_replay_driver import build_persona_request
from backend.services.visa_engine import compiler, evaluator
from backend.services.visa_engine.enums import DecisionState, RuleScope
from backend.tests.services.visa_engine.test_evaluator_gold import Persona

_PACKS_DIR = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts" / "packs"
)
_SEQ29 = _PACKS_DIR / "rulepack-prod-029.source.json"
_SEQ28 = _PACKS_DIR / "rulepack-prod-028.source.json"


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


def _pack(path: Path) -> tuple[Any, Any]:
    payload = load_rule_pack_payload(path)
    compiled = compiler.build_compiled_pack(wrap_as_unsigned_pack(payload))
    latest = max(rule.valid_period.from_ for rule in payload.rules)
    latest_read = max(record.verified_at for record in payload.source_records)
    return compiled, max(latest, latest_read) + timedelta(hours=12)


@pytest.fixture(scope="module")
def seq29() -> tuple[Any, Any]:
    return _pack(_SEQ29)


@pytest.fixture(scope="module")
def seq28() -> tuple[Any, Any]:
    return _pack(_SEQ28)


def _family(
    relation: str,
    *,
    nationality: str = "IT",
    birth_date: str = "2000-11-11",
    stay_days: int = 121,
    sponsor_confirmed: bool = True,
) -> dict[str, Any]:
    return {
        "person.birth_date": _known(birth_date),
        "person.nationalities": _known([nationality]),
        "person.marital_status": _known("SINGLE"),
        "immigration.currently_in_indonesia": _known(False),
        "immigration.current_status_code": _known("NO_STAY_PERMIT"),
        "immigration.overstay_days": _known(0),
        "immigration.violation_history": _known([]),
        "intent.purposes": _known(["FAMILY"]),
        "intent.stay_days": _known(stay_days),
        "family.relation_to_sponsor": _known(relation),
        "family.sponsor_nationalities": _known(["IT"]),
        "family.sponsor_status_code": _known("E23"),
        "family.marriage_registered": _known(True),
        "family.sponsor_confirmed": _known(sponsor_confirmed),
        "sponsor.type": _known("NONE"),
    }


def _decide(pack: tuple[Any, Any], overrides: dict[str, Any]) -> Any:
    compiled, as_of = pack
    persona = Persona(
        id=0,
        label="e31-b01",
        overrides=overrides,
        expected_state=DecisionState.NO_SUPPORTED_PATH,
    )
    request = build_persona_request(persona)
    return evaluator.evaluate(
        request.applicant_facts(),
        compiled,
        effective_at=as_of,
        observed_at=as_of,
        identity_provider=gold_coverage_eval._offline_identity_provider,
    )


def _codes(decision: Any) -> list[str]:
    assert decision.state is DecisionState.NO_SUPPORTED_PATH
    return [str(reason.code) for reason in decision.no_path_reasons]


def _scopes(compiled: Any) -> dict[str, RuleScope]:
    return {rule.rule_id: rule.scope for rule in compiled.rules}


class TestGlobalCauseListsOnlyGlobalCauses:
    def test_calling_visa_nationality_is_the_only_reason(self, seq29: tuple[Any, Any]) -> None:
        decision = _decide(seq29, _family("SPOUSE", nationality="NG"))
        assert _codes(decision) == ["CALLING_VISA_NATIONALITY_NOT_ASSESSED"]

    def test_indonesian_citizen_is_the_only_reason(self, seq29: tuple[Any, Any]) -> None:
        decision = _decide(seq29, _family("SPOUSE", nationality="ID"))
        assert _codes(decision) == ["APPLICANT_IS_INDONESIAN_CITIZEN"]

    def test_minor_parent_without_confirmed_sponsor_hides_the_parent_product_reason(
        self, seq29: tuple[Any, Any]
    ) -> None:
        decision = _decide(
            seq29, _family("PARENT", birth_date="2015-01-01", sponsor_confirmed=False)
        )
        assert _codes(decision) == ["MINOR_SPONSOR_NOT_CONFIRMED"]

    def test_a_global_cause_is_not_hidden_when_no_product_covers_the_purposes(
        self, seq29: tuple[Any, Any]
    ) -> None:
        """FAMILY+STUDY: no single product claims both purposes, so the
        purpose-feasible filter would leave nothing and fall back to the
        'no product covers the purposes' reason; the global cause must still win."""
        overrides = _family("SPOUSE", nationality="NG")
        overrides["intent.purposes"] = _known(["FAMILY", "STUDY"])
        assert _codes(_decide(seq29, overrides)) == ["CALLING_VISA_NATIONALITY_NOT_ASSESSED"]

    def test_two_global_causes_are_both_kept(self, seq29: tuple[Any, Any]) -> None:
        overrides = _family("SPOUSE", nationality="ID")
        overrides["person.nationalities"] = _known(["ID", "NG"])
        assert sorted(_codes(_decide(seq29, overrides))) == [
            "APPLICANT_IS_INDONESIAN_CITIZEN",
            "CALLING_VISA_NATIONALITY_NOT_ASSESSED",
        ]

    def test_every_listed_reason_comes_from_a_rule_the_pack_marks_global(
        self, seq29: tuple[Any, Any]
    ) -> None:
        scopes = _scopes(seq29[0])
        for overrides in (
            _family("SPOUSE", nationality="NG"),
            _family("SPOUSE", nationality="ID"),
            _family("PARENT", birth_date="2015-01-01", sponsor_confirmed=False),
        ):
            for reason in _decide(seq29, overrides).no_path_reasons:
                assert {scopes[rid] for rid in reason.rule_ids} == {RuleScope.GLOBAL}


class TestInnocence:
    def test_no_global_cause_keeps_the_no_product_covers_the_purposes_fallback(
        self, seq29: tuple[Any, Any]
    ) -> None:
        overrides = _family("SPOUSE")
        overrides["intent.purposes"] = _known(["FAMILY", "STUDY"])
        assert _codes(_decide(seq29, overrides)) == [
            "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES"
        ]

    def test_adult_parent_without_a_global_cause_keeps_its_product_reasons(
        self, seq29: tuple[Any, Any]
    ) -> None:
        """Measured on seq-29 (the E31E scoping leaves REQ_UNDER_18 on the PARENT
        products too, which is a pack matter and not this evaluator's): both are
        PRODUCTS-scoped, nothing global fired, so nothing may be filtered."""
        decision = _decide(seq29, _family("PARENT", stay_days=365))
        assert _codes(decision) == ["REQ_PARENT_SPONSOR_INDONESIAN", "REQ_UNDER_18"]
        scopes = _scopes(seq29[0])
        for reason in decision.no_path_reasons:
            assert {scopes[rid] for rid in reason.rule_ids} == {RuleScope.PRODUCTS}


class TestGuiltOnTheLeakingPack:
    def test_seq28_spouse_with_a_calling_visa_passport_lists_one_reason(
        self, seq28: tuple[Any, Any]
    ) -> None:
        """On seq-28 the spouse walk also carried REQ_UNDER_18 (E31E's filter,
        PRODUCTS-scoped): the pre-fix output was
        [CALLING_VISA_NATIONALITY_NOT_ASSESSED, REQ_UNDER_18]."""
        decision = _decide(seq28, _family("SPOUSE", nationality="NG"))
        assert _codes(decision) == ["CALLING_VISA_NATIONALITY_NOT_ASSESSED"]
