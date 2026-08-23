"""Golden and adversarial tests for the same-pass deterministic trace."""

from __future__ import annotations

from datetime import timedelta

import pytest

from backend.services.visa_engine.compiler import CompiledRulePack
from backend.services.visa_engine.crypto import resolve_engine_hmac_keyring
from backend.services.visa_engine.decision_seal import seal_decision, verify_decision_seal
from backend.services.visa_engine.enums import (
    EngineMode,
    Environment,
    RuleScope,
    RuleStage,
    TruthValue,
)
from backend.services.visa_engine.evaluate_path import _save_evaluate_decision
from backend.services.visa_engine.evaluator import EvaluationResult, evaluate_with_trace
from backend.tests.services.visa_engine.gold_harness import loader as gold_loader


def _business_result() -> tuple[CompiledRulePack, EvaluationResult]:
    compiled = gold_loader.load_and_compile_rule_pack()
    persona = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json")
    result = evaluate_with_trace(
        persona.facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    return compiled, result


def test_trace_golden_vector_and_observed_clock_invariance() -> None:
    compiled, first = _business_result()
    persona = gold_loader.load_persona(gold_loader.PERSONAS_DIR / "02_business_c2.json")
    second = evaluate_with_trace(
        persona.facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT + timedelta(hours=6),
    )

    # Golden vector: changes require an explicit review of the canonical
    # trace contract, not an automatic fixture rewrite.
    #
    # Moved 2026-08-10 (`acad1aff…` -> `73aa8af1…`) when `sponsor.type` joined
    # the fact vocabulary. Reviewed, and the reason is recorded here because a
    # golden literal that changes without a recorded cause is indistinguishable
    # from one that was rubber-stamped: `facts_hmac` is an HMAC over
    # `canonical_fact_payload`, which is `facts.model_dump(by_alias=True)` —
    # the WHOLE snapshot, not the subset some rule happened to read. So every
    # persona gaining one `UNKNOWN` key necessarily moves it.
    #
    # Moved again 2026-08-23 (`73aa8af1…` -> `4e18c56e…`) when
    # `family.stepchild_marriage_certificate_confirmed`,
    # `family.stepchild_birth_certificate_confirmed` and
    # `family.sponsor_permit_basis` joined the fact vocabulary (vocabulary-only
    # PR — no rule consumes them yet). Same precedent, same verification:
    # zero of the 84 trace nodes name any of the three new facts (still 84,
    # unchanged count), and all 23 `gold_harness` personas plus all 20
    # canonical `test_evaluator_gold` personas still replay their expected
    # decisions unchanged (`test_gold_replay_artifact.py` zero-divergence).
    # If this literal ever moves again while the node set or a persona's
    # decision ALSO changed, that is a behaviour change wearing a fixture's
    # clothes — do not update the number, find out what evaluated differently.
    assert (
        first.trace.sha256() == "4e18c56e329acd1d16a290fbdb08e50c52afbdae8f30b702c8d64bf302db3b2c"
    )
    assert first.decision.trace_sha256 == first.trace.sha256()
    assert second.trace == first.trace
    assert second.decision.trace_sha256 == first.decision.trace_sha256


def test_trace_is_complete_canonically_ordered_and_records_all_tri_states() -> None:
    compiled, result = _business_result()
    nodes = result.trace.ordered_nodes
    assert tuple(node.ordering_key() for node in nodes) == tuple(
        sorted(node.ordering_key() for node in nodes)
    )

    active_products = tuple(
        product
        for product in compiled.products
        if product.product.status.value == "ACTIVE"
        and product.product.valid_period.from_ <= gold_loader.GOLD_EFFECTIVE_AT
        and (
            product.product.valid_period.to is None
            or gold_loader.GOLD_EFFECTIVE_AT < product.product.valid_period.to
        )
    )
    global_prepass_count = sum(
        rule.scope is RuleScope.GLOBAL
        and rule.stage is RuleStage.HUMAN_REVIEW
        and rule.source_rule.valid_period.from_ <= gold_loader.GOLD_EFFECTIVE_AT
        and (
            rule.source_rule.valid_period.to is None
            or gold_loader.GOLD_EFFECTIVE_AT < rule.source_rule.valid_period.to
        )
        for rule in compiled.rules
    )
    product_proof_count = sum(
        rule.stage is not RuleStage.RANKING
        for product in active_products
        for rule in compiled.rules_for(product, effective_at=gold_loader.GOLD_EFFECTIVE_AT)
    )
    candidate_ids = {candidate.product_version_id for candidate in result.decision.candidates}
    ranking_count = sum(
        rule.stage is RuleStage.RANKING
        for product in active_products
        if product.product_version_id in candidate_ids
        for rule in compiled.rules_for(product, effective_at=gold_loader.GOLD_EFFECTIVE_AT)
    )
    assert len(nodes) == global_prepass_count + product_proof_count + ranking_count

    rules_by_id = {rule.rule_id: rule for rule in compiled.rules}
    for node in nodes:
        rule = rules_by_id[node.rule_id]
        # ``evaluate_condition`` traverses every AST child. The trace carries
        # every signed required path even when an earlier child decides truth.
        assert {path.value for path in node.referenced_fact_paths} == set(rule.required_facts)

    contradictory = gold_loader.load_persona(
        gold_loader.PERSONAS_DIR / "20_contradictory_facts_no_crash.json"
    )
    adversarial = evaluate_with_trace(
        contradictory.facts,
        compiled,
        effective_at=gold_loader.GOLD_EFFECTIVE_AT,
        observed_at=gold_loader.GOLD_EFFECTIVE_AT,
    )
    assert {node.condition_result for node in adversarial.trace.ordered_nodes} == {
        TruthValue.TRUE,
        TruthValue.FALSE,
        TruthValue.UNKNOWN,
    }
    assert any(node.unknown_facts for node in adversarial.trace.ordered_nodes)


def test_trace_contains_no_raw_fact_values_and_tampering_fails_closed() -> None:
    _, result = _business_result()
    wire = result.trace.model_dump(mode="json")

    def assert_no_value_key(value: object) -> None:
        if isinstance(value, dict):
            assert "value" not in value
            for child in value.values():
                assert_no_value_key(child)
        elif isinstance(value, list):
            for child in value:
                assert_no_value_key(child)

    assert_no_value_key(wire)

    first_node = result.trace.ordered_nodes[0]
    changed_truth = (
        TruthValue.TRUE if first_node.condition_result is not TruthValue.TRUE else TruthValue.FALSE
    )
    tampered_trace = result.trace.model_copy(
        update={
            "ordered_nodes": (
                first_node.model_copy(update={"condition_result": changed_truth}),
                *result.trace.ordered_nodes[1:],
            )
        }
    )
    assert not tampered_trace.matches(result.decision.trace_sha256)

    key = resolve_engine_hmac_keyring(
        Environment.TEST,
        gold_loader.GOLD_EFFECTIVE_AT,
    ).minting_key
    sealed = seal_decision(result.decision, key=key, trace=result.trace)
    assert verify_decision_seal(sealed, key=key, trace=result.trace)
    assert not verify_decision_seal(sealed, key=key, trace=tampered_trace)
    with pytest.raises(ValueError, match="does not match"):
        seal_decision(result.decision, key=key, trace=tampered_trace)


@pytest.mark.asyncio
async def test_persistence_rejects_an_unsealed_decision_before_database_access() -> None:
    _, result = _business_result()
    assert result.decision.rule_pack is not None
    assert result.decision.decision_id is not None
    with pytest.raises(ValueError, match="trace-bound and authenticated"):
        await _save_evaluate_decision(
            object(),  # type: ignore[arg-type] -- must never be dereferenced
            decision=result.decision,
            rule_pack_db_id=result.decision.rule_pack.rule_pack_id,
            ruleset_activation_id=result.decision.decision_id,
            environment="TEST",
            engine_mode=EngineMode.SHADOW,
            request_fingerprint=b"f" * 32,
            request_category="business",
            traffic_source="synthetic_gold",
        )
