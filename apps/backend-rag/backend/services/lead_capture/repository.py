"""Repository for `lead_intents` rows.

One class, one connection/pool parameter per call (no hidden state),
returns dataclass instances. Matches the convention used in
`backend/services/compliance/alert_repository.py` etc.
"""

from __future__ import annotations

import json
import logging
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.services.lead_capture.source import LeadSource

logger = logging.getLogger(__name__)

_NANOID_ALPHABET = string.ascii_lowercase + string.digits
_INTENT_TTL = timedelta(days=7)


def _nanoid(length: int = 10) -> str:
    """URL-safe nanoid. 10 chars × 36-alphabet = ~52 bits of entropy."""
    return "".join(secrets.choice(_NANOID_ALPHABET) for _ in range(length))


def new_intent_id() -> str:
    """Format: li_<nanoid>. Total length 13 chars (fits VARCHAR(20))."""
    return f"li_{_nanoid(10)}"


@dataclass(frozen=True)
class LeadIntent:
    id: str
    source: LeadSource
    context: dict[str, Any]
    utm: dict[str, Any] | None
    fingerprint: str | None
    whatsapp_url: str
    matched_client_id: str | None
    matched_at: datetime | None
    created_at: datetime
    expires_at: datetime


class LeadIntentRepository:
    """Persistence for lead_intents. Expects asyncpg connection or pool."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def insert(
        self,
        *,
        source: LeadSource,
        context: dict[str, Any],
        whatsapp_url: str,
        utm: dict[str, Any] | None = None,
        fingerprint: str | None = None,
        ttl: timedelta = _INTENT_TTL,
        intent_id: str | None = None,
    ) -> LeadIntent:
        """Insert a new lead intent, returning the hydrated row.

        The caller is responsible for building `whatsapp_url` — the
        repository does not synthesize URLs because the hash lookup
        order (insert id first, then build URL, then update) would
        require two round-trips. Routers handle the two-step flow.
        """
        now = datetime.now(timezone.utc)
        expires = now + ttl
        intent_id = intent_id or new_intent_id()

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO lead_intents
                    (id, source, context, utm, fingerprint, whatsapp_url, created_at, expires_at)
                VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, $7, $8)
                """,
                intent_id,
                source.value,
                json.dumps(context),
                json.dumps(utm) if utm is not None else None,
                fingerprint,
                whatsapp_url,
                now,
                expires,
            )

        return LeadIntent(
            id=intent_id,
            source=source,
            context=context,
            utm=utm,
            fingerprint=fingerprint,
            whatsapp_url=whatsapp_url,
            matched_client_id=None,
            matched_at=None,
            created_at=now,
            expires_at=expires,
        )

    async def update_whatsapp_url(self, intent_id: str, url: str) -> None:
        """After the caller builds the final URL using the intent_id,
        backfill it. Needed when the URL payload references the id."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE lead_intents SET whatsapp_url = $1 WHERE id = $2",
                url,
                intent_id,
            )

    async def fetch_unmatched(self, since_minutes: int = 30) -> list[LeadIntent]:
        """Matcher cron hot path. Pulls recent intents with no match yet."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, source, context, utm, fingerprint, whatsapp_url,
                       matched_client_id, matched_at, created_at, expires_at
                FROM lead_intents
                WHERE matched_client_id IS NULL
                  AND created_at >= $1
                ORDER BY created_at DESC
                LIMIT 500
                """,
                cutoff,
            )
        return [self._row_to_intent(r) for r in rows]

    async def mark_matched(self, intent_id: str, client_id: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE lead_intents
                   SET matched_client_id = $1,
                       matched_at        = NOW()
                 WHERE id = $2
                   AND matched_client_id IS NULL
                """,
                client_id,
                intent_id,
            )

    async def purge_expired(self) -> int:
        """Hard-delete intents past their TTL that never matched.
        Returns count. Safe to run periodically."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM lead_intents
                 WHERE expires_at < NOW()
                   AND matched_client_id IS NULL
                """
            )
        # asyncpg returns "DELETE <count>".
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0

    @staticmethod
    def _row_to_intent(row: Any) -> LeadIntent:
        return LeadIntent(
            id=row["id"],
            source=LeadSource(row["source"]),
            context=row["context"] if isinstance(row["context"], dict) else json.loads(row["context"] or "{}"),
            utm=row["utm"] if isinstance(row["utm"], (dict, type(None))) else json.loads(row["utm"] or "null"),
            fingerprint=row["fingerprint"],
            whatsapp_url=row["whatsapp_url"],
            matched_client_id=row["matched_client_id"],
            matched_at=row["matched_at"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
        )
