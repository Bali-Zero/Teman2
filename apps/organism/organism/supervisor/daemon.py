"""Stateless Supervisor daemon — main consume loop.

Modes:
- W1 shadow_mode=True: logs decisions to JSONL, does NOT invoke actuators.
- W2 shadow_mode=False: looks up actuator in `actuator_registry`, calls
  `await actuator.run(...)`, optionally fires `on_dispatched` callback for
  Telegram alerts. Kill switch is the file `~/.agent/supervisor/active.flag`
  (read by `ActiveFlag.is_active()`); when set to "1" the daemon flips to
  W2. Anything else (file missing, "0", empty) → shadow.

Architecture:
    - consumes events from Redis stream `organism:events` via the
      `organism-supervisor` consumer group
    - hydrates IncidentContext per correlation_id (state is in Redis,
      not in process memory — the daemon itself is stateless and can be
      restarted freely)
    - asks Decider for an ActionDecision (L0 YAML only in W1)
    - appends a decision record to ~/logs/organism/decisions.jsonl
    - in active mode: routes the decision through Dispatcher → actuator
      registry → optional Telegram callback
    - writes a heartbeat every cycle so W0.3 guardians can enter
      local_emergency_mode if the Supervisor dies
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

from organism.blackout import BlackoutManager
from organism.schemas import Event
from organism.supervisor.active_flag import ActiveFlag
from organism.supervisor.circuit_breaker import CircuitBreaker
from organism.supervisor.decider import Decider
from organism.supervisor.dispatch import Dispatcher, DispatchOutcome
from organism.supervisor.incident_context import IncidentStore
from organism.supervisor.mutex import Mutex
from organism.supervisor.yaml_rules import RuleMatcher


log = logging.getLogger(__name__)

STREAM_KEY = "organism:events"
SUPERVISOR_HB_KEY = "organism:supervisor:heartbeat"
HB_TTL = 600  # 10 min — matches heartbeat.DEFAULT_MAX_LAG_SECONDS safety window
CONSUMER_GROUP = "organism-supervisor"
CONSUMER_NAME = "supervisor-1"

# Operator-controlled active flag — file at ~/.agent/supervisor/active.flag
DEFAULT_ACTIVE_FLAG_PATH = Path.home() / ".agent" / "supervisor" / "active.flag"
DEFAULT_BLACKOUT_FLAG_PATH = Path.home() / ".agent" / "supervisor" / "pause.flag"


async def _write_heartbeat(redis) -> None:
    """Refresh the Supervisor liveness key used by W0.3 guardians."""
    await redis.set(SUPERVISOR_HB_KEY, str(time.time()), ex=HB_TTL)


async def _ensure_consumer_group(redis) -> None:
    """Create the consumer group on the events stream if missing.

    mkstream=True is safe: if the stream does not exist yet, Redis creates
    an empty stream. id="0" means the group starts from the oldest entry
    so a Supervisor restart drains any backlog of events that arrived
    while it was down (stream MAXLEN caps growth).
    BUSYGROUP just means the group already exists — ignore. Anything else
    is surfaced.
    """
    try:
        await redis.xgroup_create(
            STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True,
        )
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def _decode_data_field(fields: Any) -> str:
    """Extract the 'data' field as a str from a variety of fakeredis/redis shapes."""
    if isinstance(fields, dict):
        raw = fields.get(b"data")
        if raw is None:
            raw = fields.get("data")
    else:
        raw = fields["data"]
    if isinstance(raw, (bytes, bytearray)):
        return raw.decode("utf-8")
    return str(raw)


def _target_for(decision_actuator: str, params: Mapping[str, Any]) -> str:
    """Compute a stable per-target key for circuit breaker / mutex.

    For restart_agent the target is the agent name. For other actuators we
    fall back to a sentinel so cross-target calls don't share a single
    bucket. Keep this in sync with rules/base.yaml param shapes.
    """
    if decision_actuator == "restart_agent":
        ref = params.get("agent_ref")
        if isinstance(ref, str) and ref:
            return ref
    if decision_actuator == "adopt_module":
        path = params.get("module_path")
        if isinstance(path, str) and path:
            return path
    if decision_actuator == "cleanup_log":
        # cleanup_log is global per-host — single target lane is fine.
        return "global"
    return "global"


async def run_once(
    *,
    redis,
    decisions_log: Path,
    rules_yaml: str | None = None,
    rules_path: Path | None = None,
    shadow_mode: bool = True,
    block_ms: int = 1000,
    count: int = 100,
    actuator_registry: Mapping[str, Any] | None = None,
    blackout_flag: Path | None = None,
    on_dispatched: Callable[..., Awaitable[None]] | None = None,
) -> int:
    """Run one consume+decide+dispatch+log cycle. Returns events processed.

    Active-mode behavior (shadow_mode=False):
      - constructs Dispatcher with shared CircuitBreaker, Mutex, BlackoutManager
        on the supplied flag path
      - looks up the decided actuator in `actuator_registry` and invokes it
      - on a DISPATCHED outcome, fires `on_dispatched` (best-effort Telegram)

    Shadow-mode behavior (shadow_mode=True):
      - everything above except the actuator is invoked in DRY-RUN through
        Dispatcher's shadow path; in practice run_once short-circuits to
        SHADOW_LOGGED. `on_dispatched` is NOT called in shadow.
    """
    await _write_heartbeat(redis)
    await _ensure_consumer_group(redis)

    if rules_yaml is None and rules_path is not None:
        rules_yaml = Path(rules_path).read_text(encoding="utf-8")
    matcher = RuleMatcher.from_yaml_text(rules_yaml or "rules: []")
    decider = Decider(
        matcher=matcher, incident_store=IncidentStore(redis=redis),
    )

    blackout_path = blackout_flag or DEFAULT_BLACKOUT_FLAG_PATH
    dispatcher = Dispatcher(
        redis=redis,
        circuit_breaker=CircuitBreaker(redis=redis),
        mutex=Mutex(redis=redis),
        blackout=BlackoutManager(flag_path=blackout_path),
        shadow_mode=shadow_mode,
        actuator_registry=actuator_registry or {},
        on_dispatched=on_dispatched if not shadow_mode else None,
    )

    result = await redis.xreadgroup(
        CONSUMER_GROUP, CONSUMER_NAME,
        {STREAM_KEY: ">"},
        count=count, block=block_ms,
    )
    if not result:
        return 0

    decisions_log = Path(decisions_log)
    decisions_log.parent.mkdir(parents=True, exist_ok=True)

    processed = 0
    for _stream_name, entries in result:
        for msg_id, fields in entries:
            try:
                raw = _decode_data_field(fields)
                event = Event.model_validate_json(raw)
                decision = await decider.decide(event)
                target = _target_for(decision.actuator, decision.params)

                outcome = await dispatcher.dispatch(
                    decision=decision,
                    target=target,
                    correlation_id=event.correlation_id,
                )

                entry = {
                    "ts": time.time(),
                    "event_kind": event.kind,
                    "correlation_id": event.correlation_id,
                    "actuator": decision.actuator,
                    "tier": decision.tier,
                    "confidence": decision.confidence,
                    "shadow_mode": shadow_mode,
                    "dispatch_outcome": outcome.value,
                    "target": target,
                }
                with decisions_log.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")

                await redis.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)
                processed += 1
            except Exception:
                log.exception("failed to process event %s", msg_id)
    return processed


async def main() -> None:  # pragma: no cover — launchd entrypoint
    import redis.asyncio as _redis  # local import so tests don't need live Redis

    from organism.actuators import build_actuator_registry

    r = _redis.from_url(
        os.getenv("ORGANISM_REDIS_URL", "redis://127.0.0.1:6379/0"),
    )
    rules_path = Path(os.getenv(
        "ORGANISM_RULES_PATH",
        str(Path(__file__).resolve().parents[2] / "rules" / "base.yaml"),
    ))
    decisions_log = Path(os.getenv(
        "ORGANISM_DECISIONS_LOG",
        str(Path.home() / "logs" / "organism" / "decisions.jsonl"),
    ))
    active_flag_path = Path(os.getenv(
        "ORGANISM_ACTIVE_FLAG_PATH", str(DEFAULT_ACTIVE_FLAG_PATH),
    ))
    blackout_flag_path = Path(os.getenv(
        "ORGANISM_BLACKOUT_FLAG_PATH", str(DEFAULT_BLACKOUT_FLAG_PATH),
    ))
    # ORGANISM_SHADOW_MODE remains a backward-compat hard-off switch:
    # if explicitly set to "true", we stay in shadow regardless of file flag.
    forced_shadow_env = (
        os.getenv("ORGANISM_SHADOW_MODE", "true").lower() == "true"
    )
    active_flag = ActiveFlag(path=active_flag_path)
    registry = build_actuator_registry(redis=r)

    # Lazy import to keep the daemon import light when telegram bits absent
    from organism.supervisor.telegram_alert import build_dispatch_alerter

    on_dispatched = build_dispatch_alerter(registry)

    while True:
        try:
            file_active = active_flag.is_active()
            shadow = (not file_active) or forced_shadow_env
            if file_active and forced_shadow_env:
                log.warning(
                    "active.flag=1 BUT ORGANISM_SHADOW_MODE=true — staying "
                    "in shadow. Unset env var to enable W2.",
                )
            await run_once(
                redis=r,
                rules_path=rules_path,
                decisions_log=decisions_log,
                shadow_mode=shadow,
                actuator_registry=registry,
                blackout_flag=blackout_flag_path,
                on_dispatched=on_dispatched if not shadow else None,
            )
        except Exception:
            log.exception("run_once failed; sleeping 5s")
            await asyncio.sleep(5)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
