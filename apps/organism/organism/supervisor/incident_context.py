"""IncidentContext hydrate/persist — state layer for stateless Supervisor.

The Supervisor daemon is stateless by design: all incident state lives in
Redis with a 10min TTL. IncidentStore is the narrow interface that lets the
Decider hydrate a correlation_id into an IncidentContext object and persist
it back after appending new events or updating fields like last_action.
"""
from organism.schemas import IncidentContext


INCIDENT_KEY_PREFIX = "organism:incident:"
INCIDENT_TTL = 600  # 10 min — matches spec §2 (stateless + Redis TTL)


class IncidentStore:
    """Thin Redis-backed store for IncidentContext objects."""

    def __init__(self, *, redis) -> None:
        self.redis = redis

    async def hydrate(self, correlation_id: str) -> IncidentContext:
        """Load IncidentContext for correlation_id, or return a fresh empty one."""
        key = INCIDENT_KEY_PREFIX + correlation_id
        raw = await self.redis.get(key)
        if raw is None:
            return IncidentContext(correlation_id=correlation_id)
        return IncidentContext.model_validate_json(raw)

    async def persist(self, ctx: IncidentContext) -> None:
        """Write the IncidentContext with a 10min TTL."""
        key = INCIDENT_KEY_PREFIX + ctx.correlation_id
        await self.redis.set(key, ctx.model_dump_json(), ex=INCIDENT_TTL)
