"""F13: CompiledRulePack.rules_for() must order rules by the SEMANTIC
processing order (HARD_FILTER -> HUMAN_REVIEW -> ELIGIBILITY -> RANKING per
§4.2/§4.5), not the alphabetical order of RuleStage.value
("ELIGIBILITY" < "HARD_FILTER" < "HUMAN_REVIEW" < "RANKING").
"""

from __future__ import annotations

from backend.services.visa_engine.compiler import compile_rule_pack
from backend.services.visa_engine.enums import RuleStage
from backend.services.visa_engine.fact_registry import FactRegistry
from backend.services.visa_engine.models import RulePack

from ._builders import new_uuid, product, rule, rule_pack_envelope, rule_pack_payload, source_record


def _four_stage_pack() -> RulePack:
    source_id = new_uuid()
    product_id = new_uuid()
    src = source_record(source_id=source_id)
    prod = product(product_id=product_id, source_id=source_id)

    rules = [
        rule(
            rule_id="hard-filter-rule",
            stage="HARD_FILTER",
            scope="GLOBAL",
            when={"op": "gt", "fact": "immigration.overstay_days", "value": 60},
            effect={"type": "EXCLUDE", "reason_code": "OVERSTAY"},
            source_id=source_id,
            required_facts=["immigration.overstay_days"],
        ),
        rule(
            rule_id="human-review-rule",
            stage="HUMAN_REVIEW",
            scope="GLOBAL",
            when={"op": "known", "fact": "family.sponsor_confirmed"},
            effect={"type": "REQUIRE_REVIEW", "reason_code": "NEEDS_REVIEW"},
            source_id=source_id,
            required_facts=["family.sponsor_confirmed"],
        ),
        rule(
            rule_id="eligibility-rule",
            stage="ELIGIBILITY",
            scope="GLOBAL",
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={
                "type": "SUPPORT",
                "reason_code": "TOURISM_OK",
                "covered_purposes": ["TOURISM"],
            },
            source_id=source_id,
            required_facts=["intent.purposes"],
        ),
        rule(
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

    payload = rule_pack_payload(rules=rules, products=[prod], source_records=[src])
    envelope = rule_pack_envelope(payload)
    return RulePack(**envelope)


def test_rules_for_orders_by_semantic_stage_not_alphabetical() -> None:
    pack = _four_stage_pack()
    compiled = compile_rule_pack(pack, fact_registry=FactRegistry())
    product = compiled.products[0]

    ordered = compiled.rules_for(product)
    ordered_ids = [r.rule_id for r in ordered]

    assert ordered_ids == [
        "hard-filter-rule",
        "human-review-rule",
        "eligibility-rule",
        "ranking-rule",
    ]


def test_stage_order_mapping_matches_enum_property() -> None:
    assert RuleStage.HARD_FILTER.order == 0
    assert RuleStage.HUMAN_REVIEW.order == 1
    assert RuleStage.ELIGIBILITY.order == 2
    assert RuleStage.RANKING.order == 3
