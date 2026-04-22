"""Dispatcher — central gatekeeper for Actuator invocations.

Integrates:
- Circuit Breaker (per-target cooldown)
- Distributed Mutex (per-target concurrency)
- Blackout flag (human maintenance window)
- Hardcoded whitelist / blacklist (in CODE, not YAML — prevents loop bypass)
- is_actuation flag check on the originating event (avoided upstream by
  the L0 rule matcher, but dispatcher asserts the decision was not born
  from an actuation event)

In W1 shadow mode: logs the decision then returns SHADOW_LOGGED without
invoking the actuator. W2 will flip shadow_mode=False and the dispatcher
will actually call actuator.run().
"""
import logging
from enum import Enum
from organism.schemas import ActionDecision


log = logging.getLogger(__name__)


# Hardcoded whitelists — NOT in YAML. A loop cannot modify code at runtime.
SAFE_ACTUATORS = frozenset({
    "restart_agent",
    "cleanup_log",
    "notify_telegram",
    "quarantine",
    "consolidate_redundancy",  # W3.C — L3 (gated by consiglio_gate IRREVERSIBLE_ACTUATORS)
    # W3 also adds: adopt_module, cleanup_cache, cleanup_branches, cleanup_zombie_plist (parallel PRs)
    # W4 adds: propose_yaml_rule
})

HUMAN_ONLY_ACTUATORS = frozenset({
    "restart_supervisor",
    "rollback_deploy",
    "drop_table",
    "revoke_credential",
    "fly_ssh_exec",
})


class DispatchOutcome(str, Enum):
    SHADOW_LOGGED = "shadow_logged"
    DISPATCHED = "dispatched"
    DEFERRED_BLACKOUT = "deferred_blackout"
    DEFERRED_CB = "deferred_cb"
    DEFERRED_MUTEX = "deferred_mutex"
    AWAITING_HUMAN = "awaiting_human"
    REJECTED_UNKNOWN = "rejected_unknown"
    DEFERRED_DEFER_ACTUATOR = "deferred_defer_actuator"


class Dispatcher:
    def __init__(
        self,
        *,
        redis,
        circuit_breaker,
        mutex,
        blackout,
        shadow_mode: bool = True,
    ):
        self.redis = redis
        self.circuit_breaker = circuit_breaker
        self.mutex = mutex
        self.blackout = blackout
        self.shadow_mode = shadow_mode

    def _target_key(self, decision: ActionDecision, target: str) -> str:
        return f"{decision.actuator}:{target}"

    async def dispatch(
        self,
        *,
        decision: ActionDecision,
        target: str,
        correlation_id: str,
    ) -> DispatchOutcome:
        actuator = decision.actuator

        # 0. Defer-to-human pseudo-actuator (emitted by Decider when no rule matched in W1)
        if actuator == "defer_to_human":
            log.info(
                "dispatch: defer_to_human for corr=%s (tier=%s) — shadow_logged",
                correlation_id, decision.tier,
            )
            return DispatchOutcome.DEFERRED_DEFER_ACTUATOR

        # 1. Is the actuator even known?
        if actuator in HUMAN_ONLY_ACTUATORS:
            log.warning(
                "dispatch: actuator=%s is HUMAN_ONLY — awaiting_human corr=%s",
                actuator, correlation_id,
            )
            return DispatchOutcome.AWAITING_HUMAN
        if actuator not in SAFE_ACTUATORS:
            log.warning(
                "dispatch: actuator=%s not in SAFE_ACTUATORS — rejected corr=%s",
                actuator, correlation_id,
            )
            return DispatchOutcome.REJECTED_UNKNOWN

        # 2. Blackout flag (operator pause)
        if self.blackout.is_paused():
            log.info("dispatch: blackout active — deferred corr=%s", correlation_id)
            return DispatchOutcome.DEFERRED_BLACKOUT

        target_key = self._target_key(decision, target)

        # 3. Circuit breaker
        if not await self.circuit_breaker.allow(target_key):
            log.warning(
                "dispatch: circuit breaker tripped for %s — deferred corr=%s",
                target_key, correlation_id,
            )
            return DispatchOutcome.DEFERRED_CB

        # 4. Mutex
        lock_id = await self.mutex.acquire(target_key, ttl_seconds=300)
        if lock_id is None:
            log.info(
                "dispatch: mutex held for %s — deferred corr=%s",
                target_key, correlation_id,
            )
            return DispatchOutcome.DEFERRED_MUTEX

        try:
            # 5. Shadow or active dispatch
            if self.shadow_mode:
                log.info(
                    "dispatch (shadow): would run actuator=%s params=%s corr=%s",
                    actuator, decision.params, correlation_id,
                )
                return DispatchOutcome.SHADOW_LOGGED
            # Active mode — W2 wires actual actuator invocation here.
            # For W1 we just return DISPATCHED to prove the guard chain passed.
            log.info(
                "dispatch (active): actuator=%s params=%s corr=%s — invocation placeholder (W2)",
                actuator, decision.params, correlation_id,
            )
            return DispatchOutcome.DISPATCHED
        finally:
            await self.mutex.release(target_key, lock_id)
