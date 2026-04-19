"""CRUD for email_subscriptions — drip scheduler backend."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import string
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN_ALPHABET = string.ascii_letters + string.digits


def new_unsubscribe_token(length: int = 28) -> str:
    return "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(length))


def context_hash(payload: dict[str, Any]) -> str:
    """Stable hash for deduplication of the same (email, app, payload)."""
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


@dataclass(frozen=True)
class EmailSubscription:
    id: int
    email: str
    app: str
    context_hash: str
    trigger_type: str
    next_fire_at: datetime | None
    fired_count: int
    unsubscribed: bool
    unsubscribe_token: str
    payload: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class EmailSubscriptionRepository:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def upsert(
        self,
        *,
        email: str,
        app: str,
        trigger_type: str,
        payload: dict[str, Any],
        next_fire_at: datetime | None,
    ) -> EmailSubscription:
        """Insert or update (email, app, trigger_type) subscription.

        If the same (email, app, context_hash, trigger_type) already exists
        with unsubscribed=TRUE, we do NOT re-subscribe the user. That's the
        one-click opt-out contract.
        """
        ch = context_hash(payload)
        token = new_unsubscribe_token()

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO email_subscriptions
                    (email, app, context_hash, trigger_type,
                     next_fire_at, unsubscribe_token, payload)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                ON CONFLICT DO NOTHING
                RETURNING id, email, app, context_hash, trigger_type,
                          next_fire_at, fired_count, unsubscribed,
                          unsubscribe_token, payload,
                          created_at, updated_at
                """,
                email.lower().strip(),
                app,
                ch,
                trigger_type,
                next_fire_at,
                token,
                json.dumps(payload),
            )

        if row is None:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, email, app, context_hash, trigger_type,
                           next_fire_at, fired_count, unsubscribed,
                           unsubscribe_token, payload,
                           created_at, updated_at
                      FROM email_subscriptions
                     WHERE email = $1 AND app = $2 AND context_hash = $3 AND trigger_type = $4
                    """,
                    email.lower().strip(),
                    app,
                    ch,
                    trigger_type,
                )

        return self._row_to_sub(row)

    async def fetch_due(self, limit: int = 100) -> list[EmailSubscription]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, email, app, context_hash, trigger_type,
                       next_fire_at, fired_count, unsubscribed,
                       unsubscribe_token, payload,
                       created_at, updated_at
                  FROM email_subscriptions
                 WHERE unsubscribed = FALSE
                   AND next_fire_at IS NOT NULL
                   AND next_fire_at <= NOW()
                 ORDER BY next_fire_at ASC
                 LIMIT $1
                """,
                limit,
            )
        return [self._row_to_sub(r) for r in rows]

    async def mark_fired(
        self, subscription_id: int, *, next_fire_at: datetime | None
    ) -> None:
        """Increment fired_count; set next_fire_at (or NULL if last)."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE email_subscriptions
                   SET fired_count  = fired_count + 1,
                       next_fire_at = $1
                 WHERE id = $2
                """,
                next_fire_at,
                subscription_id,
            )

    async def unsubscribe_by_token(self, token: str) -> int:
        """One-click opt-out. Flips unsubscribed=TRUE for ALL rows sharing
        the same email+app as the token holder. Returns the count touched."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT email, app FROM email_subscriptions
                 WHERE unsubscribe_token = $1
                 LIMIT 1
                """,
                token,
            )
            if not row:
                return 0
            result = await conn.execute(
                """
                UPDATE email_subscriptions
                   SET unsubscribed = TRUE,
                       next_fire_at = NULL
                 WHERE email = $1 AND app = $2
                """,
                row["email"],
                row["app"],
            )
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0

    @staticmethod
    def _row_to_sub(row: Any) -> EmailSubscription:
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return EmailSubscription(
            id=row["id"],
            email=row["email"],
            app=row["app"],
            context_hash=row["context_hash"],
            trigger_type=row["trigger_type"],
            next_fire_at=row["next_fire_at"],
            fired_count=row["fired_count"],
            unsubscribed=row["unsubscribed"],
            unsubscribe_token=row["unsubscribe_token"],
            payload=payload,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
