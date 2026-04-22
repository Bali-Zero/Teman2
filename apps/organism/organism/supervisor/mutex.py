"""Distributed mutex via Redis SET NX EX with opaque lock_id.

Prevents two actuators from running concurrently on the same target.
Release is owner-checked (classic Redlock-lite: only lock owner can
release, preventing late delete races).
"""
import secrets


MUTEX_KEY_PREFIX = "organism:mutex:"

# Lua script for atomic compare-and-delete. Ensures only the lock owner
# can release, preventing race where a stale release kills a new lock.
_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class Mutex:
    def __init__(self, *, redis):
        self.redis = redis

    async def acquire(self, target: str, *, ttl_seconds: int = 300) -> str | None:
        """Try to acquire lock for target. Returns opaque lock_id or None."""
        lock_id = secrets.token_urlsafe(16)
        key = MUTEX_KEY_PREFIX + target
        # SET NX EX — atomic "set if not exists, with TTL"
        acquired = await self.redis.set(key, lock_id, nx=True, ex=ttl_seconds)
        return lock_id if acquired else None

    async def release(self, target: str, lock_id: str) -> bool:
        """Release only if caller owns the lock. Returns True if released."""
        key = MUTEX_KEY_PREFIX + target
        try:
            result = await self.redis.eval(_RELEASE_LUA, 1, key, lock_id)
            return int(result) == 1
        except Exception:
            # Fallback (should not happen in prod — fakeredis supports eval)
            current = await self.redis.get(key)
            if current is None:
                return False
            # Normalize to str for compare
            if isinstance(current, bytes):
                current = current.decode("utf-8")
            if current == lock_id:
                await self.redis.delete(key)
                return True
            return False
