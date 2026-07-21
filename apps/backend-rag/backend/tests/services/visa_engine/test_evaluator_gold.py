"""The 20 gold personas (spec §7 First 20 personas table) as parametrized
acceptance fixtures for ``evaluator.evaluate``.

Each case asserts (per spec §7's own "every case asserts" list, narrowed to
what PR5's scope actually produces — pack sequence/hash and quote status are
asserted via ``rule_pack``/``quotes`` where meaningful; pricing itself is
out of PR5 scope, see ``evaluator.py``'s module docstring divergence #4):

- exact state;
- exact candidate order (product codes, in rank order);
- exact missing/review/no-path reason codes;
- no candidate for any review/unknown/no-path case (enforced structurally by
  ``models.Decision``'s own state-conditional validators — a bug here would
  raise ``ValidationError`` inside ``evaluator.evaluate`` itself, never
  silently pass).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from backend.services.visa_engine import evaluator
from backend.services.visa_engine.enums import DecisionState
from backend.tests.services.visa_engine import _gold_fixtures as gf

_INV_MIN = gf.GOLD_INVESTOR_MIN_IDR


@dataclass(frozen=True)
class Persona:
    id: int
    label: str
    overrides: dict
    expected_state: DecisionState
    expected_candidates: tuple[str, ...] = ()
    expected_missing: tuple[str, ...] = ()
    expected_review_codes: tuple[str, ...] = ()
    expected_no_path_codes: tuple[str, ...] = ()
    expected_notice_codes: tuple[str, ...] = field(default_factory=tuple)


PERSONAS: tuple[Persona, ...] = (
    Persona(
        id=1,
        label="ID citizen excluded outright",
        overrides={"person.nationalities": gf.known(["ID", "IT"])},
        expected_state=DecisionState.NO_SUPPORTED_PATH,
        expected_no_path_codes=("APPLICANT_IS_INDONESIAN_CITIZEN",),
    ),
    Persona(
        id=2,
        label="conflicting nationality evidence -> human review",
        overrides={"person.nationalities": gf.unknown("CONFLICTING")},
        expected_state=DecisionState.HUMAN_REVIEW_REQUIRED,
        expected_review_codes=("CITIZENSHIP_EVIDENCE_CONFLICT",),
    ),
    Persona(
        id=3,
        label="calling-visa nationality -> human review",
        overrides={"person.nationalities": gf.known(["AF"])},
        expected_state=DecisionState.HUMAN_REVIEW_REQUIRED,
        expected_review_codes=("CALLING_VISA_REVIEW",),
    ),
    Persona(
        id=4,
        label="active overstay -> human review",
        overrides={
            "immigration.currently_in_indonesia": gf.known(True),
            "immigration.current_status_code": gf.known("C1"),
            "immigration.overstay_days": gf.known(3),
            "immigration.violation_history": gf.known(["OVERSTAY"]),
        },
        expected_state=DecisionState.HUMAN_REVIEW_REQUIRED,
        expected_review_codes=("ACTIVE_OVERSTAY",),
    ),
    Persona(
        id=5,
        label="minor without confirmed guardian -> human review",
        overrides={
            "person.birth_date": gf.known("2012-01-01"),
            "family.sponsor_confirmed": gf.known(False),
        },
        expected_state=DecisionState.HUMAN_REVIEW_REQUIRED,
        expected_review_codes=("MINOR_WITHOUT_CONFIRMED_GUARDIAN",),
    ),
    Persona(
        id=6,
        label="minor child with confirmed family sponsor -> E31",
        overrides={
            "person.birth_date": gf.known("2012-01-01"),
            "intent.purposes": gf.known(["FAMILY"]),
            "family.relation_to_sponsor": gf.known("CHILD"),
            "family.sponsor_status_code": gf.known("E23"),
            "family.sponsor_confirmed": gf.known(True),
        },
        expected_state=DecisionState.SUPPORTED_CANDIDATES,
        expected_candidates=("E31",),
    ),
    Persona(
        id=7,
        label="adult spouse, registered marriage, confirmed sponsor -> E31",
        overrides={
            "intent.purposes": gf.known(["FAMILY"]),
            "family.relation_to_sponsor": gf.known("SPOUSE"),
            "family.sponsor_nationalities": gf.known(["ID"]),
            "family.marriage_registered": gf.known(True),
            "family.sponsor_confirmed": gf.known(True),
        },
        expected_state=DecisionState.SUPPORTED_CANDIDATES,
        expected_candidates=("E31",),
    ),
    Persona(
        id=8,
        label="same as #7 but marriage_registered unverified -> needs input",
        overrides={
            # Gate round 2 (2026-07-20) parziale item 2: this is now a
            # genuine, PURE single-fact differential from #7 — every key
            # here except ``family.marriage_registered`` is identical to
            # #7's own overrides. Round 1 had ALSO added an explicit
            # ``family.sponsor_status_code`` override here to neutralize a
            # dead-branch unknown-fact leak (see ``_gold_fixtures.py``'s
            # persona-8 docstring for the full history); that leak is now
            # fixed at its root (the shared baseline's own
            # ``family.sponsor_status_code`` default), so the override is
            # no longer needed and has been removed.
            "intent.purposes": gf.known(["FAMILY"]),
            "family.relation_to_sponsor": gf.known("SPOUSE"),
            "family.sponsor_nationalities": gf.known(["ID"]),
            "family.marriage_registered": gf.unknown("UNVERIFIED"),
            "family.sponsor_confirmed": gf.known(True),
        },
        expected_state=DecisionState.NEEDS_INPUT,
        expected_missing=("family.marriage_registered",),
    ),
    Persona(
        id=9,
        label="investor direct onshore conversion -> unsupported",
        overrides={
            "immigration.currently_in_indonesia": gf.known(True),
            "immigration.current_status_code": gf.known("C1"),
            "intent.purposes": gf.known(["INVESTMENT"]),
            "intent.requested_product_code": gf.known("E28A"),
            "process.application_channel": gf.known("ONSHORE_CONVERSION"),
            "investment.investment_capital_idr": gf.known(_INV_MIN),
            "investment.pt_pma_committed": gf.known(True),
            "investment.proposed_role": gf.known("SHAREHOLDER_DIRECTOR"),
        },
        expected_state=DecisionState.NO_SUPPORTED_PATH,
        expected_no_path_codes=("DIRECT_ONSHORE_CONVERSION_UNSUPPORTED",),
    ),
    Persona(
        id=10,
        label="same investor facts via status bridging -> human review",
        overrides={
            "immigration.currently_in_indonesia": gf.known(True),
            "immigration.current_status_code": gf.known("C1"),
            "intent.purposes": gf.known(["INVESTMENT"]),
            "intent.requested_product_code": gf.known("E28A"),
            "process.application_channel": gf.known("STATUS_BRIDGING"),
            "investment.investment_capital_idr": gf.known(_INV_MIN),
            "investment.pt_pma_committed": gf.known(True),
            "investment.proposed_role": gf.known("SHAREHOLDER_DIRECTOR"),
        },
        expected_state=DecisionState.HUMAN_REVIEW_REQUIRED,
        expected_review_codes=("STATUS_BRIDGING_REVIEW",),
    ),
    Persona(
        id=11,
        label="clean remote worker, no local footprint -> E33G",
        # `work.employer_country_code` is deliberately NOT wired into any
        # rule (gate round 1 audit, 2026-07-19, see _gold_fixtures.py's
        # module docstring) — it stays here as case-narrative context only;
        # `work.employer_is_indonesian_entity` is the actual rule input.
        overrides={
            "intent.purposes": gf.known(["REMOTE_WORK"]),
            "work.employer_country_code": gf.known("FR"),
            "work.employer_is_indonesian_entity": gf.known(False),
            "work.serves_indonesian_clients": gf.known(False),
            "work.indonesia_source_compensation": gf.known(False),
        },
        expected_state=DecisionState.SUPPORTED_CANDIDATES,
        expected_candidates=("E33G",),
    ),
    Persona(
        id=12,
        label="remote worker serving Indonesian clients -> human review",
        overrides={
            "intent.purposes": gf.known(["REMOTE_WORK"]),
            "work.employer_is_indonesian_entity": gf.known(False),
            "work.serves_indonesian_clients": gf.known(True),
            "work.indonesia_source_compensation": gf.known(False),
        },
        expected_state=DecisionState.HUMAN_REVIEW_REQUIRED,
        expected_review_codes=("LOCAL_MARKET_ACTIVITY_REVIEW",),
    ),
    Persona(
        id=13,
        label="remote worker, local-clients fact unprovided -> needs input",
        overrides={
            "intent.purposes": gf.known(["REMOTE_WORK"]),
            "work.employer_is_indonesian_entity": gf.known(False),
            "work.serves_indonesian_clients": gf.unknown("NOT_PROVIDED"),
            "work.indonesia_source_compensation": gf.known(False),
        },
        expected_state=DecisionState.NEEDS_INPUT,
        expected_missing=("work.serves_indonesian_clients",),
    ),
    Persona(
        id=14,
        label="tourism + remote-work purposes -> E33G only, never C1",
        overrides={
            "intent.purposes": gf.known(["TOURISM", "REMOTE_WORK"]),
            "work.employer_is_indonesian_entity": gf.known(False),
            "work.serves_indonesian_clients": gf.known(False),
            "work.indonesia_source_compensation": gf.known(False),
        },
        expected_state=DecisionState.SUPPORTED_CANDIDATES,
        expected_candidates=("E33G",),
    ),
    Persona(
        id=15,
        label="tourism + employment purposes -> E23 only, never C1",
        overrides={
            "intent.purposes": gf.known(["TOURISM", "EMPLOYMENT"]),
            "work.employer_is_indonesian_entity": gf.known(True),
            "work.indonesian_work_sponsor_confirmed": gf.known(True),
        },
        expected_state=DecisionState.SUPPORTED_CANDIDATES,
        expected_candidates=("E23",),
    ),
    Persona(
        id=16,
        label="investor capital 1 IDR below minimum -> no supported path",
        overrides={
            "intent.purposes": gf.known(["INVESTMENT"]),
            "investment.investment_capital_idr": gf.known(_INV_MIN - 1),
            "investment.pt_pma_committed": gf.known(True),
            "investment.proposed_role": gf.known("SHAREHOLDER_DIRECTOR"),
        },
        expected_state=DecisionState.NO_SUPPORTED_PATH,
        expected_no_path_codes=("INVESTMENT_CAPITAL_BELOW_FIXTURE_MINIMUM",),
    ),
    Persona(
        id=17,
        label="investor at fixture minimum, low budget never filters -> E28A",
        overrides={
            "intent.purposes": gf.known(["INVESTMENT"]),
            "investment.investment_capital_idr": gf.known(_INV_MIN),
            "investment.pt_pma_committed": gf.known(True),
            "investment.proposed_role": gf.known("SHAREHOLDER_DIRECTOR"),
            "commercial.service_fee_budget_idr": gf.known(1),
        },
        expected_state=DecisionState.SUPPORTED_CANDIDATES,
        expected_candidates=("E28A",),
    ),
    Persona(
        id=18,
        label="obsolete code requested, purposes not provided -> needs input + notice",
        overrides={
            "intent.purposes": gf.unknown("NOT_PROVIDED"),
            "intent.stay_days": gf.known(30),
            "intent.requested_product_code": gf.known("B211A"),
        },
        expected_state=DecisionState.NEEDS_INPUT,
        expected_missing=("intent.purposes",),
        expected_notice_codes=("OBSOLETE_PRODUCT_CODE",),
    ),
    Persona(
        id=19,
        label="obsolete code requested, complete tourism facts -> C1 + notice",
        overrides={
            "intent.purposes": gf.known(["TOURISM"]),
            "intent.stay_days": gf.known(30),
            "intent.requested_product_code": gf.known("B211A"),
        },
        expected_state=DecisionState.SUPPORTED_CANDIDATES,
        expected_candidates=("C1",),
        expected_notice_codes=("OBSOLETE_PRODUCT_CODE",),
    ),
    Persona(
        id=20,
        label="onshore conversion wanted, status+overstay both unprovided",
        overrides={
            "immigration.currently_in_indonesia": gf.known(True),
            "process.wants_onshore_conversion": gf.known(True),
            "immigration.current_status_code": gf.unknown("NOT_PROVIDED"),
            "immigration.overstay_days": gf.unknown("NOT_PROVIDED"),
        },
        expected_state=DecisionState.NEEDS_INPUT,
        expected_missing=("immigration.current_status_code", "immigration.overstay_days"),
    ),
)

assert len(PERSONAS) == 20, "gold harness must carry exactly the 20 personas from spec §7"
assert [p.id for p in PERSONAS] == list(range(1, 21)), "persona ids must be 1..20 in order"


@pytest.fixture(scope="module")
def compiled_gold_pack():
    return gf.build_gold_compiled_pack()


@pytest.mark.parametrize("persona", PERSONAS, ids=[f"persona-{p.id:02d}" for p in PERSONAS])
def test_gold_persona(persona: Persona, compiled_gold_pack) -> None:
    facts = gf.applicant_facts(overrides=persona.overrides)
    decision = evaluator.evaluate(
        facts,
        compiled_gold_pack,
        effective_at=gf.GOLD_EFFECTIVE_AT,
        observed_at=gf.GOLD_EFFECTIVE_AT,
    )

    assert decision.state is persona.expected_state, (
        f"persona {persona.id} ({persona.label}): expected {persona.expected_state}, "
        f"got {decision.state}"
    )
    assert tuple(c.product_code for c in decision.candidates) == persona.expected_candidates
    assert tuple(sorted(m.value for m in decision.missing_facts)) == tuple(
        sorted(persona.expected_missing)
    )
    assert tuple(r.code for r in decision.review_reasons) == persona.expected_review_codes
    assert tuple(r.code for r in decision.no_path_reasons) == persona.expected_no_path_codes
    assert tuple(sorted(n.code for n in decision.notices)) == tuple(
        sorted(persona.expected_notice_codes)
    )

    # Every candidate/reason carries at least one citation (task bar: zero
    # uncited outputs) — the one documented exception is the evaluator's own
    # NO_PRODUCT_SUPPORTS_DECLARED_PURPOSES fallback, never reached by any of
    # these 20 personas (each has a named, cited rule driving its outcome).
    for candidate in decision.candidates:
        assert candidate.source_refs
    for reason in (*decision.review_reasons, *decision.no_path_reasons):
        assert reason.source_refs, f"reason {reason.code} must carry a citation"


# ---------------------------------------------------------------------------
# Gate round 1 (2026-07-19): metamorphic differential tests — each of these
# takes a gold persona's own facts and flips ONLY its previously-flagged
# "distinguishing" fact, proving the flip actually changes the outcome (the
# gate's ask: "make each distinguishing fact actually influential"). Personas
# 11/20 are intentionally excluded — documented as non-influential-by-design
# / already-influential in _gold_fixtures.py's module docstring instead.
# ---------------------------------------------------------------------------


def test_persona_6_sponsor_status_code_is_influential(compiled_gold_pack) -> None:
    base_overrides = PERSONAS[5].overrides  # persona id=6
    assert base_overrides["family.sponsor_status_code"] == gf.known("E23")

    facts = gf.applicant_facts(
        overrides={**base_overrides, "family.sponsor_status_code": gf.known("C1")}
    )
    decision = evaluator.evaluate(
        facts,
        compiled_gold_pack,
        effective_at=gf.GOLD_EFFECTIVE_AT,
        observed_at=gf.GOLD_EFFECTIVE_AT,
    )
    assert decision.state is DecisionState.NO_SUPPORTED_PATH
    assert decision.candidates == ()


def test_persona_7_sponsor_nationalities_is_influential(compiled_gold_pack) -> None:
    base_overrides = PERSONAS[6].overrides  # persona id=7
    assert base_overrides["family.sponsor_nationalities"] == gf.known(["ID"])

    facts = gf.applicant_facts(
        overrides={**base_overrides, "family.sponsor_nationalities": gf.known(["US"])}
    )
    decision = evaluator.evaluate(
        facts,
        compiled_gold_pack,
        effective_at=gf.GOLD_EFFECTIVE_AT,
        observed_at=gf.GOLD_EFFECTIVE_AT,
    )
    assert decision.state is DecisionState.NO_SUPPORTED_PATH
    assert decision.candidates == ()


def test_persona_8_is_a_pure_single_fact_differential_from_persona_7(compiled_gold_pack) -> None:
    """Gate round 2 (2026-07-20) parziale item 2: persona 8's own label
    claims "same as #7 but marriage_registered unverified" — this asserts
    that claim is now LITERALLY true at the overrides-dict level (every
    key identical to persona 7's except ``family.marriage_registered``),
    not just true in spirit. Round 1 had silently broken this by also
    adding a ``family.sponsor_status_code`` override to neutralize a
    dead-branch unknown-fact leak (see ``_gold_fixtures.py``'s persona-8
    docstring) — fixed at the root (shared baseline default) in round 2,
    so the override is gone and the differential is pure again.
    """
    persona_7_overrides = PERSONAS[6].overrides  # id=7
    persona_8_overrides = PERSONAS[7].overrides  # id=8

    differing_keys = {
        key
        for key in set(persona_7_overrides) | set(persona_8_overrides)
        if persona_7_overrides.get(key) != persona_8_overrides.get(key)
    }
    assert differing_keys == {"family.marriage_registered"}, (
        f"persona 8 must differ from persona 7 by exactly one fact "
        f"(family.marriage_registered), found: {differing_keys}"
    )


def test_persona_17_service_fee_budget_influences_ranking_score_never_eligibility(
    compiled_gold_pack,
) -> None:
    """Persona 17's own label: "low budget never filters". The gate round 1
    fix wires `commercial.service_fee_budget_idr` into a dedicated ranking
    rule (`rank.budget-covers-fee`) — this proves the fact IS influential
    (on score) while the legal state/candidate stays identical either way,
    which is a stronger demonstration of the persona's claim than an inert
    fact would be.
    """
    base_overrides = PERSONAS[16].overrides  # persona id=17
    assert base_overrides["commercial.service_fee_budget_idr"] == gf.known(1)

    low_budget = gf.applicant_facts(overrides=base_overrides)
    high_budget = gf.applicant_facts(
        overrides={**base_overrides, "commercial.service_fee_budget_idr": gf.known(2_000_000)}
    )

    low_decision = evaluator.evaluate(
        low_budget,
        compiled_gold_pack,
        effective_at=gf.GOLD_EFFECTIVE_AT,
        observed_at=gf.GOLD_EFFECTIVE_AT,
    )
    high_decision = evaluator.evaluate(
        high_budget,
        compiled_gold_pack,
        effective_at=gf.GOLD_EFFECTIVE_AT,
        observed_at=gf.GOLD_EFFECTIVE_AT,
    )

    # Legal state/candidate identity untouched by budget either way.
    assert low_decision.state is DecisionState.SUPPORTED_CANDIDATES
    assert high_decision.state is DecisionState.SUPPORTED_CANDIDATES
    assert [c.product_code for c in low_decision.candidates] == ["E28A"]
    assert [c.product_code for c in high_decision.candidates] == ["E28A"]

    # But the score IS influenced by the budget fact.
    assert high_decision.candidates[0].score > low_decision.candidates[0].score


def test_persona_20_asymmetric_influence_matrix(compiled_gold_pack) -> None:
    """Gate round 2 (2026-07-20) parziale item 3: Codex sol xhigh's EXECUTED
    probe found the round-1 documentation FALSE — it claimed "flipping
    EITHER distinguishing fact to KNOWN changes the outcome away from
    NEEDS_INPUT". The real 4-way matrix (see ``_gold_fixtures.py``'s
    persona-20 docstring for the mechanism):

    - both unknown (persona 20's own baseline) -> NEEDS_INPUT, both facts
      missing.
    - ``current_status_code`` known ALONE -> still NEEDS_INPUT (only
      ``overstay_days`` remains missing) — the STATE does not change.
    - ``overstay_days`` known ALONE (even at 0) -> SUPPORTED_CANDIDATES on
      C1 — the STATE DOES change, with no need for ``current_status_code``
      at all.
    - both known -> SUPPORTED_CANDIDATES on C1 (same as overstay-only).
    """
    base_overrides = PERSONAS[19].overrides  # id=20
    assert base_overrides["immigration.current_status_code"] == gf.unknown("NOT_PROVIDED")
    assert base_overrides["immigration.overstay_days"] == gf.unknown("NOT_PROVIDED")

    def _decide(overrides: dict) -> tuple[DecisionState, tuple[str, ...], tuple[str, ...]]:
        facts = gf.applicant_facts(overrides=overrides)
        decision = evaluator.evaluate(
            facts,
            compiled_gold_pack,
            effective_at=gf.GOLD_EFFECTIVE_AT,
            observed_at=gf.GOLD_EFFECTIVE_AT,
        )
        return (
            decision.state,
            tuple(sorted(m.value for m in decision.missing_facts)),
            tuple(c.product_code for c in decision.candidates),
        )

    both_unknown = _decide(base_overrides)
    status_only = _decide(
        {**base_overrides, "immigration.current_status_code": gf.known("C1")}
    )
    overstay_only = _decide({**base_overrides, "immigration.overstay_days": gf.known(0)})
    both_known = _decide(
        {
            **base_overrides,
            "immigration.current_status_code": gf.known("C1"),
            "immigration.overstay_days": gf.known(0),
        }
    )

    assert both_unknown == (
        DecisionState.NEEDS_INPUT,
        ("immigration.current_status_code", "immigration.overstay_days"),
        (),
    )
    assert status_only == (
        DecisionState.NEEDS_INPUT,
        ("immigration.overstay_days",),
        (),
    )
    assert overstay_only == (DecisionState.SUPPORTED_CANDIDATES, (), ("C1",))
    assert both_known == (DecisionState.SUPPORTED_CANDIDATES, (), ("C1",))
