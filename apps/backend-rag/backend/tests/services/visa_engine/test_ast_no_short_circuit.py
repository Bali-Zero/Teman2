"""No-short-circuit proof + collect_fact_paths completeness on nested trees.

Spec: "All logical children are evaluated even when the truth value is
already known, so the trace is complete. Evaluation does not short-circuit."
(§4.1, line 2356).
"""

from __future__ import annotations

from backend.services.visa_engine.ast import (
    AllCondition,
    AnyCondition,
    EqCondition,
    FactSnapshot,
    KnownFact,
    NotCondition,
    PresenceCondition,
    UnknownFact,
    collect_fact_paths,
    evaluate_condition,
)
from backend.services.visa_engine.enums import FactPath, TruthValue, UnknownReason

SNAPSHOT = FactSnapshot(
    values={
        FactPath.IMMIGRATION_OVERSTAY_DAYS: KnownFact(value=100),  # deciding fact, evaluated first
        FactPath.INTENT_STAY_DAYS: UnknownFact(reason=UnknownReason.NOT_ASKED),
        FactPath.INTENT_DESIRED_ENTRY_DATE: UnknownFact(reason=UnknownReason.NOT_PROVIDED),
        FactPath.WORK_EMPLOYER_COUNTRY_CODE: UnknownFact(reason=UnknownReason.UNVERIFIED),
    }
)


def test_all_first_child_false_still_evaluates_and_records_later_children() -> None:
    """The first child of `all` is already FALSE (deciding the aggregate),
    but the trailing children reference facts that must still show up in
    referenced_facts/unknown_facts."""

    first_child = EqCondition(op="eq", fact="immigration.overstay_days", value=0)  # FALSE
    second_child = PresenceCondition(op="known", fact="intent.stay_days")  # references unknown
    third_child = PresenceCondition(op="known", fact="intent.desired_entry_date")  # also unknown

    cond = AllCondition(op="all", args=[first_child, second_child, third_child])
    result = evaluate_condition(cond, SNAPSHOT)

    assert result.truth is TruthValue.FALSE
    assert result.referenced_facts == frozenset(
        {
            FactPath.IMMIGRATION_OVERSTAY_DAYS,
            FactPath.INTENT_STAY_DAYS,
            FactPath.INTENT_DESIRED_ENTRY_DATE,
        }
    )
    assert result.unknown_facts == frozenset(
        {FactPath.INTENT_STAY_DAYS, FactPath.INTENT_DESIRED_ENTRY_DATE}
    )


def test_any_first_child_true_still_evaluates_and_records_later_children() -> None:
    """The first child of `any` is already TRUE (deciding the aggregate),
    but the trailing children's fact references must still be recorded."""

    first_child = EqCondition(op="eq", fact="immigration.overstay_days", value=100)  # TRUE
    second_child = PresenceCondition(op="known", fact="work.employer_country_code")  # unknown
    third_child = EqCondition(op="eq", fact="intent.stay_days", value=1)  # UNKNOWN (fact unknown)

    cond = AnyCondition(op="any", args=[first_child, second_child, third_child])
    result = evaluate_condition(cond, SNAPSHOT)

    assert result.truth is TruthValue.TRUE
    assert result.referenced_facts == frozenset(
        {
            FactPath.IMMIGRATION_OVERSTAY_DAYS,
            FactPath.WORK_EMPLOYER_COUNTRY_CODE,
            FactPath.INTENT_STAY_DAYS,
        }
    )
    assert FactPath.WORK_EMPLOYER_COUNTRY_CODE in result.unknown_facts
    assert FactPath.INTENT_STAY_DAYS in result.unknown_facts


def test_nested_all_any_not_every_leaf_contributes_to_referenced_facts() -> None:
    """A deeply nested tree — every leaf's fact path must appear in the root
    result's referenced_facts, regardless of which branch decided the
    aggregate truth value."""

    tree = AllCondition(
        op="all",
        args=[
            EqCondition(
                op="eq", fact="immigration.overstay_days", value=100
            ),  # TRUE, decides quickly
            NotCondition(
                op="not",
                arg=AnyCondition(
                    op="any",
                    args=[
                        PresenceCondition(op="known", fact="intent.stay_days"),
                        PresenceCondition(op="known", fact="intent.desired_entry_date"),
                        PresenceCondition(op="known", fact="work.employer_country_code"),
                    ],
                ),
            ),
        ],
    )
    result = evaluate_condition(tree, SNAPSHOT)

    expected_paths = frozenset(
        {
            FactPath.IMMIGRATION_OVERSTAY_DAYS,
            FactPath.INTENT_STAY_DAYS,
            FactPath.INTENT_DESIRED_ENTRY_DATE,
            FactPath.WORK_EMPLOYER_COUNTRY_CODE,
        }
    )
    assert result.referenced_facts == expected_paths
    # collect_fact_paths (pure AST walk, no evaluation) must find the same
    # set — as plain strings (its own, pre-existing PR1 contract).
    assert collect_fact_paths(tree) == frozenset(p.value for p in expected_paths)


def test_collect_fact_paths_on_nested_condition_is_complete() -> None:
    """collect_fact_paths walks every branch of a nested all/any/not tree,
    independent of evaluation — every fact path referenced anywhere in the
    subtree must be present."""

    tree = AnyCondition(
        op="any",
        args=[
            AllCondition(
                op="all",
                args=[
                    EqCondition(op="eq", fact="immigration.overstay_days", value=0),
                    EqCondition(op="eq", fact="intent.stay_days", value=30),
                ],
            ),
            NotCondition(
                op="not", arg=EqCondition(op="eq", fact="work.employer_country_code", value="US")
            ),
            PresenceCondition(op="known", fact="intent.desired_entry_date"),
        ],
    )

    paths = collect_fact_paths(tree)
    assert paths == frozenset(
        {
            "immigration.overstay_days",
            "intent.stay_days",
            "work.employer_country_code",
            "intent.desired_entry_date",
        }
    )


def test_collect_fact_paths_single_leaf() -> None:
    leaf = PresenceCondition(op="known", fact="intent.stay_days")
    assert collect_fact_paths(leaf) == frozenset({"intent.stay_days"})
