"""
AlertRepository — asyncpg CRUD on compliance_alerts (m114).

Built on BaseRepository (db/base_repository.py) for pool management.
Also exposes `with_connection(conn)` for transaction-scoped use in tests.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import asyncpg

from backend.db.base_repository import BaseRepository


@dataclass
class AlertRow:
    """In-code mirror of compliance_alerts row."""
    alert_id: str
    client_id: int
    category: str
    severity: str
    status: str
    deadline: date
    days_until: int
    compliance_item_ref: str | None
    dedup_key: str
    message_it: str | None
    message_en: str | None
    message_id: str | None
    suggested_action: str | None
    estimated_cost_idr: int | None
    evidence_refs: list[dict]
    nb2_ref: str | None
    upgrade_count: int = 0
    created_at: datetime | None = None
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None


def _row_to_alert(record: asyncpg.Record) -> AlertRow:
    d = dict(record)
    evidence = d.get("evidence_refs")
    if isinstance(evidence, str):
        evidence = json.loads(evidence)
    return AlertRow(
        alert_id=d["alert_id"],
        client_id=d["client_id"],
        category=d["category"],
        severity=d["severity"],
        status=d["status"],
        deadline=d["deadline"],
        days_until=d["days_until"],
        compliance_item_ref=d.get("compliance_item_ref"),
        dedup_key=d["dedup_key"],
        message_it=d.get("message_it"),
        message_en=d.get("message_en"),
        message_id=d.get("message_id"),
        suggested_action=d.get("suggested_action"),
        estimated_cost_idr=d.get("estimated_cost_idr"),
        evidence_refs=evidence or [],
        nb2_ref=d.get("nb2_ref"),
        upgrade_count=d.get("upgrade_count", 0),
        created_at=d.get("created_at"),
        sent_at=d.get("sent_at"),
        acknowledged_at=d.get("acknowledged_at"),
        resolved_at=d.get("resolved_at"),
    )


class AlertRepository(BaseRepository):
    """CRUD for compliance_alerts."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        super().__init__(db_pool)
        self._conn: asyncpg.Connection | None = None

    @classmethod
    def with_connection(cls, conn: asyncpg.Connection) -> "AlertRepository":
        """Bind the repo to a single pre-acquired connection (tests)."""
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

    async def insert(self, row: AlertRow) -> AlertRow:
        record = await self._exec(
            "fetchrow",
            """
            INSERT INTO compliance_alerts (
              alert_id, client_id, category, severity, status,
              deadline, days_until, compliance_item_ref, dedup_key,
              message_it, message_en, message_id,
              suggested_action, estimated_cost_idr, evidence_refs, nb2_ref
            ) VALUES (
              $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb,$16
            ) RETURNING *
            """,
            row.alert_id, row.client_id, row.category, row.severity, row.status,
            row.deadline, row.days_until, row.compliance_item_ref, row.dedup_key,
            row.message_it, row.message_en, row.message_id,
            row.suggested_action, row.estimated_cost_idr,
            json.dumps(row.evidence_refs or []), row.nb2_ref,
        )
        return _row_to_alert(record)

    async def find_active_by_dedup_key(self, dedup_key: str) -> AlertRow | None:
        record = await self._exec(
            "fetchrow",
            """
            SELECT * FROM compliance_alerts
            WHERE dedup_key = $1
              AND status IN ('pending','sent','acknowledged')
            LIMIT 1
            """,
            dedup_key,
        )
        return _row_to_alert(record) if record else None

    async def get(self, alert_id: str) -> AlertRow | None:
        record = await self._exec(
            "fetchrow",
            "SELECT * FROM compliance_alerts WHERE alert_id = $1",
            alert_id,
        )
        return _row_to_alert(record) if record else None

    async def promote(
        self, alert_id: str, *, new_severity: str, new_days_until: int,
    ) -> AlertRow:
        record = await self._exec(
            "fetchrow",
            """
            UPDATE compliance_alerts
               SET severity = $2,
                   days_until = $3,
                   upgrade_count = upgrade_count + 1
             WHERE alert_id = $1
            RETURNING *
            """,
            alert_id, new_severity, new_days_until,
        )
        if record is None:
            raise LookupError(f"alert_id {alert_id} not found")
        return _row_to_alert(record)

    async def update_status(self, alert_id: str, *, new_status: str) -> AlertRow:
        timestamp_column = {
            "sent": "sent_at",
            "acknowledged": "acknowledged_at",
            "resolved": "resolved_at",
        }.get(new_status)

        if timestamp_column:
            query = f"""
                UPDATE compliance_alerts
                   SET status = $2, {timestamp_column} = NOW()
                 WHERE alert_id = $1
                RETURNING *
            """
        else:
            query = """
                UPDATE compliance_alerts
                   SET status = $2
                 WHERE alert_id = $1
                RETURNING *
            """
        record = await self._exec("fetchrow", query, alert_id, new_status)
        if record is None:
            raise LookupError(f"alert_id {alert_id} not found")
        return _row_to_alert(record)

    async def list_by_client(
        self, client_id: int, *, limit: int = 50, offset: int = 0,
    ) -> list[AlertRow]:
        records = await self._exec(
            "fetch",
            """
            SELECT * FROM compliance_alerts
             WHERE client_id = $1
             ORDER BY created_at DESC
             LIMIT $2 OFFSET $3
            """,
            client_id, limit, offset,
        )
        return [_row_to_alert(r) for r in records]


__all__ = ["AlertRepository", "AlertRow"]
