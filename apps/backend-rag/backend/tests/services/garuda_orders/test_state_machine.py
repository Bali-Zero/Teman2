"""Bite-proofed against STATE-MACHINE.md's own tables (order half)."""

from __future__ import annotations

import pytest

from backend.services.garuda_orders.state_machine import (
    OrderState,
    TransitionId,
    TransitionRejected,
    apply_transition,
    guard_op_f04_late_paid_after_refund,
    guard_op_f05_late_paid_after_terminal,
    is_forbidden_destination,
    is_terminal,
)


@pytest.mark.parametrize(
    ("current", "transition", "expected"),
    [
        (OrderState.CREATED, TransitionId.OP_01, OrderState.AWAITING_PAYMENT),
        (OrderState.AWAITING_PAYMENT, TransitionId.OP_02, OrderState.PAID),
        (OrderState.AWAITING_PAYMENT, TransitionId.OP_03, OrderState.FAILED),
        (OrderState.AWAITING_PAYMENT, TransitionId.OP_04, OrderState.EXPIRED),
        (OrderState.AWAITING_PAYMENT, TransitionId.OP_05, OrderState.REFUNDED),
        (OrderState.PAID, TransitionId.OP_06, OrderState.REFUNDED),
    ],
)
def test_allowed_transitions(
    current: OrderState, transition: TransitionId, expected: OrderState
) -> None:
    result = apply_transition(current, transition)
    assert result.new_state is expected
    assert result.transition_id is transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderState.CREATED, OrderState.PAID),
        (OrderState.CREATED, OrderState.REFUNDED),
        (OrderState.CREATED, OrderState.FAILED),
        (OrderState.CREATED, OrderState.EXPIRED),
        (OrderState.AWAITING_PAYMENT, OrderState.CREATED),
        (OrderState.PAID, OrderState.CREATED),
        (OrderState.PAID, OrderState.AWAITING_PAYMENT),
        (OrderState.PAID, OrderState.FAILED),
        (OrderState.PAID, OrderState.EXPIRED),
        (OrderState.REFUNDED, OrderState.CREATED),
        (OrderState.REFUNDED, OrderState.AWAITING_PAYMENT),
        (OrderState.REFUNDED, OrderState.PAID),
        (OrderState.REFUNDED, OrderState.FAILED),
        (OrderState.REFUNDED, OrderState.EXPIRED),
        (OrderState.FAILED, OrderState.CREATED),
        (OrderState.FAILED, OrderState.AWAITING_PAYMENT),
        (OrderState.FAILED, OrderState.PAID),
        (OrderState.FAILED, OrderState.REFUNDED),
        (OrderState.EXPIRED, OrderState.CREATED),
        (OrderState.EXPIRED, OrderState.AWAITING_PAYMENT),
        (OrderState.EXPIRED, OrderState.PAID),
        (OrderState.EXPIRED, OrderState.REFUNDED),
    ],
)
def test_forbidden_destinations_are_flagged(current: OrderState, target: OrderState) -> None:
    assert is_forbidden_destination(current, target) is True


def test_self_transition_is_not_forbidden() -> None:
    # CodeQL false positive (py/non-iterable-in-for-loop): `OrderState` is
    # `class OrderState(str, Enum)` — genuinely iterable at runtime
    # (EnumMeta.__iter__), confirmed by this test passing. CodeQL's type
    # inference on `(str, Enum)` mixins misses the metaclass __iter__.
    for state in OrderState:  # lgtm[py/non-iterable-in-for-loop]
        assert is_forbidden_destination(state, state) is False


def test_apply_transition_rejects_every_forbidden_edge() -> None:
    # Bite: every non-self edge that is NOT in the allowed map must raise.
    for current in OrderState:  # lgtm[py/non-iterable-in-for-loop]
        for transition in (
            TransitionId.OP_00,
            TransitionId.OP_01,
            TransitionId.OP_02,
            TransitionId.OP_03,
            TransitionId.OP_04,
            TransitionId.OP_05,
            TransitionId.OP_06,
        ):
            try:
                result = apply_transition(current, transition)
            except TransitionRejected:
                continue
            # If it didn't raise, the destination must be a legal (non-forbidden) edge.
            assert is_forbidden_destination(current, result.new_state) is False


def test_op_07_08_09_are_not_state_transitions() -> None:
    for non_state_transition in (TransitionId.OP_07, TransitionId.OP_08, TransitionId.OP_09):
        with pytest.raises(ValueError):
            apply_transition(OrderState.AWAITING_PAYMENT, non_state_transition)


def test_op_f04_guard_fires_only_from_refunded() -> None:
    assert guard_op_f04_late_paid_after_refund(OrderState.REFUNDED) is True
    for other in OrderState:
        if other is not OrderState.REFUNDED:
            assert guard_op_f04_late_paid_after_refund(other) is False


def test_op_f05_guard_fires_only_from_failed_or_expired() -> None:
    assert guard_op_f05_late_paid_after_terminal(OrderState.FAILED) is True
    assert guard_op_f05_late_paid_after_terminal(OrderState.EXPIRED) is True
    for other in (
        OrderState.CREATED,
        OrderState.AWAITING_PAYMENT,
        OrderState.PAID,
        OrderState.REFUNDED,
    ):
        assert guard_op_f05_late_paid_after_terminal(other) is False


def test_is_terminal() -> None:
    assert is_terminal(OrderState.FAILED) is True
    assert is_terminal(OrderState.EXPIRED) is True
    assert is_terminal(OrderState.REFUNDED) is True
    assert is_terminal(OrderState.CREATED) is False
    assert is_terminal(OrderState.AWAITING_PAYMENT) is False
    assert is_terminal(OrderState.PAID) is False


# --- BITE PROOF: break the guard, watch this test go red, restore, watch it go green.
def test_bite_proof_forbidden_created_to_paid_is_caught() -> None:
    """If someone deletes the `created` row from `_FORBIDDEN_DESTINATIONS` or
    changes `is_forbidden_destination` to always return False, THIS test is
    the one that goes red — it is not redundant with the parametrized sweep
    above, which iterates the SAME source data structure and would go red
    for the same reason. This one hardcodes the literal values so a
    structural rewrite of `_FORBIDDEN_DESTINATIONS` cannot silently pass by
    construction."""

    assert is_forbidden_destination(OrderState.CREATED, OrderState.PAID) is True
