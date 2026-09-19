"""Unit tests for `review_hold_inventory.py` — the PR-O1 keystone.

Ground-truth strategy: the counts against the REAL signed pack are asserted
with the sequence baked into the assertion message (a seq-23 fold that
changes the count fails loudly, naming the sequence, instead of silently
grading against a stale number). `test_inventory_is_a_derivation_not_a_hand_list`
then proves this is a real derivation and not a hand list (cicatrix family
#3's guilt-AND-innocence discipline): a synthetic pack with one extra
HUMAN_REVIEW rule must move the count, because a hardcoded ``9`` never
would.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from backend.scripts.visa_engine.review_hold_inventory import (
    DEFAULT_FACT_MAPPER_PATH,
    DEFAULT_TREE_TS_PATH,
    adapter_review_codes,
    load_highest_signed_pack,
    minor_privacy_review_code,
    orphan_review_gate_items,
    pack_review_rules,
    pack_unknown_escalations,
    split_disclosed_review_codes,
)
from backend.services.visa_engine import models as M
from backend.services.visa_engine.api_models import DisclosedReviewFlag
from backend.services.visa_engine.evaluate_path import (
    HOLDING_DISCLOSED_FLAGS,
    MINOR_GUARDIAN_PRIVACY_REVIEW_CODE,
)
from backend.tests.services.visa_engine.conftest import (
    make_product,
    make_rule_pack_payload,
    make_source_record,
)

#: A single, fully-valid `Rule` used as the building block for the synthetic
#: packs below — never the census's own pack, so this test never depends on
#: what the real signed pack happens to contain today.
_SOURCE_REF = uuid.uuid4()
_OPEN_FROM = datetime(2026, 7, 17, 0, 0, 0, tzinfo=timezone.utc)


def _synthetic_review_rule(rule_id: str) -> M.Rule:
    return M.Rule(
        rule_id=rule_id,
        stage="HUMAN_REVIEW",
        scope="GLOBAL",
        product_version_ids=None,
        priority=100,
        valid_period={"from": _OPEN_FROM, "to": None},
        when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
        effect={"type": "REQUIRE_REVIEW", "reason_code": "SYNTHETIC_TEST_REVIEW"},
        on_unknown="NO_EFFECT",
        required_facts=["intent.purposes"],
        source_refs=[_SOURCE_REF],
        explanation_key="explain.synthetic-review",
        safety_critical=True,
    )


def _synthetic_payload(*, rules: list[M.Rule]) -> M.RulePackPayload:
    source_record = make_source_record()
    product = make_product(
        product_version_id=uuid.uuid4(), source_refs=[source_record.source_record_id]
    )
    return make_rule_pack_payload(
        rules=rules,
        products=[product],
        source_records=[source_record],
        sequence=1,
    )


@pytest.fixture(scope="module")
def real_pack() -> M.RulePackPayload:
    return load_highest_signed_pack()


def test_inventory_counts_match_the_signed_pack(real_pack: M.RulePackPayload) -> None:
    review_rules = pack_review_rules(real_pack)
    escalations = pack_unknown_escalations(real_pack)
    assert len(review_rules) == 9, (
        f"sequence {real_pack.sequence}: expected 9 HUMAN_REVIEW-stage rules, "
        f"got {len(review_rules)} — PLAN §1.3(c) named exactly 9 for seq-22; a "
        "changed count on a later sequence is real news, not a stale pin"
    )
    assert len(escalations) == 7, (
        f"sequence {real_pack.sequence}: expected 7 on_unknown=HUMAN_REVIEW "
        f"escalations, got {len(escalations)} — PLAN §1.3(d) named exactly 7 for "
        "seq-22 (the 3 overlapping HUMAN_REVIEW-stage rules plus 4 HARD_FILTER "
        "rules)"
    )


def test_every_disclosed_flag_has_exactly_one_code() -> None:
    codes = adapter_review_codes()
    assert len(codes) == 11
    assert set(codes) == set(DisclosedReviewFlag)


def test_holding_split_matches_the_2026_09_13_ruling_floor() -> None:
    """PLAN VISA-ORACLE-DW-20260919 slice A1' (gate vo-gate-a1, OBS-3
    MEDIUM): the inventory must derive holding vs conditioning from
    `HOLDING_DISCLOSED_FLAGS` itself, not hand-list the split — a future
    widening of that frozenset moves this test's counts without editing it,
    exactly as `test_inventory_is_a_derivation_not_a_hand_list` proves for
    the pack rules below."""

    codes = adapter_review_codes()
    holding, conditioning = split_disclosed_review_codes(codes)

    assert set(holding) == HOLDING_DISCLOSED_FLAGS
    assert set(holding) == {
        DisclosedReviewFlag.CRIMINAL_RECORD,
        DisclosedReviewFlag.ACTIVITY_BOUNDARY,
    }
    assert len(holding) == 2
    assert len(conditioning) == 9
    assert set(holding) | set(conditioning) == set(DisclosedReviewFlag)
    assert set(holding) & set(conditioning) == set()
    # Every code stays paired with its own flag across the split — the
    # split partitions rows, it never rewrites a code.
    assert holding == {flag: codes[flag] for flag in holding}
    assert conditioning == {flag: codes[flag] for flag in conditioning}


def test_minor_privacy_code_matches_the_adapter_constant() -> None:
    assert minor_privacy_review_code() == MINOR_GUARDIAN_PRIVACY_REVIEW_CODE
    assert minor_privacy_review_code() == "MINOR_GUARDIAN_PRIVACY_REVIEW"


def test_orphan_review_gate_items_are_named() -> None:
    assert orphan_review_gate_items() == frozenset(
        {"overstay", "blacklist", "immigration_investigation"}
    )
    # When slice A3 fixes them this assertion goes red and A3 updates it —
    # that is the intended coupling PLAN §4 describes for this test.


def test_orphan_review_gate_items_fails_loud_on_a_missing_literal(tmp_path) -> None:
    """Guilt: a path that does not contain the literal must raise, never
    silently report an empty orphan set (cicatrix family #3)."""

    empty_tree = tmp_path / "tree.ts"
    empty_tree.write_text("export const SOMETHING_ELSE = 1;\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="REVIEW_GATE_ITEMS"):
        orphan_review_gate_items(
            tree_ts_path=empty_tree, fact_mapper_ts_path=DEFAULT_FACT_MAPPER_PATH
        )

    real_tree_text = DEFAULT_TREE_TS_PATH.read_text(encoding="utf-8")
    tree_copy = tmp_path / "tree_copy.ts"
    tree_copy.write_text(real_tree_text, encoding="utf-8")
    empty_mapper = tmp_path / "fact-mapper.ts"
    empty_mapper.write_text("export const SOMETHING_ELSE = 1;\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="REVIEW_FLAG_MAP"):
        orphan_review_gate_items(tree_ts_path=tree_copy, fact_mapper_ts_path=empty_mapper)


def test_inventory_is_a_derivation_not_a_hand_list() -> None:
    """Guilt: a synthetic pack with one extra HUMAN_REVIEW rule must move
    `pack_review_rules`'s count — proof this is a derivation, not a hardcoded
    number that would stay 9 regardless of what the pack says."""

    baseline = _synthetic_payload(rules=[_synthetic_review_rule("test.synthetic-review-a")])
    augmented = _synthetic_payload(
        rules=[
            _synthetic_review_rule("test.synthetic-review-a"),
            _synthetic_review_rule("test.synthetic-review-b"),
        ]
    )

    baseline_count = len(pack_review_rules(baseline))
    augmented_count = len(pack_review_rules(augmented))

    assert baseline_count == 1
    assert augmented_count == 2
    assert augmented_count == baseline_count + 1
