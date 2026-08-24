"""In-process fake of the F3 codex-broker wire protocol: claim / complete,
a time-bounded lease, and a circuit breaker.

Modeled on the SHAPE of the existing dark implementation,
``backend.services.integrations.wa_broker`` (offer/claim/complete, a
persisted 3-fail/5-min breaker with closed → open → half_open states) —
but wired to the F3 mandate's closed wire-error vocabulary
(``AUTH_DEAD | QUOTA | TIMEOUT | HOST_OFFLINE | OUTPUT_INVALID |
POLICY_BLOCKED | INTERNAL``), which is a DIFFERENT, newer set than
``wa_broker.ALLOWED_ERROR_CLASSES`` (``exec_timeout`` / ``cli_failure`` /
... — a narrower vocabulary for a different, already-shipped queue). F3
states AUTH_DEAD and QUOTA collapse in the live system today and must be
split before the codex-broker leg arms; this fake keeps them as two
distinct enum members on two distinct code paths from the start, so
anything built against this fake's contract cannot silently re-collapse
them (a test proves exactly this — see
``test_fake_codex_broker.py::test_auth_dead_and_quota_are_distinct_outcomes``).

Zero network, zero disk, zero DB: every method here is pure in-memory
state manipulation keyed off an injectable clock, so a test using only
this class needs no infrastructure, cannot leak a real connection by
construction, and never sleeps for real time.
"""

from __future__ import annotations

import enum
import itertools
import time
from collections.abc import Callable
from dataclasses import dataclass


class BrokerErrorClass(str, enum.Enum):
    """The F3 closed wire-error vocabulary (mandate §F3). Nothing outside
    this set is a valid ``complete(..., error_class=...)`` value —
    ``FakeCodexBroker`` type-checks against this enum, so a caller cannot
    smuggle a free-text failure reason onto a terminal job the way an
    untyped string field would allow.
    """

    AUTH_DEAD = "AUTH_DEAD"
    QUOTA = "QUOTA"
    TIMEOUT = "TIMEOUT"
    HOST_OFFLINE = "HOST_OFFLINE"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    INTERNAL = "INTERNAL"


ALL_ERROR_CLASSES: frozenset[BrokerErrorClass] = frozenset(BrokerErrorClass)


class BreakerState(str, enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class JobState(str, enum.Enum):
    OFFERED = "offered"
    LEASED = "leased"
    COMPLETED_PENDING_CONSUME = "completed_pending_consume"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    FAILED = "failed"


_TERMINAL_STATES = frozenset({JobState.CONSUMED, JobState.EXPIRED, JobState.FAILED})


class BrokerProtocolError(RuntimeError):
    """A wire-protocol violation: double-claim, complete on an unknown or
    foreign job, complete past lease expiry, double-consume, etc. Distinct
    from a typed ``BrokerErrorClass`` outcome, which is a VALID protocol
    result — a job that legitimately failed with ``TIMEOUT`` completed the
    protocol correctly; a second ``complete()`` call on it did not.
    """


class BreakerOpenError(RuntimeError):
    """Raised by ``offer()`` when the circuit breaker does not admit."""


@dataclass
class Job:
    job_id: str
    package: dict
    lease_ttl_s: float
    state: JobState = JobState.OFFERED
    leased_at: float | None = None
    result: dict | None = None
    error_class: BrokerErrorClass | None = None

    def lease_expired(self, now: float) -> bool:
        return self.leased_at is not None and (now - self.leased_at) > self.lease_ttl_s


@dataclass
class BreakerSnapshot:
    state: BreakerState
    consecutive_failures: int
    opened_at: float | None


class FakeCodexBroker:
    """Single-flight (F3: "queue depth 1") in-process broker fake.

    Args:
        clock: zero-arg callable returning a monotonically increasing
            float, defaulting to ``time.monotonic``. Tests should pass a
            controllable fake (a simple mutable counter) rather than
            sleeping for real seconds to exercise lease expiry or breaker
            cooldown — see ``test_fake_codex_broker.py`` for the pattern.
    """

    BREAKER_TRIP_AFTER = 3  # F3: "breaker 3-fail/5-min"
    BREAKER_OPEN_SECONDS = 300.0
    DEFAULT_LEASE_TTL_S = 20.0  # F3: "lease 20s"

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.monotonic
        self._jobs: dict[str, Job] = {}
        self._breaker_state = BreakerState.CLOSED
        self._consecutive_failures = 0
        self._breaker_opened_at: float | None = None
        self._job_ids = itertools.count(1)

    # -- breaker -----------------------------------------------------------

    @property
    def breaker(self) -> BreakerSnapshot:
        self._maybe_cool_down()
        return BreakerSnapshot(
            state=self._breaker_state,
            consecutive_failures=self._consecutive_failures,
            opened_at=self._breaker_opened_at,
        )

    def _maybe_cool_down(self) -> None:
        """OPEN → HALF_OPEN once ``BREAKER_OPEN_SECONDS`` has elapsed since
        the breaker tripped — mirrors ``wa_broker.breaker_admits``'s
        open-to-half-open CAS, minus the multi-worker race (this fake is
        single-threaded by construction).
        """
        if (
            self._breaker_state == BreakerState.OPEN
            and self._breaker_opened_at is not None
            and (self._clock() - self._breaker_opened_at) >= self.BREAKER_OPEN_SECONDS
        ):
            self._breaker_state = BreakerState.HALF_OPEN

    def admits(self) -> bool:
        """CLOSED always admits. OPEN never admits until cooldown flips it
        to HALF_OPEN. HALF_OPEN admits — modeled here as "the next offer is
        the canary", which is sufficient for a single-flight fake with no
        concurrent offerers (real ``wa_broker`` needs a DB CAS for exactly
        this race; this fake has no concurrency to race).
        """
        return self.breaker.state in (BreakerState.CLOSED, BreakerState.HALF_OPEN)

    def _record_result(self, *, success: bool) -> None:
        if success:
            self._breaker_state = BreakerState.CLOSED
            self._consecutive_failures = 0
            self._breaker_opened_at = None
            return

        self._consecutive_failures += 1
        if self._breaker_state == BreakerState.HALF_OPEN:
            # A failed canary re-opens immediately with a FRESH cooldown —
            # never falls through to closed, and never needs a second
            # trip-threshold's worth of failures to re-open.
            self._breaker_state = BreakerState.OPEN
            self._breaker_opened_at = self._clock()
        elif (
            self._breaker_state == BreakerState.CLOSED
            and self._consecutive_failures >= self.BREAKER_TRIP_AFTER
        ):
            self._breaker_state = BreakerState.OPEN
            self._breaker_opened_at = self._clock()

    # -- offer / claim / complete / consume --------------------------------

    def offer(self, package: dict, *, lease_ttl_s: float | None = None) -> str:
        """Enqueue a job for claim (the worker side). Raises
        ``BreakerOpenError`` if the breaker does not currently admit.
        """
        if not self.admits():
            raise BreakerOpenError(f"breaker is {self.breaker.state.value} — offer refused")
        job_id = f"fake-job-{next(self._job_ids)}"
        self._jobs[job_id] = Job(
            job_id=job_id,
            package=package,
            lease_ttl_s=lease_ttl_s if lease_ttl_s is not None else self.DEFAULT_LEASE_TTL_S,
        )
        return job_id

    def claim(self) -> Job | None:
        """The daemon side: claim the oldest OFFERED job and start its
        lease clock. Returns ``None`` if nothing is offered — never
        raises, mirroring a poll loop finding an empty queue.
        """
        for job in self._jobs.values():
            if job.state == JobState.OFFERED:
                job.state = JobState.LEASED
                job.leased_at = self._clock()
                return job
        return None

    def complete(
        self,
        job_id: str,
        *,
        result: dict | None = None,
        error_class: BrokerErrorClass | None = None,
    ) -> Job:
        """Report a claimed job's outcome — exactly one of ``result`` /
        ``error_class``, mirroring the real transport's terminal-state
        contract where every accepted transition NULLs the columns the
        outcome didn't use.
        """
        if (result is None) == (error_class is None):
            raise BrokerProtocolError("complete() takes exactly one of result= or error_class=")
        if error_class is not None and error_class not in ALL_ERROR_CLASSES:
            raise BrokerProtocolError(
                f"error_class {error_class!r} is not in the F3 closed vocabulary"
            )

        job = self._jobs.get(job_id)
        if job is None:
            raise BrokerProtocolError(f"complete() on unknown job_id={job_id!r}")
        if job.state != JobState.LEASED:
            raise BrokerProtocolError(
                f"complete() on job {job_id!r} in state {job.state.value!r}, expected "
                f"'leased' — double-complete, or completing an expired/unclaimed job"
            )
        if job.lease_expired(self._clock()):
            job.state = JobState.EXPIRED
            self._record_result(success=False)
            raise BrokerProtocolError(
                f"complete() on job {job_id!r} arrived after its lease expired — "
                f"treated as a late/lost completion, not accepted (F3: no late delivery)"
            )

        if error_class is not None:
            job.state = JobState.FAILED
            job.error_class = error_class
            self._record_result(success=False)
        else:
            job.state = JobState.COMPLETED_PENDING_CONSUME
            job.result = result
            self._record_result(success=True)
        return job

    def consume(self, job_id: str) -> dict:
        """The single consumer reads a completed job's result exactly
        once. A second ``consume()`` on the same job is a protocol error
        (mirrors ``wa_broker.consume_result``'s single-consumer contract).
        """
        job = self._jobs.get(job_id)
        if job is None or job.state != JobState.COMPLETED_PENDING_CONSUME:
            state = job.state.value if job else "unknown"
            raise BrokerProtocolError(
                f"consume() on job {job_id!r} not in 'completed_pending_consume' (was {state!r})"
            )
        job.state = JobState.CONSUMED
        assert job.result is not None
        return job.result

    def expire_stale(self) -> list[str]:
        """Reaper pass: any LEASED job whose lease has expired is folded
        into the breaker as a failure and marked EXPIRED. Returns the ids
        expired this pass — call this explicitly in tests instead of a
        background thread, so lease-expiry tests stay deterministic.
        """
        now = self._clock()
        expired: list[str] = []
        for job in self._jobs.values():
            if job.state == JobState.LEASED and job.lease_expired(now):
                job.state = JobState.EXPIRED
                self._record_result(success=False)
                expired.append(job.job_id)
        return expired

    def get(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise BrokerProtocolError(f"no such job_id={job_id!r}")
        return job


def make_lockstep_clock(start: float = 0.0) -> tuple[Callable[[], float], Callable[[float], None]]:
    """A trivial fake clock for deterministic lease/breaker-cooldown tests:
    returns the current value until ``advance(seconds)`` is called. Avoids
    real ``time.sleep`` — see the ``P3 FLAKY`` orphan scar in
    ``.claude/rules/cicatrix-superscar.md`` ("orologio congelato, non un
    iteratore di tick").
    """
    state = {"now": start}

    def now() -> float:
        return state["now"]

    def advance(seconds: float) -> None:
        state["now"] += seconds

    return now, advance
