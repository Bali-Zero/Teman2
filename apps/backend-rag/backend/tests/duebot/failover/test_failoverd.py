"""Unit-level proof of ``failoverd.py``'s own pieces — the failure
tracker's promotion-eligibility rule (F9 §4.2 step 2, in isolation) and
each :class:`ActionKind` :func:`evaluate_and_act_once` can produce, one
at a time, before ``test_staging_drill.py`` composes them into the
orchestrator's named end-to-end scenarios.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.services.team_bot_ingress.failoverd import (
    ActionKind,
    FailoverdDeps,
    MiniFailureTracker,
    SelfHealthReport,
    _fence_write_with_live_epoch,
    evaluate_and_act_once,
)
from backend.services.team_bot_ingress.ingress_leader import (
    DEFAULT_RECORD_ID,
    IngressLeaderState,
    InMemoryIngressLeaderStore,
)
from backend.services.team_bot_ingress.waba_override import WABAOverrideClient
from backend.tests.duebot.failover.fake_graph_api import FakeGraphAPI

T0 = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)
HEALTHY = SelfHealthReport(
    ollama_reachable=True,
    replication_lag_ok=True,
    identity_snapshot_valid=True,
    backend_crm_healthy=True,
    funnel_reachable=True,
)


# ---------------------------------------------------------------------
# MiniFailureTracker — pure logic, no I/O.
# ---------------------------------------------------------------------


def test_tracker_starts_ineligible() -> None:
    tracker = MiniFailureTracker()
    assert tracker.should_attempt_promotion(T0, mini_unavailable_in_tailscale=False) is False


def test_tracker_ineligible_below_consecutive_threshold() -> None:
    tracker = MiniFailureTracker()
    tracker.record_failure(T0)
    tracker.record_failure(T0 + timedelta(seconds=5))
    assert (
        tracker.should_attempt_promotion(
            T0 + timedelta(seconds=40), mini_unavailable_in_tailscale=True
        )
        is False
    )


def test_tracker_eligible_at_threshold_when_tailscale_unavailable() -> None:
    tracker = MiniFailureTracker()
    for i in range(3):
        tracker.record_failure(T0 + timedelta(seconds=i))
    assert (
        tracker.should_attempt_promotion(T0 + timedelta(seconds=3), mini_unavailable_in_tailscale=True)
        is True
    )


def test_tracker_at_threshold_but_reachable_needs_sustained_30s() -> None:
    tracker = MiniFailureTracker()
    for i in range(3):
        tracker.record_failure(T0 + timedelta(seconds=i))
    # Reachable in Tailscale (just slow/erroring), only 3s elapsed — not eligible yet.
    assert (
        tracker.should_attempt_promotion(
            T0 + timedelta(seconds=3), mini_unavailable_in_tailscale=False
        )
        is False
    )
    # Same reachable state, 30s elapsed since FIRST failure — now eligible.
    assert (
        tracker.should_attempt_promotion(
            T0 + timedelta(seconds=30), mini_unavailable_in_tailscale=False
        )
        is True
    )


def test_tracker_success_resets_everything() -> None:
    tracker = MiniFailureTracker()
    for i in range(5):
        tracker.record_failure(T0 + timedelta(seconds=i))
    tracker.record_success()
    assert tracker.consecutive_failures == 0
    assert tracker.first_failure_at is None
    assert (
        tracker.should_attempt_promotion(
            T0 + timedelta(seconds=100), mini_unavailable_in_tailscale=True
        )
        is False
    )


# ---------------------------------------------------------------------
# evaluate_and_act_once — one ActionKind at a time.
# ---------------------------------------------------------------------


def _deps(
    *,
    node_id: str,
    store: InMemoryIngressLeaderStore,
    waba: FakeGraphAPI,
    httpx_client,
    mini_ready: bool,
    mini_unavailable: bool = True,
    self_health: SelfHealthReport = HEALTHY,
    auto_enabled: bool = True,
) -> FailoverdDeps:
    """``auto_enabled`` defaults True here — these tests exercise the
    ARMED decision logic. The disabled/shadow default itself is proven
    separately by
    ``test_shadow_mode_takes_no_action_even_when_eligible_and_healthy``
    below, which passes ``auto_enabled=False`` explicitly.
    """

    async def check_mini_ready() -> bool:
        return mini_ready

    async def check_mini_tailscale_unavailable() -> bool:
        return mini_unavailable

    async def run_self_prechecks() -> SelfHealthReport:
        return self_health

    return FailoverdDeps(
        node_id=node_id,
        store=store,
        waba_client=WABAOverrideClient(httpx_client, access_token="fake"),
        waba_id="waba-1",
        callback_uri="https://pro.example.ts.net/webhooks/team-wa",
        callback_uri_sha256="f" * 64,
        verify_token="vt",
        check_mini_ready=check_mini_ready,
        check_mini_tailscale_unavailable=check_mini_tailscale_unavailable,
        run_self_prechecks=run_self_prechecks,
        auto_enabled=auto_enabled,
    )


def _bootstrap_store(*, active_node_id: str = "mini-pro2", epoch: int = 1) -> InMemoryIngressLeaderStore:
    return InMemoryIngressLeaderStore(
        IngressLeaderState(
            record_id=DEFAULT_RECORD_ID,
            active_node_id=active_node_id,
            leader_epoch=epoch,
            lease_expires_at=T0 + timedelta(seconds=60),
            callback_uri_sha256="a" * 64,
            changed_at=T0,
        )
    )


async def test_mini_healthy_takes_no_action() -> None:
    store = _bootstrap_store()
    fake = FakeGraphAPI()
    async with fake.client() as httpx_client:
        deps = _deps(
            node_id="pro", store=store, waba=fake, httpx_client=httpx_client, mini_ready=True
        )
        result = await evaluate_and_act_once(tracker=MiniFailureTracker(), deps=deps, now=T0)
    assert result.kind is ActionKind.NO_ACTION_MINI_HEALTHY
    assert len(fake.post_calls) == 0
    assert (await store.read()).active_node_id == "mini-pro2"


async def test_not_yet_eligible_takes_no_action() -> None:
    store = _bootstrap_store()
    fake = FakeGraphAPI()
    tracker = MiniFailureTracker()
    async with fake.client() as httpx_client:
        deps = _deps(
            node_id="pro", store=store, waba=fake, httpx_client=httpx_client, mini_ready=False
        )
        result = await evaluate_and_act_once(tracker=tracker, deps=deps, now=T0)
    assert result.kind is ActionKind.NO_ACTION_NOT_YET_ELIGIBLE
    assert len(fake.post_calls) == 0


async def test_self_unhealthy_refuses_promotion() -> None:
    store = _bootstrap_store()
    fake = FakeGraphAPI()
    unhealthy = SelfHealthReport(
        ollama_reachable=True,
        replication_lag_ok=True,
        identity_snapshot_valid=True,
        backend_crm_healthy=False,  # Pro's own backend check fails
        funnel_reachable=True,
    )
    tracker = MiniFailureTracker()
    for i in range(3):
        tracker.record_failure(T0 + timedelta(seconds=i))
    async with fake.client() as httpx_client:
        deps = _deps(
            node_id="pro",
            store=store,
            waba=fake,
            httpx_client=httpx_client,
            mini_ready=False,
            self_health=unhealthy,
        )
        result = await evaluate_and_act_once(tracker=tracker, deps=deps, now=T0 + timedelta(seconds=3))
    assert result.kind is ActionKind.REFUSED_SELF_UNHEALTHY
    assert len(fake.post_calls) == 0
    assert (await store.read()).leader_epoch == 1  # unchanged — no CAS attempted


async def test_healthy_promotion_confirms_callback() -> None:
    store = _bootstrap_store(active_node_id="mini-pro2", epoch=1)
    fake = FakeGraphAPI()
    tracker = MiniFailureTracker()
    for i in range(3):
        tracker.record_failure(T0 + timedelta(seconds=i))
    async with fake.client() as httpx_client:
        deps = _deps(
            node_id="pro", store=store, waba=fake, httpx_client=httpx_client, mini_ready=False
        )
        result = await evaluate_and_act_once(tracker=tracker, deps=deps, now=T0 + timedelta(seconds=3))
    assert result.kind is ActionKind.PROMOTED_AND_CONFIRMED
    assert len(fake.post_calls) == 1
    state = await store.read()
    assert state.active_node_id == "pro"
    assert state.leader_epoch == 2


async def test_promotion_with_failed_waba_override_is_its_own_outcome() -> None:
    store = _bootstrap_store(active_node_id="mini-pro2", epoch=1)
    fake = FakeGraphAPI(force_status=500)
    tracker = MiniFailureTracker()
    for i in range(3):
        tracker.record_failure(T0 + timedelta(seconds=i))
    async with fake.client() as httpx_client:
        deps = _deps(
            node_id="pro", store=store, waba=fake, httpx_client=httpx_client, mini_ready=False
        )
        result = await evaluate_and_act_once(tracker=tracker, deps=deps, now=T0 + timedelta(seconds=3))
    assert result.kind is ActionKind.PROMOTED_BUT_CALLBACK_UNCONFIRMED
    # The epoch DID advance — Pro is mutation-leader even though the
    # callback confirmation failed. That is the documented accepted
    # partial state, not a bug — this assertion is what keeps it honest.
    state = await store.read()
    assert state.active_node_id == "pro"
    assert state.leader_epoch == 2


async def test_already_leader_retries_callback_without_repromoting() -> None:
    """Pro already holds the seat (a prior tick promoted it) — a further
    tick with Mini still down must NOT bump the epoch again, only retry
    the callback confirmation.
    """
    store = _bootstrap_store(active_node_id="pro", epoch=2)
    fake = FakeGraphAPI()
    tracker = MiniFailureTracker()
    for i in range(3):
        tracker.record_failure(T0 + timedelta(seconds=i))
    async with fake.client() as httpx_client:
        deps = _deps(
            node_id="pro", store=store, waba=fake, httpx_client=httpx_client, mini_ready=False
        )
        result = await evaluate_and_act_once(tracker=tracker, deps=deps, now=T0 + timedelta(seconds=3))
    assert result.kind is ActionKind.ALREADY_LEADER_CALLBACK_CONFIRMED
    state = await store.read()
    assert state.leader_epoch == 2  # UNCHANGED — no re-promotion


async def test_shadow_mode_takes_no_action_even_when_eligible_and_healthy() -> None:
    """``TEAM_BOT_FAILOVER_AUTO_ENABLED=false`` (the default —
    KILL-SWITCHES.md) — Mini is down, Pro is fully healthy, eligibility
    threshold is met, and STILL zero store writes and zero WABA calls.
    Only the observable ActionKind changes, so shadow-mode metrics can
    tell "would have promoted" apart from "not eligible yet" and from
    "refused, unhealthy" (F11 / owner switchboard item 7's first rung).
    """
    store = _bootstrap_store(active_node_id="mini-pro2", epoch=1)
    fake = FakeGraphAPI()
    tracker = MiniFailureTracker()
    for i in range(3):
        tracker.record_failure(T0 + timedelta(seconds=i))
    async with fake.client() as httpx_client:
        deps = _deps(
            node_id="pro",
            store=store,
            waba=fake,
            httpx_client=httpx_client,
            mini_ready=False,
            auto_enabled=False,
        )
        result = await evaluate_and_act_once(tracker=tracker, deps=deps, now=T0 + timedelta(seconds=3))
    assert result.kind is ActionKind.SHADOW_WOULD_PROMOTE_BUT_DISABLED
    assert len(fake.post_calls) == 0
    assert len(fake.get_calls) == 0
    final = await store.read()
    assert final.active_node_id == "mini-pro2"
    assert final.leader_epoch == 1


# ---------------------------------------------------------------------
# _fence_write_with_live_epoch — refutation findings #3/#4. See
# F9-CALLBACK-WRITE-FENCE-SPEC.md.
# ---------------------------------------------------------------------


async def test_write_fence_refuses_stale_epoch() -> None:
    store = _bootstrap_store(active_node_id="pro", epoch=2)
    fake = FakeGraphAPI()
    async with fake.client() as httpx_client:
        deps = _deps(
            node_id="pro", store=store, waba=fake, httpx_client=httpx_client, mini_ready=False
        )
        rejection = await _fence_write_with_live_epoch(deps=deps, epoch=1, now=T0)  # stale epoch
    assert rejection is not None
    assert "authorize" in rejection


async def test_write_fence_refuses_expired_lease_even_with_matching_epoch_and_node() -> None:
    """Refutation finding #4: an expired lease must refuse the write, the
    SAME way authorize() already refuses a CRM mutation under an expired
    lease -- consistency between the two gates is the whole point.
    """
    store = InMemoryIngressLeaderStore(
        IngressLeaderState(
            record_id=DEFAULT_RECORD_ID,
            active_node_id="pro",
            leader_epoch=2,
            lease_expires_at=T0 - timedelta(seconds=5),  # already expired
            callback_uri_sha256="a" * 64,
            changed_at=T0 - timedelta(seconds=35),
        )
    )
    fake = FakeGraphAPI()
    async with fake.client() as httpx_client:
        deps = _deps(
            node_id="pro", store=store, waba=fake, httpx_client=httpx_client, mini_ready=False
        )
        rejection = await _fence_write_with_live_epoch(deps=deps, epoch=2, now=T0)
    assert rejection is not None
    assert "authorize" in rejection


async def test_write_fence_succeeds_and_extends_the_lease() -> None:
    store = _bootstrap_store(active_node_id="pro", epoch=2)
    fake = FakeGraphAPI()
    async with fake.client() as httpx_client:
        deps = _deps(
            node_id="pro", store=store, waba=fake, httpx_client=httpx_client, mini_ready=False
        )
        rejection = await _fence_write_with_live_epoch(deps=deps, epoch=2, now=T0)
    assert rejection is None
    state = await store.read()
    assert state.lease_expires_at == T0 + timedelta(seconds=deps.lease_seconds)


async def test_already_leader_branch_calls_the_fence_and_refuses_on_expired_lease() -> None:
    """End-to-end through evaluate_and_act_once itself, not just the fence
    helper in isolation -- proves the ALREADY-LEADER branch actually wires
    the fence in, not merely that the fence works when called directly.
    """
    store = InMemoryIngressLeaderStore(
        IngressLeaderState(
            record_id=DEFAULT_RECORD_ID,
            active_node_id="pro",
            leader_epoch=2,
            lease_expires_at=T0 - timedelta(seconds=5),
            callback_uri_sha256="a" * 64,
            changed_at=T0 - timedelta(seconds=35),
        )
    )
    fake = FakeGraphAPI()
    tracker = MiniFailureTracker()
    for i in range(3):
        tracker.record_failure(T0 + timedelta(seconds=i))
    async with fake.client() as httpx_client:
        deps = _deps(
            node_id="pro", store=store, waba=fake, httpx_client=httpx_client, mini_ready=False
        )
        result = await evaluate_and_act_once(
            tracker=tracker, deps=deps, now=T0 + timedelta(seconds=3)
        )
    assert result.kind is ActionKind.REFUSED_STALE_LEADERSHIP_BEFORE_WRITE
    assert len(fake.post_calls) == 0, "the stale-lease leader must never reach Meta"
