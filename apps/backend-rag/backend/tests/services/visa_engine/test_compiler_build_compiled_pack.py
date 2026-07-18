"""Tests for ``backend.services.visa_engine.compiler.build_compiled_pack``
and ``CompiledRulePack.rules_for()`` (PR3 compile-to-evaluator-form step).

``rules_for()`` must order rules by the SEMANTIC processing order
(HARD_FILTER -> HUMAN_REVIEW -> ELIGIBILITY -> RANKING per spec §4.2/§4.5),
not the alphabetical order of ``RuleStage.value``
("ELIGIBILITY" < "HARD_FILTER" < "HUMAN_REVIEW" < "RANKING").
"""

from __future__ import annotations

import uuid

import pytest

from backend.services.visa_engine import models as M
from backend.services.visa_engine.compiler import (
    CompiledProduct,
    CompiledRule,
    CompiledRulePack,
    build_compiled_pack,
    compile_rule_pack,
)
from backend.services.visa_engine.enums import RuleScope
from backend.services.visa_engine.errors import RulePackCompilationError
from backend.services.visa_engine.fact_registry import FactRegistry
from backend.tests.services.visa_engine import _builders as B
from backend.tests.services.visa_engine.conftest import (
    make_product,
    make_rule_pack,
    make_rule_pack_payload,
    make_support_rule,
)


def _four_stage_pack() -> M.RulePack:
    """One rule per stage, all GLOBAL except ELIGIBILITY (PRODUCTS-scoped) —
    enough to prove ``rules_for()``'s ordering AND scope-filtering in one
    pack. Built via ``_builders``' raw-dict helpers (this package's
    ``bundle.py``-test idiom), not ``conftest.py``'s Pydantic-object
    fixtures, since we want a full signed-envelope-shaped ``RulePack``
    covering all four stages at once.
    """

    source_id = B.new_uuid()
    product_id = B.new_uuid()
    src = B.source_record(source_id=source_id)
    prod = B.product(product_id=product_id, source_id=source_id)

    rules = [
        B.rule(
            rule_id="hard-filter-rule",
            stage="HARD_FILTER",
            scope="GLOBAL",
            when={"op": "gt", "fact": "immigration.overstay_days", "value": 60},
            effect={"type": "EXCLUDE", "reason_code": "OVERSTAY"},
            source_id=source_id,
            required_facts=["immigration.overstay_days"],
        ),
        B.rule(
            rule_id="human-review-rule",
            stage="HUMAN_REVIEW",
            scope="GLOBAL",
            when={"op": "known", "fact": "family.sponsor_confirmed"},
            effect={"type": "REQUIRE_REVIEW", "reason_code": "NEEDS_REVIEW"},
            source_id=source_id,
            required_facts=["family.sponsor_confirmed"],
        ),
        B.rule(
            rule_id="eligibility-rule",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={
                "type": "SUPPORT",
                "reason_code": "TOURISM_OK",
                "covered_purposes": ["TOURISM"],
            },
            source_id=source_id,
            required_facts=["intent.purposes"],
        ),
        B.rule(
            rule_id="ranking-rule",
            stage="RANKING",
            scope="GLOBAL",
            when={"op": "known", "fact": "commercial.wants_quote"},
            effect={"type": "ADD_SCORE", "reason_code": "WANTS_QUOTE", "points": 5},
            source_id=source_id,
            required_facts=["commercial.wants_quote"],
            on_unknown="NO_EFFECT",
        ),
    ]

    payload = B.rule_pack_payload(rules=rules, products=[prod], source_records=[src])
    envelope = B.rule_pack_envelope(payload)
    return M.RulePack(**envelope)


class TestRulesForOrdering:
    def test_rules_for_orders_by_semantic_stage_not_alphabetical(self) -> None:
        pack = _four_stage_pack()
        compiled = build_compiled_pack(pack, fact_registry=FactRegistry())
        first_product = compiled.products[0]

        ordered = compiled.rules_for(first_product)
        ordered_ids = [r.rule_id for r in ordered]

        assert ordered_ids == [
            "hard-filter-rule",
            "human-review-rule",
            "eligibility-rule",
            "ranking-rule",
        ]

    def test_global_rule_applies_to_every_product(self) -> None:
        pack = _four_stage_pack()
        compiled = build_compiled_pack(pack, fact_registry=FactRegistry())
        first_product = compiled.products[0]

        ordered = compiled.rules_for(first_product)
        global_rule_ids = {r.rule_id for r in ordered if r.scope is RuleScope.GLOBAL}
        assert global_rule_ids == {"hard-filter-rule", "human-review-rule", "ranking-rule"}

    def test_products_scoped_rule_excluded_for_non_matching_product(self) -> None:
        pack = _four_stage_pack()
        compiled = build_compiled_pack(pack, fact_registry=FactRegistry())

        other_product = CompiledProduct(
            product_version_id=uuid.uuid4(),  # not in the pack
            product_code="OTHER",
            product=compiled.products[0].product,
        )
        ordered = compiled.rules_for(other_product)
        ordered_ids = [r.rule_id for r in ordered]
        # GLOBAL rules still apply; the PRODUCTS-scoped eligibility rule does not.
        assert "eligibility-rule" not in ordered_ids
        assert ordered_ids == ["hard-filter-rule", "human-review-rule", "ranking-rule"]


class TestBuildCompiledPackStructure:
    def test_returns_compiled_rule_pack(self, minimal_valid_pack: M.RulePack) -> None:
        compiled = build_compiled_pack(minimal_valid_pack)
        assert isinstance(compiled, CompiledRulePack)
        assert compiled.rule_pack_id == minimal_valid_pack.payload.rule_pack_id
        assert compiled.sequence == minimal_valid_pack.payload.sequence
        assert compiled.version == minimal_valid_pack.payload.version
        assert compiled.environment == minimal_valid_pack.payload.environment

    def test_compiled_products_preserve_identity(self, minimal_valid_pack: M.RulePack) -> None:
        # `compiled.product` is the REVALIDATED pack's product (see
        # build_compiled_pack's docstring: every check runs against the
        # re-parsed pack, never the caller's original instance) — equal by
        # value to the source, never the same object.
        compiled = build_compiled_pack(minimal_valid_pack)
        assert len(compiled.products) == len(minimal_valid_pack.payload.products)
        source_product = minimal_valid_pack.payload.products[0]
        compiled_product = compiled.products[0]
        assert isinstance(compiled_product, CompiledProduct)
        assert compiled_product.product_version_id == source_product.product_version_id
        assert compiled_product.product_code == source_product.product_code
        assert compiled_product.product == source_product

    def test_compiled_rule_carries_ast_depth_and_node_count(
        self, minimal_valid_pack: M.RulePack
    ) -> None:
        compiled = build_compiled_pack(minimal_valid_pack)
        assert len(compiled.rules) == 1
        compiled_rule = compiled.rules[0]
        assert isinstance(compiled_rule, CompiledRule)
        assert compiled_rule.ast_depth >= 1
        assert compiled_rule.ast_node_count >= 1
        assert compiled_rule.required_facts == frozenset({"intent.purposes"})

    def test_global_rule_has_none_product_version_ids(self) -> None:
        pack = _four_stage_pack()
        compiled = build_compiled_pack(pack, fact_registry=FactRegistry())
        hard_filter = next(r for r in compiled.rules if r.rule_id == "hard-filter-rule")
        assert hard_filter.scope is RuleScope.GLOBAL
        assert hard_filter.product_version_ids is None

    def test_products_rule_has_frozenset_product_version_ids(self) -> None:
        pack = _four_stage_pack()
        compiled = build_compiled_pack(pack, fact_registry=FactRegistry())
        eligibility = next(r for r in compiled.rules if r.rule_id == "eligibility-rule")
        assert eligibility.scope is RuleScope.PRODUCTS
        assert eligibility.product_version_ids == frozenset(
            {compiled.products[0].product_version_id}
        )


class TestBuildCompiledPackPrecondition:
    def test_raises_on_pack_that_fails_compile_rule_pack(
        self, source_record: M.SourceRecord
    ) -> None:
        """A pack with a REQUIRED_FACTS_MISMATCH defect must never reach
        CompiledRulePack — build_compiled_pack re-checks the precondition
        itself rather than trusting the caller."""

        product_id = uuid.uuid4()
        prod = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        broken_rule = make_support_rule(
            rule_id="rule.broken",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            required_facts=(),  # `when` references intent.purposes; declared empty
        )
        payload = make_rule_pack_payload(
            rules=[broken_rule], products=[prod], source_records=[source_record]
        )
        pack = make_rule_pack(payload)

        report = compile_rule_pack(pack)
        assert not report.ok  # sanity: the fixture really is broken

        with pytest.raises(RulePackCompilationError, match="REQUIRED_FACTS_MISMATCH"):
            build_compiled_pack(pack)

    def test_innocent_pack_never_raises(self, minimal_valid_pack: M.RulePack) -> None:
        compiled = build_compiled_pack(minimal_valid_pack)
        assert isinstance(compiled, CompiledRulePack)
