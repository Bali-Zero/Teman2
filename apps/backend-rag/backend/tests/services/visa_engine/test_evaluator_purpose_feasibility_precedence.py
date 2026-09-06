"""``evaluate_product`` tests purpose-feasibility BEFORE it blocks on a
gate unknown — the decisiveness reorder from
``research/visa/2026-09-06-visa-oracle-decisiveness-investigation.md`` §4
PR-2.

The defect: ``evaluate`` picks the globally-asked question with
``min(blocked, key=lambda proof: len(proof.missing_facts))``. Before the
reorder, a product whose SUPPORT rules can NEVER cover the applicant's
declared purposes still produced a one-missing-fact ``BLOCKED_UNKNOWN``
proof — and therefore still won that ``min()`` and chose the question the
applicant was asked. Nine seq-19 products carry zero SUPPORT rules at all
(E23U, E23V, E28B, E28C, E28D, E28F, E33A, E33B, E33C): each can never be a
candidate under ANY fact resolution, and each was nonetheless asking
everybody for ``sponsor.type`` or ``intent.requested_product_code``.

Why this is not a fail-open, structurally: the hoisted block's only
possible return is ``UNSUPPORTED``. It cannot manufacture a candidate, and
it cannot silence a gate — every EXCLUDED and REVIEW return in
``evaluate_product`` (including the ``on_unknown=HUMAN_REVIEW`` escalation)
already ran ABOVE the block it moved past, and the three precedence tests
in ``TestSafetyPrecedenceIsUnchanged`` pin exactly that. The only reachable
user-visible change is ``NEEDS_INPUT`` → the honest ``NO_SUPPORTED_PATH``.

Two layers of witness:

- ``TestMechanism`` / ``TestSafetyPrecedenceIsUnchanged`` /
  ``TestDecisionLevelQuestionChoice`` — minimal hand-built packs, the house
  pattern of ``test_evaluator_purpose_coverage.py``, so the mechanic is
  isolated from any pack's content.
- ``TestSignedSeq19Witnesses`` — the real seq-19 pack on disk, pinning the
  two dead ends §2.2 measured (a business applicant asked for investment
  capital they never claimed; a retirement applicant asked for
  ``sponsor.type`` by three products that have no eligibility rule) and the
  innocence side (every persona that was SUPPORTED stays SUPPORTED, with
  byte-identical candidates).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_pack import (
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.scripts.visa_engine.gold_replay_driver import (
    _offline_identity_provider,
    build_persona_request,
)
from backend.services.visa_engine import compiler
from backend.services.visa_engine import models as M
from backend.services.visa_engine.compiler import DEFAULT_FACT_REGISTRY, build_compiled_pack
from backend.services.visa_engine.enums import DecisionState
from backend.services.visa_engine.evaluator import ProductProofStatus, evaluate, evaluate_product
from backend.tests.services.visa_engine import _builders as B
from backend.tests.services.visa_engine import _gold_fixtures as gf
from backend.tests.services.visa_engine.conftest import make_applicant_facts
from backend.tests.services.visa_engine.test_evaluator_gold import Persona

_EFFECTIVE_AT = datetime(2026, 7, 18, tzinfo=timezone.utc)

_PACKS_DIR = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts" / "packs"
)
#: Pinned deliberately at seq-19 — the pack the §2.2 census was measured
#: against. A later fold (seq-20 raises the visit-visa stay-day caps) would
#: legitimately change what these personas are ELIGIBLE for; this file is a
#: witness on the evaluator's ORDERING, not on any pack's content, so it
#: must not drift with the active pack.
_SEQ19_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-019.source.json"

#: Same instant ``test_seq19_pack.py`` pins, and for the same reason: the
#: seq-18/seq-19 packs carry an OFFICIAL_PORTAL freshness window, so a
#: wall-clock evaluation is a clock bomb.
AS_OF = datetime(2026, 9, 5, 0, 30, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.skipif(
    not _SEQ19_SOURCE_PATH.exists(),
    reason="rulepack-prod-019.source.json does not exist on disk",
)


# ---------------------------------------------------------------------------
# Minimal hand-built packs
# ---------------------------------------------------------------------------


def _facts(overrides: dict[str, Any]) -> M.ApplicantFacts:
    base = make_applicant_facts()
    data = base.facts.model_dump(by_alias=True, mode="json")
    data.update(overrides)
    return M.ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=base.assessment_id,
        collected_at=base.collected_at,
        facts=data,
    )


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


def _unknown(reason: str = "NOT_PROVIDED") -> dict[str, Any]:
    return {"status": "UNKNOWN", "reason": reason}


def _proof(
    compiled: compiler.CompiledRulePack,
    product_id: str,
    facts: M.ApplicantFacts,
    purposes: frozenset[str],
):
    (product,) = [p for p in compiled.products if str(p.product_version_id) == product_id]
    snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=_EFFECTIVE_AT)
    rules = compiled.rules_for(product, effective_at=_EFFECTIVE_AT)
    return evaluate_product(product=product, rules=rules, facts=snapshot, purposes=purposes)


_EXCLUDE = {"type": "EXCLUDE", "reason_code": "GATE_EXCLUDES"}
_REQUIRE_REVIEW = {"type": "REQUIRE_REVIEW", "reason_code": "GATE_REVIEWS"}
#: The gate every mechanism test below shares: one safety-critical rule
#: reading ``sponsor.type``, the exact shape of seq-19's
#: ``hf.e33{a,b,c}.sponsor-not-government*``.
_SPONSOR_IS_GOVERNMENT = {"op": "eq", "fact": "sponsor.type", "value": "GOVERNMENT"}


def _gated_pack(
    product_id: str,
    *,
    gate_stage: str = "HARD_FILTER",
    gate_effect: dict[str, Any] = _EXCLUDE,
    on_unknown: str = "NEEDS_INPUT",
    with_support_rule: bool = True,
) -> compiler.CompiledRulePack:
    """One product covering TOURISM+STUDY whose ONLY SUPPORT rule covers
    STUDY (so TOURISM is permanently uncoverable), plus one ``sponsor.type``
    gate. ``with_support_rule=False`` is the zero-SUPPORT shape."""
    src_id = B.new_uuid()
    prod = B.product(product_id=product_id, source_id=src_id, covered_purposes=["TOURISM", "STUDY"])
    support = B.rule(
        rule_id="el.support",
        stage="ELIGIBILITY",
        scope="PRODUCTS",
        product_version_ids=[product_id],
        when={"op": "eq", "fact": "study.admission_confirmed", "value": True},
        effect={"type": "SUPPORT", "reason_code": "SUPPORT_OK", "covered_purposes": ["STUDY"]},
        source_id=src_id,
        required_facts=["study.admission_confirmed"],
    )
    gate = B.rule(
        rule_id="gate.the-question",
        stage=gate_stage,
        scope="PRODUCTS",
        product_version_ids=[product_id],
        when=_SPONSOR_IS_GOVERNMENT,
        effect=gate_effect,
        source_id=src_id,
        required_facts=["sponsor.type"],
        on_unknown=on_unknown,
        safety_critical=True,
    )
    payload = B.rule_pack_payload(
        rules=([support] if with_support_rule else []) + [gate],
        products=[prod],
        source_records=[B.source_record(source_id=src_id)],
    )
    return build_compiled_pack(M.RulePack.model_validate(B.rule_pack_envelope(payload)))


def _gated_proof(purposes: set[str], overrides: dict[str, Any], **pack_kwargs: Any):
    """Build a ``_gated_pack`` and take its proof in one call."""
    product_id = B.new_uuid()
    compiled = _gated_pack(product_id, **pack_kwargs)
    return _proof(compiled, product_id, _facts(overrides), frozenset(purposes))


_SPONSOR_NOT_ASKED = {"sponsor.type": _unknown("NOT_ASKED")}
_SPONSOR_IS_GOV = {"sponsor.type": _known("GOVERNMENT")}


class TestMechanism:
    def test_a_product_that_cannot_cover_the_purposes_is_unsupported_not_blocked(self) -> None:
        """GUILT. The product's only SUPPORT rule covers STUDY; the
        applicant declared TOURISM. Before the reorder this returned
        BLOCKED_UNKNOWN(sponsor.type) — a question whose every possible
        answer leaves the product unable to cover TOURISM."""
        proof = _gated_proof({"TOURISM"}, _SPONSOR_NOT_ASKED)
        assert proof.status is ProductProofStatus.UNSUPPORTED
        assert proof.missing_purposes == frozenset({"TOURISM"})
        assert proof.missing_facts == frozenset(), "an infeasible product must ask nothing"

    def test_a_zero_support_product_asks_nothing(self) -> None:
        """GUILT, the seq-19 E33A/E33B/E33C/E23U/E23V shape: a product with
        NO support rule at all can never be a candidate under any fact
        resolution, so its gate unknown must not become anybody's
        question."""
        proof = _gated_proof({"TOURISM"}, _SPONSOR_NOT_ASKED, with_support_rule=False)
        assert proof.status is ProductProofStatus.UNSUPPORTED
        assert proof.missing_facts == frozenset()

    def test_a_purpose_feasible_product_still_blocks_on_its_gate_unknown(self) -> None:
        """INNOCENCE — the load-bearing one. The reorder must not turn
        ``on_unknown=NEEDS_INPUT`` into a no-op: when the product COULD
        cover the declared purposes, the unknown gate still asks."""
        proof = _gated_proof(
            {"STUDY"}, {**_SPONSOR_NOT_ASKED, "study.admission_confirmed": _known(True)}
        )
        assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert "sponsor.type" in {path.value for path in proof.missing_facts}

    def test_a_feasible_product_whose_support_rule_is_itself_unknown_still_blocks(self) -> None:
        """INNOCENCE. ``naive_potential_coverage`` is the OPTIMISTIC union
        — it counts unresolved SUPPORT rules as potentially TRUE — so a
        product whose coverage is merely unproven, not impossible, keeps
        its BLOCKED_UNKNOWN and keeps asking."""
        proof = _gated_proof(
            {"STUDY"},
            {**_SPONSOR_NOT_ASKED, "study.admission_confirmed": _unknown("NOT_ASKED")},
        )
        assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN


class TestSafetyPrecedenceIsUnchanged:
    """The reorder moved the feasibility test past ONE block — the
    input-tagged gate unknown. Everything that can refuse or hold an
    applicant still runs first, and these four pin it. Every case declares
    TOURISM, the purpose the product can never cover, so the hoisted return
    is reachable and only precedence keeps it from winning."""

    def test_a_true_hard_filter_still_excludes_an_infeasible_product(self) -> None:
        proof = _gated_proof({"TOURISM"}, _SPONSOR_IS_GOV)
        assert proof.status is ProductProofStatus.EXCLUDED
        assert {reason.code for reason in proof.reasons} == {"GATE_EXCLUDES"}

    def test_a_true_review_rule_still_holds_an_infeasible_product(self) -> None:
        proof = _gated_proof(
            {"TOURISM"},
            _SPONSOR_IS_GOV,
            gate_stage="HUMAN_REVIEW",
            gate_effect=_REQUIRE_REVIEW,
        )
        assert proof.status is ProductProofStatus.REVIEW
        assert {reason.code for reason in proof.reasons} == {"GATE_REVIEWS"}

    def test_an_on_unknown_human_review_gate_still_holds_an_infeasible_product(self) -> None:
        """The ``on_unknown=HUMAN_REVIEW`` escalation (evaluator module
        docstring P1) is review-tagged, and review-tagged unknowns resolve
        ABOVE the hoisted block — an unknown that should reach a human
        still does, even when the product could never be recommended."""
        proof = _gated_proof({"TOURISM"}, _SPONSOR_NOT_ASKED, on_unknown="HUMAN_REVIEW")
        assert proof.status is ProductProofStatus.REVIEW

    def test_the_reorder_never_produces_a_supported_proof(self) -> None:
        """The structural claim, stated as a test: the hoisted block sits
        strictly before the ``purposes <= covered`` SUPPORTED return, and
        its predicate (``purposes <= naive_potential_coverage``, the
        OPTIMISTIC union) is implied by that one — so no fact pattern
        reaching the hoisted return can be SUPPORTED. Here the applicant
        satisfies the support rule outright and the product is still
        infeasible for one declared purpose."""
        proof = _gated_proof(
            {"TOURISM", "STUDY"},
            {**_SPONSOR_NOT_ASKED, "study.admission_confirmed": _known(True)},
        )
        assert proof.status is ProductProofStatus.UNSUPPORTED
        assert proof.missing_purposes == frozenset({"TOURISM"})


class TestDecisionLevelQuestionChoice:
    """``evaluate``'s ``min(blocked, key=len(missing_facts))`` is where the
    defect actually bit users: the cheapest-to-answer blocked proof wins,
    and an infeasible product's one-fact proof is always the cheapest."""

    def test_the_infeasible_product_no_longer_chooses_the_question(self) -> None:
        infeasible_id = B.new_uuid()
        feasible_id = B.new_uuid()
        src_id = B.new_uuid()
        source = B.source_record(source_id=src_id)
        infeasible = B.product(
            product_id=infeasible_id,
            source_id=src_id,
            product_code="E33A",
            covered_purposes=["STUDY"],
        )
        feasible = B.product(
            product_id=feasible_id,
            source_id=src_id,
            product_code="C1",
            covered_purposes=["TOURISM"],
        )
        # The infeasible product: one gate, ONE missing fact — the cheapest
        # blocked proof in the pack, and the one `min()` used to pick.
        infeasible_gate = B.rule(
            rule_id="hf.infeasible.sponsor",
            stage="HARD_FILTER",
            scope="PRODUCTS",
            product_version_ids=[infeasible_id],
            when=_SPONSOR_IS_GOVERNMENT,
            effect=_EXCLUDE,
            source_id=src_id,
            required_facts=["sponsor.type"],
            on_unknown="NEEDS_INPUT",
            safety_critical=True,
        )
        # The feasible product: genuinely answerable, but TWO missing facts.
        feasible_gate = B.rule(
            rule_id="hf.feasible.two-facts",
            stage="HARD_FILTER",
            scope="PRODUCTS",
            product_version_ids=[feasible_id],
            when={
                "op": "all",
                "args": [
                    {"op": "eq", "fact": "immigration.overstay_days", "value": 1},
                    {"op": "eq", "fact": "intent.stay_days", "value": 1},
                ],
            },
            effect=_EXCLUDE,
            source_id=src_id,
            required_facts=["immigration.overstay_days", "intent.stay_days"],
            on_unknown="NEEDS_INPUT",
            safety_critical=True,
        )
        feasible_support = B.rule(
            rule_id="el.feasible.tourism",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[feasible_id],
            when={"op": "eq", "fact": "study.admission_confirmed", "value": True},
            effect={
                "type": "SUPPORT",
                "reason_code": "TOURISM_OK",
                "covered_purposes": ["TOURISM"],
            },
            source_id=src_id,
            required_facts=["study.admission_confirmed"],
        )
        payload = B.rule_pack_payload(
            rules=[infeasible_gate, feasible_gate, feasible_support],
            products=[infeasible, feasible],
            source_records=[source],
        )
        compiled = build_compiled_pack(M.RulePack.model_validate(B.rule_pack_envelope(payload)))
        facts = _facts(
            {
                "intent.purposes": _known(["TOURISM"]),
                "sponsor.type": _unknown("NOT_ASKED"),
                "immigration.overstay_days": _unknown("NOT_ASKED"),
                "intent.stay_days": _unknown("NOT_ASKED"),
                "study.admission_confirmed": _known(True),
            }
        )
        decision = evaluate(facts, compiled, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT)
        assert decision.state is DecisionState.NEEDS_INPUT
        missing = {path.value for path in decision.missing_facts}
        assert "sponsor.type" not in missing, (
            "a STUDY-only product must not choose the question for a TOURISM applicant"
        )
        assert missing == {"immigration.overstay_days", "intent.stay_days"}


# ---------------------------------------------------------------------------
# The real seq-19 pack
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def seq19() -> compiler.CompiledRulePack:
    """seq-19 through a PLACEHOLDER envelope — never a trust claim; the
    same access path ``test_seq19_pack.py`` documents."""
    payload = load_rule_pack_payload(_SEQ19_SOURCE_PATH)
    return build_compiled_pack(wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY)


def _decide(seq19: compiler.CompiledRulePack, label: str, overrides: dict[str, Any]):
    persona = Persona(
        id=99, label=label, overrides=overrides, expected_state=DecisionState.NEEDS_INPUT
    )
    facts = build_persona_request(persona).applicant_facts()
    return evaluate(
        facts,
        seq19,
        effective_at=AS_OF,
        observed_at=AS_OF,
        identity_provider=_offline_identity_provider,
    )


#: A business traveller who declared BUSINESS_MEETINGS for 121 days with no
#: sponsor. Under seq-19 no visit-visa rule covers a 121-day business stay
#: (§2.3 L3-a — the caps encode the initial grant), so the honest answer is
#: "no path". Before the reorder the E28 family — whose SUPPORT rules all
#: require INVESTMENT purposes this applicant never declared — asked them
#: for their company's investment capital instead.
_BUSINESS_121D: dict[str, Any] = {
    "intent.purposes": gf.known(["BUSINESS_MEETINGS"]),
    "intent.stay_days": gf.known(121),
    "sponsor.type": gf.known("NONE"),
}


class TestSignedSeq19Witnesses:
    def test_a_business_applicant_is_not_asked_for_investment_capital(
        self, seq19: compiler.CompiledRulePack
    ) -> None:
        """GUILT, §2.2's ``investment.investment_capital_idr`` dead end
        (2 of the 43 interview walks). Measured on seq-19 before the
        reorder: ``NEEDS_INPUT missing=[investment.investment_capital_idr,
        investment.paid_up_capital_idr]``."""
        decision = _decide(
            seq19,
            "business 121d, investment capital never claimed",
            {
                **_BUSINESS_121D,
                "investment.investment_capital_idr": gf.unknown("NOT_ASKED"),
                "investment.paid_up_capital_idr": gf.unknown("NOT_ASKED"),
            },
        )
        assert decision.state is DecisionState.NO_SUPPORTED_PATH
        assert not decision.missing_facts

    def test_answering_the_investment_question_could_never_have_changed_the_answer(
        self, seq19: compiler.CompiledRulePack
    ) -> None:
        """The proof that the retired question was worthless, not merely
        inconvenient: supplying both investment facts yields the SAME
        decision state — on the old evaluator too, which is why the old
        NEEDS_INPUT was a dead end rather than a step."""
        answered = _decide(
            seq19,
            "business 121d, investment capital supplied",
            {
                **_BUSINESS_121D,
                "investment.investment_capital_idr": gf.known(1),
                "investment.paid_up_capital_idr": gf.known(1),
            },
        )
        assert answered.state is DecisionState.NO_SUPPORTED_PATH

    def test_a_retirement_applicant_is_not_asked_for_sponsor_type(
        self, seq19: compiler.CompiledRulePack
    ) -> None:
        """GUILT, §2.2's ``sponsor.type`` dead end (5 of the 43 walks).
        E33A/E33B/E33C's ``hf.e33{a,b,c}.sponsor-not-government*`` were its
        sole cause — on three products that carry no eligibility rule and
        therefore cannot be recommended under ANY sponsor value."""
        decision = _decide(
            seq19,
            "retirement, sponsor.type never asked",
            {
                "intent.purposes": gf.known(["RETIREMENT"]),
                "sponsor.type": gf.unknown("NOT_ASKED"),
            },
        )
        assert decision.state is DecisionState.NO_SUPPORTED_PATH
        assert "sponsor.type" not in {path.value for path in decision.missing_facts}

    @pytest.mark.parametrize(
        ("label", "overrides", "expected"),
        [
            (
                "tourism",
                {"intent.purposes": gf.known(["TOURISM"])},
                ("B1", "C1"),
            ),
            (
                "business meetings, default stay",
                {"intent.purposes": gf.known(["BUSINESS_MEETINGS"])},
                ("D2",),
            ),
            (
                "investment",
                {"intent.purposes": gf.known(["INVESTMENT"])},
                ("D12",),
            ),
        ],
    )
    def test_supported_personas_keep_byte_identical_candidates(
        self,
        seq19: compiler.CompiledRulePack,
        label: str,
        overrides: dict[str, Any],
        expected: tuple[str, ...],
    ) -> None:
        """INNOCENCE. The reorder's only possible output is UNSUPPORTED, so
        the SUPPORTED set must not move — measured over the 43 interview
        walks it was byte-identical (7 SUPPORTED before, the same 7
        after)."""
        decision = _decide(seq19, label, overrides)
        assert decision.state is DecisionState.SUPPORTED_CANDIDATES
        assert tuple(sorted(c.product_code for c in decision.candidates)) == expected

    def test_a_genuinely_askable_gate_still_asks(self, seq19: compiler.CompiledRulePack) -> None:
        """INNOCENCE on the real pack: gold persona #13's own legal
        description is "remote worker, local-clients fact unprovided ->
        needs input". It still needs input, and after the reorder it
        finally names ITS OWN fact rather than a zero-support product's
        ``sponsor.type``."""
        decision = _decide(
            seq19,
            "remote worker, local-clients fact unprovided",
            {
                "intent.purposes": gf.known(["REMOTE_WORK"]),
                "work.employer_is_indonesian_entity": gf.known(False),
                "work.serves_indonesian_clients": gf.unknown("NOT_PROVIDED"),
                "work.indonesia_source_compensation": gf.known(False),
            },
        )
        assert decision.state is DecisionState.NEEDS_INPUT
        assert {path.value for path in decision.missing_facts} == {"work.serves_indonesian_clients"}


def test_the_pack_under_test_is_the_one_the_census_was_measured_against() -> None:
    """Anti-drift: the numbers in this file's docstrings were measured on
    seq-19's 109 rules / 38 products."""
    payload = json.loads(_SEQ19_SOURCE_PATH.read_text(encoding="utf-8"))
    assert payload["sequence"] == 19
    assert len(payload["rules"]) == 109
    assert len(payload["products"]) == 38
