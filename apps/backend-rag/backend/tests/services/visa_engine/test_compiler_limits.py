"""Compiler limit/invariant tests: AST depth 12, condition nodes 256, an
unregistered fact path, a RANKING rule referencing a legal (non-commercial)
fact, and the happy path (a small well-formed pack compiles).

Spec: research/visa/.../round2-codex-engine-concretization.md line 2281
("Maximum AST depth 12, condition nodes 256, rules 4096, products 256.").
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.visa_engine.compiler import (
    MAX_AST_DEPTH,
    MAX_CONDITION_NODES,
    CompiledRulePack,
    compile_rule_pack,
)
from backend.services.visa_engine.errors import RulePackCompilationError
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_SPECS, FactRegistry
from backend.services.visa_engine.models import RulePack

from ._builders import minimal_valid_envelope


def _leaf() -> dict[str, Any]:
    return {"op": "known", "fact": "immigration.overstay_days"}


def _not_chain(total_depth: int) -> dict[str, Any]:
    """A condition tree of exactly `total_depth` levels (leaf counts as 1)."""

    cond: dict[str, Any] = _leaf()
    for _ in range(total_depth - 1):
        cond = {"op": "not", "arg": cond}
    return cond


def _condition_with_node_count(target_total_nodes: int) -> dict[str, Any]:
    """Build a condition with exactly `target_total_nodes` total condition
    nodes, shaped as a top-level `all` of up to 64 groups (each group is
    either a single leaf, or an `all` wrapping 3 leaves = 4 nodes/group) —
    keeps depth at 3 regardless of node count so this exercises the
    node-count limit independently of the depth limit."""

    remaining = target_total_nodes - 1  # minus the top-level `all` node itself
    assert remaining > 0
    children: list[dict[str, Any]] = []
    while remaining > 0:
        if remaining == 1:
            children.append(_leaf())
            remaining -= 1
        else:
            group_leaves = min(3, remaining - 1)
            children.append({"op": "all", "args": [_leaf() for _ in range(group_leaves)]})
            remaining -= group_leaves + 1
    assert len(children) <= 64, "test fixture must respect the args maxItems:64 schema limit"
    return {"op": "all", "args": children}


def _envelope_with_hard_filter_condition(when: dict[str, Any]) -> dict[str, Any]:
    envelope = minimal_valid_envelope()
    envelope["payload"]["rules"][0]["when"] = when
    return envelope


class TestAstDepthLimit:
    def test_depth_at_limit_compiles(self) -> None:
        envelope = _envelope_with_hard_filter_condition(_not_chain(MAX_AST_DEPTH))
        pack = RulePack(**envelope)
        compiled = compile_rule_pack(pack, fact_registry=FactRegistry())
        assert isinstance(compiled, CompiledRulePack)

    def test_depth_over_limit_rejected(self) -> None:
        envelope = _envelope_with_hard_filter_condition(_not_chain(MAX_AST_DEPTH + 1))
        pack = RulePack(**envelope)
        with pytest.raises(RulePackCompilationError, match="depth"):
            compile_rule_pack(pack, fact_registry=FactRegistry())


class TestConditionNodeCountLimit:
    def test_node_count_at_limit_compiles(self) -> None:
        envelope = _envelope_with_hard_filter_condition(
            _condition_with_node_count(MAX_CONDITION_NODES)
        )
        pack = RulePack(**envelope)
        compiled = compile_rule_pack(pack, fact_registry=FactRegistry())
        assert isinstance(compiled, CompiledRulePack)

    def test_node_count_over_limit_rejected(self) -> None:
        envelope = _envelope_with_hard_filter_condition(
            _condition_with_node_count(MAX_CONDITION_NODES + 1)
        )
        pack = RulePack(**envelope)
        with pytest.raises(RulePackCompilationError, match="nodes"):
            compile_rule_pack(pack, fact_registry=FactRegistry())


class TestFactPathRegistration:
    def test_unregistered_fact_path_rejected(self) -> None:
        """FactRegistry is an injected parameter — a registry deliberately
        missing a spec for an otherwise wire-valid fact path must fail
        compilation, even though the same rule pack compiles fine against
        the default (complete) registry."""

        envelope = minimal_valid_envelope()
        pack = RulePack(**envelope)

        full_registry = FactRegistry()
        compile_rule_pack(
            pack, fact_registry=full_registry
        )  # sanity: compiles against full registry

        reduced_registry = FactRegistry(
            specs=[s for s in DEFAULT_FACT_SPECS if s.path != "immigration.overstay_days"]
        )
        with pytest.raises(RulePackCompilationError, match="unregistered fact path"):
            compile_rule_pack(pack, fact_registry=reduced_registry)


class TestRankingLegalFactForbidden:
    def test_ranking_rule_referencing_legal_fact_rejected(self) -> None:
        envelope = minimal_valid_envelope()
        ranking_rule = envelope["payload"]["rules"][2]
        assert ranking_rule["stage"] == "RANKING"
        # immigration.overstay_days is a legal fact (commercial_only=False) -
        # forbidden in a RANKING-stage rule's `when`.
        ranking_rule["when"] = {"op": "gt", "fact": "immigration.overstay_days", "value": 10}
        ranking_rule["required_facts"] = ["immigration.overstay_days"]

        pack = RulePack(**envelope)
        with pytest.raises(RulePackCompilationError, match="RANKING"):
            compile_rule_pack(pack, fact_registry=FactRegistry())

    def test_ranking_rule_referencing_commercial_fact_compiles(self) -> None:
        envelope = minimal_valid_envelope()
        ranking_rule = envelope["payload"]["rules"][2]
        assert ranking_rule["stage"] == "RANKING"
        assert ranking_rule["when"] == {"op": "known", "fact": "commercial.wants_quote"}

        pack = RulePack(**envelope)
        compiled = compile_rule_pack(pack, fact_registry=FactRegistry())
        assert isinstance(compiled, CompiledRulePack)


class TestHappyPath:
    def test_small_well_formed_pack_compiles(self) -> None:
        envelope = minimal_valid_envelope()
        pack = RulePack(**envelope)
        compiled = compile_rule_pack(pack, fact_registry=FactRegistry())

        assert len(compiled.rules) == 3
        assert len(compiled.products) == 1
        assert str(compiled.rule_pack_id) == envelope["payload"]["rule_pack_id"]

        product = compiled.products[0]
        rules_for_product = compiled.rules_for(product)
        rule_ids = [r.rule_id for r in rules_for_product]
        # GLOBAL rules (hf-overstay, rank-budget) + the PRODUCTS rule naming this product
        assert set(rule_ids) == {"hf-overstay", "el-tourism", "rank-budget"}


class TestRulesAndProductsCountLimits:
    def test_too_many_products_rejected(self) -> None:
        """Defense-in-depth re-check independent of how `pack` was
        constructed — Pydantic's own `max_length=256` on
        `RulePackPayload.products` already prevents building such a `pack`
        through normal construction, so this constructs the payload via
        `model_construct` to bypass that validation and exercise the
        compiler's own guard directly."""

        envelope = minimal_valid_envelope()
        pack = RulePack(**envelope)

        oversized_products = pack.payload.products * 257  # 257 > MAX_PRODUCTS (256)
        bypassed_payload = pack.payload.model_copy(update={"products": oversized_products})
        bypassed_pack = pack.model_copy(update={"payload": bypassed_payload})

        with pytest.raises(RulePackCompilationError, match="products"):
            compile_rule_pack(bypassed_pack, fact_registry=FactRegistry())
