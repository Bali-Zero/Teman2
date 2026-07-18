"""Tests for ``RuleStage.order``/``STAGE_ORDER`` (PR3).

Spec §4.2 (``evaluate_product``): the true runtime processing sequence is
HARD_FILTER -> HUMAN_REVIEW -> ELIGIBILITY -> RANKING — NOT the enum's
declaration order (HARD_FILTER, ELIGIBILITY, HUMAN_REVIEW, RANKING) and NOT
alphabetical ``.value`` order ("ELIGIBILITY" < "HARD_FILTER" <
"HUMAN_REVIEW" < "RANKING"). ``CompiledRulePack.rules_for()``
(``test_compiler_stage_order.py``) is the consumer that actually depends on
this; this file pins the mapping itself in isolation.
"""

from __future__ import annotations

from backend.services.visa_engine.enums import STAGE_ORDER, RuleStage


class TestStageOrder:
    def test_hard_filter_runs_first(self) -> None:
        assert RuleStage.HARD_FILTER.order == 0

    def test_human_review_runs_before_eligibility(self) -> None:
        assert RuleStage.HUMAN_REVIEW.order == 1
        assert RuleStage.ELIGIBILITY.order == 2
        assert RuleStage.HUMAN_REVIEW.order < RuleStage.ELIGIBILITY.order

    def test_ranking_runs_last(self) -> None:
        assert RuleStage.RANKING.order == 3
        assert all(
            RuleStage.RANKING.order > stage.order
            for stage in RuleStage
            if stage is not RuleStage.RANKING
        )

    def test_order_is_not_alphabetical_value_order(self) -> None:
        by_order = sorted(RuleStage, key=lambda s: s.order)
        by_alpha = sorted(RuleStage, key=lambda s: s.value)
        assert by_order != by_alpha

    def test_stage_order_dict_covers_every_member_exactly_once(self) -> None:
        assert frozenset(STAGE_ORDER) == frozenset(RuleStage)
        assert sorted(STAGE_ORDER.values()) == [0, 1, 2, 3]
