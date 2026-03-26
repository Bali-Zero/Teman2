"""LegalInstrumentsService — CRUD for the legal_instruments table.

Provides read/write access to T0/T1 normative instrument metadata,
used by the Verified Generation Pipeline to track NLM upload status
and retrieve conflict resolution notes.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LegalInstrumentsService:
    """Async service for legal_instruments table operations."""

    def __init__(self, db_pool: Any) -> None:
        self._pool = db_pool

    async def get_active_instruments_for_domain(self, domain: str) -> list[dict[str, Any]]:
        """Return active and partially_superseded instruments for a domain.

        Ordered by tier ASC (T0 first), year DESC (newest first).
        """
        sql = """
            SELECT
                instrument_id, instrument_type, tier, domain, title,
                number, year, status, vigore_date, revoked_by,
                conflict_note, source_url, source_file, nb_uploaded, nb_uploaded_at
            FROM legal_instruments
            WHERE domain = $1
              AND status IN ('active', 'partially_superseded')
            ORDER BY tier ASC, year DESC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, domain)
        return [dict(r) for r in rows]

    async def mark_uploaded_to_nb(self, instrument_id: str) -> None:
        """Set nb_uploaded=TRUE and nb_uploaded_at=NOW() for an instrument."""
        sql = """
            UPDATE legal_instruments
            SET nb_uploaded = TRUE, nb_uploaded_at = NOW()
            WHERE instrument_id = $1
        """
        async with self._pool.acquire() as conn:
            await conn.execute(sql, instrument_id)
        logger.info("Marked %s as uploaded to NLM primary notebook", instrument_id)

    async def get_conflict_notes_for_domain(self, domain: str) -> list[dict[str, Any]]:
        """Return instruments with non-null conflict notes for a domain."""
        sql = """
            SELECT instrument_id, conflict_note, revoked_by, status
            FROM legal_instruments
            WHERE domain = $1
              AND conflict_note IS NOT NULL
            ORDER BY year DESC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, domain)
        return [dict(r) for r in rows]

    async def get_not_yet_uploaded(self, domain: str) -> list[dict[str, Any]]:
        """Return active instruments not yet uploaded to NLM primary notebook."""
        sql = """
            SELECT instrument_id, instrument_type, title, source_file, source_url
            FROM legal_instruments
            WHERE domain = $1
              AND status IN ('active', 'partially_superseded')
              AND nb_uploaded = FALSE
            ORDER BY tier ASC, year DESC
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, domain)
        return [dict(r) for r in rows]
