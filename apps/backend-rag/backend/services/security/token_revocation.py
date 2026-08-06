"""
Redis-backed token revocation service (S03 Sprint 2).

Uses Redis SETEX for O(1) token revocation checks.
Authentication fails closed when the revocation store is unavailable.
"""

import logging
from collections.abc import Mapping
from typing import Any

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RevocationStoreUnavailable(RuntimeError):
    """Raised when session revocation cannot be checked or persisted safely."""


class TokenRevocationService:
    """
    Token revocation via Redis.

    Per-token: SETEX revoked:{jti} <ttl> "reason"
    Per-user: SETEX revoked_user:{email} 86400 "reason"

    Fail-closed: Redis down = authentication or revocation is denied.
    """

    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client

    async def revoke_token(
        self,
        jti: str,
        ttl_seconds: int,
        reason: str = "manual",
    ) -> bool:
        if not self._redis:
            raise RevocationStoreUnavailable("Token revocation store is unavailable")
        try:
            await self._redis.setex(f"revoked:{jti}", ttl_seconds, reason)
            logger.info("S03: Token revoked reason=%s ttl=%ss", reason, ttl_seconds)
            return True
        except (RedisError, OSError) as e:
            logger.error("S03: Token revocation store error: %s", type(e).__name__)
            raise RevocationStoreUnavailable("Token revocation store error") from e
        except Exception as e:
            logger.exception("S03: Unexpected token revocation store error")
            raise RevocationStoreUnavailable("Token revocation store error") from e

    async def is_revoked(self, jti: str) -> bool:
        if not self._redis:
            raise RevocationStoreUnavailable("Token revocation store is unavailable")
        try:
            result = await self._redis.exists(f"revoked:{jti}")
            return bool(result)
        except (RedisError, OSError) as e:
            logger.error("S03: Revocation check store error: %s", type(e).__name__)
            raise RevocationStoreUnavailable("Token revocation store error") from e
        except Exception as e:
            logger.exception("S03: Unexpected revocation check store error")
            raise RevocationStoreUnavailable("Token revocation store error") from e

    async def revoke_all_user_tokens(
        self,
        user_email: str,
        reason: str = "bulk_revoke",
    ) -> bool:
        if not self._redis:
            raise RevocationStoreUnavailable("Token revocation store is unavailable")
        try:
            normalized_email = user_email.lower()
            await self._redis.setex(f"revoked_user:{normalized_email}", 86400, reason)
            logger.info("S03: All user tokens revoked reason=%s", reason)
            return True
        except (RedisError, OSError) as e:
            logger.error("S03: User revocation store error: %s", type(e).__name__)
            raise RevocationStoreUnavailable("Token revocation store error") from e
        except Exception as e:
            logger.exception("S03: Unexpected user revocation store error")
            raise RevocationStoreUnavailable("Token revocation store error") from e

    async def is_user_revoked(self, user_email: str) -> bool:
        if not self._redis:
            raise RevocationStoreUnavailable("Token revocation store is unavailable")
        try:
            result = await self._redis.exists(f"revoked_user:{user_email.lower()}")
            return bool(result)
        except (RedisError, OSError) as e:
            logger.error("S03: User revocation check store error: %s", type(e).__name__)
            raise RevocationStoreUnavailable("Token revocation store error") from e
        except Exception as e:
            logger.exception("S03: Unexpected user revocation check store error")
            raise RevocationStoreUnavailable("Token revocation store error") from e


async def is_session_revoked(payload: Mapping[str, Any]) -> bool:
    """Check token- and user-level revocation using the shared async Redis client."""
    from backend.core.redis_manager import RedisManager

    redis_client = RedisManager.get_instance().get_async_client()
    service = TokenRevocationService(redis_client=redis_client)
    jti = str(payload.get("jti") or "")
    user_email = str(payload.get("email") or payload.get("sub") or "").lower()

    if jti and await service.is_revoked(jti):
        return True
    return bool(user_email and await service.is_user_revoked(user_email))


def is_session_revoked_sync(payload: Mapping[str, Any]) -> bool:
    """Check token- and user-level revocation using the shared sync Redis client."""
    from backend.core.redis_manager import RedisManager

    redis_client = RedisManager.get_instance().get_sync_client()
    if not redis_client:
        raise RevocationStoreUnavailable("Token revocation store is unavailable")

    jti = str(payload.get("jti") or "")
    user_email = str(payload.get("email") or payload.get("sub") or "").lower()
    try:
        if jti and redis_client.exists(f"revoked:{jti}"):
            return True
        return bool(user_email and redis_client.exists(f"revoked_user:{user_email}"))
    except (RedisError, OSError) as e:
        logger.error("S03: Sync revocation check store error: %s", type(e).__name__)
        raise RevocationStoreUnavailable("Token revocation store error") from e
    except Exception as e:
        logger.exception("S03: Unexpected sync revocation check store error")
        raise RevocationStoreUnavailable("Token revocation store error") from e
