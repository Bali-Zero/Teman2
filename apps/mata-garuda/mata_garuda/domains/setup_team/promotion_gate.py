"""Promotion gate — INTEL→AUTHORITY with timeboxed SLA (Task 6).

Spec rationale (Wave 2 review):
  Trust tier promotion needs SLA timeboxed. Without that the queue silently
  rotted: 30+ days old promotion candidates pile up because nobody clicked
  approve.

Algorithm:
  - Feeder ingests INTEL source (Regulation with tier <= 2).
  - Caller proposes promotion → row in `promotion_queue` with
    sla_deadline = now + SLA_DAYS (default 14).
  - Daily cron calls check_sla_and_alert() → returns Alerts:
      * SLA-3 days: pre-warn alert (still pending)
      * SLA reached: tier 1 → auto-approve, tier 2 → escalate (manual)
  - All decision transitions are logged with `decided_at`.

SQLite schema:

  CREATE TABLE IF NOT EXISTS promotion_queue (
      queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
      intel_source_id TEXT NOT NULL,
      target_authority_nb TEXT NOT NULL,
      proposed_at TEXT NOT NULL,
      sla_deadline TEXT NOT NULL,
      owner TEXT NOT NULL,
      decision TEXT NOT NULL DEFAULT 'pending',
      decided_at TEXT,
      tier INTEGER NOT NULL DEFAULT 2,
      UNIQUE(intel_source_id, target_authority_nb)
  );

`tier` is denormalised onto the queue row so we don't need to re-look-up the
Regulation by intel_source_id when running auto-approve. Default 2 (escalate)
which is the safe choice if the caller doesn't pass it.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from mata_garuda.domains.setup_team.types import PromotionDecision

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "setup_team.sqlite"
)
DEFAULT_SLA_DAYS = 14
ALERT_THRESHOLD_DAYS = 3  # warn N days before SLA

PROMOTION_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS promotion_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    intel_source_id TEXT NOT NULL,
    target_authority_nb TEXT NOT NULL,
    proposed_at TEXT NOT NULL,
    sla_deadline TEXT NOT NULL,
    owner TEXT NOT NULL,
    decision TEXT NOT NULL DEFAULT 'pending',
    decided_at TEXT,
    tier INTEGER NOT NULL DEFAULT 2,
    UNIQUE(intel_source_id, target_authority_nb)
);

CREATE INDEX IF NOT EXISTS idx_promotion_decision
    ON promotion_queue(decision);
CREATE INDEX IF NOT EXISTS idx_promotion_sla
    ON promotion_queue(sla_deadline);
"""


@dataclass(frozen=True)
class Alert:
    """One alert emitted by check_sla_and_alert()."""

    queue_id: int
    intel_source_id: str
    target_authority_nb: str
    owner: str
    kind: str  # "sla_warning" | "sla_reached_tier1_auto_approve" | "sla_reached_tier2_escalate"
    sla_deadline: datetime
    days_remaining: int  # negative if SLA passed
    tier: int


def _open_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(PROMOTION_SCHEMA_DDL)
    conn.commit()
    return conn


def _now(now: Optional[datetime] = None) -> datetime:
    if now is not None:
        return now
    return datetime.now(timezone.utc)


def propose_promotion(
    intel_source_id: str,
    target_authority_nb: str,
    owner: str,
    *,
    tier: int = 2,
    sla_days: int = DEFAULT_SLA_DAYS,
    db_path: Path | str | None = None,
    now: Optional[datetime] = None,
) -> int:
    """Insert a promotion proposal into the queue. Returns queue_id.

    If a row with the same (intel_source_id, target_authority_nb) already
    exists, returns the existing queue_id without modifying the row (so a
    re-proposal doesn't reset the SLA clock).
    """
    when = _now(now)
    sla_deadline = when + timedelta(days=sla_days)
    conn = _open_db(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO promotion_queue (
                intel_source_id, target_authority_nb, proposed_at,
                sla_deadline, owner, decision, tier
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                intel_source_id,
                target_authority_nb,
                when.isoformat(),
                sla_deadline.isoformat(),
                owner,
                int(tier),
            ),
        )
        conn.commit()
        if cursor.lastrowid:
            return int(cursor.lastrowid)
        # Conflict — return existing queue_id.
        row = cursor.execute(
            """SELECT queue_id FROM promotion_queue
               WHERE intel_source_id=? AND target_authority_nb=?""",
            (intel_source_id, target_authority_nb),
        ).fetchone()
        return int(row["queue_id"]) if row else -1
    finally:
        conn.close()


def _row_to_alert(row, kind: str, now: datetime) -> Alert:
    sla = datetime.fromisoformat(row["sla_deadline"])
    days_remaining = (sla - now).days
    return Alert(
        queue_id=int(row["queue_id"]),
        intel_source_id=row["intel_source_id"],
        target_authority_nb=row["target_authority_nb"],
        owner=row["owner"],
        kind=kind,
        sla_deadline=sla,
        days_remaining=days_remaining,
        tier=int(row["tier"]),
    )


def check_sla_and_alert(
    *,
    db_path: Path | str | None = None,
    now: Optional[datetime] = None,
    threshold_days: int = ALERT_THRESHOLD_DAYS,
) -> list[Alert]:
    """Scan pending entries; return a list of Alerts.

    Three classes of alert:
      - sla_warning: pending, SLA - threshold_days <= now < SLA
      - sla_reached_tier1_auto_approve: SLA passed AND tier == 1
        (ATTENTION: this only EMITS the alert. Caller must invoke
        auto_approve_tier1_after_sla() to actually flip the row.)
      - sla_reached_tier2_escalate: SLA passed AND tier >= 2

    Does NOT mutate the queue itself — pure observation.
    """
    when = _now(now)
    warn_cutoff = when + timedelta(days=threshold_days)
    conn = _open_db(db_path)
    try:
        rows = conn.execute(
            """SELECT * FROM promotion_queue WHERE decision='pending'
               ORDER BY sla_deadline ASC"""
        ).fetchall()
    finally:
        conn.close()

    alerts: list[Alert] = []
    for row in rows:
        sla = datetime.fromisoformat(row["sla_deadline"])
        if sla <= when:
            # SLA passed.
            kind = (
                "sla_reached_tier1_auto_approve"
                if int(row["tier"]) == 1
                else "sla_reached_tier2_escalate"
            )
            alerts.append(_row_to_alert(row, kind, when))
        elif sla <= warn_cutoff:
            alerts.append(_row_to_alert(row, "sla_warning", when))
    return alerts


def auto_approve_tier1_after_sla(
    *,
    db_path: Path | str | None = None,
    now: Optional[datetime] = None,
) -> int:
    """Auto-approve every pending tier-1 row whose SLA has passed.

    Returns count of rows transitioned from pending → approved. Tier 2 rows
    that have passed SLA stay pending (escalation is handled by alerts;
    human owner must manually approve/reject).
    """
    when = _now(now)
    conn = _open_db(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE promotion_queue
               SET decision='approved', decided_at=?
               WHERE decision='pending' AND tier=1 AND sla_deadline<=?""",
            (when.isoformat(), when.isoformat()),
        )
        conn.commit()
        return int(cursor.rowcount or 0)
    finally:
        conn.close()


def manual_decide(
    queue_id: int,
    decision: PromotionDecision,
    *,
    db_path: Path | str | None = None,
    now: Optional[datetime] = None,
) -> bool:
    """Owner-driven manual transition. Returns True if updated, False if no-op.

    Permitted decisions: 'approved', 'rejected', 'escalated'. Reverting
    to 'pending' is not supported (would reset the SLA clock).
    """
    if decision not in ("approved", "rejected", "escalated"):
        raise ValueError(f"invalid manual decision: {decision!r}")
    when = _now(now)
    conn = _open_db(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE promotion_queue
               SET decision=?, decided_at=?
               WHERE queue_id=? AND decision='pending'""",
            (decision, when.isoformat(), queue_id),
        )
        conn.commit()
        return bool(cursor.rowcount)
    finally:
        conn.close()


__all__ = [
    "ALERT_THRESHOLD_DAYS",
    "Alert",
    "DEFAULT_SLA_DAYS",
    "PROMOTION_SCHEMA_DDL",
    "auto_approve_tier1_after_sla",
    "check_sla_and_alert",
    "manual_decide",
    "propose_promotion",
]
