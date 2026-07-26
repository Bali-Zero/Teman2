"""Global state-precedence matrix (frozen, ``enums.DecisionState``'s own
docstring): HUMAN_REVIEW_REQUIRED > SUPPORTED_CANDIDATES > NEEDS_INPUT >
NO_SUPPORTED_PATH, proven two ways: (1) the original cascade — successively
removing the winning product from a single 4-product pack and observing the
outer assembly fall through to the next tier; (2) a full pairwise matrix
(gate round 1, 2026-07-19) isolating every one of the 10 unordered pairs
among the 5 per-product proof outcomes {REVIEW, SUPPORTED, BLOCKED_UNKNOWN,
EXCLUDED, UNSUPPORTED}, added because the cascade alone had encoded a WRONG
expectation (SUPPORTED beating REVIEW) that the gate caught — see
``TestStatePrecedenceCascade.test_review_wins_over_supported_when_both_
compete`` below.

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
from backend.services.visa_engine.compiler import build_compiled_pack
from backend.services.visa_engine.enums import DecisionState
from backend.services.visa_engine.evaluator import evaluate
from backend.tests.services.visa_engine import _builders as B
from backend.tests.services.visa_engine.conftest import make_applicant_facts

_EFFECTIVE_AT = datetime(2026, 7, 18, tzinfo=timezone.utc)

_SUPP_FACT = "work.employer_is_indonesian_entity"
_REV_FACT = "work.serves_indonesian_clients"
_REV_ELIGIBILITY_FACT = "work.indonesia_source_compensation"
_BLK_FACT = "study.admission_confirmed"
_EXC_FACT = "work.indonesian_work_sponsor_confirmed"
_EXC_ELIGIBILITY_FACT = "investment.pt_pma_committed"


def _four_product_pack():
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
            # A dedicated, independently-controllable fact (gate round 1,
            # 2026-07-19 — the original `intersects(intent.purposes,
            # ["TOURISM"])` was ALWAYS true given this fixture's fixed
            # purposes fact, so EXC's "not excluded" fate could only ever be
            # SUPPORTED, never UNSUPPORTED — the new full pairwise matrix
            # needs EXC to reach a clean UNSUPPORTED baseline when not
            # excluded, to isolate EXCLUDED-vs-{BLOCKED_UNKNOWN,UNSUPPORTED}
            # pairs without an accidental extra SUPPORTED competitor). Not a
            # `commercial.*` fact — the compiler's own
            # COMMERCIAL_FACT_IN_LEGAL_STAGE invariant bars those from
            # ELIGIBILITY rules (ranking-only, spec §4.4).
            when={"op": "eq", "fact": _EXC_ELIGIBILITY_FACT, "value": True},
            effect={
                "type": "SUPPORT",
                "reason_code": "EXC_ELIGIBLE",
                "covered_purposes": ["TOURISM"],
            },
            source_id=source_id,
            required_facts=[_EXC_ELIGIBILITY_FACT],
        ),
    ]

    payload = B.rule_pack_payload(rules=rules, products=products, source_records=[src])
    envelope = B.rule_pack_envelope(payload)
    pack = M.RulePack.model_validate(envelope)
    return build_compiled_pack(pack)


@pytest.fixture(scope="module")
def compiled_pack():
    return _four_product_pack()


def _facts(overrides: dict) -> M.ApplicantFacts:
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


def _known(value):
    return {"status": "KNOWN", "value": value}


def _unknown(reason: str = "NOT_PROVIDED"):
    return {"status": "UNKNOWN", "reason": reason}


class TestStatePrecedenceCascade:
    """Every step keeps the PREVIOUS winner's disqualifying fact and only
    flips the current tier's product to prove precedence, not coincidence."""

    def test_review_wins_over_supported_blocked_and_excluded(self, compiled_pack) -> None:
        """Gate round 1 P0-B fix (2026-07-19, Codex gate on PR5): the WRONG
        expectation this test previously encoded — asserting
        SUPPORTED_CANDIDATES here — is exactly the bug the gate caught.
        Frozen precedence (``enums.DecisionState``'s own docstring) ranks
        HUMAN_REVIEW_REQUIRED above SUPPORTED_CANDIDATES UNCONDITIONALLY, not
        only when the review trigger happens to be GLOBAL — REV here is a
        PRODUCTS-scoped review rule on a DIFFERENT product than the one that
        is genuinely SUPPORTED (SUPP), and REVIEW must still win the whole
        decision.
        """
        facts = _facts(
            {
                _SUPP_FACT: _known(True),  # SUPP -> SUPPORTED
                _REV_FACT: _known(True),  # REV -> REVIEW
                _BLK_FACT: _unknown(),  # BLK -> BLOCKED_UNKNOWN
                _EXC_FACT: _known(True),  # EXC -> EXCLUDED
            }
        )
        decision = evaluate(
            facts, compiled_pack, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT
        )
        assert decision.state is DecisionState.HUMAN_REVIEW_REQUIRED
        assert [r.code for r in decision.review_reasons] == ["REV_REVIEW"]
        assert decision.candidates == ()

    def test_review_wins_over_blocked_and_excluded_when_nothing_supported(
        self, compiled_pack
    ) -> None:
        facts = _facts(
            {
                _SUPP_FACT: _known(False),  # SUPP -> UNSUPPORTED
                _REV_FACT: _known(True),  # REV -> REVIEW
                _BLK_FACT: _unknown(),  # BLK -> BLOCKED_UNKNOWN
                _EXC_FACT: _known(True),  # EXC -> EXCLUDED
            }
        )
        decision = evaluate(
            facts, compiled_pack, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT
        )
        assert decision.state is DecisionState.HUMAN_REVIEW_REQUIRED
        assert [r.code for r in decision.review_reasons] == ["REV_REVIEW"]

    def test_needs_input_wins_over_excluded_when_nothing_supported_or_reviewed(
        self, compiled_pack
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
            facts, compiled_pack, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT
        )
        assert decision.state is DecisionState.NEEDS_INPUT
        assert tuple(m.value for m in decision.missing_facts) == (_BLK_FACT,)

    def test_no_supported_path_is_the_floor(self, compiled_pack) -> None:
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
            facts, compiled_pack, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT
        )
        assert decision.state is DecisionState.NO_SUPPORTED_PATH
        assert [r.code for r in decision.no_path_reasons] == ["EXC_EXCLUDED"]
        assert decision.candidates == ()


#: Every product forced to UNSUPPORTED — the weakest, most inert per-product
#: status — so a pairwise-matrix case can override ONLY the two products
#: under test without an unintended third competitor. `_EXC_ELIGIBILITY_FACT`
#: neutral is REQUIRED (not merely convenient): left at its
#: ``make_applicant_facts()`` UNKNOWN default, `exc.eligibility`'s condition
#: would itself be UNKNOWN whenever `_EXC_FACT` is False, pushing EXC to
#: BLOCKED_UNKNOWN instead of the clean UNSUPPORTED baseline this matrix
#: needs.
_NEUTRAL_UNSUPPORTED_FACTS = {
    _SUPP_FACT: _known(False),
    _REV_FACT: _known(False),
    _REV_ELIGIBILITY_FACT: _known(False),
    _BLK_FACT: _known(False),
    _EXC_FACT: _known(False),
    _EXC_ELIGIBILITY_FACT: _known(False),
}


def _pairwise_facts(overrides: dict) -> M.ApplicantFacts:
    merged = dict(_NEUTRAL_UNSUPPORTED_FACTS)
    merged.update(overrides)
    return _facts(merged)


# Every one of the 10 unordered pairs among the 5 per-product proof outcomes
# {REVIEW, SUPPORTED, BLOCKED_UNKNOWN, EXCLUDED, UNSUPPORTED}, isolated (only
# the two products under test flip away from the neutral UNSUPPORTED
# baseline), asserting the frozen precedence order wins regardless of which
# concrete products carry which status.
_PAIRWISE_CASES: tuple[tuple[str, dict, DecisionState], ...] = (
    (
        "REVIEW(REV) vs SUPPORTED(SUPP)",
        {_REV_FACT: _known(True), _SUPP_FACT: _known(True)},
        DecisionState.HUMAN_REVIEW_REQUIRED,
    ),
    (
        "REVIEW(REV) vs BLOCKED_UNKNOWN(BLK)",
        {_REV_FACT: _known(True), _BLK_FACT: _unknown()},
        DecisionState.HUMAN_REVIEW_REQUIRED,
    ),
    (
        "REVIEW(REV) vs EXCLUDED(EXC)",
        {_REV_FACT: _known(True), _EXC_FACT: _known(True)},
        DecisionState.HUMAN_REVIEW_REQUIRED,
    ),
    (
        "REVIEW(REV) vs UNSUPPORTED(SUPP)",
        {_REV_FACT: _known(True)},
        DecisionState.HUMAN_REVIEW_REQUIRED,
    ),
    (
        "SUPPORTED(SUPP) vs BLOCKED_UNKNOWN(BLK)",
        {_SUPP_FACT: _known(True), _BLK_FACT: _unknown()},
        DecisionState.SUPPORTED_CANDIDATES,
    ),
    (
        "SUPPORTED(SUPP) vs EXCLUDED(EXC)",
        {_SUPP_FACT: _known(True), _EXC_FACT: _known(True)},
        DecisionState.SUPPORTED_CANDIDATES,
    ),
    (
        "SUPPORTED(SUPP) vs UNSUPPORTED(REV)",
        {_SUPP_FACT: _known(True)},
        DecisionState.SUPPORTED_CANDIDATES,
    ),
    (
        "BLOCKED_UNKNOWN(BLK) vs EXCLUDED(EXC)",
        {_BLK_FACT: _unknown(), _EXC_FACT: _known(True)},
        DecisionState.NEEDS_INPUT,
    ),
    (
        "BLOCKED_UNKNOWN(BLK) vs UNSUPPORTED(SUPP)",
        {_BLK_FACT: _unknown()},
        DecisionState.NEEDS_INPUT,
    ),
    (
        "EXCLUDED(EXC) vs UNSUPPORTED(SUPP)",
        {_EXC_FACT: _known(True)},
        DecisionState.NO_SUPPORTED_PATH,
    ),
)


class TestFullPairwisePrecedenceMatrix:
    """Gate round 1 (2026-07-19): the cascade above proves the chain
    transitively but never isolates each pair on its own — this is the
    literal "all pairwise combinations of per-product proof outcomes" the
    gate asked for, using the frozen precedence order
    (``enums.DecisionState``'s own docstring) as ground truth for every one
    of the 10 unordered pairs among the 5 possible per-product statuses.
    """

    @pytest.mark.parametrize(
        "label,overrides,expected_state",
        _PAIRWISE_CASES,
        ids=[case[0] for case in _PAIRWISE_CASES],
    )
    def test_pair(
        self, compiled_pack, label: str, overrides: dict, expected_state: DecisionState
    ) -> None:
        facts = _pairwise_facts(overrides)
        decision = evaluate(
            facts, compiled_pack, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT
        )
        assert decision.state is expected_state, (
            f"{label}: expected {expected_state}, got {decision.state}"
        )
