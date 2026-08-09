"""The seq-6 refuter's witnesses, pinned as tests.

Every case here is a concrete failure a cross-family adversarial seat (gpt-5.6-sol,
xhigh, read-only) NAMED against draft 2 of `rulepack-prod-006.source.json` on
2026-08-10, verdict DO-NOT-SHIP. Draft 2's own review was the in-house
`devils-advocate` agent, pinned `model: sonnet` — the same family as the generator —
and it passed the pack that the cross-family seat rejected. That is the reason these
live in the repo instead of in a scratch script: the claims about this pack were
previously only reproducible by the person who made them.

The disease each one pins is the same one, seen from four sides: a rule that reads a
fact which genuinely DISQUALIFIES one product has three possible homes, and two of
them are wrong.

  * ``HUMAN_REVIEW``  — walls the WHOLE answer (evaluator returns
    ``HUMAN_REVIEW_REQUIRED`` with no candidates the moment one product proves
    review), so a single unrelated product deletes the other 37.
  * ``SUPPORT``       — asserts an eligibility the fact denies. Eligibility coverage
    is a UNION, so a requirement true for everyone with the purpose carries the
    product on its own.
  * ``HARD_FILTER``   — removes that product and leaves the rest standing. Correct.

W2 is the one worth reading twice: it is asserted with the age declared UNKNOWN, not
with the key deleted. The fixture ships no default birth date, so a deleted key is an
ABSENT fact, which the engine answers with ``NO_SUPPORTED_PATH`` and no question —
a different (and still open) behaviour. Asserting the deleted-key variant would have
passed for a reason unrelated to the cure.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.scripts.visa_engine.compile_pack import (
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.services.visa_engine import compiler, evaluator
from backend.services.visa_engine.evaluator import build_decision_identity
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.tests.services.visa_engine import _gold_fixtures as gf

PACKS = Path(__file__).resolve().parents[3] / "services/visa_engine/contracts/packs"

# prod-005's valid_period opens 2026-07-25 and E33G is born 2026-07-24. An earlier
# version of this measurement ran at the gold fixtures' 2026-07-17 and every product
# was filtered out on the clock alone, so both packs answered NO_SUPPORTED_PATH and
# the comparison measured the calendar rather than the packs.
AT = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)


def _known(value):
    return {"status": "KNOWN", "value": value}


def _unknown():
    return {"status": "UNKNOWN", "reason": "NOT_ASKED"}


def _identity(facts, rule_pack_ref, effective_at, _environment):
    return build_decision_identity(
        facts,
        rule_pack_ref,
        effective_at,
        fingerprint_key=b"seq6-witness-non-secret-test-key",
        fingerprint_key_id="seq6-witness-test",
    )


def _load(name: str):
    payload = load_rule_pack_payload(PACKS / name)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture(scope="module")
def seq6():
    return _load("rulepack-prod-006.source.json")


@pytest.fixture(scope="module")
def seq5():
    return _load("rulepack-prod-005.source.json")


def _decide(compiled, overrides):
    return evaluator.evaluate(
        gf.applicant_facts(overrides=overrides),
        compiled,
        effective_at=AT,
        observed_at=AT,
        identity_provider=_identity,
    )


def _offers(compiled, decision) -> list[str]:
    codes = {p.product_version_id: p.product_code for p in compiled.products}
    return sorted(codes.get(c.product_version_id, "?") for c in decision.candidates)


RETIREE_46 = {
    "person.birth_date": _known("1980-01-01"),
    "intent.purposes": _known(["RETIREMENT"]),
    "intent.stay_days": _known(300),
    "secondhome.passive_monthly_income_usd": _known(3000),
    "family.sponsor_confirmed": _known(True),
}

ENGINEER = {
    "person.birth_date": _known("1990-01-01"),
    "intent.purposes": _known(["EMPLOYMENT"]),
    "intent.stay_days": _known(300),
    "work.indonesian_work_sponsor_confirmed": _known(True),
    "work.employer_is_indonesian_entity": _known(True),
}

MINOR_STUDENT = {
    "person.birth_date": _known("2010-01-01"),
    "intent.purposes": _known(["STUDY"]),
    "intent.stay_days": _known(300),
    "study.level": _known("SECONDARY"),
    "study.sponsor_confirmed": _known(True),
    "family.sponsor_confirmed": _known(True),
}

INVESTOR_400_DAYS = {
    "person.birth_date": _known("1985-01-01"),
    "intent.purposes": _known(["INVESTMENT"]),
    "intent.stay_days": _known(400),
    "investment.pt_pma_committed": _known(False),
}

# Zero's own applicant from the 2026-08-09 production test: nothing Indonesian
# anywhere. seq-5 answered him with a blank wall, which is what started all of this.
REMOTE_WORKER = {
    "person.nationalities": _known(["AL"]),
    "person.birth_date": _known("1987-07-01"),
    "intent.purposes": _known(["REMOTE_WORK"]),
    "intent.stay_days": _known(70),
    "work.employer_is_indonesian_entity": _known(False),
    "work.employer_country_code": _known("AL"),
    "work.indonesia_source_compensation": _known(False),
    "work.serves_indonesian_clients": _known(False),
    "investment.pt_pma_committed": _known(False),
}


def test_under_age_retiree_is_not_offered_the_retirement_kitas(seq6):
    """E33F's statutory floor is 55. Draft 2 offered it to a 46-year-old because the
    age rule had become SUPPORT and the product's gate reads income and sponsor only."""
    decision = _decide(seq6, RETIREE_46)
    assert "E33F" not in _offers(seq6, decision)


def test_unknown_age_asks_instead_of_offering(seq6):
    """The second half of the same finding: with the age not established, draft 2
    offered E33F without ever asking. The HARD_FILTER's on_unknown=NEEDS_INPUT is
    what turns that into a question."""
    decision = _decide(seq6, dict(RETIREE_46, **{"person.birth_date": _unknown()}))
    assert "E33F" not in _offers(seq6, decision)
    assert "person.birth_date" in {f.value for f in decision.missing_facts}


def test_deleting_the_age_key_is_not_the_same_as_declaring_it_unknown(seq6):
    """Pins the distinction the test above depends on. If this ever starts matching
    the UNKNOWN case, the assertion above stops being about the cure."""
    base = json.loads(gf.applicant_facts(overrides={}).model_dump_json())
    assert "person.birth_date" not in base["facts"], (
        "the fixture gained a default birth date — test_unknown_age_asks_instead_of_"
        "offering is now vacuous unless it keeps setting the fact explicitly"
    )


def test_ordinary_employee_is_not_offered_the_diplomatic_or_trade_office_routes(seq6):
    """E23U (a diplomat's household assistant) and E23V (a trade/economic office
    posting) have no distinguishing fact in the contract. Draft 2 offered both to any
    engineer with a confirmed Indonesian sponsor; seq-6 takes them out of reach."""
    decision = _decide(seq6, ENGINEER)
    offered = set(_offers(seq6, decision))
    assert not offered & {"E23U", "E23V"}
    assert "E23" in offered, "the ordinary employment route must survive the removal"


def test_a_compliant_minor_is_not_walled_out_of_the_whole_answer(seq6):
    """hr.e30a-minor-consent fires on STUDY and being a minor; it never tests consent
    or a guardian. Because one product's review deletes every candidate, a 16-year-old
    with admission, a study sponsor and a confirmed guardian got a blank answer."""
    decision = _decide(seq6, MINOR_STUDENT)
    assert decision.state.value != "HUMAN_REVIEW_REQUIRED"


def test_a_stay_longer_than_the_product_allows_removes_that_product(seq6):
    """D12 caps at 180 days. Draft 2 conjoined the >365-day review with that cap,
    producing a rule that can never be true — the signal was not moved, it was lost."""
    decision = _decide(seq6, INVESTOR_400_DAYS)
    assert "D12" not in _offers(seq6, decision)


def test_the_case_that_started_this_still_gets_an_option(seq5, seq6):
    """The regression guard. A cure that fixes false offers by walling more people is
    not a cure — this is the applicant seq-5 answered with nothing."""
    before = _decide(seq5, REMOTE_WORKER)
    after = _decide(seq6, REMOTE_WORKER)
    assert before.state.value == "HUMAN_REVIEW_REQUIRED"
    assert after.state.value == "SUPPORTED_CANDIDATES"
    assert _offers(seq6, after), "supported with no candidate is not an option"


def test_reachability_is_what_the_document_claims():
    """The research note carries a headline count. Draft 2's note said 27/38 while its
    own list of unreachable products implied 31 — a number that contradicts its
    neighbours is how a document stops being checkable."""
    raw = json.loads((PACKS / "rulepack-prod-006.source.json").read_text())
    codes = {p["product_version_id"]: p["product_code"] for p in raw["products"]}
    supported = {
        pid
        for rule in raw["rules"]
        if rule["effect"]["type"] == "SUPPORT"
        for pid in (rule.get("product_version_ids") or [])
    }
    reachable = {codes[pid] for pid in supported}
    assert len(codes) == 38
    assert len(reachable) == 29, sorted(reachable)
    assert sorted(set(codes.values()) - reachable) == [
        "E23U",
        "E23V",
        "E28B",
        "E28C",
        "E28D",
        "E28F",
        "E33A",
        "E33B",
        "E33C",
    ]
