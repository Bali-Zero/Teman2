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

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from backend.services.team_bot_ingress.ingress_leader import (
    IngressLeaderStore,
    PromoteOutcome,
)
from backend.services.team_bot_ingress.waba_override import (
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

    if current.active_node_id == deps.node_id:
        # Already the leader per the SSOT — never re-promote. Only retry
        # a PRIOR tick's failed WABA confirmation.
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


__all__ = [
    "DEFAULT_CONSECUTIVE_FAILURE_THRESHOLD",
    "DEFAULT_LEASE_SECONDS",
    "DEFAULT_SUSTAINED_FAILURE_SECONDS",
    "ActionKind",
    "FailoverAction",
    "FailoverdDeps",
    "MiniFailureTracker",
    "SelfHealthReport",
    "evaluate_and_act_once",
]
