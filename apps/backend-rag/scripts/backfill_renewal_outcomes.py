#!/usr/bin/env python3
"""Backfill renewal_alert_outcomes from historical practices state.

One-shot script run after migration 150 deploys. Infers outcome for every
existing row in renewal_alerts based on practices.status transitions and
interactions count. Writes observed_by='team_member' for all rows
(notes='backfill 2026-05').

Spec: docs/superpowers/specs/2026-05-01-post-agentic-injection-design.md §4 Sprint 0.3

Usage:
    DATABASE_URL=postgres://... python scripts/backfill_renewal_outcomes.py
    python scripts/backfill_renewal_outcomes.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

logger = logging.getLogger("backfill_renewal_outcomes")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

POST_TARGET_WINDOW_DAYS = 30  # Completion within target_date + 30d counts as "renewed by alert"


def infer_outcome(
    alert: dict[str, Any],
    practice: dict[str, Any],
    interactions_count: int,
) -> str:
    """Apply inference rules to determine outcome for a backfill row.

    Rules:
        - practice completed within [alert_date, target_date + 30d] → 'client_renewed'
        - any interactions exist on the practice → 'acted_by_team'
        - target_date in past, no completion, no interactions → 'expired_no_action'
        - else → 'client_ignored'
    """
    now = datetime.now(tz=timezone.utc)
    alert_date = alert["alert_date"]
    target_date = alert["target_date"]

    if isinstance(target_date, datetime):
        target_dt = (
            target_date if target_date.tzinfo else target_date.replace(tzinfo=timezone.utc)
        )
    else:
        target_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)

    if isinstance(alert_date, datetime):
        alert_dt = (
            alert_date if alert_date.tzinfo else alert_date.replace(tzinfo=timezone.utc)
        )
    else:
        alert_dt = datetime.combine(alert_date, datetime.min.time(), tzinfo=timezone.utc)

    completed_at = practice.get("completed_at")
    if completed_at:
        completed_dt = (
            completed_at if completed_at.tzinfo else completed_at.replace(tzinfo=timezone.utc)
        )
        window_end = target_dt + timedelta(days=POST_TARGET_WINDOW_DAYS)
        if alert_dt <= completed_dt <= window_end:
            return "client_renewed"

    if interactions_count > 0:
        return "acted_by_team"

    if target_dt < now:
        return "expired_no_action"

    return "client_ignored"


async def verify_schema(conn: asyncpg.Connection) -> None:
    """Defensive check: required columns must exist before backfill."""
    required = [
        ("practices", "completed_at"),
        ("practices", "status"),
        ("renewal_alerts", "id"),
        ("renewal_alerts", "alert_date"),
        ("renewal_alerts", "target_date"),
        ("renewal_alerts", "practice_id"),
        ("interactions", "practice_id"),
        ("renewal_alert_outcomes", "alert_id"),  # Migration 150 must be applied
    ]
    missing: list[str] = []
    for table, column in required:
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = $1 AND column_name = $2
            )
            """,
            table,
            column,
        )
        if not exists:
            missing.append(f"{table}.{column}")
    if missing:
        raise RuntimeError(
            f"Schema verification failed. Missing columns: {missing}. "
            "Migration 150 may not be applied. Aborting."
        )


async def backfill_all(
    conn: asyncpg.Connection,
    dry_run: bool = False,
) -> dict[str, int]:
    """Iterate all renewal_alerts, infer outcome, INSERT into renewal_alert_outcomes."""
    alerts = await conn.fetch(
        """
        SELECT
            ra.id,
            ra.alert_date,
            ra.target_date,
            ra.practice_id,
            p.status AS practice_status,
            p.completed_at,
            (SELECT COUNT(*) FROM interactions i WHERE i.practice_id = ra.practice_id) AS interactions_count
        FROM renewal_alerts ra
        LEFT JOIN practices p ON p.id = ra.practice_id
        WHERE NOT EXISTS (
            SELECT 1 FROM renewal_alert_outcomes rao WHERE rao.alert_id = ra.id
        )
        """,
    )

    counts: dict[str, int] = {
        "client_renewed": 0,
        "acted_by_team": 0,
        "client_ignored": 0,
        "expired_no_action": 0,
        "total": 0,
    }
    for a in alerts:
        practice = {
            "status": a["practice_status"],
            "completed_at": a["completed_at"],
        }
        outcome = infer_outcome(dict(a), practice, a["interactions_count"])
        counts[outcome] += 1
        counts["total"] += 1

        if dry_run:
            continue

        await conn.execute(
            """
            INSERT INTO renewal_alert_outcomes
                (alert_id, outcome, outcome_at, observed_by, notes)
            VALUES ($1, $2, NOW(), 'team_member', 'backfill 2026-05')
            """,
            a["id"],
            outcome,
        )

    return counts


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        return 1

    conn = await asyncpg.connect(db_url)
    try:
        await verify_schema(conn)
        counts = await backfill_all(conn, dry_run=args.dry_run)
        mode = "DRY-RUN" if args.dry_run else "WRITE"
        logger.info(
            f"[{mode}] backfilled {counts['total']} outcomes: "
            f"renewed={counts['client_renewed']}, acted={counts['acted_by_team']}, "
            f"ignored={counts['client_ignored']}, expired={counts['expired_no_action']}",
        )
        return 0
    except RuntimeError as exc:
        logger.error(str(exc))
        return 2
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
