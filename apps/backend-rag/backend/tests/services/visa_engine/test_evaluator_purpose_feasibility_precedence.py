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
import uuid
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

#: Deliberately NOT a module-level ``pytestmark`` (PR-2 gate condition
#: SKIPIF SCOPE): only the seq-19 witnesses below need a pack on disk. Every
#: other test in this file builds its own minimal pack in memory, so a pack
#: rename or a relocated `packs/` directory used to silently disable the
#: precedence tests that are this file's actual subject — a green run
#: proving nothing (cicatrix #2). Applied per-target instead.
requires_seq19 = pytest.mark.skipif(
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


def _two_product_excluded_pack() -> compiler.CompiledRulePack:
    """Two products, each EXCLUDED by its own always-TRUE hard filter, each
    with ONE ELIGIBILITY rule — ``STUDY_ONLY`` covers STUDY, ``TOURISM_ONLY``
    covers TOURISM. Whatever the applicant declares, both products are
    excluded and at most ONE of them ever claimed that purpose.
    """
    src_id = B.new_uuid()
    products = []
    rules = []
    for code, purpose in (("STUDYONLY", "STUDY"), ("TOURONLY", "TOURISM")):
        pid = B.new_uuid()
        products.append(
            B.product(
                product_id=pid,
                source_id=src_id,
                product_code=code,
                covered_purposes=[purpose],
            )
        )
        rules.append(
            B.rule(
                rule_id=f"el.{code.lower()}",
                stage="ELIGIBILITY",
                scope="PRODUCTS",
                product_version_ids=[pid],
                when={"op": "eq", "fact": "study.admission_confirmed", "value": True},
                effect={
                    "type": "SUPPORT",
                    "reason_code": f"{code}_SUPPORT",
                    "covered_purposes": [purpose],
                },
                source_id=src_id,
                required_facts=["study.admission_confirmed"],
            )
        )
        rules.append(
            B.rule(
                rule_id=f"hf.{code.lower()}",
                stage="HARD_FILTER",
                scope="PRODUCTS",
                product_version_ids=[pid],
                when={"op": "eq", "fact": "immigration.currently_in_indonesia", "value": False},
                effect={"type": "EXCLUDE", "reason_code": f"{code}_EXCLUDED"},
                source_id=src_id,
                required_facts=["immigration.currently_in_indonesia"],
            )
        )
    payload = B.rule_pack_payload(
        rules=rules, products=products, source_records=[B.source_record(source_id=src_id)]
    )
    return build_compiled_pack(M.RulePack.model_validate(B.rule_pack_envelope(payload)))


def _no_path_codes(purposes: list[str]) -> list[str]:
    facts = _facts(
        {
            "intent.purposes": _known(purposes),
            "immigration.currently_in_indonesia": _known(False),
            "study.admission_confirmed": _known(False),
        }
    )
    decision = evaluate(
        facts,
        _two_product_excluded_pack(),
        effective_at=_EFFECTIVE_AT,
        observed_at=_EFFECTIVE_AT,
    )
    assert decision.state is DecisionState.NO_SUPPORTED_PATH
    return [reason.code for reason in decision.no_path_reasons]


class TestNoPathReasonsAreScopedToPurposeFeasibleProducts:
    """The applicant-facing half of the reorder (gate follow-up, 2026-09-06).

    ``NO_SUPPORTED_PATH`` went from 0 of the 43 interview walks to 23, so the
    reason list stopped being a corner case and became the sentence people
    read. It aggregated every EXCLUDED product's reason, including products
    whose ELIGIBILITY rules never claimed the declared purpose at all — a
    true sentence about a visa the applicant was never a candidate for.
    """

    def test_guilt_a_purpose_mismatched_products_reason_is_withheld(self) -> None:
        """GUILT: the TOURISM applicant is not told why the STUDY-only
        product was excluded. Before the scoping both codes appeared."""
        assert _no_path_codes(["TOURISM"]) == ["TOURONLY_EXCLUDED"]

    def test_innocence_the_purpose_feasible_products_reason_survives(self) -> None:
        """INNOCENCE, the mirror image on the SAME pack: swap the declared
        purpose and the surviving code swaps with it. A filter that simply
        dropped reasons would fail this half."""
        assert _no_path_codes(["STUDY"]) == ["STUDYONLY_EXCLUDED"]

    def test_when_nothing_purpose_feasible_was_excluded_the_operational_fallback_fires(
        self,
    ) -> None:
        """The empty case, which the scoping newly makes reachable: the
        applicant declared a purpose NO product ever claimed, so no exclusion
        reason is theirs. ``Decision`` forbids an empty list for this state,
        and ``_fallback_no_path_reason`` supplies the honest OPERATIONAL one
        — WITH citations, since the task bar is zero uncited outputs. The
        mouth carries copy for this code (engine-adapter.ts
        ``SUPPORT_REASON_COPY``), added in the same PR, so it renders as a
        sentence and not as a raw code."""
        facts = _facts(
            {
                "intent.purposes": _known(["EMPLOYMENT"]),
                "immigration.currently_in_indonesia": _known(False),
                "study.admission_confirmed": _known(False),
            }
        )
        decision = evaluate(
            facts,
            _two_product_excluded_pack(),
            effective_at=_EFFECTIVE_AT,
            observed_at=_EFFECTIVE_AT,
        )
        assert decision.state is DecisionState.NO_SUPPORTED_PATH
        assert [reason.code for reason in decision.no_path_reasons] == [
            "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES"
        ]
        assert decision.no_path_reasons[0].source_refs

    def test_the_scoping_never_changes_the_state(self) -> None:
        """The filtered list feeds the reason TEXT and nothing else: all
        three purposes above reach NO_SUPPORTED_PATH with no candidates and
        no missing facts, exactly as they did before the scoping."""
        for purposes in (["TOURISM"], ["STUDY"], ["EMPLOYMENT"]):
            facts = _facts(
                {
                    "intent.purposes": _known(purposes),
                    "immigration.currently_in_indonesia": _known(False),
                    "study.admission_confirmed": _known(False),
                }
            )
            decision = evaluate(
                facts,
                _two_product_excluded_pack(),
                effective_at=_EFFECTIVE_AT,
                observed_at=_EFFECTIVE_AT,
            )
            assert decision.state is DecisionState.NO_SUPPORTED_PATH, purposes
            assert decision.candidates == ()
            assert decision.missing_facts == ()


def _same_code_two_sources_pack(
    *, second_code: str = "SHARED_EXCLUSION"
) -> tuple[Any, str, str]:
    """Two products that BOTH cover TOURISM and are BOTH excluded, each by its
    own HARD_FILTER rule — with ``second_code`` deciding whether the two
    exclusions carry the SAME reason code or different ones, and always from
    DIFFERENT source records so the citations differ.

    This is the exact shape the real pack produces: ``hf.e33e.age-below-55``
    and ``hf.e33f.age-below-55`` are two rules on two products carrying one
    code, and their proofs do not cite the same records.

    Returns the pack WITH its two source ids: ``B.new_uuid()`` is fresh per
    call, so the expected citations have to come out of the same build that
    produced the decision — comparing refs across two builds compares two
    unrelated sets of UUIDs and can never be meaningful.
    """
    src_a = B.new_uuid()
    src_b = B.new_uuid()
    products = []
    rules = []
    for code, src, reason_code in (
        ("DUPA", src_a, "SHARED_EXCLUSION"),
        ("DUPB", src_b, second_code),
    ):
        pid = B.new_uuid()
        products.append(
            B.product(
                product_id=pid,
                source_id=src_a,
                product_code=code,
                covered_purposes=["TOURISM"],
            )
        )
        rules.append(
            B.rule(
                rule_id=f"el.{code.lower()}",
                stage="ELIGIBILITY",
                scope="PRODUCTS",
                product_version_ids=[pid],
                when={"op": "eq", "fact": "study.admission_confirmed", "value": True},
                effect={
                    "type": "SUPPORT",
                    "reason_code": f"{code}_SUPPORT",
                    "covered_purposes": ["TOURISM"],
                },
                source_id=src_a,
                required_facts=["study.admission_confirmed"],
            )
        )
        rules.append(
            B.rule(
                rule_id=f"hf.{code.lower()}",
                stage="HARD_FILTER",
                scope="PRODUCTS",
                product_version_ids=[pid],
                when={"op": "eq", "fact": "immigration.currently_in_indonesia", "value": False},
                effect={"type": "EXCLUDE", "reason_code": reason_code},
                source_id=src,
                required_facts=["immigration.currently_in_indonesia"],
            )
        )
    payload = B.rule_pack_payload(
        rules=rules,
        products=products,
        source_records=[B.source_record(source_id=src_a), B.source_record(source_id=src_b)],
    )
    pack = build_compiled_pack(M.RulePack.model_validate(B.rule_pack_envelope(payload)))
    return pack, src_a, src_b


def _no_path_reasons_on(pack: Any) -> tuple[Any, ...]:
    facts = _facts(
        {
            "intent.purposes": _known(["TOURISM"]),
            "immigration.currently_in_indonesia": _known(False),
            "study.admission_confirmed": _known(False),
        }
    )
    decision = evaluate(facts, pack, effective_at=_EFFECTIVE_AT, observed_at=_EFFECTIVE_AT)
    assert decision.state is DecisionState.NO_SUPPORTED_PATH
    return decision.no_path_reasons


class TestNoPathReasonsAreMergedByCodeNotRepeated:
    """One SENTENCE per reason, and no citation lost merging them.

    Same root cause as the class above: the reorder made ``no_path_reasons``
    the text a real person reads, and it repeated itself. ``_dedupe_reasons``
    keys on the whole (code, rule_ids, source_refs) triple, so two DIFFERENT
    rules carrying ONE code both survived — and ``engine-adapter.ts`` maps the
    list 1:1 through copy keyed by CODE ALONE, so the applicant was told "you
    must be at least 55" twice on one sheet. Measured on seq-20 before the fix:
    six walks rendered ``['AGE_BELOW_55', 'AGE_BELOW_55']``.

    Collapsing on the code and keeping the first entry would have been the
    wrong fix and is what these tests forbid: the two proofs cite DIFFERENT
    source records, and ``requireDecisiveRefs`` makes citations load-bearing on
    this surface. The merge unions them.
    """

    def test_guilt_one_code_from_two_rules_renders_once(self) -> None:
        """GUILT: two products, two rules, one code. Before the merge this
        returned the code TWICE."""
        pack, _, _ = _same_code_two_sources_pack()
        reasons = _no_path_reasons_on(pack)
        assert [reason.code for reason in reasons] == ["SHARED_EXCLUSION"]

    def test_guilt_the_merge_unions_the_citations_and_drops_none(self) -> None:
        """GUILT, and the half that makes 'merge' different from 'dedupe':
        the surviving entry carries BOTH rules and BOTH source records. A
        collapse that kept the first-seen entry would pass the test above and
        fail this one, having silently dropped ``src_b``."""
        pack, src_a, src_b = _same_code_two_sources_pack()
        merged = _no_path_reasons_on(pack)
        assert len(merged) == 1
        assert set(merged[0].rule_ids) == {"hf.dupa", "hf.dupb"}
        assert set(merged[0].source_refs) == {uuid.UUID(src_a), uuid.UUID(src_b)}, (
            "the merge lost a citation — every source_ref the two separate "
            "reasons carried must survive on the merged one"
        )
        assert len(set(merged[0].source_refs)) == len(merged[0].source_refs)

    def test_innocence_two_different_codes_are_two_reasons(self) -> None:
        """INNOCENCE: the merge is keyed on the CODE, so two genuinely
        different sentences stay two entries in engine order, each keeping its
        OWN single citation. A blanket 'one reason per state' collapse would
        fail here, and so would a merge that unioned across codes."""
        pack, src_a, src_b = _same_code_two_sources_pack(second_code="OTHER_EXCLUSION")
        reasons = _no_path_reasons_on(pack)
        assert [reason.code for reason in reasons] == ["SHARED_EXCLUSION", "OTHER_EXCLUSION"]
        assert set(reasons[0].source_refs) == {uuid.UUID(src_a)}
        assert set(reasons[1].source_refs) == {uuid.UUID(src_b)}

    def test_innocence_the_merge_never_changes_the_state(self) -> None:
        """The merged list feeds the reason TEXT and nothing else — same
        guarantee the scoping carries, and the reason both are safe."""
        for second_code in ("SHARED_EXCLUSION", "OTHER_EXCLUSION"):
            facts = _facts(
                {
                    "intent.purposes": _known(["TOURISM"]),
                    "immigration.currently_in_indonesia": _known(False),
                    "study.admission_confirmed": _known(False),
                }
            )
            pack, _, _ = _same_code_two_sources_pack(second_code=second_code)
            decision = evaluate(
                facts,
                pack,
                effective_at=_EFFECTIVE_AT,
                observed_at=_EFFECTIVE_AT,
            )
            assert decision.state is DecisionState.NO_SUPPORTED_PATH, second_code
            assert decision.candidates == ()
            assert decision.missing_facts == ()


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


@requires_seq19
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


@requires_seq19
def test_the_pack_under_test_is_the_one_the_census_was_measured_against() -> None:
    """Anti-drift: the numbers in this file's docstrings were measured on
    seq-19's 109 rules / 38 products."""
    payload = json.loads(_SEQ19_SOURCE_PATH.read_text(encoding="utf-8"))
    assert payload["sequence"] == 19
    assert len(payload["rules"]) == 109
    assert len(payload["products"]) == 38
