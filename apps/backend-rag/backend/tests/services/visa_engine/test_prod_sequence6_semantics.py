"""Semantic regressions for the unsigned production RulePack sequence 6.

These tests execute the real compiler and evaluator.  They deliberately avoid
searching the JSON text: a rule can be present yet unreachable, or a generic
rule can accidentally support a specialised product, and only evaluation
proves the public decision semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from backend.scripts.visa_engine.compile_pack import (
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.services.visa_engine.compiler import CompiledRulePack, build_compiled_pack
from backend.services.visa_engine.enums import DecisionState, Environment
from backend.services.visa_engine.evaluator import (
    DecisionIdentity,
    build_decision_identity,
    evaluate,
)
from backend.services.visa_engine.models import (
    ApplicantFacts,
    Candidate,
    Decision,
    RulePackRef,
)
from backend.tests.services.visa_engine._gold_fixtures import applicant_facts, known

PACK_PATH = (
    Path(__file__).resolve().parents[3]
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
    / "rulepack-prod-006.source.json"
)
OBSERVED_AT = datetime(2026, 8, 10, 0, 0, tzinfo=timezone.utc)
UU_6_2011_PRIMARY_SOURCE_ID = UUID("5a0d367b-bf64-535d-83e4-f40c45de2008")


@pytest.fixture(scope="module")
def compiled_pack() -> CompiledRulePack:
    payload = load_rule_pack_payload(PACK_PATH)
    unsigned_pack = wrap_as_unsigned_pack(payload, observed_at=OBSERVED_AT)
    return build_compiled_pack(unsigned_pack)


def _identity_provider(
    facts: ApplicantFacts,
    rule_pack_ref: RulePackRef,
    effective_at: datetime,
    _environment: Environment,
) -> DecisionIdentity:
    return build_decision_identity(
        facts,
        rule_pack_ref,
        effective_at,
        fingerprint_key=b"s" * 32,
        fingerprint_key_id="seq6-semantic-regression",
    )


def _evaluate(compiled_pack: CompiledRulePack, overrides: dict[str, dict]) -> Decision:
    return evaluate(
        applicant_facts(overrides=overrides),
        compiled_pack,
        effective_at=OBSERVED_AT,
        observed_at=OBSERVED_AT,
        identity_provider=_identity_provider,
    )


def _candidate(decision: Decision, product_code: str) -> Candidate:
    return next(
        candidate for candidate in decision.candidates if candidate.product_code == product_code
    )


def test_generic_employee_does_not_gain_special_routes_or_unverified_labor_claims(
    compiled_pack: CompiledRulePack,
) -> None:
    decision = _evaluate(
        compiled_pack,
        {
            "intent.purposes": known(["EMPLOYMENT"]),
            "work.employer_is_indonesian_entity": known(True),
            "work.indonesian_work_sponsor_confirmed": known(True),
        },
    )

    assert decision.state is DecisionState.SUPPORTED_CANDIDATES
    product_codes = {candidate.product_code for candidate in decision.candidates}
    assert "E23" in product_codes
    assert product_codes.isdisjoint({"E23U", "E23V"})

    e23 = _candidate(decision, "E23")
    assert set(e23.reason_codes).isdisjoint(
        {
            "REQUIRED_RPTKA_APPROVAL",
            "JABATAN_MUST_MATCH_KBLI",
            "PROHIBITED_HR_ROLES_KEPMENAKER_349_2019",
        }
    )


def test_generic_undergraduate_does_not_gain_kek_or_exchange_routes(
    compiled_pack: CompiledRulePack,
) -> None:
    decision = _evaluate(
        compiled_pack,
        {
            "intent.purposes": known(["STUDY"]),
            "study.level": known("UNDERGRADUATE"),
            "study.admission_confirmed": known(True),
            "study.sponsor_confirmed": known(True),
        },
    )

    assert decision.state is DecisionState.SUPPORTED_CANDIDATES
    product_codes = {candidate.product_code for candidate in decision.candidates}
    assert {"E30", "E30B"} <= product_codes
    assert product_codes.isdisjoint({"E30E", "E30F"})


def test_spouse_reasons_are_narrowly_grounded_in_uu_6_2011_articles_60_and_61(
    compiled_pack: CompiledRulePack,
) -> None:
    decision = _evaluate(
        compiled_pack,
        {
            "intent.purposes": known(["FAMILY"]),
            "family.relation_to_sponsor": known("SPOUSE"),
            "family.sponsor_nationalities": known(["ID"]),
            "family.marriage_registered": known(True),
            "process.wants_onshore_conversion": known(True),
        },
    )

    assert decision.state is DecisionState.SUPPORTED_CANDIDATES
    e31a = _candidate(decision, "E31A")
    assert {
        "SPOUSAL_WORK_ARTICLE_61_CONTEXT",
        "KITAP_TWO_YEAR_MARRIAGE_AND_INTEGRATION_NOT_VERIFIED",
    } <= set(e31a.reason_codes)
    assert set(e31a.reason_codes).isdisjoint(
        {"SPOUSAL_WORK_KEMENAKER_CAVEAT", "KITAP_CONVERSION_TWO_YEAR_DOOR"}
    )

    rules = {rule.rule_id: rule for rule in compiled_pack.rules}
    for rule_id in (
        "el.e31a-spousal-work-article-61",
        "el.e31a-kitap-prerequisites",
    ):
        assert rules[rule_id].source_refs == frozenset({UU_6_2011_PRIMARY_SOURCE_ID})

    source = next(
        record
        for record in compiled_pack.source_pack.payload.source_records
        if record.source_record_id == UU_6_2011_PRIMARY_SOURCE_ID
    )
    assert source.authority_type == "PRIMARY_LAW"
    assert source.document_number == "UU 6/2011"
    assert {locator.value for locator in source.locators} >= {
        "Pasal 60 ayat (2)",
        "Pasal 61",
    }
