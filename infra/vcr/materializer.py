"""infra/vcr/materializer.py — hysteresis debounce over the observation log (R2).

A single flaky probe cycle must not flip a seat's reported truth_state — the
materializer requires 2 CONSECUTIVE observations agreeing on a new value before
reporting a transition, symmetrically for failure and recovery. Without this,
a false-positive-rate criterion is unmeasurable: a single-sample design
conflates "the seat is actually down" with "the probe had one bad run" — the
exact proxy-trusted-as-reality failure this whole pilot exists to cure.
"""

from __future__ import annotations

from infra.vcr.records import ClaimObservation, UNVERIFIED


def derive_truth_state(observations: list[ClaimObservation]) -> tuple[str, str]:
    """Fold an ordered (oldest-first) observation log into a debounced truth_state.

    Returns (truth_state, reason). Empty log -> UNVERIFIED. A single observation
    has no debounce history yet, so it is trusted as-is (nothing to debounce
    against). From the second observation on, a transition away from the
    currently-confirmed value requires 2 consecutive observations agreeing on
    the SAME new value.
    """
    if not observations:
        return UNVERIFIED, "no observations yet"
    if len(observations) == 1:
        only = observations[0]
        return only.truth_state, "single observation, no debounce history yet"

    confirmed = observations[0].truth_state
    pending_value: str | None = None
    pending_count = 0

    for obs in observations[1:]:
        if obs.truth_state == confirmed:
            pending_value = None
            pending_count = 0
            continue
        if obs.truth_state == pending_value:
            pending_count += 1
        else:
            pending_value = obs.truth_state
            pending_count = 1
        if pending_count >= 2:
            confirmed = pending_value
            pending_value = None
            pending_count = 0

    last_raw = observations[-1].truth_state
    if confirmed != last_raw:
        reason = (
            f"debounced: {len(observations)} observations, confirmed={confirmed}, "
            f"latest raw={last_raw} not yet confirmed twice"
        )
    else:
        reason = f"debounced: {len(observations)} observations, confirmed={confirmed}"
    return confirmed, reason
