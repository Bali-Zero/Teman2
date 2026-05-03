"""
Redis-backed token revocation service (S03 Sprint 2).

Uses Redis SETEX for O(1) token revocation checks.
Fail-open policy: if Redis is unavailable, tokens are NOT rejected.
"""

import logging
from typing import Any

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class TokenRevocationService:
    """
    Token revocation via Redis.

    Per-token: SETEX revoked:{jti} <ttl> "reason"
    Per-user: SETEX revoked_user:{email} 86400 "reason"

    Fail-open: Redis down = tokens accepted (not rejected).
    """

    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client

    async def revoke_token(
        self, jti: str, ttl_seconds: int, reason: str = "manual",
    ) -> bool:
        if not self._redis:
            logger.warning("S03: Token revocation skipped — Redis unavailable")
            return False
        try:
            await self._redis.setex(f"revoked:{jti}", ttl_seconds, reason)
            logger.info(f"S03: Token revoked jti={jti} reason={reason} ttl={ttl_seconds}s")
            return True
        except (RedisError, OSError) as e:
            logger.warning("S03: Token revocation failed jti=%s: %s", jti, e)
            return False
        except Exception as e:
            logger.exception("S03: Unexpected error revoking token jti=%s", jti)
            return False

    async def is_revoked(self, jti: str) -> bool:
        if not self._redis:
            return False
        try:
            result = await self._redis.exists(f"revoked:{jti}")
            return bool(result)
        except (RedisError, OSError) as e:
            logger.warning("S03: Revocation check failed (fail-open): %s", e)
            return False
        except Exception as e:
            logger.exception("S03: Unexpected error checking revocation for jti=%s", jti)
            return False

    async def revoke_all_user_tokens(
        self, user_email: str, reason: str = "bulk_revoke",
    ) -> bool:
        if not self._redis:
            logger.warning("S03: User revocation skipped — Redis unavailable")
            return False
        try:
            await self._redis.setex(f"revoked_user:{user_email}", 86400, reason)
            logger.info(f"S03: All tokens revoked for {user_email} reason={reason}")
            return True
        except (RedisError, OSError) as e:
            logger.warning("S03: User revocation failed %s: %s", user_email, e)
            return False
        except Exception as e:
            logger.exception("S03: Unexpected error revoking tokens for %s", user_email)
            return False

    async def is_user_revoked(self, user_email: str) -> bool:
        if not self._redis:
            return False
        try:
            result = await self._redis.exists(f"revoked_user:{user_email}")
            return bool(result)
        except (RedisError, OSError) as e:
            logger.warning("S03: User revocation check failed (fail-open): %s", e)
            return False
        except Exception as e:
            logger.exception("S03: Unexpected error checking user revocation for %s", user_email)
            return False
