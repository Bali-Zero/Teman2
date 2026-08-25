"""``team-bot-failoverd`` — the Pro-only watch loop (F9 §4.2 steps 1-8).

Every dependency is injected (``FailoverdDeps``) — health probes, the
leader store, the WABA client, the clock. That is what lets
``test_staging_drill.py`` drive :func:`evaluate_and_act_once` directly,
one tick at a time, with zero real sockets and zero real sleep: this
module's OWN test coverage is "does the decision logic do the right
thing given these inputs", not "does a real network probe actually see
a real Mini" — that empirical question is F9's separate staging-WABA
drill, never claimed to be answered by anything in this repo's test
suite.

**Design decisions worth reading before extending this file**:

- ``evaluate_and_act_once`` re-reads :class:`IngressLeaderStore` FRESH
  on every tick — no locally cached "am I the leader" belief survives
  across ticks or a process restart. This is the same SSOT discipline
  ``ingress_leader.py`` documents (superscar family #10): a per-process
  belief that outlives a restart is exactly the kind of state that
  causes split-brain, so there isn't one here.
- Once Pro already holds leadership (``current.active_node_id ==
  node_id``), a further tick with Mini still down NEVER calls
  ``try_promote`` again — it only retries the WABA callback
  confirmation if a PRIOR tick's override call failed. Re-promoting a
  node that already holds the seat would bump the epoch for no reason
  and is simply unnecessary given the fresh-read discipline above.
- Mini recovering healthy touches NOTHING in this module — there is no
  code path from "Mini's ``/readyz`` returned 200" to any store or WABA
  call. That omission, not a flag, is what makes F9's "no automatic
  failback" true after every future edit to this file, not just today.
- A promotion that succeeds locally (CAS won) but whose WABA override
  call then fails is reported as its OWN distinct outcome
  (``PROMOTED_BUT_CALLBACK_UNCONFIRMED``), never silently folded into
  either full success or full failure — Pro is, at that point, the
  authoritative mutation leader per the SSOT while Meta may still be
  routing inbound traffic to Mini. That window is F9's own accepted
  design ("not zero downtime"), but it must be OBSERVABLE, not silent.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import asyncpg
import httpx

from backend.services.team_bot_ingress.ingress_leader import (
    DEFAULT_RECORD_ID,
    AuthorizeOutcome,
    IngressLeaderStore,
    PromoteOutcome,
    RenewOutcome,
    evaluate_authorize,
)
from backend.services.team_bot_ingress.ingress_state_repo import PostgresIngressLeaderStore
from backend.services.team_bot_ingress.waba_override import (
    DEFAULT_GRAPH_VERSION,
    WABAOverrideClient,
    WABAOverrideError,
)

logger = logging.getLogger(__name__)

DEFAULT_CONSECUTIVE_FAILURE_THRESHOLD = 3
DEFAULT_SUSTAINED_FAILURE_SECONDS = 30.0
DEFAULT_LEASE_SECONDS = 30.0


class ActionKind(StrEnum):
    NO_ACTION_MINI_HEALTHY = "no_action_mini_healthy"
    NO_ACTION_NOT_YET_ELIGIBLE = "no_action_not_yet_eligible"
    REFUSED_SELF_UNHEALTHY = "refused_self_unhealthy"
    REFUSED_CAS_CONFLICT = "refused_cas_conflict"
    REFUSED_STALE_LEADERSHIP_BEFORE_WRITE = "refused_stale_leadership_before_write"
    SHADOW_WOULD_PROMOTE_BUT_DISABLED = "shadow_would_promote_but_disabled"
    PROMOTED_AND_CONFIRMED = "promoted_and_confirmed"
    PROMOTED_BUT_CALLBACK_UNCONFIRMED = "promoted_but_callback_unconfirmed"
    ALREADY_LEADER_CALLBACK_CONFIRMED = "already_leader_callback_confirmed"
    ALREADY_LEADER_CALLBACK_RETRY_FAILED = "already_leader_callback_retry_failed"


@dataclass(frozen=True, slots=True)
class SelfHealthReport:
    """F9 step 3's five prechecks. ``ollama_reachable`` and
    ``replication_lag_ok`` and ``identity_snapshot_valid`` are legitimately
    NOT this lane's substance (B4 owns Ollama serving, B3 owns sqlite
    replication + identity) — this dataclass names the CONTRACT those
    lanes' checks must satisfy, it does not fabricate an implementation
    of them. See :data:`FailoverdDeps.run_self_prechecks` for where a real
    caller wires the real checks in.
    """

    ollama_reachable: bool
    replication_lag_ok: bool
    identity_snapshot_valid: bool
    backend_crm_healthy: bool
    funnel_reachable: bool

    @property
    def all_pass(self) -> bool:
        return (
            self.ollama_reachable
            and self.replication_lag_ok
            and self.identity_snapshot_valid
            and self.backend_crm_healthy
            and self.funnel_reachable
        )


@dataclass(frozen=True, slots=True)
class FailoverAction:
    kind: ActionKind
    detail: str = ""


@dataclass
class MiniFailureTracker:
    """Pure in-process bookkeeping — the 3-consecutive-failures AND
    30s-sustained rule from F9 §4.2 step 2. No I/O, unit-testable on its
    own (see the parametrized tests in ``test_failoverd.py``).
    """

    consecutive_failures: int = 0
    first_failure_at: datetime | None = None

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.first_failure_at = None

    def record_failure(self, now: datetime) -> None:
        if self.consecutive_failures == 0:
            self.first_failure_at = now
        self.consecutive_failures += 1

    def should_attempt_promotion(
        self,
        now: datetime,
        *,
        mini_unavailable_in_tailscale: bool,
        consecutive_threshold: int = DEFAULT_CONSECUTIVE_FAILURE_THRESHOLD,
        sustained_seconds: float = DEFAULT_SUSTAINED_FAILURE_SECONDS,
    ) -> bool:
        if self.consecutive_failures < consecutive_threshold:
            return False
        if mini_unavailable_in_tailscale:
            return True
        assert self.first_failure_at is not None  # invariant: failures>0 implies this is set
        return (now - self.first_failure_at) >= timedelta(seconds=sustained_seconds)


HealthProbe = Callable[[], Awaitable[bool]]
SelfPrechecks = Callable[[], Awaitable[SelfHealthReport]]


@dataclass
class FailoverdDeps:
    """Everything :func:`evaluate_and_act_once` needs, all injected.

    ``check_mini_ready`` / ``check_mini_tailscale_unavailable`` and
    ``run_self_prechecks`` are the THREE probes a real deployment must
    wire to actual network calls before ``TEAM_BOT_FAILOVER_AUTO_ENABLED``
    ever flips — nothing in this module calls a real socket itself.
    """

    node_id: str
    store: IngressLeaderStore
    waba_client: WABAOverrideClient
    waba_id: str
    callback_uri: str
    callback_uri_sha256: str
    verify_token: str
    check_mini_ready: HealthProbe
    check_mini_tailscale_unavailable: HealthProbe
    run_self_prechecks: SelfPrechecks
    lease_seconds: float = DEFAULT_LEASE_SECONDS
    auto_enabled: bool = False
    """``TEAM_BOT_FAILOVER_AUTO_ENABLED`` (KILL-SWITCHES.md, owned by
    lane B7 — this field just reads the same name). Defaults False, same
    as the documented kill switch default. When False, EVERY action past
    the initial health/eligibility check — a brand-new promotion AND a
    retry of an already-held leadership's callback confirmation — is
    replaced by :data:`ActionKind.SHADOW_WOULD_PROMOTE_BUT_DISABLED`,
    never a real store write or a real Meta call. This is what makes F9's
    "shadow intent/tool selection" promotion rung (owner switchboard item
    7) observable: the daemon can run continuously and prove what it
    WOULD have done, with zero side effects, before the operator arms it.
    """


async def _fence_write_with_live_epoch(
    *, deps: FailoverdDeps, epoch: int, now: datetime
) -> str | None:
    """The write-fence every outbound WABA write must pass through
    immediately before it fires — see
    docs/plans/2026-08-25-due-bot-live/ops/F9-CALLBACK-WRITE-FENCE-SPEC.md.

    Two live checks, in order, both against a FRESH read — never the
    belief the caller formed earlier in the same tick:

    1. ``evaluate_authorize`` — the SAME 3-way rule (epoch match, node
       match, lease not expired) a CRM mutation endpoint uses per F7.
       This is what makes "am I still leader RIGHT NOW" mean the SAME
       thing for an outbound WABA write as it means for every other
       protected action — refutation finding #4 named exactly this
       inconsistency (an expired lease rejects a mutation via
       authorize() but the WABA-write path checked nothing).
    2. ``renew()`` — extends the lease NOW, as a CAS on the SAME
       (node_id, epoch). A pure read-only check like authorize() cannot
       do this (by design — it must stay safe for a read-only caller);
       this fence is allowed to mutate, so it also keeps a legitimate
       leader's lease topped up going forward, closing a separate,
       previously-unexercised gap: nothing anywhere called renew()
       before this fix, so a leader's lease was only ever set once, at
       promotion.

    Returns ``None`` if the write may proceed, or a short string naming
    which check failed (for logging/ActionKind detail) otherwise.
    """
    current = await deps.store.read()
    auth = evaluate_authorize(current, node_id=deps.node_id, epoch=epoch, now=now)
    if auth.outcome is not AuthorizeOutcome.AUTHORIZED:
        return f"authorize:{auth.outcome}"
    renew_result = await deps.store.renew(
        node_id=deps.node_id, epoch=epoch, lease_seconds=deps.lease_seconds, now=now
    )
    if renew_result.outcome is not RenewOutcome.RENEWED:
        return f"renew:{renew_result.outcome}"
    return None


async def evaluate_and_act_once(
    *, tracker: MiniFailureTracker, deps: FailoverdDeps, now: datetime
) -> FailoverAction:
    """One tick of the failoverd loop. See the module docstring for the
    three design invariants this function's shape enforces.
    """

    mini_ready = await deps.check_mini_ready()
    if mini_ready:
        tracker.record_success()
        return FailoverAction(kind=ActionKind.NO_ACTION_MINI_HEALTHY)

    tracker.record_failure(now)
    mini_unavailable = await deps.check_mini_tailscale_unavailable()
    if not tracker.should_attempt_promotion(now, mini_unavailable_in_tailscale=mini_unavailable):
        return FailoverAction(
            kind=ActionKind.NO_ACTION_NOT_YET_ELIGIBLE,
            detail=f"consecutive_failures={tracker.consecutive_failures}",
        )

    current = await deps.store.read()

    if not deps.auto_enabled:
        return FailoverAction(
            kind=ActionKind.SHADOW_WOULD_PROMOTE_BUT_DISABLED,
            detail=f"current_active_node={current.active_node_id} current_epoch={current.leader_epoch}",
        )

    if current.active_node_id == deps.node_id:
        # Already the leader per an EARLIER read — never trust that
        # belief for the outbound write itself. Fence immediately before
        # firing (spec: F9-CALLBACK-WRITE-FENCE-SPEC.md).
        fence_rejection = await _fence_write_with_live_epoch(
            deps=deps, epoch=current.leader_epoch, now=now
        )
        if fence_rejection is not None:
            logger.warning(
                "team-bot-failoverd: refusing already-leader callback write, "
                "live re-check failed (%s) — leadership belief was stale",
                fence_rejection,
            )
            return FailoverAction(
                kind=ActionKind.REFUSED_STALE_LEADERSHIP_BEFORE_WRITE,
                detail=f"already_leader_branch:{fence_rejection}",
            )
        try:
            await deps.waba_client.override_callback(
                waba_id=deps.waba_id,
                callback_uri=deps.callback_uri,
                verify_token=deps.verify_token,
            )
        except WABAOverrideError as exc:
            logger.error("team-bot-failoverd: callback retry failed: %s", exc.error_class)
            return FailoverAction(
                kind=ActionKind.ALREADY_LEADER_CALLBACK_RETRY_FAILED,
                detail=str(exc.error_class),
            )
        return FailoverAction(kind=ActionKind.ALREADY_LEADER_CALLBACK_CONFIRMED)

    self_health = await deps.run_self_prechecks()
    if not self_health.all_pass:
        logger.warning(
            "team-bot-failoverd: refusing promotion, self unhealthy: %r", self_health
        )
        return FailoverAction(
            kind=ActionKind.REFUSED_SELF_UNHEALTHY, detail=repr(self_health)
        )

    promote_result = await deps.store.try_promote(
        expected_epoch=current.leader_epoch,
        new_node_id=deps.node_id,
        lease_seconds=deps.lease_seconds,
        new_callback_sha256=deps.callback_uri_sha256,
        now=now,
    )
    if promote_result.outcome is PromoteOutcome.CONFLICT_STALE_EPOCH:
        logger.warning(
            "team-bot-failoverd: CAS conflict, someone else holds epoch=%d",
            promote_result.state.leader_epoch,
        )
        return FailoverAction(
            kind=ActionKind.REFUSED_CAS_CONFLICT,
            detail=f"actual_epoch={promote_result.state.leader_epoch}",
        )

    logger.info(
        "team-bot-failoverd: PROMOTED node=%s epoch=%d",
        deps.node_id,
        promote_result.state.leader_epoch,
    )
    # Fence even a JUST-won promotion — try_promote's CAS already set a
    # fresh lease, but the CAS commit and this write are two separate
    # awaits with a real (if small) window between them where another
    # concurrent promoter could have raced past (refutation finding #1's
    # exact scenario: "DB leader B, WABA callback A"). Spec:
    # F9-CALLBACK-WRITE-FENCE-SPEC.md.
    fence_rejection = await _fence_write_with_live_epoch(
        deps=deps, epoch=promote_result.state.leader_epoch, now=now
    )
    if fence_rejection is not None:
        logger.critical(
            "team-bot-failoverd: promoted to epoch=%d but the live write-fence "
            "refused (%s) — refusing to write a callback that would overwrite "
            "the CURRENT leader's own",
            promote_result.state.leader_epoch,
            fence_rejection,
        )
        return FailoverAction(
            kind=ActionKind.REFUSED_STALE_LEADERSHIP_BEFORE_WRITE,
            detail=f"post_promotion:{fence_rejection}",
        )
    try:
        await deps.waba_client.override_callback(
            waba_id=deps.waba_id,
            callback_uri=deps.callback_uri,
            verify_token=deps.verify_token,
        )
    except WABAOverrideError as exc:
        logger.critical(
            "team-bot-failoverd: promoted to epoch=%d but WABA override FAILED "
            "(%s) — Pro is mutation-leader while Meta may still route ingress "
            "to Mini; operator alert required",
            promote_result.state.leader_epoch,
            exc.error_class,
        )
        return FailoverAction(
            kind=ActionKind.PROMOTED_BUT_CALLBACK_UNCONFIRMED,
            detail=str(exc.error_class),
        )

    return FailoverAction(
        kind=ActionKind.PROMOTED_AND_CONFIRMED,
        detail=f"epoch={promote_result.state.leader_epoch}",
    )


# =======================================================================
# Real deployment wiring — everything above this line has zero I/O
# dependencies of its own and is exercised entirely by the drill suite.
# Everything below is the "operator step is a one-value flip" boundary:
# a real process, real env vars, real (if narrow) network/subprocess
# calls. None of this is exercised by backend/tests/duebot/ — it is the
# thing the F9 staging-WABA drill (not a test file) validates for real.
# =======================================================================


def _find_tailscale_peer_online(hostname: str) -> bool | None:
    """Real check via ``tailscale status --json`` (verified against the
    installed CLI, v1.96.5, empirically — NOT copied from the research
    capture, whose example commands use an older/different CLI syntax
    that this installed version's ``--help`` output does not accept).

    Returns ``None`` when the peer cannot be found in the tailnet map at
    all — deliberately distinct from ``False`` ("definitely offline"),
    since "we don't even know this node" and "we know it and it's down"
    should not be silently conflated by a caller that treats both as
    "unavailable" without at least being ABLE to tell them apart in logs.
    """

    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        status = json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as exc:
        logger.warning("team-bot-failoverd: tailscale status check failed: %s", exc)
        return None

    for peer in status.get("Peer", {}).values():
        if str(peer.get("HostName", "")).lower() == hostname.lower():
            return bool(peer.get("Online"))
    return None


@dataclass(frozen=True, slots=True)
class FailoverdConfig:
    """Every setting read from the environment — Golden Rule #6, no
    hardcoded secrets. ``from_env`` reads NAMES, never bundles a default
    for anything secret (``waba_access_token``/``verify_token``/
    ``database_url`` are required — a missing one is a startup failure,
    never a silent empty string reaching a live Meta/Postgres call).
    """

    node_id: str
    waba_id: str
    callback_uri: str
    callback_uri_sha256: str
    verify_token: str
    waba_access_token: str
    database_url: str
    mini_readyz_url: str
    mini_tailscale_hostname: str
    backend_health_url: str
    funnel_local_url: str
    poll_seconds: float
    auto_enabled: bool

    @classmethod
    def from_env(cls) -> FailoverdConfig:
        def _require(name: str) -> str:
            value = os.environ.get(name)
            if not value:
                raise RuntimeError(f"team-bot-failoverd: required env var {name} is unset")
            return value

        return cls(
            node_id=os.environ.get("TEAM_BOT_FAILOVER_NODE_ID", "pro"),
            waba_id=_require("TEAM_BOT_WABA_ID"),
            callback_uri=_require("TEAM_BOT_FAILOVER_CALLBACK_URI"),
            callback_uri_sha256=_require("TEAM_BOT_FAILOVER_CALLBACK_URI_SHA256"),
            verify_token=_require("TEAM_BOT_WABA_VERIFY_TOKEN"),
            waba_access_token=_require("TEAM_BOT_WABA_ACCESS_TOKEN"),
            database_url=_require("TEAM_BOT_FAILOVER_DATABASE_URL"),
            mini_readyz_url=_require("TEAM_BOT_MINI_READYZ_URL"),
            mini_tailscale_hostname=os.environ.get(
                "TEAM_BOT_MINI_TAILSCALE_HOSTNAME", "Mini-Pro2"
            ),
            backend_health_url=_require("TEAM_BOT_BACKEND_HEALTH_URL"),
            funnel_local_url=os.environ.get(
                "TEAM_BOT_FUNNEL_LOCAL_URL", "http://127.0.0.1:8765/livez"
            ),
            poll_seconds=float(os.environ.get("TEAM_BOT_FAILOVER_POLL_SECONDS", "5.0")),
            auto_enabled=os.environ.get("TEAM_BOT_FAILOVER_AUTO_ENABLED", "false").lower()
            == "true",
        )


async def _run_self_prechecks_not_fully_wired(
    *, http_client: httpx.AsyncClient, config: FailoverdConfig
) -> SelfHealthReport:
    """Two of F9 step 3's five prechecks are genuinely this lane's to
    implement (``backend_crm_healthy``, ``funnel_reachable`` — both real
    HTTP calls below). The other three are NOT: ``ollama_reachable`` is
    B4's serving-plant substance, ``replication_lag_ok`` is B3's sqlite-
    replication substance, ``identity_snapshot_valid`` is B3's F7
    identity substance. They are hardcoded False here rather than
    faked True, so this daemon can be run TODAY (even armed) and can
    never actually promote until whichever lane owns each check replaces
    this function's body — refusing to promote is the safe failure mode
    for an unwired precheck, silently passing is not.
    """

    logger.warning(
        "team-bot-failoverd: ollama_reachable/replication_lag_ok/"
        "identity_snapshot_valid are NOT WIRED YET (B4/B3) — promotion "
        "will always be REFUSED_SELF_UNHEALTHY until they are replaced"
    )

    async def _check(url: str) -> bool:
        try:
            response = await http_client.get(url, timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    backend_crm_healthy = await _check(config.backend_health_url)
    # "Reachable from an external probe" (F9 step 3) is NOT what this
    # checks — it only proves the LOCAL service behind the Funnel is up,
    # which is the part Pro can verify about itself without a third
    # party. True external reachability needs a probe from OUTSIDE the
    # tailnet, which is not something this process can do to itself.
    funnel_reachable = await _check(config.funnel_local_url)

    return SelfHealthReport(
        ollama_reachable=False,
        replication_lag_ok=False,
        identity_snapshot_valid=False,
        backend_crm_healthy=backend_crm_healthy,
        funnel_reachable=funnel_reachable,
    )


def build_real_deps(
    *, config: FailoverdConfig, http_client: httpx.AsyncClient, pg_pool: asyncpg.Pool
) -> FailoverdDeps:
    """Wires :class:`FailoverdDeps` to real network/subprocess calls.
    Never constructs its own ``httpx.AsyncClient`` or pool (Golden Rule
    #10 — both are owned and closed by :func:`main`'s lifespan).
    """

    async def check_mini_ready() -> bool:
        try:
            response = await http_client.get(config.mini_readyz_url, timeout=5.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def check_mini_tailscale_unavailable() -> bool:
        online = await asyncio.to_thread(
            _find_tailscale_peer_online, config.mini_tailscale_hostname
        )
        return online is not True  # None (unknown) or False both count as unavailable

    async def run_self_prechecks() -> SelfHealthReport:
        return await _run_self_prechecks_not_fully_wired(http_client=http_client, config=config)

    return FailoverdDeps(
        node_id=config.node_id,
        store=PostgresIngressLeaderStore(pg_pool, record_id=DEFAULT_RECORD_ID),
        waba_client=WABAOverrideClient(
            http_client,
            access_token=config.waba_access_token,
            graph_version=DEFAULT_GRAPH_VERSION,
        ),
        waba_id=config.waba_id,
        callback_uri=config.callback_uri,
        callback_uri_sha256=config.callback_uri_sha256,
        verify_token=config.verify_token,
        check_mini_ready=check_mini_ready,
        check_mini_tailscale_unavailable=check_mini_tailscale_unavailable,
        run_self_prechecks=run_self_prechecks,
        auto_enabled=config.auto_enabled,
    )


async def _create_pool_with_retry(
    database_url: str,
    *,
    max_attempts: int = 6,
    initial_delay: float = 5.0,
    max_delay: float = 60.0,
) -> asyncpg.Pool:
    """Bounded exponential-backoff retry around ``asyncpg.create_pool`` —
    refutation finding #8: config parsing and pool creation ran before
    ``asyncio.run()``/outside the runner's own tick-level exception
    handling, so a transient Postgres-unavailable-at-BOOT condition
    (network blip, boot ordering where the Postgres LaunchDaemon has not
    started yet) exited the whole process and relied on launchd's
    KeepAlive+ThrottleInterval to relaunch it every 30s forever — "the
    loop is genuinely long-running only after initialization succeeds"
    (the refuter's own words, spec: F9-CALLBACK-WRITE-FENCE-SPEC.md).
    This absorbs an ordinary boot-ordering race INSIDE the process.

    A PERMANENTLY broken DSN (wrong host, wrong credentials, Postgres
    genuinely down for good) still fails — just after ``max_attempts``
    (default: ~2 minutes total) rather than after one try. Missing
    REQUIRED ENV VARS (``FailoverdConfig.from_env()``) are DELIBERATELY
    NOT retried here — a real misconfiguration a human must fix by
    editing the env file, which no amount of retrying resolves.
    """
    delay = initial_delay
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await asyncpg.create_pool(database_url, min_size=1, max_size=2)
        except (OSError, asyncpg.PostgresError) as exc:
            last_error = exc
            logger.warning(
                "team-bot-failoverd: Postgres pool creation failed (attempt %d/%d): %s "
                "— retrying in %.0fs",
                attempt,
                max_attempts,
                exc,
                delay,
            )
            if attempt < max_attempts:
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
    raise RuntimeError(
        f"team-bot-failoverd: could not create Postgres pool after {max_attempts} attempts"
    ) from last_error


class FailoverdRunner:
    """The real blocking loop (superscar family #7's antidote — a
    genuine ``while`` loop under ``KeepAlive``, never a one-shot script
    a LaunchDaemon would restart-storm on every exit). Mirrors
    ``wa_codex_daemon.py``'s own shape: an interruptible sleep so a
    SIGTERM/SIGINT wakes the loop immediately rather than waiting out a
    poll interval, and every tick's exception is caught and logged —
    one bad tick must never kill the daemon (that would BE the restart
    storm this shape exists to avoid).
    """

    def __init__(self, *, deps: FailoverdDeps, poll_seconds: float) -> None:
        self._deps = deps
        self._poll_seconds = poll_seconds
        self._tracker = MiniFailureTracker()
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        logger.info(
            "team-bot-failoverd: starting node=%s auto_enabled=%s poll_seconds=%.1f",
            self._deps.node_id,
            self._deps.auto_enabled,
            self._poll_seconds,
        )
        while not self._stop.is_set():
            try:
                action = await evaluate_and_act_once(
                    tracker=self._tracker, deps=self._deps, now=datetime.now(UTC)
                )
                if action.kind is not ActionKind.NO_ACTION_MINI_HEALTHY:
                    logger.info("team-bot-failoverd: tick -> %s (%s)", action.kind, action.detail)
            except Exception:
                logger.exception("team-bot-failoverd: tick raised, continuing")
            await self._sleep(self._poll_seconds)
        logger.info("team-bot-failoverd: stopped")

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except TimeoutError:
            pass  # normal poll-interval wake; stop stays unset


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    config = FailoverdConfig.from_env()

    async def _run() -> None:
        # Golden Rule #10: one httpx.AsyncClient for the daemon's entire
        # process lifetime (created once at startup, threaded through
        # FailoverdDeps by injection, never re-instantiated per tick or
        # per call — evaluate_and_act_once/_run_self_prechecks reuse this
        # SAME client on every poll). Not hoisted to a module-level
        # `*_http.py` singleton like email_http.py: this file's whole
        # design (see module docstring) is explicit DI with zero hidden
        # module-level state, precisely so test_staging_drill.py can
        # drive the decision logic with an injected fake client — a
        # global singleton getter would reintroduce the module-level
        # state that design deliberately avoids, for a client this
        # module's own single call site already owns end-to-end.
        # `async with` (rather than manual try/finally) also closes the
        # client if `_create_pool_with_retry` below raises, which the
        # prior try/finally — entered only after both lines ran — did
        # not.
        async with httpx.AsyncClient(base_url="https://graph.facebook.com") as http_client:
            pg_pool = await _create_pool_with_retry(config.database_url)
            try:
                deps = build_real_deps(config=config, http_client=http_client, pg_pool=pg_pool)
                runner = FailoverdRunner(deps=deps, poll_seconds=config.poll_seconds)
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.add_signal_handler(sig, runner.request_stop)
                await runner.run_forever()
            finally:
                await pg_pool.close()

    asyncio.run(_run())


if __name__ == "__main__":
    main()


__all__ = [
    "DEFAULT_CONSECUTIVE_FAILURE_THRESHOLD",
    "DEFAULT_LEASE_SECONDS",
    "DEFAULT_SUSTAINED_FAILURE_SECONDS",
    "ActionKind",
    "FailoverAction",
    "FailoverdConfig",
    "FailoverdDeps",
    "FailoverdRunner",
    "MiniFailureTracker",
    "SelfHealthReport",
    "build_real_deps",
    "evaluate_and_act_once",
    "main",
]
