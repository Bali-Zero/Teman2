"""Metamorphic properties of the REAL ``evaluator.evaluate()``, ported from
the sibling ``gold_harness/test_metamorphic_properties.py`` (which asserted
them against the harness's own Decision-agnostic adapter) onto the canonical
PR5 surface — the gate G-b(b) ask: PR5's ``test_evaluator_determinism.py``
proves repeat-call purity (same inputs -> byte-identical Decision), but NOT
fact-order invariance, NOT rule-declaration-order invariance, and NOT
monotonicity. This file closes exactly those three gaps.

Second revision (2026-07-23) — codex independent grade FIX-FIRST, five
findings addressed; the two P1s were verified by the reviewer with EXECUTED
mutation probes, and the fixes below are structured so each probe would now
fail the suite:

1. **P1 — the wire-dict fact-order test was vacuous w.r.t. the evaluator.**
   Shuffling the raw wire dict never reached ``evaluate()``: Pydantic's
   ``ApplicantFactsData`` restores declared field order at validation time,
   so the evaluator only ever saw one canonical order. Fixed two ways,
   splitting the property at the boundary it actually lives on:
   - ``TestFactOrderInvariance`` now pins the BOUNDARY MECHANISM explicitly:
     two differently-ordered wire inputs must normalize to the same internal
     field order at the ``ApplicantFacts`` model, AND produce byte-identical
     Decisions (the property as stated for callers of the public API).
   - ``TestSnapshotOrderInvariance`` permutes the evaluator's REAL input —
     the ``FactSnapshot.values`` mapping produced by
     ``FactRegistry.derive`` — and runs the real ``evaluator.evaluate_product``
     per product. This is the level at which an iteration-order dependency
     inside condition evaluation / proof assembly would actually live, and
     the permutation provably reaches it (anti-vacuity assert on the
     permuted mapping itself).
2. **P1 — the gold-pack rule-shuffle test could not detect a missing
   ``rules_for`` sort.** The reviewer replaced ``CompiledRulePack.rules_for``
   with an unsorted variant at runtime and all 60 comparisons stayed green:
   in the canonical pack no product has two co-firing rules in one stage
   whose ORDER is observable in the Decision. Fixed by
   ``TestRuleOrderInvarianceCoFiring``: two targeted one-product packs (one
   ELIGIBILITY pair, one HUMAN_REVIEW pair) whose two rules BOTH fire TRUE
   and are DECLARED in the exact reverse of their ``(stage.order, priority,
   rule_id)`` sorted order, with ordered observable output
   (``Candidate.support_rule_ids`` / ``Decision.review_reasons``). The
   canonical-decision assertions pin the sorted order directly — remove the
   sort and the declaration order (bbb before aaa) leaks into those fields
   and the test fails. ``TestRuleOrderInvariance`` (gold-pack shuffle) is
   kept as broader regression coverage for every other aggregation point,
   with its docstring corrected to stop claiming it catches a missing sort.
3. **P2 — score monotonicity was never exercised** (every gold candidate
   scores 0: neither ranking rule fires for the 20 personas). Fixed by
   ``TestScoreMonotonicity``: a supported persona variant with
   ``commercial.wants_quote=True`` (+5) and budget ≥ 1M (+3) — baseline
   score provably 8 — de-known fact-by-fact to the exact expected drops.
4. **P2 — the replay artifact's engine hash covered only ``evaluator.py``**
   (see ``gold_replay.py``'s new multi-module digest).
5. **P3 — the rule-shuffle helper passed a list where the model declares a
   tuple** (``PydanticSerializationUnexpectedValue`` at dump time). Fixed
   with ``tuple(...)``.

Anti-vacuity: every shuffle test asserts the shuffle ACTUALLY permuted its
sequence (a silent no-op shuffle would make the property vacuously green),
and every targeted test first pins the non-vacuous baseline (score 8,
co-firing rules present in ordered output). A failure of ANY of these on
the real evaluator is a finding about the engine, not a test to weaken.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from backend.services.visa_engine import evaluator
from backend.services.visa_engine import models as M
from backend.services.visa_engine.ast import FactSnapshot, KnownFact
from backend.services.visa_engine.compiler import CompiledRulePack, build_compiled_pack
from backend.services.visa_engine.enums import DecisionState, FactPath
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.tests.services.visa_engine import _builders
from backend.tests.services.visa_engine import _gold_fixtures as gf
from backend.tests.services.visa_engine.test_evaluator_gold import PERSONAS, Persona

#: Fixed (never random) assessment_id for every comparison this file makes —
#: same rationale as ``test_evaluator_determinism.py``'s own fixed id:
#: ``assessment_id`` feeds ``decision_id``/``public_id``, so two Decisions
#: can only be compared byte-for-byte when it is pinned identically on both
#: sides. (The monotonicity test never compares ids — its de-known variant
#: legitimately has different facts — but pinning keeps every run pure.)
_FIXED_ASSESSMENT_ID = uuid.UUID("b1b1b1b1-b1b1-4b1b-8b1b-b1b1b1b1b1b1")

_SHUFFLE_SEEDS = (0, 1, 2)


@pytest.fixture(scope="module")
def compiled_gold_pack() -> CompiledRulePack:
    return gf.build_gold_compiled_pack()


def _evaluate(facts: M.ApplicantFacts, pack: CompiledRulePack) -> M.Decision:
    return evaluator.evaluate(
        facts,
        pack,
        effective_at=gf.GOLD_EFFECTIVE_AT,
        observed_at=gf.GOLD_EFFECTIVE_AT,
    )


def _wire_facts(persona: Persona) -> dict[str, dict[str, Any]]:
    """The persona's full 35-key wire facts mapping (baseline + overrides) as
    plain ``{"status": ..., ...}`` dicts, taken from the validated
    ``ApplicantFacts`` model's own dump so every consumer below mutates a
    plain-data copy, never fixture state."""
    facts = gf.applicant_facts(assessment_id=_FIXED_ASSESSMENT_ID, overrides=persona.overrides)
    return facts.facts.model_dump(by_alias=True, mode="python")


def _facts_from_wire(wire: dict[str, dict[str, Any]]) -> M.ApplicantFacts:
    return M.ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=_FIXED_ASSESSMENT_ID,
        collected_at=gf.GOLD_EFFECTIVE_AT,
        facts=wire,
    )


# ---------------------------------------------------------------------------
# (a) Monotonicity — de-knowing a fact never increases support
# ---------------------------------------------------------------------------


#: Legal successor states after retracting exactly one KNOWN fact to UNKNOWN
#: (derivation in the module docstring's revision-1 discussion and in the
#: harness's own table): removing information can only move a condition leaf
#: toward UNKNOWN — never to a NEW definite value — for every op this pack
#: uses, with ONE exception: the ``unknown(fact)`` leaf in
#: ``review.citizenship-conflict`` legitimately goes FALSE -> TRUE when
#: nationalities are retracted (a GLOBAL HUMAN_REVIEW trigger, i.e. a safety
#: escalation, never support). Both "definite" states can therefore only
#: degrade toward the indeterminate ones; the indeterminate ones can only
#: stay indeterminate; and NO state outside SUPPORTED_CANDIDATES lists
#: SUPPORTED_CANDIDATES as a successor — removing information can never
#: manufacture support. NO_SUPPORTED_PATH is likewise never manufacturable:
#: the naive potential-coverage union (TRUE support rules' covered purposes
#: UNION unknown support rules') is INVARIANT under retraction, and the real
#: ``evaluate_product`` blocks (BLOCKED_UNKNOWN) on ANY non-NO_EFFECT
#: UNKNOWN hard-filter/review rule (it does NOT gate that on
#: ``safety_critical`` — unlike the harness adapter).
_ALLOWED_DEKNOW_TRANSITIONS: dict[DecisionState, frozenset[DecisionState]] = {
    DecisionState.SUPPORTED_CANDIDATES: frozenset(
        {
            DecisionState.SUPPORTED_CANDIDATES,
            DecisionState.NEEDS_INPUT,
            DecisionState.HUMAN_REVIEW_REQUIRED,
        }
    ),
    DecisionState.HUMAN_REVIEW_REQUIRED: frozenset(
        {DecisionState.HUMAN_REVIEW_REQUIRED, DecisionState.NEEDS_INPUT}
    ),
    DecisionState.NEEDS_INPUT: frozenset(
        {DecisionState.NEEDS_INPUT, DecisionState.HUMAN_REVIEW_REQUIRED}
    ),
    DecisionState.NO_SUPPORTED_PATH: frozenset(
        {
            DecisionState.NO_SUPPORTED_PATH,
            DecisionState.NEEDS_INPUT,
            DecisionState.HUMAN_REVIEW_REQUIRED,
        }
    ),
}


class TestMonotonicity:
    @pytest.mark.parametrize("persona", PERSONAS, ids=[f"persona-{p.id:02d}" for p in PERSONAS])
    def test_deknowing_any_known_fact_never_increases_support(
        self, persona: Persona, compiled_gold_pack: CompiledRulePack
    ) -> None:
        baseline_facts = _facts_from_wire(_wire_facts(persona))
        baseline = _evaluate(baseline_facts, compiled_gold_pack)
        baseline_candidates = {c.product_code: c.score for c in baseline.candidates}
        allowed = _ALLOWED_DEKNOW_TRANSITIONS[baseline.state]

        wire = baseline_facts.facts.model_dump(by_alias=True, mode="python")
        known_paths = sorted(path for path, fact in wire.items() if fact["status"] == "KNOWN")
        assert known_paths, (
            f"persona {persona.id}: zero KNOWN facts — nothing to de-know, "
            "the property would be vacuous for this persona"
        )

        for path in known_paths:
            deknown_wire = {**wire, path: gf.unknown("NOT_PROVIDED")}
            deknown = _evaluate(_facts_from_wire(deknown_wire), compiled_gold_pack)
            assert deknown.state in allowed, (
                f"persona {persona.id} ({persona.label}): de-knowing {path} moved the "
                f"Decision from {baseline.state.value} to {deknown.state.value}, outside "
                f"the legal successor set {sorted(s.value for s in allowed)} — removing "
                "information must never manufacture support (no new SUPPORTED_CANDIDATES "
                "from a non-supported baseline) and never resolve an indeterminate state "
                "to a different definite one"
            )
            if baseline.state is DecisionState.SUPPORTED_CANDIDATES and (
                deknown.state is DecisionState.SUPPORTED_CANDIDATES
            ):
                deknown_candidates = {c.product_code: c.score for c in deknown.candidates}
                assert set(deknown_candidates) <= set(baseline_candidates), (
                    f"persona {persona.id}: de-knowing {path} GREW the candidate set "
                    f"from {sorted(baseline_candidates)} to {sorted(deknown_candidates)}"
                )
                for code, new_score in deknown_candidates.items():
                    assert new_score <= baseline_candidates[code], (
                        f"persona {persona.id}: de-knowing {path} raised candidate "
                        f"{code}'s score from {baseline_candidates[code]} to {new_score} "
                        "(a TRUE ranking rule going UNKNOWN can only drop points)"
                    )


class TestScoreMonotonicity:
    """Codex-grade P2 fix: the 20 gold personas all score 0 (neither RANKING
    rule fires for them), so ``TestMonotonicity``'s score-half never actually
    exercised a TRUE ranking rule going UNKNOWN. This targeted variant starts
    from a provably non-zero score (8 = 5 wants-quote + 3 budget) and
    de-knows exactly those facts, pinning the exact drops."""

    def test_deknowing_true_ranking_facts_drops_score_exactly(
        self, compiled_gold_pack: CompiledRulePack
    ) -> None:
        base_overrides = PERSONAS[10].overrides  # persona 11: clean remote worker -> E33G
        overrides = {
            **base_overrides,
            "commercial.wants_quote": gf.known(True),
            "commercial.service_fee_budget_idr": gf.known(2_000_000),
        }

        def score_for(overrides: dict[str, dict[str, Any]]) -> int:
            facts = gf.applicant_facts(assessment_id=_FIXED_ASSESSMENT_ID, overrides=overrides)
            decision = _evaluate(facts, compiled_gold_pack)
            assert decision.state is DecisionState.SUPPORTED_CANDIDATES
            assert [c.product_code for c in decision.candidates] == ["E33G"]
            return decision.candidates[0].score

        # Non-vacuous baseline: BOTH ranking rules fire (5 + 3).
        assert score_for(overrides) == 8
        # De-knowing either TRUE ranking fact drops exactly its own points —
        # the concrete, measurable form of "removing information never adds
        # support" on the score axis.
        assert score_for({**overrides, "commercial.wants_quote": gf.unknown("NOT_PROVIDED")}) == 3
        assert (
            score_for(
                {
                    **overrides,
                    "commercial.service_fee_budget_idr": gf.unknown("NOT_PROVIDED"),
                }
            )
            == 5
        )
        assert (
            score_for(
                {
                    **overrides,
                    "commercial.wants_quote": gf.unknown("NOT_PROVIDED"),
                    "commercial.service_fee_budget_idr": gf.unknown("NOT_PROVIDED"),
                }
            )
            == 0
        )


# ---------------------------------------------------------------------------
# (b) Fact-order invariance — wire boundary AND the evaluator's real input
# ---------------------------------------------------------------------------


class TestFactOrderInvariance:
    """The public-API property: two ``ApplicantFacts`` built from wire dicts
    with different insertion orders are the SAME assessment. This test pins
    the mechanism that makes it true — the ``ApplicantFactsData`` model
    restores declared field order at validation time — explicitly (codex
    grade P1: asserting only Decision equality here was vacuous w.r.t. the
    evaluator, because the permuted order never reached it; the evaluator-
    side property now lives in ``TestSnapshotOrderInvariance`` below)."""

    @pytest.mark.parametrize("seed", _SHUFFLE_SEEDS)
    @pytest.mark.parametrize("persona", PERSONAS, ids=[f"persona-{p.id:02d}" for p in PERSONAS])
    def test_wire_insertion_order_is_canonicalized_and_decisions_match(
        self, persona: Persona, seed: int, compiled_gold_pack: CompiledRulePack
    ) -> None:
        wire = _wire_facts(persona)
        shuffled_items = list(wire.items())
        random.Random(seed).shuffle(shuffled_items)
        shuffled_wire = dict(shuffled_items)

        # Anti-vacuity, INPUT side: the wire mapping really was permuted
        # before crossing the model boundary (35 keys, fixed seeds — a no-op
        # shuffle here means the test itself is broken).
        assert list(shuffled_wire) != list(wire), (
            f"persona {persona.id} / seed={seed}: fact shuffle did not permute the "
            "wire insertion order"
        )

        canonical_facts = _facts_from_wire(wire)
        shuffled_facts = _facts_from_wire(shuffled_wire)

        # The boundary mechanism, pinned explicitly: after validation the two
        # models expose the SAME internal field order (and the same values) —
        # caller insertion order is canonicalized away here, at the
        # ``ApplicantFacts`` boundary, before the evaluator ever runs.
        canonical_fields = list(canonical_facts.facts.model_dump(by_alias=True))
        shuffled_fields = list(shuffled_facts.facts.model_dump(by_alias=True))
        assert shuffled_fields == canonical_fields

        canonical = _evaluate(canonical_facts, compiled_gold_pack)
        shuffled = _evaluate(shuffled_facts, compiled_gold_pack)
        assert shuffled.model_dump_json() == canonical.model_dump_json(), (
            f"persona {persona.id} ({persona.label}) / seed={seed}: two wire orderings "
            "of the same facts produced different Decisions"
        )


class TestSnapshotOrderInvariance:
    """The evaluator-side property (codex grade P1 fix): permute the REAL
    input the evaluator consumes — the ``FactSnapshot.values`` mapping that
    ``FactRegistry.derive`` produces inside ``evaluate()`` — and run the
    real ``evaluator.evaluate_product`` on it. Any iteration-order
    dependency inside condition evaluation or per-product proof assembly
    (the only places snapshot order could conceivably leak) fails here.
    ``Decision``-level order invariance is then the composition of this
    property with the sorted/deduped aggregation points covered by the
    wire-level test and the rule-order tests."""

    @pytest.mark.parametrize("seed", _SHUFFLE_SEEDS)
    @pytest.mark.parametrize("persona", PERSONAS, ids=[f"persona-{p.id:02d}" for p in PERSONAS])
    def test_permuted_snapshot_yields_identical_product_proofs(
        self, persona: Persona, seed: int, compiled_gold_pack: CompiledRulePack
    ) -> None:
        facts = _facts_from_wire(_wire_facts(persona))
        snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=gf.GOLD_EFFECTIVE_AT)

        shuffled_items = list(snapshot.values.items())
        random.Random(seed).shuffle(shuffled_items)
        # Anti-vacuity: the evaluator's actual input mapping really was
        # permuted (37 entries, fixed seeds).
        assert [path for path, _ in shuffled_items] != list(snapshot.values), (
            f"persona {persona.id} / seed={seed}: snapshot shuffle did not permute the "
            "FactSnapshot.values order"
        )
        permuted_snapshot = FactSnapshot(values=dict(shuffled_items))

        purposes_fact = snapshot.values.get(FactPath.INTENT_PURPOSES)
        if not isinstance(purposes_fact, KnownFact):
            # Persona 18 (purposes UNKNOWN): ``evaluate()`` short-circuits to
            # NEEDS_INPUT BEFORE any per-product evaluation, so there is no
            # product proof for snapshot order to leak into — pin that
            # boundary behavior instead of skipping silently.
            decision = _evaluate(facts, compiled_gold_pack)
            assert decision.state is DecisionState.NEEDS_INPUT
            assert tuple(m.value for m in decision.missing_facts) == ("intent.purposes",)
            return
        purposes = frozenset(purposes_fact.value)

        for product in compiled_gold_pack.products:
            rules = compiled_gold_pack.rules_for(product, effective_at=gf.GOLD_EFFECTIVE_AT)
            canonical = evaluator.evaluate_product(
                product=product, rules=rules, facts=snapshot, purposes=purposes
            )
            permuted = evaluator.evaluate_product(
                product=product, rules=rules, facts=permuted_snapshot, purposes=purposes
            )
            assert permuted == canonical, (
                f"persona {persona.id} ({persona.label}) / {product.product_code} / "
                f"seed={seed}: permuting FactSnapshot.values changed the product proof "
                f"({canonical} != {permuted}) — the evaluator's condition/proof layer "
                "is snapshot-order-sensitive"
            )


# ---------------------------------------------------------------------------
# (c) Rule-order invariance
# ---------------------------------------------------------------------------


def _pack_with_shuffled_rules(seed: int) -> M.RulePack:
    """The canonical gold RulePack with ONLY its ``rules`` array permuted
    (seeded). Everything else — products, source records, ids, the envelope
    — is bit-identical, so any Decision difference is attributable to rule
    declaration order alone. Built via ``model_copy`` on the already-
    validated models (never a serialization round-trip), so the shuffled
    pack cannot drift from the canonical one in any other field."""
    pack = gf.build_gold_rule_pack()
    shuffled_rules = list(pack.payload.rules)
    random.Random(seed).shuffle(shuffled_rules)

    canonical_order = [rule.rule_id for rule in pack.payload.rules]
    shuffled_order = [rule.rule_id for rule in shuffled_rules]
    assert shuffled_order != canonical_order, (
        f"seed={seed}: rule shuffle did not permute the declaration order — the "
        "invariance assertion would be vacuous"
    )
    assert sorted(shuffled_order) == sorted(canonical_order)

    shuffled_payload = pack.payload.model_copy(update={"rules": tuple(shuffled_rules)}, deep=True)
    return pack.model_copy(update={"payload": shuffled_payload}, deep=True)


class TestRuleOrderInvariance:
    """Gold-pack rule-declaration shuffle: broad regression coverage that no
    aggregation point in ``evaluate()``/``build_compiled_pack`` depends on
    declaration order. Scope honesty (codex grade P1, verified by the
    reviewer's mutation probe): in the canonical pack no product has two
    co-firing rules in one stage with observable ordered output, so this
    test alone CANNOT catch a deleted ``rules_for`` sort — that detection
    lives in ``TestRuleOrderInvarianceCoFiring`` below, by construction."""

    @pytest.mark.parametrize("seed", _SHUFFLE_SEEDS)
    def test_shuffled_rule_declaration_order_yields_identical_decisions(
        self, seed: int, compiled_gold_pack: CompiledRulePack
    ) -> None:
        shuffled_pack = build_compiled_pack(_pack_with_shuffled_rules(seed))
        # Sanity: a pure permutation — same rule/product multisets.
        assert len(shuffled_pack.rules) == len(compiled_gold_pack.rules)
        assert sorted(p.product_code for p in shuffled_pack.products) == sorted(
            p.product_code for p in compiled_gold_pack.products
        )

        for persona in PERSONAS:
            facts = _facts_from_wire(_wire_facts(persona))
            canonical = _evaluate(facts, compiled_gold_pack)
            shuffled = _evaluate(facts, shuffled_pack)
            assert shuffled.model_dump_json() == canonical.model_dump_json(), (
                f"persona {persona.id} ({persona.label}) / seed={seed}: shuffling the "
                "rules' declaration order changed the Decision"
            )


# ---------------------------------------------------------------------------
# (c') Rule-order invariance — targeted co-firing packs (codex grade P1 fix)
# ---------------------------------------------------------------------------

#: The targeted packs use ``_builders``' default ``UTC_NOW``-anchored
#: validity periods (from 2026-07-18), so they are evaluated at that instant
#: rather than ``GOLD_EFFECTIVE_AT`` — the property under test (declaration
#: order vs sorted order) is instant-independent, and the gold baseline
#: facts are not period-gated.
_TARGET_EFFECTIVE_AT = datetime(2026, 7, 18, 0, 0, 0, tzinfo=timezone.utc)

#: Pinned ids (uuid5, never uuid4) so every pack variant built below shares
#: one ``rule_pack`` reference and the Decisions are comparable byte-for-byte
#: across declaration permutations.
_TARGET_NS = uuid.UUID("c2c2c2c2-c2c2-4c2c-8c2c-c2c2c2c2c2c2")
_TARGET_SOURCE_ID = str(uuid.uuid5(_TARGET_NS, "cofiring-source"))
_TARGET_PRODUCT_ID = str(uuid.uuid5(_TARGET_NS, "cofiring-product"))
_TARGET_PACK_ID = str(uuid.uuid5(_TARGET_NS, "cofiring-pack"))


def _cofiring_envelope(kind: str, declared_rule_ids: list[str]) -> dict[str, Any]:
    """One product + two PRODUCTS-scope rules of one stage, BOTH TRUE for
    the gold baseline facts (``intent.stay_days == 30``), declared in
    exactly ``declared_rule_ids`` order. ``kind="support"`` builds an
    ELIGIBILITY pair (observable ordered output:
    ``Candidate.support_rule_ids``); ``kind="review"`` builds a HUMAN_REVIEW
    pair (observable ordered output: ``Decision.review_reasons``).
    """
    rules = [
        _builders.rule(
            rule_id=rule_id,
            stage="ELIGIBILITY" if kind == "support" else "HUMAN_REVIEW",
            scope="PRODUCTS",
            product_version_ids=[_TARGET_PRODUCT_ID],
            when={"op": "eq", "fact": "intent.stay_days", "value": 30},
            effect=(
                {
                    "type": "SUPPORT",
                    "reason_code": f"SUPPORT_TARGET_{rule_id.rsplit('.', 1)[1].upper()}",
                    "covered_purposes": ["TOURISM"],
                }
                if kind == "support"
                else {
                    "type": "REQUIRE_REVIEW",
                    "reason_code": f"REVIEW_TARGET_{rule_id.rsplit('.', 1)[1].upper()}",
                }
            ),
            source_id=_TARGET_SOURCE_ID,
            required_facts=["intent.stay_days"],
        )
        for rule_id in declared_rule_ids
    ]
    payload = _builders.rule_pack_payload(
        rules=rules,
        products=[_builders.product(source_id=_TARGET_SOURCE_ID, product_id=_TARGET_PRODUCT_ID)],
        source_records=[_builders.source_record(source_id=_TARGET_SOURCE_ID)],
        rule_pack_id=_TARGET_PACK_ID,
    )
    return _builders.rule_pack_envelope(payload)


def _cofiring_pack(kind: str, declared_rule_ids: list[str]) -> CompiledRulePack:
    return build_compiled_pack(
        M.RulePack.model_validate(_cofiring_envelope(kind, declared_rule_ids))
    )


def _evaluate_cofiring(pack: CompiledRulePack) -> M.Decision:
    facts = gf.applicant_facts(assessment_id=_FIXED_ASSESSMENT_ID)
    return evaluator.evaluate(
        facts,
        pack,
        effective_at=_TARGET_EFFECTIVE_AT,
        observed_at=_TARGET_EFFECTIVE_AT,
    )


class TestRuleOrderInvarianceCoFiring:
    """The load-bearing detection a gold-pack shuffle cannot provide (codex
    grade P1): two rules in ONE stage on ONE product that BOTH fire TRUE,
    DECLARED in the exact reverse of their ``(stage.order, priority,
    rule_id)`` sorted order, with ordered observable output. The canonical
    assertions pin the SORTED order directly — if ``rules_for`` (or the
    relevant aggregation point) stopped sorting, the declaration order
    (``bbb`` before ``aaa``) would leak into the Decision and these tests
    fail. Seeded permutations then cover every other declaration order."""

    def test_two_cofiring_support_rules_emit_sorted_support_rule_ids(self) -> None:
        rule_ids = ["el.target.aaa", "el.target.bbb"]
        # Canonical pack: declared REVERSED vs sorted order (bbb before aaa).
        canonical = _evaluate_cofiring(_cofiring_pack("support", list(reversed(rule_ids))))
        assert canonical.state is DecisionState.SUPPORTED_CANDIDATES
        assert len(canonical.candidates) == 1
        candidate = canonical.candidates[0]
        # Both rules really co-fired (non-vacuity), in SORTED order despite
        # the reversed declaration (the mutation detection).
        assert candidate.support_rule_ids == ("el.target.aaa", "el.target.bbb")

        tested_orders: set[tuple[str, ...]] = set()
        for seed in _SHUFFLE_SEEDS:
            shuffled_ids = rule_ids[:]
            random.Random(seed).shuffle(shuffled_ids)
            tested_orders.add(tuple(shuffled_ids))
            variant = _evaluate_cofiring(_cofiring_pack("support", shuffled_ids))
            assert variant.model_dump_json() == canonical.model_dump_json(), (
                f"seed={seed}: declaration order {shuffled_ids} changed the Decision "
                "for two co-firing support rules"
            )
        # Anti-vacuity: with a two-rule pack, a "shuffle" that always lands
        # on the same order would make the sweep vacuous.
        assert len(tested_orders | {tuple(reversed(rule_ids))}) == 2

    def test_two_cofiring_review_rules_emit_sorted_review_reasons(self) -> None:
        rule_ids = ["review.target.aaa", "review.target.bbb"]
        canonical = _evaluate_cofiring(_cofiring_pack("review", list(reversed(rule_ids))))
        assert canonical.state is DecisionState.HUMAN_REVIEW_REQUIRED
        # Both review rules really co-fired (non-vacuity), reason codes in
        # SORTED rule order despite the reversed declaration.
        assert tuple(reason.code for reason in canonical.review_reasons) == (
            "REVIEW_TARGET_AAA",
            "REVIEW_TARGET_BBB",
        )

        tested_orders: set[tuple[str, ...]] = set()
        for seed in _SHUFFLE_SEEDS:
            shuffled_ids = rule_ids[:]
            random.Random(seed).shuffle(shuffled_ids)
            tested_orders.add(tuple(shuffled_ids))
            variant = _evaluate_cofiring(_cofiring_pack("review", shuffled_ids))
            assert variant.model_dump_json() == canonical.model_dump_json(), (
                f"seed={seed}: declaration order {shuffled_ids} changed the Decision "
                "for two co-firing review rules"
            )
        assert len(tested_orders | {tuple(reversed(rule_ids))}) == 2
