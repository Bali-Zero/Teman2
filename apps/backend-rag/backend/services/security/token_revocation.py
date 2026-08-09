"""
Redis-backed token revocation service (S03 Sprint 2).

Uses Redis SETEX for O(1) token revocation checks.
Authentication fails closed when the revocation store is unavailable.
"""

import logging
import math
import time
from collections.abc import Mapping
from typing import Any

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

USER_REVOCATION_TTL_SECONDS = 86400


class RevocationStoreUnavailable(RuntimeError):
    """Raised when session revocation cannot be checked or persisted safely."""


def is_token_revocation_enabled() -> bool:
    """Return the runtime revocation policy without caching environment state."""
    from backend.app.core.config import settings

    return bool(settings.enable_token_revocation)


class TokenRevocationService:
    """
    Token revocation via Redis.

    Per-token: SETEX revoked:{jti} <ttl> "reason"
    Per-user: SETEX revoked_user:{email} 86400 "<revoked_at_epoch>"

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
            revoked_at = time.time()
            await self._redis.setex(
                f"revoked_user:{normalized_email}",
                USER_REVOCATION_TTL_SECONDS,
                str(revoked_at),
            )
            logger.info("S03: All user tokens revoked reason=%s", reason)
            return True
        except (RedisError, OSError) as e:
            logger.error("S03: User revocation store error: %s", type(e).__name__)
            raise RevocationStoreUnavailable("Token revocation store error") from e
        except Exception as e:
            logger.exception("S03: Unexpected user revocation store error")
            raise RevocationStoreUnavailable("Token revocation store error") from e

    async def is_user_revoked(self, user_email: str, token_issued_at: Any) -> bool:
        if not self._redis:
            raise RevocationStoreUnavailable("Token revocation store is unavailable")
        try:
            revoked_at = await self._redis.get(f"revoked_user:{user_email.lower()}")
            return _is_issued_at_revoked(token_issued_at, revoked_at)
        except (RedisError, OSError) as e:
            logger.error("S03: User revocation check store error: %s", type(e).__name__)
            raise RevocationStoreUnavailable("Token revocation store error") from e
        except Exception as e:
            logger.exception("S03: Unexpected user revocation check store error")
            raise RevocationStoreUnavailable("Token revocation store error") from e


def _is_issued_at_revoked(token_issued_at: Any, revoked_at: Any) -> bool:
    """Return whether a token predates a user-level revocation marker.

    A missing marker means that no bulk revocation is active. Once a marker
    exists, malformed marker data or a missing/malformed ``iat`` fails closed:
    accepting an unverifiable token would defeat the revoke-all guarantee.
    """
    if revoked_at is None:
        return False

    try:
        if isinstance(revoked_at, bytes):
            revoked_at = revoked_at.decode("ascii")
        if isinstance(token_issued_at, bool) or isinstance(revoked_at, bool):
            raise ValueError("boolean timestamps are invalid")

        issued_at_value = float(token_issued_at)
        revoked_at_value = float(revoked_at)
        if (
            not math.isfinite(issued_at_value)
            or not math.isfinite(revoked_at_value)
            or issued_at_value <= 0
            or revoked_at_value <= 0
        ):
            raise ValueError("timestamps must be finite positive numbers")
    except (TypeError, ValueError, UnicodeDecodeError):
        logger.error("S03: Invalid user revocation timestamp state; denying session")
        return True

    return issued_at_value <= revoked_at_value


async def is_session_revoked(payload: Mapping[str, Any]) -> bool:
    """Check token- and user-level revocation using the shared async Redis client."""
    if not is_token_revocation_enabled():
        return False

    from backend.core.redis_manager import RedisManager

    redis_client = RedisManager.get_instance().get_async_client()
    service = TokenRevocationService(redis_client=redis_client)
    jti = str(payload.get("jti") or "")
    user_email = str(payload.get("email") or payload.get("sub") or "").lower()
    token_issued_at = payload.get("iat")

    if jti and await service.is_revoked(jti):
        return True
    return bool(
        user_email and await service.is_user_revoked(user_email, token_issued_at)
    )


def is_session_revoked_sync(payload: Mapping[str, Any]) -> bool:
    """Check token- and user-level revocation using the shared sync Redis client."""
    if not is_token_revocation_enabled():
        return False

    from backend.core.redis_manager import RedisManager

    redis_client = RedisManager.get_instance().get_sync_client()
    if not redis_client:
        raise RevocationStoreUnavailable("Token revocation store is unavailable")

    jti = str(payload.get("jti") or "")
    user_email = str(payload.get("email") or payload.get("sub") or "").lower()
    token_issued_at = payload.get("iat")
    try:
        if jti and redis_client.exists(f"revoked:{jti}"):
            return True
        revoked_at = redis_client.get(f"revoked_user:{user_email}") if user_email else None
        return bool(user_email and _is_issued_at_revoked(token_issued_at, revoked_at))
    except (RedisError, OSError) as e:
        logger.error("S03: Sync revocation check store error: %s", type(e).__name__)
        raise RevocationStoreUnavailable("Token revocation store error") from e
    except Exception as e:
        logger.exception("S03: Unexpected sync revocation check store error")
        raise RevocationStoreUnavailable("Token revocation store error") from e
