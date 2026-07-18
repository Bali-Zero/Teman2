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

import pytest

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


class TestStageOrderImmutability:
    """F4 (2-seat review, 2026-07-18): ``STAGE_ORDER`` is a
    ``MappingProxyType``, not a plain ``dict`` — the same "type-annotated
    read-only is not actually immutable at runtime" class of defect
    ``fact_registry.FactRegistry._specs`` already guards against (see
    ``test_fact_registry.py::TestRegistryImmutability``). A plain ``dict``
    would let any importer mutate the single module-level ordering every
    ``RuleStage.order``/``CompiledRulePack.rules_for()`` call relies on.
    """

    def test_item_assignment_raises_type_error(self) -> None:
        # Guilt: MappingProxyType raises TypeError on item assignment —
        # a plain dict would silently corrupt the shared ordering here.
        with pytest.raises(TypeError):
            STAGE_ORDER[RuleStage.RANKING] = -1  # type: ignore[index]

    def test_reads_still_work_after_attempted_mutation(self) -> None:
        # Innocence: the guard above must never impair ordinary reads —
        # every stage's `.order` property still resolves correctly.
        assert RuleStage.HARD_FILTER.order == 0
        assert RuleStage.HUMAN_REVIEW.order == 1
        assert RuleStage.ELIGIBILITY.order == 2
        assert RuleStage.RANKING.order == 3
