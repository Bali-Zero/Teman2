"""Provider-neutral terminal-failure taxonomy — DECISIONS.md Q8.

Our vocabulary, not the provider's. Provider codes map INTO this at the
port boundary and are never surfaced. The two properties Q8 requires:

1. An unrecognised provider code maps to a generic RETRYABLE outcome and
   pages — it is never silently treated as terminal.
2. The customer copy distinguishes "try a different card" (issuer-side,
   a different card might work) from "try again later" (provider/network
   side, the same card might work later) — those ask the customer for
   different things.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum


class FailureOutcome(str, Enum):
    """Our closed vocabulary. Never a provider's raw code."""

    DECLINED_BY_ISSUER = "DECLINED_BY_ISSUER"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    EXPIRED = "EXPIRED"
    CANCELLED_BY_CUSTOMER = "CANCELLED_BY_CUSTOMER"
    # Not one of Q8's six named terminals: the safety net for anything this
    # mapping does not recognise. Deliberately retryable, deliberately paged.
    UNRECOGNISED_RETRYABLE = "UNRECOGNISED_RETRYABLE"


class CustomerAction(str, Enum):
    TRY_A_DIFFERENT_CARD = "TRY_A_DIFFERENT_CARD"
    TRY_AGAIN_LATER = "TRY_AGAIN_LATER"
    NONE_ORDER_CLOSED = "NONE_ORDER_CLOSED"


@dataclass(frozen=True, slots=True)
class MappedFailure:
    outcome: FailureOutcome
    retryable: bool
    customer_action: CustomerAction
    should_page: bool


# Card/issuer-side declines: "try a different card" is the useful ask,
# because the same card retried the same way is expected to decline again.
_ISSUER_SIDE = frozenset({FailureOutcome.DECLINED_BY_ISSUER, FailureOutcome.INSUFFICIENT_FUNDS})

# Everything else terminal-but-named: "try again later" or the order is
# simply closed (customer cancelled, or the session itself expired).
_RETRY_LATER = frozenset(
    {FailureOutcome.AUTHENTICATION_FAILED, FailureOutcome.PROVIDER_UNAVAILABLE}
)
_CLOSED = frozenset({FailureOutcome.EXPIRED, FailureOutcome.CANCELLED_BY_CUSTOMER})


def classify(outcome: FailureOutcome) -> MappedFailure:
    if outcome is FailureOutcome.UNRECOGNISED_RETRYABLE:
        return MappedFailure(
            outcome=outcome,
            retryable=True,
            customer_action=CustomerAction.TRY_AGAIN_LATER,
            should_page=True,
        )
    if outcome in _ISSUER_SIDE:
        return MappedFailure(
            outcome=outcome,
            retryable=True,
            customer_action=CustomerAction.TRY_A_DIFFERENT_CARD,
            should_page=False,
        )
    if outcome in _RETRY_LATER:
        return MappedFailure(
            outcome=outcome,
            retryable=True,
            customer_action=CustomerAction.TRY_AGAIN_LATER,
            should_page=outcome is FailureOutcome.PROVIDER_UNAVAILABLE,
        )
    if outcome in _CLOSED:
        return MappedFailure(
            outcome=outcome,
            retryable=False,
            customer_action=CustomerAction.NONE_ORDER_CLOSED,
            should_page=False,
        )
    # Every FailureOutcome member is covered above; a future member added
    # without updating this function fails loudly rather than silently
    # falling through to a wrong classification.
    raise AssertionError(f"unclassified FailureOutcome member: {outcome!r}")


def map_provider_failure_code(
    provider: str, raw_code: str | None, table: dict[str, FailureOutcome]
) -> MappedFailure:
    """Map one provider's raw failure code through its lookup `table`.

    `table` is provider-specific and lives in that provider's adapter
    module (e.g. `xendit.py::_FAILURE_CODE_MAP`), never here — this
    function only enforces the Q8 safety property: an absent or unknown
    key NEVER resolves to a terminal outcome by accident.
    """

    if not raw_code:
        outcome = FailureOutcome.UNRECOGNISED_RETRYABLE
    else:
        outcome = table.get(raw_code, FailureOutcome.UNRECOGNISED_RETRYABLE)
    if outcome is FailureOutcome.UNRECOGNISED_RETRYABLE and raw_code:
        logging.getLogger(__name__).warning(
            "payments.terminal_taxonomy: %s sent an unmapped failure code %r — treating as retryable and paging",
            provider,
            raw_code,
        )
    return classify(outcome)


__all__ = [
    "CustomerAction",
    "FailureOutcome",
    "MappedFailure",
    "classify",
    "map_provider_failure_code",
]
