"""Tests for ``backend.services.visa_engine.ast``.

Covers: every one of the 15 node types parses through the discriminated
union; the ``known``/``unknown`` merge into one ``PresenceCondition`` type
(the resolved 15-vs-16 ambiguity, see ``enums.ConditionOperator``'s
docstring); structural limits (depth <=12, nodes <=256) with an explicit
guilt/innocence pair at the exact boundary; ``$defs/Scalar`` validation
(float rejection, integer range, string length, duplicate-value rejection);
``collect_fact_paths``/``collect_leaf_operators`` correctness; ``extra:
forbid`` on a condition node.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.services.visa_engine import ast as A
from backend.services.visa_engine.errors import ConditionStructureError


def _nest_not(depth: int) -> dict:
    """A pure chain of ``not`` wrapping one ``known`` leaf: ``depth`` nots
    gives a tree of depth ``depth + 1`` (the leaf itself is depth 1).
    """
    node: dict = {"op": "known", "fact": "person.birth_date"}
    for _ in range(depth):
        node = {"op": "not", "arg": node}
    return node


def _wide_tree(num_groups: int, leaves_per_group: int) -> dict:
    """A 3-level ``any``-of-``any``-of-leaves tree with exactly
    ``1 + num_groups * (1 + leaves_per_group)`` total nodes, staying under
    the JSON Schema's own ``args`` maxItems (64) at every level — needed
    because a single flat ``any`` cannot exceed 64 children on its own, so
    reaching 256+ nodes needs this shape rather than one wide combinator.
    """
    leaf = {"op": "known", "fact": "person.birth_date"}
    groups = [{"op": "any", "args": [leaf] * leaves_per_group} for _ in range(num_groups)]
    return {"op": "any", "args": groups}


class TestNodeTypesParseThroughDiscriminatedUnion:
    @pytest.mark.parametrize(
        "raw",
        [
            {"op": "all", "args": [{"op": "known", "fact": "person.birth_date"}]},
            {"op": "any", "args": [{"op": "known", "fact": "person.birth_date"}]},
            {"op": "not", "arg": {"op": "known", "fact": "person.birth_date"}},
            {"op": "known", "fact": "person.birth_date"},
            {"op": "unknown", "fact": "person.birth_date"},
            {"op": "eq", "fact": "person.marital_status", "value": "MARRIED"},
            {"op": "neq", "fact": "person.marital_status", "value": "MARRIED"},
            {"op": "lt", "fact": "immigration.overstay_days", "value": 3},
            {"op": "lte", "fact": "immigration.overstay_days", "value": 3},
            {"op": "gt", "fact": "immigration.overstay_days", "value": 3},
            {"op": "gte", "fact": "immigration.overstay_days", "value": 3},
            {"op": "in", "fact": "person.marital_status", "values": ["MARRIED", "SINGLE"]},
            {"op": "not_in", "fact": "person.marital_status", "values": ["DIVORCED"]},
            {"op": "between", "fact": "immigration.overstay_days", "lower": 0, "upper": 10},
            {"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            {"op": "contains_all", "fact": "intent.purposes", "values": ["TOURISM"]},
        ],
    )
    def test_parses(self, raw: dict) -> None:
        condition = A.parse_condition(raw)
        assert condition.op == raw["op"]

    def test_presence_condition_carries_both_known_and_unknown(self) -> None:
        known = A.parse_condition({"op": "known", "fact": "person.birth_date"})
        unknown = A.parse_condition({"op": "unknown", "fact": "person.birth_date"})
        assert isinstance(known, A.PresenceCondition)
        assert isinstance(unknown, A.PresenceCondition)
        assert known.op == "known"
        assert unknown.op == "unknown"

    def test_unrecognized_operator_rejected(self) -> None:
        with pytest.raises(ValidationError):
            A.parse_condition({"op": "regex_match", "fact": "person.birth_date", "value": ".*"})


class TestExtraForbid:
    def test_condition_rejects_unexpected_field(self) -> None:
        with pytest.raises(ValidationError):
            A.parse_condition(
                {
                    "op": "eq",
                    "fact": "person.marital_status",
                    "value": "MARRIED",
                    "unexpected": True,
                }
            )

    def test_condition_is_frozen(self) -> None:
        condition = A.parse_condition({"op": "known", "fact": "person.birth_date"})
        with pytest.raises(ValidationError):
            condition.fact = "person.nationalities"  # type: ignore[misc]


class TestStructuralLimits:
    def test_depth_12_is_innocent(self) -> None:
        # 11 nots + 1 leaf = depth 12 (the boundary itself must pass).
        condition = A.parse_condition(_nest_not(11))
        assert A.compute_depth(condition) == 12
        A.validate_ast_limits(condition)  # must not raise

    def test_depth_13_is_guilty(self) -> None:
        # 12 nots + 1 leaf = depth 13 (one over the limit).
        condition = A.parse_condition(_nest_not(12))
        assert A.compute_depth(condition) == 13
        with pytest.raises(ConditionStructureError, match="depth"):
            A.validate_ast_limits(condition)

    def test_node_count_at_limit_is_innocent(self) -> None:
        # root(1) + 5 groups + 5*50 leaves = 256 total nodes exactly.
        condition = A.parse_condition(_wide_tree(num_groups=5, leaves_per_group=50))
        assert A.count_nodes(condition) == 256
        A.validate_ast_limits(condition)  # must not raise

    def test_node_count_over_limit_is_guilty(self) -> None:
        # root(1) + 4 groups + 4*63 leaves = 257 total nodes (one over).
        condition = A.parse_condition(_wide_tree(num_groups=4, leaves_per_group=63))
        assert A.count_nodes(condition) == 257
        with pytest.raises(ConditionStructureError, match="node count"):
            A.validate_ast_limits(condition)

    def test_custom_limits_respected(self) -> None:
        condition = A.parse_condition(_nest_not(2))
        A.validate_ast_limits(condition, max_depth=3)
        with pytest.raises(ConditionStructureError):
            A.validate_ast_limits(condition, max_depth=2)


class TestScalarValidation:
    def test_float_rejected(self) -> None:
        with pytest.raises(ValidationError, match="float"):
            A.parse_condition({"op": "eq", "fact": "immigration.overstay_days", "value": 1.5})

    def test_integer_within_js_safe_range_accepted(self) -> None:
        condition = A.parse_condition(
            {"op": "eq", "fact": "immigration.overstay_days", "value": 9_007_199_254_740_991}
        )
        assert condition.value == 9_007_199_254_740_991

    def test_integer_outside_js_safe_range_rejected(self) -> None:
        with pytest.raises(ValidationError):
            A.parse_condition(
                {"op": "eq", "fact": "immigration.overstay_days", "value": 9_007_199_254_740_992}
            )

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            A.parse_condition({"op": "eq", "fact": "person.marital_status", "value": ""})

    def test_string_over_128_chars_rejected(self) -> None:
        with pytest.raises(ValidationError):
            A.parse_condition(
                {"op": "eq", "fact": "intent.requested_product_code", "value": "x" * 129}
            )

    def test_boolean_scalar_not_confused_with_integer(self) -> None:
        condition = A.parse_condition(
            {"op": "eq", "fact": "immigration.currently_in_indonesia", "value": True}
        )
        assert condition.value is True

    def test_duplicate_values_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate"):
            A.parse_condition(
                {
                    "op": "in",
                    "fact": "person.marital_status",
                    "values": ["MARRIED", "MARRIED"],
                }
            )

    def test_unique_values_accepted(self) -> None:
        condition = A.parse_condition(
            {"op": "in", "fact": "person.marital_status", "values": ["MARRIED", "SINGLE"]}
        )
        assert len(condition.values) == 2

    def test_empty_args_rejected_for_all(self) -> None:
        with pytest.raises(ValidationError):
            A.parse_condition({"op": "all", "args": []})

    def test_empty_values_rejected_for_in(self) -> None:
        with pytest.raises(ValidationError):
            A.parse_condition({"op": "in", "fact": "person.marital_status", "values": []})


class TestFactPathCollection:
    def test_collect_fact_paths_across_nested_tree(self) -> None:
        condition = A.parse_condition(
            {
                "op": "all",
                "args": [
                    {"op": "eq", "fact": "person.marital_status", "value": "MARRIED"},
                    {
                        "op": "any",
                        "args": [
                            {"op": "known", "fact": "person.birth_date"},
                            {"op": "gt", "fact": "immigration.overstay_days", "value": 0},
                        ],
                    },
                ],
            }
        )
        assert A.collect_fact_paths(condition) == frozenset(
            {"person.marital_status", "person.birth_date", "immigration.overstay_days"}
        )

    def test_collect_fact_paths_deduplicates_repeated_fact(self) -> None:
        condition = A.parse_condition(
            {
                "op": "all",
                "args": [
                    {"op": "known", "fact": "person.birth_date"},
                    {"op": "unknown", "fact": "person.birth_date"},
                ],
            }
        )
        assert A.collect_fact_paths(condition) == frozenset({"person.birth_date"})

    def test_collect_leaf_operators_excludes_combinators(self) -> None:
        condition = A.parse_condition(
            {
                "op": "not",
                "arg": {"op": "known", "fact": "person.birth_date"},
            }
        )
        assert A.collect_leaf_operators(condition) == frozenset({"known"})

    def test_collect_leaf_operators_mixed(self) -> None:
        condition = A.parse_condition(
            {
                "op": "all",
                "args": [
                    {"op": "known", "fact": "person.birth_date"},
                    {"op": "gt", "fact": "immigration.overstay_days", "value": 0},
                ],
            }
        )
        assert A.collect_leaf_operators(condition) == frozenset({"known", "gt"})


class TestOperatorEnumCompleteness:
    def test_condition_operator_has_16_values(self) -> None:
        from backend.services.visa_engine.enums import ConditionOperator

        assert len(list(ConditionOperator)) == 16

    def test_condition_operator_values_match_ast_leaf_ops(self) -> None:
        from backend.services.visa_engine.enums import ConditionOperator

        expected = {op.value for op in ConditionOperator}
        # every op literal used anywhere in ast.py's node classes
        actual = {
            "all",
            "any",
            "not",
            "known",
            "unknown",
            "eq",
            "neq",
            "lt",
            "lte",
            "gt",
            "gte",
            "in",
            "not_in",
            "between",
            "intersects",
            "contains_all",
        }
        assert expected == actual
