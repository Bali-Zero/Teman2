"""Generic dead-man-switch evaluator, per SLO.md SYN-01.

Family #2 (`cicatrix-superscar.md`, "esiste != armato") is exactly the
failure this file exists to refuse: a probe that is scheduled but whose
absence nobody notices. The contract (SLO.md SYN-01) is explicit that
*absence* of a success signal must page, and that a late probe can never
auto-re-enable the flag — both are encoded below, not left to the caller's
judgement.

This module has no I/O and no dependency on `ports.py` — it takes a single
timestamp and returns a verdict, which is what makes it bite-provable in
isolation: see
`apps/backend-rag/backend/tests/services/garuda_ops/test_deadman.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class DeadmanState(str, Enum):
    HEALTHY = "healthy"  # a success landed within the window
    DEAD = "dead"  # silence exceeded the window — page + flag off


@dataclass(frozen=True, slots=True)
class DeadmanVerdict:
    state: DeadmanState
    age_seconds: float | None  # seconds since last success; None if never succeeded
    should_page: bool
    should_disable_flag: bool


def evaluate_deadman(
    *,
    last_success_at: datetime | None,
    now: datetime,
    max_silence: timedelta,
    monitoring_started_at: datetime,
) -> DeadmanVerdict:
    """SYN-01: "If no complete signed result is recorded within 15 minutes
    of its scheduled start, set the public flag off and alert the owner."

    `monitoring_started_at` is when the probe cron was armed — it stands in
    for "scheduled start" so a fresh deployment isn't declared DEAD in its
    first second (age since a start that hasn't happened yet is undefined,
    not zero and not infinite).
    """
    if now < monitoring_started_at:
        msg = "now precedes monitoring_started_at"
        raise ValueError(msg)

    if last_success_at is None:
        silence = now - monitoring_started_at
    else:
        if last_success_at > now:
            msg = "last_success_at is in the future"
            raise ValueError(msg)
        silence = now - last_success_at

    age_seconds = silence.total_seconds()

    if silence <= max_silence:
        return DeadmanVerdict(
            state=DeadmanState.HEALTHY,
            age_seconds=age_seconds,
            should_page=False,
            should_disable_flag=False,
        )

    # Past the window: DEAD, not a softer "LATE" — SYN-01 names one grace
    # period, not two, and a probe that never started prior to launch reads
    # identically to one whose last success rotted off the window.
    return DeadmanVerdict(
        state=DeadmanState.DEAD,
        age_seconds=age_seconds,
        should_page=True,
        should_disable_flag=True,
    )
