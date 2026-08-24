"""The F9 staging-drill suite — the orchestrator's own ask, verbatim:

    "The staging drill must be synthetic and must prove failure, not
    just success ... Prove the cases that hurt: split-brain attempted
    and refused, stale epoch rejected, both nodes up, neither node up,
    takeover during an in-flight action. Guilt AND innocence."

Every scenario below is named after the orchestrator's own words, and
composes the REAL production pieces this lane built — no re-implemented
shortcuts: :class:`InMemoryIngressLeaderStore` (the same
``IngressLeaderStore`` Protocol the Postgres adapter implements),
:func:`evaluate_and_act_once` (``failoverd.py``'s actual decision
function, unmodified), and :class:`FakeGraphAPI` (``httpx.MockTransport``
— zero real sockets, ``network_guard.py`` would refuse one anyway).

**What this drill does NOT prove** (disclosed here, not left implicit,
per this repo's anti-hallucination discipline): whether the real Meta
Graph API actually behaves the way :class:`FakeGraphAPI` assumes, and
whether Meta re-addresses in-flight retries to a new callback the way
F9 hopes. Research §5.4's own closing line: *"The vendor-specific
assertion 'Meta retries an already failed delivery against the new
callback' cannot be proven by mocks. That requires one controlled
pre-production WABA/test-number drill."* This suite is the SYNTHETIC
half of F9's two-part gate; the staging-WABA half is a live drill this
repo cannot run from a test file, and ``TEAM_BOT_FAILOVER_AUTO_ENABLED``
must stay dark until BOTH halves pass.

Coverage map (defect_classes.yaml ``bot: transport`` entries this suite
exercises — ``transport.failover-stale-epoch-mutation-rejected`` already
existed from B6a; the others below were added by this lane):

    test_both_nodes_up_takes_no_action
        -> transport.failover-both-nodes-healthy-no-action
    test_neither_node_up_refuses_promotion
        -> transport.failover-neither-node-healthy-refused
    test_split_brain_attempted_and_refused
        -> transport.failover-split-brain-attempted-refused
    test_stale_epoch_rejected_after_promotion
        -> transport.failover-stale-epoch-mutation-rejected (existing)
    test_takeover_during_in_flight_action
        -> transport.failover-takeover-mid-flight-action
    test_no_automatic_failback_after_mini_recovers
        -> transport.failover-no-automatic-failback
    test_stale_node_wakes_believing_stale_epoch
        -> transport.failover-stale-node-wakes-stale-epoch
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from backend.services.team_bot_ingress.failoverd import (
    ActionKind,
    FailoverdDeps,
    MiniFailureTracker,
    SelfHealthReport,
    evaluate_and_act_once,
)
from backend.services.team_bot_ingress.ingress_leader import (
    DEFAULT_RECORD_ID,
    AuthorizeOutcome,
    IngressLeaderState,
    InMemoryIngressLeaderStore,
    RenewOutcome,
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
UNHEALTHY = SelfHealthReport(
    ollama_reachable=False,
    replication_lag_ok=True,
    identity_snapshot_valid=True,
    backend_crm_healthy=False,
    funnel_reachable=True,
)


def _bootstrap_store(
    *, active_node_id: str = "mini-pro2", epoch: int = 1
) -> InMemoryIngressLeaderStore:
    return InMemoryIngressLeaderStore(
        IngressLeaderState(
            record_id=DEFAULT_RECORD_ID,
            active_node_id=active_node_id,
            leader_epoch=epoch,
            lease_expires_at=T0 + timedelta(seconds=120),
            callback_uri_sha256="a" * 64,
            changed_at=T0,
        )
    )


def _deps(
    *,
    node_id: str,
    store: InMemoryIngressLeaderStore,
    httpx_client,
    mini_ready: bool,
    mini_unavailable: bool = True,
    self_health: SelfHealthReport = HEALTHY,
) -> FailoverdDeps:
    async def check_mini_ready() -> bool:
        return mini_ready

    async def check_mini_tailscale_unavailable() -> bool:
        return mini_unavailable

    async def run_self_prechecks() -> SelfHealthReport:
        return self_health

    return FailoverdDeps(
        node_id=node_id,
        store=store,
        waba_client=WABAOverrideClient(httpx_client, access_token="fake-token"),
        waba_id="waba-team-drill",
        callback_uri=f"https://{node_id}.example.ts.net/webhooks/team-wa",
        callback_uri_sha256="f" * 64,
        verify_token="fake-verify-token",
        check_mini_ready=check_mini_ready,
        check_mini_tailscale_unavailable=check_mini_tailscale_unavailable,
        run_self_prechecks=run_self_prechecks,
    )


async def _drive_n_unhealthy_ticks(
    *,
    n: int,
    tracker: MiniFailureTracker,
    store: InMemoryIngressLeaderStore,
    httpx_client,
    node_id: str = "pro",
    self_health: SelfHealthReport = HEALTHY,
    start: datetime = T0,
    tick_seconds: float = 1.0,
):
    """Drive ``n`` consecutive Mini-unhealthy ticks and return the LAST
    action. Mirrors what a real failoverd loop does across real time —
    each tick 1s apart, well under the 30s sustained-failure fallback,
    so eligibility here comes from the 3-consecutive-failures branch
    (mini_unavailable_in_tailscale=True in ``_deps``), matching F9's
    "OR" — not the sustained-30s branch, which
    ``test_failoverd.py::test_tracker_at_threshold_but_reachable_needs_sustained_30s``
    already covers on its own.
    """
    action = None
    for i in range(n):
        deps = _deps(
            node_id=node_id,
            store=store,
            httpx_client=httpx_client,
            mini_ready=False,
            self_health=self_health,
        )
        action = await evaluate_and_act_once(
            tracker=tracker, deps=deps, now=start + timedelta(seconds=tick_seconds * i)
        )
    return action


# ---------------------------------------------------------------------
# INNOCENCE — both nodes up.
# ---------------------------------------------------------------------


async def test_both_nodes_up_takes_no_action() -> None:
    """Mini healthy the entire time: across five ticks, failoverd never
    touches the leader store and never calls Meta. The innocent
    counterpart to every refusal test below — proves the machinery is
    quiet by default, not merely "fails closed when provoked".
    """
    store = _bootstrap_store(active_node_id="mini-pro2", epoch=1)
    fake = FakeGraphAPI()
    tracker = MiniFailureTracker()
    async with fake.client() as httpx_client:
        for i in range(5):
            deps = _deps(
                node_id="pro", store=store, httpx_client=httpx_client, mini_ready=True
            )
            action = await evaluate_and_act_once(
                tracker=tracker, deps=deps, now=T0 + timedelta(seconds=i)
            )
            assert action.kind is ActionKind.NO_ACTION_MINI_HEALTHY
    assert len(fake.post_calls) == 0
    assert len(fake.get_calls) == 0
    final = await store.read()
    assert final.active_node_id == "mini-pro2"
    assert final.leader_epoch == 1


# ---------------------------------------------------------------------
# GUILT — neither node up.
# ---------------------------------------------------------------------


async def test_neither_node_up_refuses_promotion() -> None:
    """Mini is down AND Pro itself fails its own prechecks (Ollama
    unreachable, backend CRM unhealthy) — Pro must NOT claim leadership
    just because Mini is worse off. Zero CAS attempts, zero Meta calls,
    leader state completely unchanged.
    """
    store = _bootstrap_store(active_node_id="mini-pro2", epoch=1)
    fake = FakeGraphAPI()
    tracker = MiniFailureTracker()
    async with fake.client() as httpx_client:
        action = await _drive_n_unhealthy_ticks(
            n=3, tracker=tracker, store=store, httpx_client=httpx_client, self_health=UNHEALTHY
        )
    assert action.kind is ActionKind.REFUSED_SELF_UNHEALTHY
    assert len(fake.post_calls) == 0
    final = await store.read()
    assert final.active_node_id == "mini-pro2"
    assert final.leader_epoch == 1


# ---------------------------------------------------------------------
# GUILT — split-brain attempted and refused.
# ---------------------------------------------------------------------


async def test_split_brain_attempted_and_refused() -> None:
    """Two contenders race a promotion attempt against the SAME store at
    the SAME expected epoch — the shape a genuine split-brain bug (two
    failoverd processes, or a mis-provisioned third node) would produce.
    ``asyncio.gather`` runs both truly concurrently; the store's
    internal lock (proven directly in
    ``test_ingress_leader.py::test_split_brain_concurrent_promote_exactly_one_winner``)
    is what makes exactly one win regardless of scheduling. Here the
    proof runs through the FULL failoverd decision path, not just the
    bare store primitive: both contenders pass their own health
    prechecks and both believe (correctly, at read time) that epoch=1
    is current — only one may act on that belief.
    """
    store = _bootstrap_store(active_node_id="mini-pro2", epoch=1)
    fake = FakeGraphAPI()
    tracker_a = MiniFailureTracker()
    tracker_b = MiniFailureTracker()
    for t in (tracker_a, tracker_b):
        for i in range(3):
            t.record_failure(T0 + timedelta(seconds=i))

    async with fake.client() as httpx_client:
        deps_a = _deps(node_id="pro-contender-a", store=store, httpx_client=httpx_client, mini_ready=False)
        deps_b = _deps(node_id="pro-contender-b", store=store, httpx_client=httpx_client, mini_ready=False)
        result_a, result_b = await asyncio.gather(
            evaluate_and_act_once(tracker=tracker_a, deps=deps_a, now=T0 + timedelta(seconds=3)),
            evaluate_and_act_once(tracker=tracker_b, deps=deps_b, now=T0 + timedelta(seconds=3)),
        )

    outcomes = {result_a.kind, result_b.kind}
    winners = [r for r in (result_a, result_b) if r.kind is ActionKind.PROMOTED_AND_CONFIRMED]
    losers = [r for r in (result_a, result_b) if r.kind is ActionKind.REFUSED_CAS_CONFLICT]
    assert len(winners) == 1, f"split-brain: expected exactly one winner, outcomes={outcomes}"
    assert len(losers) == 1
    assert len(fake.post_calls) == 1  # the loser NEVER reaches the WABA call
    final = await store.read()
    assert final.leader_epoch == 2
    assert final.active_node_id in {"pro-contender-a", "pro-contender-b"}


# ---------------------------------------------------------------------
# GUILT — stale epoch rejected.
# ---------------------------------------------------------------------


async def test_stale_epoch_rejected_after_promotion() -> None:
    """After a real failoverd promotion, a mutation attempt carrying the
    OLD epoch — exactly what a CRM endpoint would check via
    ``store.authorize()`` per F7 — is rejected with 409, never executed.
    """
    store = _bootstrap_store(active_node_id="mini-pro2", epoch=1)
    fake = FakeGraphAPI()
    tracker = MiniFailureTracker()
    async with fake.client() as httpx_client:
        action = await _drive_n_unhealthy_ticks(
            n=3, tracker=tracker, store=store, httpx_client=httpx_client
        )
    assert action.kind is ActionKind.PROMOTED_AND_CONFIRMED

    stale_mutation = await store.authorize(node_id="mini-pro2", epoch=1, now=T0 + timedelta(seconds=10))
    assert stale_mutation.outcome is AuthorizeOutcome.REJECTED_STALE_EPOCH
    assert stale_mutation.http_status == 409

    fresh_mutation = await store.authorize(node_id="pro", epoch=2, now=T0 + timedelta(seconds=10))
    assert fresh_mutation.outcome is AuthorizeOutcome.AUTHORIZED


# ---------------------------------------------------------------------
# GUILT — takeover during an in-flight action.
# ---------------------------------------------------------------------


async def test_takeover_during_in_flight_action() -> None:
    """A mutation ("open practice B1 for this client", say) reads the
    CURRENT epoch at its START — then, WHILE it is still in flight
    (before it calls back to confirm), Mini goes down and failoverd
    promotes Pro. The mutation's completion check must use the epoch it
    captured at start, and must be rejected — never silently allowed to
    finish under the new leader's identity just because node_id happens
    to differ from what it captured.
    """
    store = _bootstrap_store(active_node_id="mini-pro2", epoch=1)
    fake = FakeGraphAPI()

    # The in-flight action starts HERE, under Mini's leadership.
    action_start_state = await store.read()
    captured_node_id = action_start_state.active_node_id
    captured_epoch = action_start_state.leader_epoch

    # ...failover happens while that action is still "in flight"...
    tracker = MiniFailureTracker()
    async with fake.client() as httpx_client:
        failover_result = await _drive_n_unhealthy_ticks(
            n=3, tracker=tracker, store=store, httpx_client=httpx_client
        )
    assert failover_result.kind is ActionKind.PROMOTED_AND_CONFIRMED

    # ...the action NOW tries to complete, using what it captured at start.
    completion_check = await store.authorize(
        node_id=captured_node_id, epoch=captured_epoch, now=T0 + timedelta(seconds=10)
    )
    assert completion_check.outcome is AuthorizeOutcome.REJECTED_STALE_EPOCH
    assert completion_check.http_status == 409


# ---------------------------------------------------------------------
# INNOCENCE (of the WRONG action) — no automatic failback.
# ---------------------------------------------------------------------


async def test_no_automatic_failback_after_mini_recovers() -> None:
    """Pro takes over (Mini down); Mini then recovers healthy. A further
    failoverd tick must do NOTHING — no code path in failoverd.py hands
    leadership back on its own. Leadership stays with Pro until an
    explicit operator action (not exercised here — there is none to
    exercise; that is the point).
    """
    store = _bootstrap_store(active_node_id="mini-pro2", epoch=1)
    fake = FakeGraphAPI()
    tracker = MiniFailureTracker()
    async with fake.client() as httpx_client:
        failover_result = await _drive_n_unhealthy_ticks(
            n=3, tracker=tracker, store=store, httpx_client=httpx_client
        )
        assert failover_result.kind is ActionKind.PROMOTED_AND_CONFIRMED
        promoted_calls = len(fake.post_calls)

        # Mini "recovers" — /readyz now returns healthy.
        deps_recovered = _deps(
            node_id="pro", store=store, httpx_client=httpx_client, mini_ready=True
        )
        recovery_action = await evaluate_and_act_once(
            tracker=tracker, deps=deps_recovered, now=T0 + timedelta(seconds=100)
        )

    assert recovery_action.kind is ActionKind.NO_ACTION_MINI_HEALTHY
    assert len(fake.post_calls) == promoted_calls  # no NEW callback call fired
    final = await store.read()
    assert final.active_node_id == "pro"  # leadership did NOT revert
    assert final.leader_epoch == 2


# ---------------------------------------------------------------------
# GUILT — a stale node wakes up believing a stale epoch.
# ---------------------------------------------------------------------


async def test_stale_node_wakes_believing_stale_epoch() -> None:
    """The orchestrator's explicit example: Mini crashes and restarts
    (or was merely partitioned) and, on restart/reconnect, still
    believes it holds epoch=1 with itself as the active node. It tries
    to heartbeat (``renew``) and — separately — to authorize a mutation.
    Both must be rejected; neither may succeed just because Mini
    presents a technically-valid-looking (node_id, epoch) pair that is
    simply OLD.
    """
    store = _bootstrap_store(active_node_id="mini-pro2", epoch=1)
    fake = FakeGraphAPI()
    tracker = MiniFailureTracker()
    async with fake.client() as httpx_client:
        failover_result = await _drive_n_unhealthy_ticks(
            n=3, tracker=tracker, store=store, httpx_client=httpx_client
        )
    assert failover_result.kind is ActionKind.PROMOTED_AND_CONFIRMED

    # Mini wakes up and tries to heartbeat with its stale belief.
    stale_renew = await store.renew(
        node_id="mini-pro2", epoch=1, lease_seconds=30.0, now=T0 + timedelta(seconds=10)
    )
    assert stale_renew.outcome is RenewOutcome.REJECTED_STALE_EPOCH

    # Mini also tries to authorize a mutation with the same stale belief.
    stale_mutation = await store.authorize(
        node_id="mini-pro2", epoch=1, now=T0 + timedelta(seconds=10)
    )
    assert stale_mutation.outcome is AuthorizeOutcome.REJECTED_STALE_EPOCH
    assert stale_mutation.http_status == 409

    # Pro, meanwhile, is unaffected — its own heartbeat still works.
    pro_renew = await store.renew(
        node_id="pro", epoch=2, lease_seconds=30.0, now=T0 + timedelta(seconds=10)
    )
    assert pro_renew.outcome is RenewOutcome.RENEWED
