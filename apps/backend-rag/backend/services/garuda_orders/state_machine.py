"""Pure order/payment state machine — STATE-MACHINE.md, order-half only.

No I/O. `repository.py` is the only caller that touches Postgres; every
transition decision (allowed / forbidden, and what the forbidden case must
NOT do) is decided here so it can be bite-proofed without a database.

The practice half of STATE-MACHINE.md (PR-01..PR-12) is NOT this lane's
file — L4/L7 own practice transitions. This module owns exactly the "Order /
payment transitions" and "Forbidden order / payment transitions" tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OrderState(str, Enum):
    CREATED = "created"
    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUNDED = "refunded"


class TransitionId(str, Enum):
    OP_00 = "OP-00"
    OP_01 = "OP-01"
    OP_02 = "OP-02"
    OP_03 = "OP-03"
    OP_04 = "OP-04"
    OP_05 = "OP-05"
    OP_06 = "OP-06"
    OP_07 = "OP-07"  # browser observation — not an order-state transition
    OP_08 = "OP-08"  # duplicate paid charge — order stays `paid`
    OP_09 = "OP-09"  # exact retry no-op
    OP_F04 = "OP-F04"  # refunded -> paid (late), forbidden as a state move
    OP_F05 = "OP-F05"  # failed/expired -> paid (late), forbidden as a state move


# STATE-MACHINE.md "Order / payment transitions" table (OP-07/OP-08/OP-09
# never move `state`, so they are absent from this map by construction).
_ALLOWED: dict[OrderState, dict[TransitionId, OrderState]] = {
    OrderState.CREATED: {
        TransitionId.OP_01: OrderState.AWAITING_PAYMENT,
    },
    OrderState.AWAITING_PAYMENT: {
        TransitionId.OP_02: OrderState.PAID,
        TransitionId.OP_03: OrderState.FAILED,
        TransitionId.OP_04: OrderState.EXPIRED,
        TransitionId.OP_05: OrderState.REFUNDED,
    },
    OrderState.PAID: {
        TransitionId.OP_06: OrderState.REFUNDED,
    },
    OrderState.FAILED: {},
    OrderState.EXPIRED: {},
    OrderState.REFUNDED: {},
}

# STATE-MACHINE.md "Forbidden order / payment transitions" — the source-state
# rows. OP-F01..OP-F07 forbidden INPUTS are enforced by the specific guard
# functions below, not by this table (they are not state->state edges).
_FORBIDDEN_DESTINATIONS: dict[OrderState, frozenset[OrderState]] = {
    OrderState.CREATED: frozenset(
        {OrderState.PAID, OrderState.REFUNDED, OrderState.FAILED, OrderState.EXPIRED}
    ),
    OrderState.AWAITING_PAYMENT: frozenset({OrderState.CREATED}),
    OrderState.PAID: frozenset(
        {OrderState.CREATED, OrderState.AWAITING_PAYMENT, OrderState.FAILED, OrderState.EXPIRED}
    ),
    OrderState.REFUNDED: frozenset(
        {
            OrderState.CREATED,
            OrderState.AWAITING_PAYMENT,
            OrderState.PAID,
            OrderState.FAILED,
            OrderState.EXPIRED,
        }
    ),
    OrderState.FAILED: frozenset(
        {
            OrderState.CREATED,
            OrderState.AWAITING_PAYMENT,
            OrderState.PAID,
            OrderState.REFUNDED,
            OrderState.EXPIRED,
        }
    ),
    OrderState.EXPIRED: frozenset(
        {
            OrderState.CREATED,
            OrderState.AWAITING_PAYMENT,
            OrderState.PAID,
            OrderState.REFUNDED,
            OrderState.FAILED,
        }
    ),
}


class TransitionRejected(Exception):
    """Raised for any transition STATE-MACHINE.md forbids.

    Carries no order/payment data — callers append a security/reconciliation
    journal entry from the *inputs they already had*, never from this
    exception's message.
    """


@dataclass(frozen=True, slots=True)
class TransitionResult:
    new_state: OrderState
    transition_id: TransitionId


def apply_transition(current: OrderState, transition_id: TransitionId) -> TransitionResult:
    """Resolve one state->state move, or raise `TransitionRejected`.

    OP-07/OP-08/OP-09 are not state->state moves (see module docstring) and
    must never be passed here — callers route them to their own handlers.
    """

    if transition_id in (TransitionId.OP_07, TransitionId.OP_08, TransitionId.OP_09):
        raise ValueError(f"{transition_id} is not a state->state transition")
    edges = _ALLOWED.get(current, {})
    new_state = edges.get(transition_id)
    if new_state is None:
        raise TransitionRejected(f"{transition_id} is forbidden from {current.value}")
    return TransitionResult(new_state=new_state, transition_id=transition_id)


def is_forbidden_destination(current: OrderState, target: OrderState) -> bool:
    """True when `current -> target` is an explicitly forbidden edge.

    Self-transitions are OP-09 no-ops, never "forbidden" — this function is
    only meaningful for `current != target`.
    """

    return target in _FORBIDDEN_DESTINATIONS.get(current, frozenset())


def guard_op_f04_late_paid_after_refund(current: OrderState) -> bool:
    """OP-F04: a late valid `paid` webhook arrives after `refunded`.

    Returns True when the guard fires (i.e. this IS the OP-F04 case). The
    caller must then: keep `refunded`, append `payment.late_paid_after_refund`,
    page reconciliation, and never release a practice.
    """

    return current is OrderState.REFUNDED


def guard_op_f05_late_paid_after_terminal(current: OrderState) -> bool:
    """OP-F05: a late valid `paid` webhook arrives after `failed`/`expired`.

    Returns True when the guard fires. The caller must then: keep the
    terminal state, append `payment.late_paid_after_terminal`, open exactly
    one staff remediation case, and page — never release a practice, and
    never silently drop the money (DECISIONS.md Q2/Q10).
    """

    return current in (OrderState.FAILED, OrderState.EXPIRED)


def is_terminal(state: OrderState) -> bool:
    return state in (OrderState.FAILED, OrderState.EXPIRED, OrderState.REFUNDED)


__all__ = [
    "OrderState",
    "TransitionId",
    "TransitionRejected",
    "TransitionResult",
    "apply_transition",
    "guard_op_f04_late_paid_after_refund",
    "guard_op_f05_late_paid_after_terminal",
    "is_forbidden_destination",
    "is_terminal",
]
