"""ObligationsRepository: asyncpg access to client_obligations (m309).

Proposals come from obligations_register.propose(). A reviewer moves a row proposed ->
approved | rejected exactly once; approved -> alerted -> done belongs to the bridge into
compliance_alerts (PR A2), not to this class.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime

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
    """CRUD for client_obligations."""

    async def upsert_proposals(
        self, client_id: int, proposals: Sequence[ProposedObligation]
    ) -> int:
        """Insert new proposals; existing (client, rule, period) rows are left untouched.

        ON CONFLICT DO NOTHING is the point: a row a reviewer already approved or rejected is
        never reset to proposed by a later run. Returns the number of rows inserted.
        """
        if not proposals:
            return 0
        records = await self.fetch_safe(
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
        records = await self.fetch_safe(
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

    async def get(self, obligation_id: int) -> ObligationRow | None:
        record = await self.fetchrow_safe(
            "SELECT * FROM client_obligations WHERE id = $1", obligation_id
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
        record = await self.fetchrow_safe(
            _REVIEW_SQL, obligation_id, status, reviewer_email.strip().lower(), note
        )
        return _to_row(record) if record else None


__all__ = ["MAX_PAGE", "STATUSES", "ObligationRow", "ObligationsRepository"]
