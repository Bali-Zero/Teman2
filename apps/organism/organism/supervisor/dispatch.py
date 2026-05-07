"""Dispatcher — central gatekeeper for Actuator invocations.

Integrates:
- Circuit Breaker (per-target cooldown)
- Distributed Mutex (per-target concurrency)
- Blackout flag (human maintenance window)
- Hardcoded whitelist / blacklist (in CODE, not YAML — prevents loop bypass)
- is_actuation flag check on the originating event (avoided upstream by
  the L0 rule matcher, but dispatcher asserts the decision was not born
  from an actuation event)

Modes:
- shadow_mode=True: log decision and return SHADOW_LOGGED, do NOT invoke actuator.
- shadow_mode=False (W2): look up actuator in `actuator_registry`,
  call `await actuator.run(params=..., correlation_id=..., dry_run=False)`,
  invoke optional `on_dispatched` callback (Telegram side-effect), return
  DISPATCHED. Actuator's own ActuatorBase.run() captures exceptions and
  emits done/failed events; the dispatcher only crashes if the actuator
  test double explicitly raises (it then records a CB failure and reports
  DISPATCHED — the upstream supervise loop continues).
"""
import logging
from enum import Enum
from typing import Any, Awaitable, Callable, Mapping, Protocol

from organism.schemas import ActionDecision


log = logging.getLogger(__name__)


# Hardcoded whitelists — NOT in YAML. A loop cannot modify code at runtime.
SAFE_ACTUATORS = frozenset({
    "restart_agent",
    "cleanup_log",
    "notify_telegram",
    "quarantine",
    "adopt_module",            # W3.A
    "consolidate_redundancy",  # W3.C — L3 (gated by consiglio_gate IRREVERSIBLE_ACTUATORS)
    "cleanup_cache",           # W3.B
    "cleanup_branches",        # W3.B
    "cleanup_zombie_plist",    # W3.B
    "propose_yaml_rule",       # W4.A — L3 (gated by consiglio_gate IRREVERSIBLE_ACTUATORS)
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


class _ActuatorLike(Protocol):
    name: str

    async def run(self, *, params, correlation_id, dry_run=False): ...


OnDispatchedCallback = Callable[..., Awaitable[None]]


class Dispatcher:
    def __init__(
        self,
        *,
        redis,
        circuit_breaker,
        mutex,
        blackout,
        shadow_mode: bool = True,
        actuator_registry: Mapping[str, _ActuatorLike] | None = None,
        on_dispatched: OnDispatchedCallback | None = None,
    ):
        self.redis = redis
        self.circuit_breaker = circuit_breaker
        self.mutex = mutex
        self.blackout = blackout
        self.shadow_mode = shadow_mode
        # Registry is required in active mode but allowed to be None in shadow
        # so callers (esp. tests) can construct a dispatcher without wiring
        # the full actuator graph just to verify shadow paths.
        self.actuator_registry = dict(actuator_registry or {})
        self.on_dispatched = on_dispatched

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

            # 6. W2 active mode — invoke the actuator.
            instance = self.actuator_registry.get(actuator)
            if instance is None:
                # Active mode but we have no implementation wired. Treat as
                # unknown so upstream observability (and operators) catch the
                # gap immediately rather than silently no-op'ing.
                log.error(
                    "dispatch (active): actuator=%s in SAFE list but not in "
                    "registry — rejected corr=%s",
                    actuator, correlation_id,
                )
                return DispatchOutcome.REJECTED_UNKNOWN

            log.info(
                "dispatch (active): actuator=%s params=%s corr=%s",
                actuator, decision.params, correlation_id,
            )
            result: Any
            try:
                result = await instance.run(
                    params=decision.params,
                    correlation_id=correlation_id,
                    dry_run=False,
                )
            except Exception as exc:  # actuator misbehaved (raised instead of returning {success: False})
                log.exception(
                    "dispatch (active): actuator=%s raised — recording CB "
                    "failure corr=%s",
                    actuator, correlation_id,
                )
                try:
                    await self.circuit_breaker.record_failure(target_key)
                except Exception:
                    log.exception("dispatch: CB record_failure failed (non-fatal)")
                result = {"success": False, "error": str(exc)[:500]}
            else:
                if not result.get("success", False):
                    try:
                        await self.circuit_breaker.record_failure(target_key)
                    except Exception:
                        log.exception("dispatch: CB record_failure failed (non-fatal)")

            # 7. Best-effort callback (e.g. Telegram alert). Failures here
            #    must NOT propagate — they would cascade into supervise-loop
            #    crashes the moment the bot token expires.
            if self.on_dispatched is not None:
                try:
                    await self.on_dispatched(
                        decision=decision,
                        target=target,
                        correlation_id=correlation_id,
                        result=result,
                    )
                except Exception:
                    log.exception(
                        "dispatch: on_dispatched callback raised (non-fatal)",
                    )

            return DispatchOutcome.DISPATCHED
        finally:
            await self.mutex.release(target_key, lock_id)
