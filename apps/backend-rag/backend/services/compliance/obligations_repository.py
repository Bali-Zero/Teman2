"""ObligationsRepository: asyncpg access to client_obligations (m309).

Proposals come from obligations_register.propose(). A reviewer moves a row proposed ->
approved | rejected exactly once; approved -> alerted -> done belongs to the bridge into
compliance_alerts (PR A2), not to this class.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime
from typing import Any

import asyncpg

from backend.db.base_repository import BaseRepository
from backend.services.compliance.obligations_register import ProposedObligation

STATUSES = frozenset({"proposed", "approved", "rejected", "alerted", "done"})
REVIEW_OUTCOMES = frozenset({"approved", "rejected"})
MAX_PAGE = 200

_UPSERT_SQL = """
INSERT INTO client_obligations (client_id, rule_id, period_key, due_date, needs_review_reason)
SELECT $1, p.rule_id, p.period_key, p.due_date, p.needs_review_reason
  FROM unnest($2::text[], $3::text[], $4::date[], $5::text[])
       AS p(rule_id, period_key, due_date, needs_review_reason)
ON CONFLICT (client_id, rule_id, period_key) DO NOTHING
RETURNING id
"""

_REVIEW_SQL = """
UPDATE client_obligations
   SET status = $2, reviewer_email = $3, review_note = $4,
       reviewed_at = NOW(), updated_at = NOW()
 WHERE id = $1 AND status = 'proposed'
RETURNING *
"""

_MARK_ALERTED_SQL = """
UPDATE client_obligations
   SET status = 'alerted', alert_id = $2, updated_at = NOW()
 WHERE id = $1 AND status = 'approved'
RETURNING *
"""

_LIST_FILTERED_SQL = """
SELECT * FROM client_obligations
 WHERE ($1::integer IS NULL OR client_id = $1)
   AND ($2::text IS NULL OR status = $2)
 ORDER BY due_date, id
 LIMIT $3 OFFSET $4
"""

_COUNT_FILTERED_SQL = """
SELECT COUNT(*) FROM client_obligations
 WHERE ($1::integer IS NULL OR client_id = $1)
   AND ($2::text IS NULL OR status = $2)
"""


@dataclass
class ObligationRow:
    """In-code mirror of a client_obligations row."""

    id: int
    client_id: int
    rule_id: str
    period_key: str
    due_date: date
    status: str
    needs_review_reason: str | None
    reviewer_email: str | None
    reviewed_at: datetime | None
    review_note: str | None
    alert_id: str | None
    created_at: datetime | None
    updated_at: datetime | None


_COLUMNS = tuple(f.name for f in fields(ObligationRow))


def _to_row(record: asyncpg.Record) -> ObligationRow:
    return ObligationRow(**{name: record[name] for name in _COLUMNS})


class ObligationsRepository(BaseRepository):
    """CRUD for client_obligations.

    Supports two modes, mirroring ``alert_repository.AlertRepository``: pool mode
    (``ObligationsRepository(pool)``, each call acquires its own connection) and
    connection mode (``ObligationsRepository.with_connection(conn)``), which binds
    every call to a single pre-acquired connection so the obligation transition and
    the bridge into ``compliance_alerts`` (PR A2's ``approve``) commit or roll back
    together in one transaction.
    """

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        super().__init__(db_pool)
        self._conn: asyncpg.Connection | None = None

    @classmethod
    def with_connection(cls, conn: asyncpg.Connection) -> ObligationsRepository:
        """Bind the repo to a single pre-acquired connection (transactional use)."""
        inst = cls.__new__(cls)
        inst.db_pool = None  # type: ignore[assignment]
        inst.logger = logging.getLogger(cls.__qualname__)
        inst._conn = conn
        return inst

    async def _exec(self, fn_name: str, query: str, *args: Any) -> Any:
        if self._conn is not None:
            return await getattr(self._conn, fn_name)(query, *args)
        async with self.db_pool.acquire() as conn:
            return await getattr(conn, fn_name)(query, *args)

    async def upsert_proposals(
        self, client_id: int, proposals: Sequence[ProposedObligation]
    ) -> int:
        """Insert new proposals; existing (client, rule, period) rows are left untouched.

        ON CONFLICT DO NOTHING is the point: a row a reviewer already approved or rejected is
        never reset to proposed by a later run. Returns the number of rows inserted.
        """
        if not proposals:
            return 0
        records = await self._exec(
            "fetch",
            _UPSERT_SQL,
            client_id,
            [p.rule_id for p in proposals],
            [p.period_key for p in proposals],
            [p.due_date for p in proposals],
            [p.needs_review_reason for p in proposals],
        )
        return len(records)

    async def list_by_status(
        self, status: str | None = "proposed", limit: int = 50, offset: int = 0
    ) -> list[ObligationRow]:
        """Rows with the given status (None = all), earliest due date first."""
        if status is not None and status not in STATUSES:
            raise ValueError(f"unknown status {status!r}")
        records = await self._exec(
            "fetch",
            """
            SELECT * FROM client_obligations
             WHERE ($1::text IS NULL OR status = $1::text)
             ORDER BY due_date, id
             LIMIT $2 OFFSET $3
            """,
            status,
            max(1, min(limit, MAX_PAGE)),
            max(0, offset),
        )
        return [_to_row(r) for r in records]

    async def list_filtered(
        self,
        *,
        client_id: int | None = None,
        status: str | None = "proposed",
        limit: int = 50,
        offset: int = 0,
    ) -> list[ObligationRow]:
        """Rows filtered by client_id and/or status (either None = no filter on it)."""
        if status is not None and status not in STATUSES:
            raise ValueError(f"unknown status {status!r}")
        records = await self._exec(
            "fetch",
            _LIST_FILTERED_SQL,
            client_id,
            status,
            max(1, min(limit, MAX_PAGE)),
            max(0, offset),
        )
        return [_to_row(r) for r in records]

    async def count_filtered(
        self, *, client_id: int | None = None, status: str | None = "proposed"
    ) -> int:
        """Total rows matching the same filters as ``list_filtered`` (for pagination)."""
        if status is not None and status not in STATUSES:
            raise ValueError(f"unknown status {status!r}")
        value = await self._exec("fetchval", _COUNT_FILTERED_SQL, client_id, status)
        return int(value or 0)

    async def get(self, obligation_id: int) -> ObligationRow | None:
        record = await self._exec(
            "fetchrow", "SELECT * FROM client_obligations WHERE id = $1", obligation_id
        )
        return _to_row(record) if record else None

    async def set_status(
        self, obligation_id: int, status: str, reviewer_email: str, note: str | None = None
    ) -> ObligationRow | None:
        """Review a proposal: proposed -> approved | rejected, once.

        Returns None when the row does not exist or is no longer proposed (the caller tells
        404 from 409 with get()).
        """
        if status not in REVIEW_OUTCOMES:
            raise ValueError(f"review outcome must be approved or rejected, got {status!r}")
        if not reviewer_email or not reviewer_email.strip():
            raise ValueError("reviewer_email is required")
        record = await self._exec(
            "fetchrow", _REVIEW_SQL, obligation_id, status, reviewer_email.strip().lower(), note
        )
        return _to_row(record) if record else None

    async def mark_alerted(self, obligation_id: int, alert_id: str) -> ObligationRow | None:
        """Bridge step of ``approve``: approved -> alerted, stamping the compliance_alerts id.

        Returns None when the row does not exist or is no longer ``approved`` — the caller
        (running inside the same transaction as the ``compliance_alerts`` insert) should treat
        that as a reason to roll back rather than leave an orphaned alert.
        """
        if not alert_id or not alert_id.strip():
            raise ValueError("alert_id is required")
        record = await self._exec("fetchrow", _MARK_ALERTED_SQL, obligation_id, alert_id)
        return _to_row(record) if record else None


__all__ = ["MAX_PAGE", "STATUSES", "ObligationRow", "ObligationsRepository"]
