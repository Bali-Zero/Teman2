"""Actuator: quarantine a target by writing Redis key with TTL.

Writes `organism:quarantine:<target>` with a JSON payload describing the
reason + TTL (default 24h). Other guardians / actuators check for the
presence of the key before acting on the target — it's a soft-lockout,
not a hard mutex. TTL auto-expires so quarantine never wedges permanently.
"""
import json
import time

from organism.actuators.base import ActuatorBase


QUARANTINE_KEY_PREFIX = "organism:quarantine:"
DEFAULT_TTL_HOURS = 24


class Quarantine(ActuatorBase):
    name = "quarantine"

    def __init__(self, *, redis):
        self.redis = redis

    async def _execute(self, params: dict) -> dict:
        target = params["target"]
        reason = params.get("reason", "unspecified")
        ttl_hours = int(params.get("ttl_hours", DEFAULT_TTL_HOURS))
        ttl_seconds = ttl_hours * 3600
        payload = json.dumps(
            {
                "target": target,
                "reason": reason,
                "quarantined_at": time.time(),
                "ttl_hours": ttl_hours,
            }
        )
        await self.redis.set(
            QUARANTINE_KEY_PREFIX + target,
            payload,
            ex=ttl_seconds,
        )
        return {
            "target": target,
            "reason": reason,
            "ttl_hours": ttl_hours,
        }

    async def _dry_run(self, params: dict) -> dict:
        return {
            "would_quarantine": params.get("target"),
            "reason": params.get("reason"),
            "ttl_hours": params.get("ttl_hours", DEFAULT_TTL_HOURS),
        }
