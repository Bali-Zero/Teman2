"""Proves the leader-epoch CAS state machine (``ingress_leader.py``)
before anything else in lane B5 gets built on top of it — this is the
"failover state model settled" report to the orchestrator, expressed as
tests rather than prose.

Every scenario the orchestrator explicitly named survives here in its
purest form (no network, no daemon loop, no WABA client — just the
primitive): split-brain attempted and refused, a stale node waking up
believing a stale epoch, and a takeover racing an in-flight action.
``test_staging_drill.py`` re-exercises the SAME primitive wired into
``failoverd.py``'s health-driven loop; this file is the ground truth for
what the primitive itself guarantees, independent of how it gets called.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.team_bot_ingress.ingress_leader import (
    DEFAULT_RECORD_ID,
    AuthorizeOutcome,
    IngressLeaderState,
    InMemoryIngressLeaderStore,
    PromoteOutcome,
    RenewOutcome,
    outcome_to_http_status,
)

T0 = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)


def _bootstrap(
    *, active_node_id: str = "mini-pro2", epoch: int = 1, lease_seconds: float = 30.0
) -> InMemoryIngressLeaderStore:
    return InMemoryIngressLeaderStore(
        IngressLeaderState(
            record_id=DEFAULT_RECORD_ID,
            active_node_id=active_node_id,
            leader_epoch=epoch,
            lease_expires_at=T0 + timedelta(seconds=lease_seconds),
            callback_uri_sha256="a" * 64,
            changed_at=T0,
        )
    )


# ---------------------------------------------------------------------
# try_promote — the innocent case (guilt/innocence pairing per the
# orchestrator's ask: every rejection test below has a matching success
# test using the SAME setup with only the epoch changed).
# ---------------------------------------------------------------------


async def test_promote_succeeds_with_correct_expected_epoch() -> None:
    store = _bootstrap(epoch=1)
    result = await store.try_promote(
        expected_epoch=1,
        new_node_id="pro",
        lease_seconds=60.0,
        new_callback_sha256="b" * 64,
        now=T0 + timedelta(seconds=5),
    )
    assert result.outcome is PromoteOutcome.PROMOTED
    assert result.state.active_node_id == "pro"
    assert result.state.leader_epoch == 2
    assert result.state.callback_uri_sha256 == "b" * 64
    # Persisted — a fresh read sees the promoted state, not the bootstrap one.
    assert (await store.read()) == result.state


async def test_promote_rejects_stale_expected_epoch() -> None:
    """A caller that read epoch=1 five seconds ago, while someone else
    already promoted to epoch=2, must be refused — never silently
    overwrite the newer state.
    """
    store = _bootstrap(epoch=1)
    await store.try_promote(
        expected_epoch=1,
        new_node_id="pro",
        lease_seconds=60.0,
        new_callback_sha256="b" * 64,
        now=T0,
    )
    stale_attempt = await store.try_promote(
        expected_epoch=1,  # stale — real epoch is now 2
        new_node_id="mini-pro2",
        lease_seconds=60.0,
        new_callback_sha256="c" * 64,
        now=T0 + timedelta(seconds=1),
    )
    assert stale_attempt.outcome is PromoteOutcome.CONFLICT_STALE_EPOCH
    # The callback and owner from the FIRST promotion are untouched.
    assert stale_attempt.state.active_node_id == "pro"
    assert stale_attempt.state.callback_uri_sha256 == "b" * 64
    assert stale_attempt.state.leader_epoch == 2


async def test_split_brain_concurrent_promote_exactly_one_winner() -> None:
    """The orchestrator's split-brain case, at the primitive level: N
    concurrent CAS attempts against the SAME expected epoch — regardless
    of scheduling order, exactly one may win.
    """
    store = _bootstrap(epoch=1)
    attempts = [
        store.try_promote(
            expected_epoch=1,
            new_node_id=f"contender-{i}",
            lease_seconds=60.0,
            new_callback_sha256=f"{i}" * 64,
            now=T0,
        )
        for i in range(8)
    ]
    results = await asyncio.gather(*attempts)
    winners = [r for r in results if r.outcome is PromoteOutcome.PROMOTED]
    losers = [r for r in results if r.outcome is PromoteOutcome.CONFLICT_STALE_EPOCH]
    assert len(winners) == 1, "split-brain: more than one contender was promoted"
    assert len(losers) == 7
    final = await store.read()
    assert final.leader_epoch == 2
    assert final.active_node_id == winners[0].state.active_node_id


# ---------------------------------------------------------------------
# renew — the active node's heartbeat.
# ---------------------------------------------------------------------


async def test_renew_extends_lease_without_bumping_epoch() -> None:
    store = _bootstrap(active_node_id="mini-pro2", epoch=1, lease_seconds=10.0)
    result = await store.renew(
        node_id="mini-pro2", epoch=1, lease_seconds=30.0, now=T0 + timedelta(seconds=5)
    )
    assert result.outcome is RenewOutcome.RENEWED
    assert result.state.leader_epoch == 1  # unchanged
    assert result.state.lease_expires_at == T0 + timedelta(seconds=35)


async def test_renew_rejects_stale_epoch() -> None:
    """A stale node waking up and believing a stale epoch (the
    orchestrator's explicit example) tries to renew and is refused.
    """
    store = _bootstrap(active_node_id="mini-pro2", epoch=1)
    await store.try_promote(
        expected_epoch=1,
        new_node_id="pro",
        lease_seconds=60.0,
        new_callback_sha256="b" * 64,
        now=T0,
    )
    stale_renew = await store.renew(
        node_id="mini-pro2", epoch=1, lease_seconds=30.0, now=T0 + timedelta(seconds=1)
    )
    assert stale_renew.outcome is RenewOutcome.REJECTED_STALE_EPOCH


async def test_renew_rejects_wrong_node_even_with_current_epoch() -> None:
    """Defensive branch: epoch matches but the caller names a node that
    isn't the current owner. In practice epoch and owner change together
    via try_promote, so this only fires if a caller's ticket is simply
    wrong — still must be refused, not accepted on epoch match alone.
    """
    store = _bootstrap(active_node_id="mini-pro2", epoch=1)
    result = await store.renew(node_id="pro", epoch=1, lease_seconds=30.0, now=T0)
    assert result.outcome is RenewOutcome.REJECTED_WRONG_NODE


# ---------------------------------------------------------------------
# authorize — what a CRM mutation endpoint calls per-action.
# ---------------------------------------------------------------------


async def test_authorize_allows_current_node_and_epoch_within_lease() -> None:
    store = _bootstrap(active_node_id="mini-pro2", epoch=1, lease_seconds=30.0)
    result = await store.authorize(
        node_id="mini-pro2", epoch=1, now=T0 + timedelta(seconds=5)
    )
    assert result.outcome is AuthorizeOutcome.AUTHORIZED
    assert result.http_status == 200


async def test_authorize_rejects_stale_epoch_after_takeover_mid_flight() -> None:
    """The orchestrator's fifth named case: a mutation captured epoch=1
    BEFORE promotion; the epoch changes mid-flight; the mutation's
    authorize() check — using the epoch it captured earlier, not a fresh
    read — must be rejected, never silently allowed through under the
    new leader's identity.
    """
    store = _bootstrap(active_node_id="mini-pro2", epoch=1)
    captured_epoch = (await store.read()).leader_epoch  # action starts here
    await store.try_promote(
        expected_epoch=1,
        new_node_id="pro",
        lease_seconds=60.0,
        new_callback_sha256="b" * 64,
        now=T0 + timedelta(seconds=1),
    )  # ...failover happens WHILE the action above is still in flight...
    result = await store.authorize(
        node_id="mini-pro2", epoch=captured_epoch, now=T0 + timedelta(seconds=2)
    )
    assert result.outcome is AuthorizeOutcome.REJECTED_STALE_EPOCH
    assert result.http_status == 409


async def test_authorize_rejects_wrong_node() -> None:
    store = _bootstrap(active_node_id="mini-pro2", epoch=1)
    result = await store.authorize(node_id="pro", epoch=1, now=T0)
    assert result.outcome is AuthorizeOutcome.REJECTED_WRONG_NODE
    assert result.http_status == 403


async def test_authorize_rejects_expired_lease_even_with_matching_epoch_and_node() -> None:
    store = _bootstrap(active_node_id="mini-pro2", epoch=1, lease_seconds=10.0)
    result = await store.authorize(
        node_id="mini-pro2", epoch=1, now=T0 + timedelta(seconds=11)
    )
    assert result.outcome is AuthorizeOutcome.REJECTED_LEASE_EXPIRED
    assert result.http_status == 409


@pytest.mark.parametrize(
    "outcome",
    [
        AuthorizeOutcome.AUTHORIZED,
        AuthorizeOutcome.REJECTED_STALE_EPOCH,
        AuthorizeOutcome.REJECTED_LEASE_EXPIRED,
        AuthorizeOutcome.REJECTED_WRONG_NODE,
    ],
)
def test_outcome_to_http_status_is_exhaustive(outcome: AuthorizeOutcome) -> None:
    status = outcome_to_http_status(outcome)  # must not raise KeyError for any member
    assert status in (200, 403, 409)


def test_outcome_to_http_status_rejects_unmapped_value() -> None:
    """RED case for the mapping's own completeness guard: a value that is
    NOT a real AuthorizeOutcome member must not silently resolve to 200.
    """
    with pytest.raises(KeyError):
        outcome_to_http_status("not-a-real-outcome")  # type: ignore[arg-type]
