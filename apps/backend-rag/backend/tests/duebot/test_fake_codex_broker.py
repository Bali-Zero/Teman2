"""Proves ``FakeCodexBroker`` actually implements the F3 wire-protocol
contract this harness exists to give other lanes: claim/complete, a
20s-default lease, a 3-fail/5-min breaker, and — the specific thing F3
calls out as broken today and to be fixed before arming — that
``AUTH_DEAD`` and ``QUOTA`` are two genuinely distinct typed outcomes, not
one collapsed into the other.

Zero network: ``FakeCodexBroker`` is pure in-memory state, and every clock
here is the deterministic ``make_lockstep_clock`` helper — no test in this
file sleeps for real time.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from backend.tests.duebot.fake_codex_broker import (
    ALL_ERROR_CLASSES,
    BreakerOpenError,
    BreakerState,
    BrokerErrorClass,
    BrokerProtocolError,
    FakeCodexBroker,
    JobState,
    make_lockstep_clock,
)


def _broker() -> tuple[FakeCodexBroker, Callable[[float], None]]:
    clock, advance = make_lockstep_clock()
    return FakeCodexBroker(clock=clock), advance


# ---------------------------------------------------------------------------
# happy path: offer -> claim -> complete(result) -> consume
# ---------------------------------------------------------------------------


def test_happy_path_offer_claim_complete_consume() -> None:
    broker, _advance = _broker()

    job_id = broker.offer({"prompt": "hello"})
    claimed = broker.claim()
    assert claimed is not None
    assert claimed.job_id == job_id
    assert claimed.state == JobState.LEASED

    completed = broker.complete(job_id, result={"text": "hi"})
    assert completed.state == JobState.COMPLETED_PENDING_CONSUME

    result = broker.consume(job_id)
    assert result == {"text": "hi"}
    assert broker.get(job_id).state == JobState.CONSUMED


def test_claim_on_empty_queue_returns_none() -> None:
    broker, _advance = _broker()
    assert broker.claim() is None


# ---------------------------------------------------------------------------
# the closed F3 error vocabulary — every member emits distinctly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("error_class", sorted(ALL_ERROR_CLASSES, key=lambda e: e.value))
def test_each_f3_error_class_completes_a_job_with_its_own_typed_outcome(
    error_class: BrokerErrorClass,
) -> None:
    broker, _advance = _broker()
    job_id = broker.offer({"prompt": "will fail"})
    broker.claim()

    failed = broker.complete(job_id, error_class=error_class)

    assert failed.state == JobState.FAILED
    assert failed.error_class is error_class


def test_all_seven_f3_error_classes_are_present_and_only_those_seven() -> None:
    assert {e.value for e in ALL_ERROR_CLASSES} == {
        "AUTH_DEAD",
        "QUOTA",
        "TIMEOUT",
        "HOST_OFFLINE",
        "OUTPUT_INVALID",
        "POLICY_BLOCKED",
        "INTERNAL",
    }


def test_auth_dead_and_quota_are_distinct_outcomes() -> None:
    """The F3-named defect this fake exists to make representable: an auth
    failure and a quota exhaustion are two different jobs completing with
    two different typed outcomes — never the same value, never one
    silently standing in for the other.
    """
    broker, _advance = _broker()

    auth_job = broker.offer({"prompt": "auth probe"})
    broker.claim()
    auth_result = broker.complete(auth_job, error_class=BrokerErrorClass.AUTH_DEAD)

    quota_job = broker.offer({"prompt": "quota probe"})
    broker.claim()
    quota_result = broker.complete(quota_job, error_class=BrokerErrorClass.QUOTA)

    assert auth_result.error_class == BrokerErrorClass.AUTH_DEAD
    assert quota_result.error_class == BrokerErrorClass.QUOTA
    assert auth_result.error_class != quota_result.error_class
    # Not just "not equal" — genuinely different enum members with
    # different .value strings, so a serialized wire payload distinguishes
    # them too (a class that stringified to the same value would collapse
    # exactly as F3 describes the live system doing today).
    assert auth_result.error_class.value != quota_result.error_class.value


def test_complete_rejects_error_class_outside_the_closed_vocabulary() -> None:
    broker, _advance = _broker()
    job_id = broker.offer({"prompt": "x"})
    broker.claim()

    with pytest.raises(BrokerProtocolError):
        broker.complete(job_id, error_class="NOT_A_REAL_CODE")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# protocol errors
# ---------------------------------------------------------------------------


def test_complete_requires_exactly_one_of_result_or_error_class() -> None:
    broker, _advance = _broker()
    job_id = broker.offer({"prompt": "x"})
    broker.claim()

    with pytest.raises(BrokerProtocolError):
        broker.complete(job_id)  # neither

    with pytest.raises(BrokerProtocolError):
        broker.complete(job_id, result={"a": 1}, error_class=BrokerErrorClass.INTERNAL)  # both


def test_complete_on_unknown_job_id_is_a_protocol_error() -> None:
    broker, _advance = _broker()
    with pytest.raises(BrokerProtocolError):
        broker.complete("no-such-job", result={})


def test_double_complete_is_a_protocol_error() -> None:
    broker, _advance = _broker()
    job_id = broker.offer({"prompt": "x"})
    broker.claim()
    broker.complete(job_id, result={"ok": True})

    with pytest.raises(BrokerProtocolError):
        broker.complete(job_id, result={"ok": True})


def test_complete_without_claim_is_a_protocol_error() -> None:
    broker, _advance = _broker()
    job_id = broker.offer({"prompt": "x"})

    with pytest.raises(BrokerProtocolError):
        broker.complete(job_id, result={})


def test_double_consume_is_a_protocol_error() -> None:
    broker, _advance = _broker()
    job_id = broker.offer({"prompt": "x"})
    broker.claim()
    broker.complete(job_id, result={"ok": True})
    broker.consume(job_id)

    with pytest.raises(BrokerProtocolError):
        broker.consume(job_id)


# ---------------------------------------------------------------------------
# lease expiry (deterministic clock, no real sleep)
# ---------------------------------------------------------------------------


def test_lease_expires_after_ttl_and_is_folded_by_the_reaper() -> None:
    broker, advance = _broker()
    job_id = broker.offer({"prompt": "slow"}, lease_ttl_s=20.0)
    broker.claim()

    advance(20.1)
    expired = broker.expire_stale()

    assert expired == [job_id]
    assert broker.get(job_id).state == JobState.EXPIRED


def test_complete_after_lease_expiry_is_rejected_not_a_late_success() -> None:
    """F3: no late delivery. A completion that arrives after the lease
    window must not be silently accepted as a success.
    """
    broker, advance = _broker()
    job_id = broker.offer({"prompt": "slow"}, lease_ttl_s=20.0)
    broker.claim()

    advance(20.1)
    with pytest.raises(BrokerProtocolError):
        broker.complete(job_id, result={"too": "late"})

    assert broker.get(job_id).state == JobState.EXPIRED


def test_default_lease_ttl_matches_f3_spec() -> None:
    broker, _advance = _broker()
    job_id = broker.offer({"prompt": "x"})
    job = broker.get(job_id)
    assert job.lease_ttl_s == 20.0


# ---------------------------------------------------------------------------
# circuit breaker: 3-fail trip, open refuses offers, half-open canary
# ---------------------------------------------------------------------------


def test_breaker_starts_closed_and_admits() -> None:
    broker, _advance = _broker()
    assert broker.breaker.state == BreakerState.CLOSED
    assert broker.admits() is True


def test_breaker_trips_open_after_three_consecutive_failures() -> None:
    broker, _advance = _broker()

    for _ in range(3):
        job_id = broker.offer({"prompt": "x"})
        broker.claim()
        broker.complete(job_id, error_class=BrokerErrorClass.TIMEOUT)

    assert broker.breaker.state == BreakerState.OPEN
    assert broker.breaker.consecutive_failures == 3


def test_two_failures_do_not_trip_the_breaker() -> None:
    broker, _advance = _broker()

    for _ in range(2):
        job_id = broker.offer({"prompt": "x"})
        broker.claim()
        broker.complete(job_id, error_class=BrokerErrorClass.TIMEOUT)

    assert broker.breaker.state == BreakerState.CLOSED


def test_a_success_between_failures_resets_the_consecutive_count() -> None:
    broker, _advance = _broker()

    for error_class in (BrokerErrorClass.TIMEOUT, BrokerErrorClass.TIMEOUT):
        job_id = broker.offer({"prompt": "x"})
        broker.claim()
        broker.complete(job_id, error_class=error_class)
    assert broker.breaker.consecutive_failures == 2

    job_id = broker.offer({"prompt": "x"})
    broker.claim()
    broker.complete(job_id, result={"ok": True})
    assert broker.breaker.state == BreakerState.CLOSED
    assert broker.breaker.consecutive_failures == 0

    # Would have tripped on the 3rd consecutive failure had the success
    # above not reset the counter.
    job_id = broker.offer({"prompt": "x"})
    broker.claim()
    broker.complete(job_id, error_class=BrokerErrorClass.TIMEOUT)
    assert broker.breaker.state == BreakerState.CLOSED


def test_open_breaker_refuses_new_offers() -> None:
    broker, _advance = _broker()
    for _ in range(3):
        job_id = broker.offer({"prompt": "x"})
        broker.claim()
        broker.complete(job_id, error_class=BrokerErrorClass.HOST_OFFLINE)
    assert broker.breaker.state == BreakerState.OPEN

    with pytest.raises(BreakerOpenError):
        broker.offer({"prompt": "refused"})


def test_breaker_half_opens_after_cooldown_and_admits_the_canary() -> None:
    broker, advance = _broker()
    for _ in range(3):
        job_id = broker.offer({"prompt": "x"})
        broker.claim()
        broker.complete(job_id, error_class=BrokerErrorClass.INTERNAL)
    assert broker.breaker.state == BreakerState.OPEN

    advance(FakeCodexBroker.BREAKER_OPEN_SECONDS - 1)
    assert broker.breaker.state == BreakerState.OPEN, "must not cool down early"

    advance(2)  # crosses the 300s threshold
    assert broker.breaker.state == BreakerState.HALF_OPEN
    assert broker.admits() is True


def test_half_open_canary_success_closes_the_breaker() -> None:
    broker, advance = _broker()
    for _ in range(3):
        job_id = broker.offer({"prompt": "x"})
        broker.claim()
        broker.complete(job_id, error_class=BrokerErrorClass.POLICY_BLOCKED)
    advance(FakeCodexBroker.BREAKER_OPEN_SECONDS + 1)
    assert broker.breaker.state == BreakerState.HALF_OPEN

    canary_id = broker.offer({"prompt": "canary"})
    broker.claim()
    broker.complete(canary_id, result={"ok": True})

    assert broker.breaker.state == BreakerState.CLOSED
    assert broker.breaker.consecutive_failures == 0


def test_half_open_canary_failure_reopens_with_a_fresh_cooldown() -> None:
    broker, advance = _broker()
    for _ in range(3):
        job_id = broker.offer({"prompt": "x"})
        broker.claim()
        broker.complete(job_id, error_class=BrokerErrorClass.OUTPUT_INVALID)
    advance(FakeCodexBroker.BREAKER_OPEN_SECONDS + 1)
    assert broker.breaker.state == BreakerState.HALF_OPEN

    canary_id = broker.offer({"prompt": "canary"})
    broker.claim()
    broker.complete(canary_id, error_class=BrokerErrorClass.OUTPUT_INVALID)

    assert broker.breaker.state == BreakerState.OPEN

    # Fresh cooldown: not enough time has passed since THIS re-open even
    # though it has been > BREAKER_OPEN_SECONDS since the ORIGINAL trip.
    advance(1)
    assert broker.breaker.state == BreakerState.OPEN

    advance(FakeCodexBroker.BREAKER_OPEN_SECONDS)
    assert broker.breaker.state == BreakerState.HALF_OPEN
