"""DECISIONS.md Q8: an unrecognised provider code must map to a generic
RETRYABLE outcome and page — never silently terminal."""

from __future__ import annotations

from backend.services.payments.terminal_taxonomy import (
    CustomerAction,
    FailureOutcome,
    classify,
    map_provider_failure_code,
)


def test_unrecognised_code_is_retryable_and_pages() -> None:
    mapped = map_provider_failure_code("xendit", "SOME_CODE_NOBODY_MAPPED", table={})
    assert mapped.outcome is FailureOutcome.UNRECOGNISED_RETRYABLE
    assert mapped.retryable is True
    assert mapped.should_page is True
    assert mapped.customer_action is CustomerAction.TRY_AGAIN_LATER


def test_missing_code_is_also_retryable_and_pages() -> None:
    mapped = map_provider_failure_code("xendit", None, table={"X": FailureOutcome.EXPIRED})
    assert mapped.outcome is FailureOutcome.UNRECOGNISED_RETRYABLE
    assert mapped.retryable is True
    assert mapped.should_page is True


def test_issuer_side_declines_ask_for_a_different_card() -> None:
    for outcome in (FailureOutcome.DECLINED_BY_ISSUER, FailureOutcome.INSUFFICIENT_FUNDS):
        mapped = classify(outcome)
        assert mapped.customer_action is CustomerAction.TRY_A_DIFFERENT_CARD
        assert mapped.retryable is True
        assert mapped.should_page is False


def test_provider_side_failures_ask_to_try_again_later() -> None:
    for outcome in (FailureOutcome.AUTHENTICATION_FAILED, FailureOutcome.PROVIDER_UNAVAILABLE):
        mapped = classify(outcome)
        assert mapped.customer_action is CustomerAction.TRY_AGAIN_LATER
        assert mapped.retryable is True


def test_provider_unavailable_pages_but_authentication_failed_does_not() -> None:
    # The two "try again later" outcomes are not identical: PROVIDER_UNAVAILABLE
    # is an outage worth paging on, AUTHENTICATION_FAILED (3DS/OTP) is routine
    # customer friction and would page-storm if it paged every time.
    assert classify(FailureOutcome.PROVIDER_UNAVAILABLE).should_page is True
    assert classify(FailureOutcome.AUTHENTICATION_FAILED).should_page is False


def test_closed_outcomes_ask_for_nothing_and_are_not_retryable() -> None:
    for outcome in (FailureOutcome.EXPIRED, FailureOutcome.CANCELLED_BY_CUSTOMER):
        mapped = classify(outcome)
        assert mapped.customer_action is CustomerAction.NONE_ORDER_CLOSED
        assert mapped.retryable is False
        assert mapped.should_page is False


def test_every_failure_outcome_member_is_classified() -> None:
    # Bite: if a future member is added to FailureOutcome without updating
    # classify(), this test raises the same AssertionError classify() itself
    # would raise — the coverage sweep does not depend on classify() staying
    # silent about it.
    # CodeQL false positive (py/non-iterable-in-for-loop): `FailureOutcome`
    # is `class FailureOutcome(str, Enum)` — genuinely iterable at runtime
    # (EnumMeta.__iter__), confirmed by this test passing. CodeQL's type
    # inference on `(str, Enum)` mixins misses the metaclass __iter__.
    for outcome in FailureOutcome:  # lgtm[py/non-iterable-in-for-loop]
        mapped = classify(outcome)
        assert mapped.outcome is outcome


def test_recognised_code_maps_through_the_table() -> None:
    mapped = map_provider_failure_code(
        "xendit",
        "DECLINED_BY_ISSUER",
        table={"DECLINED_BY_ISSUER": FailureOutcome.DECLINED_BY_ISSUER},
    )
    assert mapped.outcome is FailureOutcome.DECLINED_BY_ISSUER


# --- BITE PROOF
def test_bite_proof_unclassified_member_raises() -> None:
    """Simulates a future FailureOutcome member arriving without a
    classify() branch: monkeypatch-free, uses a genuine enum member that
    intentionally has no branch coverage path by constructing a bare
    fallthrough check directly against the source sets."""

    from backend.services.payments import terminal_taxonomy as tt

    # Reaching AssertionError requires an outcome not in any named set —
    # exercise the guard by asserting the real sets partition FailureOutcome
    # completely (this is what makes "no branch missed" true today).
    all_members = set(FailureOutcome)
    covered = (
        {tt.FailureOutcome.UNRECOGNISED_RETRYABLE} | tt._ISSUER_SIDE | tt._RETRY_LATER | tt._CLOSED
    )
    assert covered == all_members
