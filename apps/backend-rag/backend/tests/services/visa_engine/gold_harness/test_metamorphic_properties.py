"""Three metamorphic properties asserted across ALL 23 gold personas, run
against the REAL evaluator (never re-derived by hand):

(a) **Monotonicity** -- de-knowing a single known fact (KNOWN -> UNKNOWN)
    can only move a product's proof state to one of a small, PRECEDENCE-
    ORDERED set of legal successors (see ``_ALLOWED_DEKNOW_TRANSITIONS``
    below); it can never flip toward a MORE decisive/permissive outcome
    (e.g. never EXCLUDED -> SUPPORTED, never SUPPORTED -> UNSUPPORTED,
    never anything -> a *different* stage's TRUE-firing verdict that wasn't
    already latently true). This is the strong-Kleene monotonicity theorem
    (removing information can only move a condition's truth toward UNKNOWN,
    never resolve it -- already exercised at the leaf level by
    ``test_ast_truth_tables.py``) lifted to the per-product proof level,
    where ``evaluate_product``'s own STAGED short-circuiting (spec Sec 4.2:
    HARD_FILTER-TRUE wins outright, then HUMAN_REVIEW-TRUE, only then
    BLOCKED_UNKNOWN/ELIGIBILITY) adds one genuinely interesting nuance a
    naive "only degrades to BLOCKED_UNKNOWN" claim would miss and this
    harness caught empirically while first writing this test: de-knowing the
    fact that made a HARD_FILTER rule fire TRUE can "unmask" an
    independently-TRUE HUMAN_REVIEW rule that was always true underneath it
    but never reached (the short-circuit returned EXCLUDED before the review
    stage ever ran) -- so EXCLUDED's legal successor set includes REVIEW, not
    just BLOCKED_UNKNOWN.

    Updated 2026-08-12 alongside the ``adapter.py`` review/input on_unknown
    split (see that module's docstring fix 2): the same "unmask" nuance also
    applies to SUPPORTED and UNSUPPORTED. Both require clearing the
    HARD_FILTER and HUMAN_REVIEW stages with no *consequential* (on_unknown
    != NO_EFFECT) unknowns before the ELIGIBILITY stage is ever consulted --
    but a GLOBAL HUMAN_REVIEW rule can be sitting there, resolved definitely
    FALSE against the persona's fully-KNOWN facts, without depending on any
    fact the ELIGIBILITY-covering rules themselves reference (e.g.
    ``hr-calling-visa`` keys only on ``person.nationalities``, unrelated to
    most products' own SUPPORT conditions). De-knowing exactly that
    unrelated fact turns the review rule's condition UNKNOWN, and since it
    declares ``on_unknown=HUMAN_REVIEW`` it escalates straight to REVIEW --
    reached AFTER the stage that produced the original SUPPORTED/UNSUPPORTED
    verdict was already past, so it silently overrides it. Empirically this
    fires on essentially every persona's C1 product (nationalities is a
    HARD_FILTER/HUMAN_REVIEW input nearly everywhere but rarely an
    ELIGIBILITY one). SUPPORTED and UNSUPPORTED's legal successor sets both
    now include REVIEW for this reason.

    BLOCKED_UNKNOWN is NO LONGER strictly absorbing either, for the same
    root cause one precedence tier over: ``evaluate_product``'s own
    docstring (see ``adapter.py``) is explicit that
    ``on_unknown=HUMAN_REVIEW`` unknowns from the HARD_FILTER/HUMAN_REVIEW
    stages are checked, and win, BEFORE ``on_unknown=NEEDS_INPUT`` unknowns
    from those same two stages -- which are themselves checked BEFORE
    anything ELIGIBILITY-stage-driven (SUPPORTED/UNSUPPORTED/an
    ELIGIBILITY-stage BLOCKED_UNKNOWN). So a BLOCKED_UNKNOWN baseline caused
    by an ELIGIBILITY-stage unknown (e.g. persona 10's E30, blocked on
    ``study.sponsor_confirmed``) can still be pre-empted by de-knowing an
    UNRELATED fact that unmasks a HARD_FILTER/HUMAN_REVIEW-stage
    ``on_unknown=HUMAN_REVIEW`` rule (persona 10's KR nationality, known
    and not calling-visa-listed in the baseline, resolves ``hr-calling-visa``
    FALSE; de-knowing it makes that rule's own condition UNKNOWN, which
    escalates straight to REVIEW ahead of the eligibility-stage block that
    was already there) -- moving BLOCKED_UNKNOWN -> REVIEW. This is not
    "resolving" BLOCKED_UNKNOWN toward more certainty (which would violate
    monotonicity); REVIEW is a DIFFERENT non-decisive verdict that simply
    sits earlier in ``evaluate_product``'s own total precedence order, and
    removing information can still move you earlier in that order, just
    never all the way to a decisive SUPPORTED/EXCLUDED/UNSUPPORTED.

(b) **Fact-order invariance** -- shuffling the insertion order of the
    ``FactSnapshot.values`` mapping never changes any outcome. A dict/
    mapping is a SET of facts semantically; nothing in ``evaluate_condition``
    or this harness's ``adapter.py`` should depend on iteration order.

(c) **Rule-order invariance** -- shuffling the declaration order of the
    ``rules`` array in the SOURCE JSON pack never changes any outcome, for
    any persona x any product. This is the direct regression test for
    ``CompiledRulePack.rules_for``'s ``sorted(..., key=(stage.order,
    priority, rule_id))`` -- remove that sort and this test fails.

All three run a few FIXED shuffles (seeded ``random.Random``) rather than a
single arbitrary one, per the task brief's "a few fixed shuffles with
different seeds" instruction -- this is deterministic property testing
(fixed seeds, reproducible), not fuzzing.
"""

from __future__ import annotations

import json
import random
from types import MappingProxyType

import pytest

from backend.services.visa_engine.ast import FactSnapshot, KnownFact, UnknownFact
from backend.services.visa_engine.compiler import build_compiled_pack, compile_rule_pack
from backend.services.visa_engine.enums import UnknownReason
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.models import RulePack

from . import adapter, loader
from .harness_utils import product_by_code

PACK = loader.load_and_compile_rule_pack()
PERSONAS = loader.load_all_personas()
PRODUCT_CODES = sorted(p.product_code for p in PACK.products)
_PERSONAS_BY_ID = {p.persona_id: p for p in PERSONAS}

_SHUFFLE_SEEDS = (0, 1, 2)


# ---------------------------------------------------------------------------
# (a) Monotonicity
# ---------------------------------------------------------------------------


#: Legal successor states for each baseline proof state after de-knowing
#: exactly one fact (see the module docstring's "Monotonicity" section for
#: the empirically-caught EXCLUDED -> REVIEW nuance, and the 2026-08-12
#: update for SUPPORTED/UNSUPPORTED -> REVIEW and BLOCKED_UNKNOWN -> REVIEW).
#: ``BLOCKED_UNKNOWN`` can still only ever move to another non-decisive
#: verdict (REVIEW or itself) -- removing information never re-adds enough
#: certainty to reach a decisive SUPPORTED/EXCLUDED/UNSUPPORTED.
_ALLOWED_DEKNOW_TRANSITIONS: dict[adapter.ProofState, frozenset[adapter.ProofState]] = {
    adapter.ProofState.EXCLUDED: frozenset(
        {adapter.ProofState.EXCLUDED, adapter.ProofState.REVIEW, adapter.ProofState.BLOCKED_UNKNOWN}
    ),
    adapter.ProofState.REVIEW: frozenset(
        {adapter.ProofState.REVIEW, adapter.ProofState.BLOCKED_UNKNOWN}
    ),
    adapter.ProofState.SUPPORTED: frozenset(
        {
            adapter.ProofState.SUPPORTED,
            adapter.ProofState.REVIEW,
            adapter.ProofState.BLOCKED_UNKNOWN,
        }
    ),
    adapter.ProofState.UNSUPPORTED: frozenset(
        {
            adapter.ProofState.UNSUPPORTED,
            adapter.ProofState.REVIEW,
            adapter.ProofState.BLOCKED_UNKNOWN,
        }
    ),
    adapter.ProofState.BLOCKED_UNKNOWN: frozenset(
        {adapter.ProofState.BLOCKED_UNKNOWN, adapter.ProofState.REVIEW}
    ),
}


def _deknow(snapshot: FactSnapshot, path) -> FactSnapshot:
    """Return a new snapshot with exactly one fact converted KNOWN -> UNKNOWN.
    A no-op (returns the same snapshot) if the fact is already unknown."""
    current = snapshot.values.get(path)
    if not isinstance(current, KnownFact):
        return snapshot
    new_values = dict(snapshot.values)
    new_values[path] = UnknownFact(reason=UnknownReason.NOT_PROVIDED)
    return FactSnapshot(values=MappingProxyType(new_values))


class TestMonotonicity:
    @pytest.mark.parametrize("persona_id", sorted(_PERSONAS_BY_ID))
    def test_deknowing_any_fact_never_produces_a_different_definite_state(
        self, persona_id: str
    ) -> None:
        persona = _PERSONAS_BY_ID[persona_id]
        baseline_snapshot = persona.derive_snapshot()
        known_paths = [
            path for path, v in baseline_snapshot.values.items() if isinstance(v, KnownFact)
        ]
        assert known_paths, f"{persona_id}: fixture has zero KNOWN facts -- nothing to de-know"

        for product_code in PRODUCT_CODES:
            product = product_by_code(PACK, product_code)
            rules = PACK.rules_for(product, effective_at=loader.GOLD_EFFECTIVE_AT)
            baseline_proof = adapter.evaluate_product(product, rules, baseline_snapshot)

            allowed = _ALLOWED_DEKNOW_TRANSITIONS[baseline_proof.state]
            for path in known_paths:
                deknowed_snapshot = _deknow(baseline_snapshot, path)
                new_proof = adapter.evaluate_product(product, rules, deknowed_snapshot)
                assert new_proof.state in allowed, (
                    f"{persona_id} / {product_code}: de-knowing {path.value} moved proof "
                    f"from {baseline_proof.state.value} to {new_proof.state.value}, not in "
                    f"the legal successor set {sorted(s.value for s in allowed)} "
                    "(monotonicity: removing information can never manufacture a NEW "
                    "TRUE-firing verdict that wasn't already latently true underneath a "
                    "short-circuit, and can never resolve BLOCKED_UNKNOWN)"
                )


# ---------------------------------------------------------------------------
# (b) Fact-order invariance
# ---------------------------------------------------------------------------


class TestFactOrderInvariance:
    @pytest.mark.parametrize("seed", _SHUFFLE_SEEDS)
    @pytest.mark.parametrize("persona_id", sorted(_PERSONAS_BY_ID))
    def test_shuffled_fact_insertion_order_matches_canonical(
        self, persona_id: str, seed: int
    ) -> None:
        persona = _PERSONAS_BY_ID[persona_id]
        canonical_snapshot = persona.derive_snapshot()

        items = list(canonical_snapshot.values.items())
        rng = random.Random(seed)
        shuffled_items = items[:]
        rng.shuffle(shuffled_items)
        shuffled_snapshot = FactSnapshot(values=MappingProxyType(dict(shuffled_items)))

        for product_code in PRODUCT_CODES:
            product = product_by_code(PACK, product_code)
            rules = PACK.rules_for(product, effective_at=loader.GOLD_EFFECTIVE_AT)
            canonical_proof = adapter.evaluate_product(product, rules, canonical_snapshot)
            shuffled_proof = adapter.evaluate_product(product, rules, shuffled_snapshot)
            assert shuffled_proof == canonical_proof, (
                f"{persona_id} / {product_code} / seed={seed}: shuffled fact-insertion-order "
                f"proof {shuffled_proof} differs from canonical {canonical_proof}"
            )


# ---------------------------------------------------------------------------
# (c) Rule-order invariance
# ---------------------------------------------------------------------------


def _pack_with_shuffled_rules(seed: int):
    raw = loader.load_rule_pack_raw()
    rules = raw["payload"]["rules"]
    rng = random.Random(seed)
    shuffled = rules[:]
    rng.shuffle(shuffled)
    # Deep-copy via round-trip so mutating this dict never touches any
    # other test's view of the raw fixture (json.load in loader.py returns
    # a fresh dict per call already, but this stays correct even if that
    # changes).
    raw = json.loads(json.dumps(raw))
    raw["payload"]["rules"] = shuffled
    pack = RulePack.model_validate(raw)
    report = compile_rule_pack(pack, fact_registry=DEFAULT_FACT_REGISTRY)
    assert report.ok, (
        f"shuffled-rules pack (seed={seed}) unexpectedly fails compile_rule_pack: "
        + "; ".join(f"{e.code}: {e.message}" for e in report.errors)
    )
    return build_compiled_pack(pack, fact_registry=DEFAULT_FACT_REGISTRY)


class TestRuleOrderInvariance:
    @pytest.mark.parametrize("seed", _SHUFFLE_SEEDS)
    def test_shuffled_rule_declaration_order_matches_canonical(self, seed: int) -> None:
        shuffled_pack = _pack_with_shuffled_rules(seed)
        # Same product set (products array itself is untouched), sanity-check.
        assert sorted(p.product_code for p in shuffled_pack.products) == PRODUCT_CODES
        assert len(shuffled_pack.rules) == len(PACK.rules)

        for persona in PERSONAS:
            snapshot = persona.derive_snapshot()
            for product_code in PRODUCT_CODES:
                canonical_product = product_by_code(PACK, product_code)
                canonical_rules = PACK.rules_for(
                    canonical_product, effective_at=loader.GOLD_EFFECTIVE_AT
                )
                canonical_proof = adapter.evaluate_product(
                    canonical_product, canonical_rules, snapshot
                )

                shuffled_product = product_by_code(shuffled_pack, product_code)
                shuffled_rules = shuffled_pack.rules_for(
                    shuffled_product, effective_at=loader.GOLD_EFFECTIVE_AT
                )
                shuffled_proof = adapter.evaluate_product(
                    shuffled_product, shuffled_rules, snapshot
                )

                assert shuffled_proof == canonical_proof, (
                    f"{persona.persona_id} / {product_code} / seed={seed}: shuffled "
                    f"rule-declaration-order proof {shuffled_proof} differs from canonical "
                    f"{canonical_proof}"
                )
