"""Stateless Supervisor daemon — main consume loop.

W1: shadow mode (logs decisions to JSONL, does NOT dispatch any actuator).
W1.C / W2 will flip the switch for a whitelisted set of safe actuators.

Architecture:
    - consumes events from Redis stream `organism:events` via the
      `organism-supervisor` consumer group
    - hydrates IncidentContext per correlation_id (state is in Redis,
      not in process memory — the daemon itself is stateless and can be
      restarted freely)
    - asks Decider for an ActionDecision (L0 YAML only in W1)
    - appends a decision record to ~/logs/organism/decisions.jsonl
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
from typing import Any

from organism.schemas import Event
from organism.supervisor.decider import Decider
from organism.supervisor.incident_context import IncidentStore
from organism.supervisor.yaml_rules import RuleMatcher


log = logging.getLogger(__name__)

STREAM_KEY = "organism:events"
SUPERVISOR_HB_KEY = "organism:supervisor:heartbeat"
HB_TTL = 600  # 10 min — matches heartbeat.DEFAULT_MAX_LAG_SECONDS safety window
CONSUMER_GROUP = "organism-supervisor"
CONSUMER_NAME = "supervisor-1"


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


async def run_once(
    *,
    redis,
    decisions_log: Path,
    rules_yaml: str | None = None,
    rules_path: Path | None = None,
    shadow_mode: bool = True,
    block_ms: int = 1000,
    count: int = 100,
) -> int:
    """Run one consume+decide+log cycle. Returns number of events processed."""
    await _write_heartbeat(redis)
    await _ensure_consumer_group(redis)

    if rules_yaml is None and rules_path is not None:
        rules_yaml = Path(rules_path).read_text(encoding="utf-8")
    matcher = RuleMatcher.from_yaml_text(rules_yaml or "rules: []")
    decider = Decider(
        matcher=matcher, incident_store=IncidentStore(redis=redis),
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
                entry = {
                    "ts": time.time(),
                    "event_kind": event.kind,
                    "correlation_id": event.correlation_id,
                    "actuator": decision.actuator,
                    "tier": decision.tier,
                    "confidence": decision.confidence,
                    "shadow_mode": shadow_mode,
                }
                with decisions_log.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
                if not shadow_mode:
                    # W1 is shadow-only; W1.C/W2 will replace this with real
                    # actuator dispatch for whitelisted safe actions.
                    log.warning(
                        "active mode dispatch not yet implemented (W1.C/W2)",
                    )
                await redis.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)
                processed += 1
            except Exception:
                log.exception("failed to process event %s", msg_id)
    return processed


async def main() -> None:  # pragma: no cover — launchd entrypoint
    import redis.asyncio as _redis  # local import so tests don't need live Redis

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
    shadow = os.getenv("ORGANISM_SHADOW_MODE", "true").lower() == "true"
    while True:
        try:
            await run_once(
                redis=r,
                rules_path=rules_path,
                decisions_log=decisions_log,
                shadow_mode=shadow,
            )
        except Exception:
            log.exception("run_once failed; sleeping 5s")
            await asyncio.sleep(5)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
