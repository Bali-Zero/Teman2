"""UNKNOWN-never-increases-eligibility truth-table tests (task TDD item #2).

For each stage (HARD_FILTER / HUMAN_REVIEW / ELIGIBILITY), a single boolean
fact drives that stage's only rule of interest, with a baseline ELIGIBILITY
rule (``intersects(intent.purposes, ["TOURISM"])``, always TRUE given the
fixed ``purposes`` fact) present whenever the stage under test is NOT
ELIGIBILITY itself, so the "nothing blocks it" case can prove the product
reaches SUPPORTED normally.

Per stage, three fact states are asserted (guilt AND innocence in one
table):

- ``KNOWN=True`` -> the stage's real effect fires (guilt: not vacuous).
- ``KNOWN=False`` -> the effect does NOT fire; downstream stages run
  normally (innocence: a definite FALSE never over-blocks).
- ``UNKNOWN`` -> the product is deferred to ``BLOCKED_UNKNOWN`` — NEVER
  ``SUPPORTED`` (an UNKNOWN standing in for TRUE would wrongly grant
  eligibility/skip review/skip exclusion; an UNKNOWN standing in for FALSE
  would wrongly let the product straight through). This is the exact
  property the task brief names: "an UNKNOWN that would make a product
  SUPPORTED must instead block/defer".
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.services.visa_engine import models as M
from backend.services.visa_engine.compiler import build_compiled_pack
from backend.services.visa_engine.enums import FactPath
from backend.services.visa_engine.evaluator import ProductProofStatus, evaluate_product
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.tests.services.visa_engine import _builders as B
from backend.tests.services.visa_engine.conftest import make_applicant_facts

_EFFECTIVE_AT = datetime(2026, 7, 18, tzinfo=timezone.utc)

_UNDER_TEST_FACT = "work.employer_is_indonesian_entity"
_BASELINE_ELIGIBILITY = {
    "op": "intersects",
    "fact": "intent.purposes",
    "values": ["TOURISM"],
}


def _applicant_facts(fact_value: bool | None) -> M.ApplicantFacts:
    base = make_applicant_facts()
    data = base.facts.model_dump(by_alias=True, mode="json")
    data["intent.purposes"] = {"status": "KNOWN", "value": ["TOURISM"]}
    if fact_value is None:
        data[_UNDER_TEST_FACT] = {"status": "UNKNOWN", "reason": "NOT_PROVIDED"}
    else:
        data[_UNDER_TEST_FACT] = {"status": "KNOWN", "value": fact_value}
    return M.ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=base.assessment_id,
        collected_at=base.collected_at,
        facts=data,
    )


def _build_pack(*, stage_under_test: str):
    source_id = B.new_uuid()
    product_id = B.new_uuid()
    src = B.source_record(source_id=source_id)
    prod = B.product(product_id=product_id, source_id=source_id, covered_purposes=["TOURISM"])

    when = {"op": "eq", "fact": _UNDER_TEST_FACT, "value": True}
    rules = []

    if stage_under_test == "HARD_FILTER":
        rules.append(
            B.rule(
                rule_id="under-test",
                stage="HARD_FILTER",
                scope="GLOBAL",
                when=when,
                effect={"type": "EXCLUDE", "reason_code": "TEST_EXCLUDE"},
                source_id=source_id,
                required_facts=[_UNDER_TEST_FACT],
            )
        )
    elif stage_under_test == "HUMAN_REVIEW":
        rules.append(
            B.rule(
                rule_id="under-test",
                stage="HUMAN_REVIEW",
                scope="GLOBAL",
                when=when,
                effect={"type": "REQUIRE_REVIEW", "reason_code": "TEST_REVIEW"},
                source_id=source_id,
                required_facts=[_UNDER_TEST_FACT],
            )
        )
    else:
        assert stage_under_test == "ELIGIBILITY"

    if stage_under_test == "ELIGIBILITY":
        rules.append(
            B.rule(
                rule_id="under-test",
                stage="ELIGIBILITY",
                scope="PRODUCTS",
                product_version_ids=[str(product_id)],
                when=when,
                effect={
                    "type": "SUPPORT",
                    "reason_code": "TEST_SUPPORT",
                    "covered_purposes": ["TOURISM"],
                },
                source_id=source_id,
                required_facts=[_UNDER_TEST_FACT],
            )
        )
    else:
        rules.append(
            B.rule(
                rule_id="baseline-eligibility",
                stage="ELIGIBILITY",
                scope="PRODUCTS",
                product_version_ids=[str(product_id)],
                when=_BASELINE_ELIGIBILITY,
                effect={
                    "type": "SUPPORT",
                    "reason_code": "BASELINE_SUPPORT",
                    "covered_purposes": ["TOURISM"],
                },
                source_id=source_id,
                required_facts=["intent.purposes"],
            )
        )

    payload = B.rule_pack_payload(rules=rules, products=[prod], source_records=[src])
    envelope = B.rule_pack_envelope(payload)
    pack = M.RulePack.model_validate(envelope)
    return build_compiled_pack(pack), product_id


def _proof_for(stage_under_test: str, fact_value: bool | None):
    compiled, product_id = _build_pack(stage_under_test=stage_under_test)
    facts = _applicant_facts(fact_value)
    snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=_EFFECTIVE_AT)
    (product,) = [p for p in compiled.products if str(p.product_version_id) == product_id]
    rules = compiled.rules_for(product, effective_at=_EFFECTIVE_AT)
    return evaluate_product(
        product=product,
        rules=rules,
        facts=snapshot,
        purposes=frozenset({"TOURISM"}),
    )


class TestHardFilterNeverUpgradesOnUnknown:
    def test_known_true_excludes(self) -> None:
        proof = _proof_for("HARD_FILTER", True)
        assert proof.status is ProductProofStatus.EXCLUDED
        assert [r.code for r in proof.reasons] == ["TEST_EXCLUDE"]

    def test_known_false_proceeds_to_supported(self) -> None:
        proof = _proof_for("HARD_FILTER", False)
        assert proof.status is ProductProofStatus.SUPPORTED

    def test_unknown_never_upgrades_to_supported_or_excluded(self) -> None:
        proof = _proof_for("HARD_FILTER", None)
        assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert FactPath(_UNDER_TEST_FACT) in proof.missing_facts


class TestHumanReviewNeverUpgradesOnUnknown:
    def test_known_true_triggers_review(self) -> None:
        proof = _proof_for("HUMAN_REVIEW", True)
        assert proof.status is ProductProofStatus.REVIEW
        assert [r.code for r in proof.reasons] == ["TEST_REVIEW"]

    def test_known_false_proceeds_to_supported(self) -> None:
        proof = _proof_for("HUMAN_REVIEW", False)
        assert proof.status is ProductProofStatus.SUPPORTED

    def test_unknown_never_upgrades_to_supported_or_review(self) -> None:
        proof = _proof_for("HUMAN_REVIEW", None)
        assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert FactPath(_UNDER_TEST_FACT) in proof.missing_facts


class TestEligibilityNeverUpgradesOnUnknown:
    """The core guilt case named verbatim by the task brief: "an UNKNOWN
    that would make a product SUPPORTED must instead block/defer"."""

    def test_known_true_supports(self) -> None:
        proof = _proof_for("ELIGIBILITY", True)
        assert proof.status is ProductProofStatus.SUPPORTED
        assert proof.covered_purposes == frozenset({"TOURISM"})

    def test_known_false_is_unsupported(self) -> None:
        proof = _proof_for("ELIGIBILITY", False)
        assert proof.status is ProductProofStatus.UNSUPPORTED
        assert proof.missing_purposes == frozenset({"TOURISM"})

    def test_unknown_blocks_never_supports(self) -> None:
        proof = _proof_for("ELIGIBILITY", None)
        assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert proof.status is not ProductProofStatus.SUPPORTED
        assert FactPath(_UNDER_TEST_FACT) in proof.missing_facts
