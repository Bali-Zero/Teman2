"""Global state-precedence matrix (spec §4.3): HUMAN_REVIEW_REQUIRED >
SUPPORTED_CANDIDATES > NEEDS_INPUT > NO_SUPPORTED_PATH, proven by
successively removing the winning product from a single 4-product pack and
observing the outer assembly fall through to the next tier.

One pack, one applicant, four products (SUPP/REV/BLK/EXC) all covering the
SAME single purpose (TOURISM) so any of them COULD be the sole candidate —
each product's fate is driven by its own dedicated fact, independent of the
others, so a single fact flip moves exactly one product between statuses
without disturbing the rest.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.services.visa_engine import models as M
from backend.services.visa_engine.compiler import CompiledRulePack, build_compiled_pack
from backend.services.visa_engine.enums import DecisionState
from backend.services.visa_engine.evaluator import evaluate
from backend.tests.services.visa_engine import _builders as B
from backend.tests.services.visa_engine.conftest import make_applicant_facts

_EFFECTIVE_AT = datetime(2026, 7, 18, tzinfo=timezone.utc)
_TEST_HMAC_KEY = b"visa-evaluator-test-key-material-32b"
_TEST_KEY_ID = "test-evaluator-v1"

_SUPP_FACT = "work.employer_is_indonesian_entity"
_REV_FACT = "work.serves_indonesian_clients"
_REV_ELIGIBILITY_FACT = "work.indonesia_source_compensation"
_BLK_FACT = "study.admission_confirmed"
_EXC_FACT = "work.indonesian_work_sponsor_confirmed"


def _four_product_pack() -> CompiledRulePack:
    source_id = B.new_uuid()
    ids = {code: B.new_uuid() for code in ("SUPP", "REV", "BLK", "EXC")}
    src = B.source_record(source_id=source_id)
    products = [
        B.product(
            product_id=ids[code],
            source_id=source_id,
            product_code=code,
            covered_purposes=["TOURISM"],
        )
        for code in ids
    ]

    rules = [
        B.rule(
            rule_id="supp.eligibility",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[ids["SUPP"]],
            when={"op": "eq", "fact": _SUPP_FACT, "value": True},
            effect={
                "type": "SUPPORT",
                "reason_code": "SUPP_ELIGIBLE",
                "covered_purposes": ["TOURISM"],
            },
            source_id=source_id,
            required_facts=[_SUPP_FACT],
        ),
        B.rule(
            rule_id="rev.review",
            stage="HUMAN_REVIEW",
            scope="PRODUCTS",
            product_version_ids=[ids["REV"]],
            when={"op": "eq", "fact": _REV_FACT, "value": True},
            effect={"type": "REQUIRE_REVIEW", "reason_code": "REV_REVIEW"},
            source_id=source_id,
            required_facts=[_REV_FACT],
        ),
        B.rule(
            rule_id="rev.eligibility",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[ids["REV"]],
            when={"op": "eq", "fact": _REV_ELIGIBILITY_FACT, "value": True},
            effect={
                "type": "SUPPORT",
                "reason_code": "REV_ELIGIBLE",
                "covered_purposes": ["TOURISM"],
            },
            source_id=source_id,
            required_facts=[_REV_ELIGIBILITY_FACT],
        ),
        B.rule(
            rule_id="blk.eligibility",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[ids["BLK"]],
            when={"op": "eq", "fact": _BLK_FACT, "value": True},
            effect={
                "type": "SUPPORT",
                "reason_code": "BLK_ELIGIBLE",
                "covered_purposes": ["TOURISM"],
            },
            source_id=source_id,
            required_facts=[_BLK_FACT],
        ),
        B.rule(
            rule_id="exc.hard-filter",
            stage="HARD_FILTER",
            scope="PRODUCTS",
            product_version_ids=[ids["EXC"]],
            when={"op": "eq", "fact": _EXC_FACT, "value": True},
            effect={"type": "EXCLUDE", "reason_code": "EXC_EXCLUDED"},
            source_id=source_id,
            required_facts=[_EXC_FACT],
        ),
        B.rule(
            rule_id="exc.eligibility",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[ids["EXC"]],
            # `intersects` (a real comparison, not a bare presence op) so the
            # compiler's `_check_eligibility_not_presence_only` invariant
            # accepts it; never actually reached in a case where EXC is
            # excluded — only relevant in the final cascade step where EXC is
            # evaluated for UNSUPPORTED-vs-EXCLUDED bookkeeping.
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={
                "type": "SUPPORT",
                "reason_code": "EXC_ELIGIBLE",
                "covered_purposes": ["TOURISM"],
            },
            source_id=source_id,
            required_facts=["intent.purposes"],
        ),
    ]

    payload = B.rule_pack_payload(rules=rules, products=products, source_records=[src])
    envelope = B.rule_pack_envelope(payload)
    pack = M.RulePack.model_validate(envelope)
    return build_compiled_pack(pack)


@pytest.fixture(scope="module")
def compiled_pack() -> CompiledRulePack:
    return _four_product_pack()


def _facts(overrides: dict[str, object]) -> M.ApplicantFacts:
    base = make_applicant_facts()
    data = base.facts.model_dump(by_alias=True, mode="json")
    data["intent.purposes"] = {"status": "KNOWN", "value": ["TOURISM"]}
    data.update(overrides)
    return M.ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=base.assessment_id,
        collected_at=base.collected_at,
        facts=data,
    )


def _known(value: object) -> dict[str, object]:
    return {"status": "KNOWN", "value": value}


def _unknown(reason: str = "NOT_PROVIDED") -> dict[str, object]:
    return {"status": "UNKNOWN", "reason": reason}


class TestStatePrecedenceCascade:
    """Every step keeps the PREVIOUS winner's disqualifying fact and only
    flips the current tier's product to prove precedence, not coincidence."""

    def test_review_wins_over_supported_blocked_and_excluded(
        self, compiled_pack: CompiledRulePack
    ) -> None:
        facts = _facts(
            {
                _SUPP_FACT: _known(True),  # SUPP -> SUPPORTED
                _REV_FACT: _known(True),  # REV -> REVIEW
                _BLK_FACT: _unknown(),  # BLK -> BLOCKED_UNKNOWN
                _EXC_FACT: _known(True),  # EXC -> EXCLUDED
            }
        )
        decision = evaluate(
            facts,
            compiled_pack,
            effective_at=_EFFECTIVE_AT,
            observed_at=_EFFECTIVE_AT,
            fingerprint_hmac_key=_TEST_HMAC_KEY,
            fingerprint_key_id=_TEST_KEY_ID,
        )
        assert decision.state is DecisionState.HUMAN_REVIEW_REQUIRED
        assert [r.code for r in decision.review_reasons] == ["REV_REVIEW"]

    def test_supported_wins_over_blocked_and_excluded_when_nothing_needs_review(
        self, compiled_pack: CompiledRulePack
    ) -> None:
        facts = _facts(
            {
                _SUPP_FACT: _known(True),  # SUPP -> SUPPORTED
                _REV_FACT: _known(False),  # REV review silent
                _REV_ELIGIBILITY_FACT: _known(False),  # REV -> UNSUPPORTED
                _BLK_FACT: _unknown(),  # BLK -> BLOCKED_UNKNOWN
                _EXC_FACT: _known(True),  # EXC -> EXCLUDED
            }
        )
        decision = evaluate(
            facts,
            compiled_pack,
            effective_at=_EFFECTIVE_AT,
            observed_at=_EFFECTIVE_AT,
            fingerprint_hmac_key=_TEST_HMAC_KEY,
            fingerprint_key_id=_TEST_KEY_ID,
        )
        assert decision.state is DecisionState.SUPPORTED_CANDIDATES
        assert [c.product_code for c in decision.candidates] == ["SUPP"]

    def test_needs_input_wins_over_excluded_when_nothing_supported_or_reviewed(
        self, compiled_pack: CompiledRulePack
    ) -> None:
        facts = _facts(
            {
                _SUPP_FACT: _known(False),  # SUPP -> UNSUPPORTED
                _REV_FACT: _known(False),  # REV review silent
                _REV_ELIGIBILITY_FACT: _known(
                    False
                ),  # REV -> UNSUPPORTED (not accidentally SUPPORTED)
                _BLK_FACT: _unknown(),  # BLK -> BLOCKED_UNKNOWN
                _EXC_FACT: _known(True),  # EXC -> EXCLUDED
            }
        )
        decision = evaluate(
            facts,
            compiled_pack,
            effective_at=_EFFECTIVE_AT,
            observed_at=_EFFECTIVE_AT,
            fingerprint_hmac_key=_TEST_HMAC_KEY,
            fingerprint_key_id=_TEST_KEY_ID,
        )
        assert decision.state is DecisionState.NEEDS_INPUT
        assert tuple(m.value for m in decision.missing_facts) == (_BLK_FACT,)

    def test_no_supported_path_is_the_floor(self, compiled_pack: CompiledRulePack) -> None:
        facts = _facts(
            {
                _SUPP_FACT: _known(False),  # SUPP -> UNSUPPORTED
                _REV_FACT: _known(False),
                _REV_ELIGIBILITY_FACT: _known(False),  # REV -> UNSUPPORTED
                _BLK_FACT: _known(False),  # BLK -> UNSUPPORTED (definite now, not unknown)
                _EXC_FACT: _known(True),  # EXC -> EXCLUDED (the only named reason left)
            }
        )
        decision = evaluate(
            facts,
            compiled_pack,
            effective_at=_EFFECTIVE_AT,
            observed_at=_EFFECTIVE_AT,
            fingerprint_hmac_key=_TEST_HMAC_KEY,
            fingerprint_key_id=_TEST_KEY_ID,
        )
        assert decision.state is DecisionState.NO_SUPPORTED_PATH
        assert [r.code for r in decision.no_path_reasons] == ["EXC_EXCLUDED"]
        assert decision.candidates == ()
