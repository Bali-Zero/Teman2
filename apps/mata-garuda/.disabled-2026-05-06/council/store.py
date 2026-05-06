"""
Consiglio v1 — SQLite store.

Follows the exact pattern from runtime/knowledge.py:
- SQLite with WAL mode
- check_same_thread=False for async compatibility
- data/ directory (gitignored)
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

from mata_garuda.council.models import CouncilDecision

logger = logging.getLogger("mata_garuda.council.store")

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "council.db"


class CouncilStore:
    """SQLite-backed store for council decisions."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS council_decisions (
                id TEXT PRIMARY KEY,
                topic_id TEXT NOT NULL,
                topic_title TEXT NOT NULL,
                topic_category TEXT NOT NULL,
                topic_description TEXT DEFAULT '',
                votes_json TEXT NOT NULL DEFAULT '[]',
                consensus_score REAL DEFAULT 0.0,
                consensus_method TEXT DEFAULT '',
                groupthink_detected INTEGER DEFAULT 0,
                dissents_json TEXT DEFAULT '[]',
                synthesis TEXT DEFAULT '',
                action_items_json TEXT DEFAULT '[]',
                requires_zero_approval INTEGER DEFAULT 0,
                escalation_reason TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                decided_at TEXT NOT NULL,
                approved_at TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS council_topics_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id TEXT NOT NULL,
                event TEXT NOT NULL,
                details TEXT DEFAULT '',
                timestamp TEXT DEFAULT (datetime('now'))
            );
        """)
        self._conn.commit()

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cursor = self._conn.execute(sql, params)
        self._conn.commit()
        return cursor

    def save_decision(self, decision: CouncilDecision) -> None:
        """Persist a council decision."""
        consensus = decision.consensus
        self._execute(
            """INSERT OR REPLACE INTO council_decisions
               (id, topic_id, topic_title, topic_category, topic_description,
                votes_json, consensus_score, consensus_method,
                groupthink_detected, dissents_json, synthesis,
                action_items_json, requires_zero_approval, escalation_reason,
                status, decided_at, approved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                decision.id,
                decision.topic.id,
                decision.topic.title,
                decision.topic.category,
                decision.topic.description,
                json.dumps([v.model_dump() for v in decision.votes]),
                consensus.score if consensus else 0.0,
                consensus.method if consensus else "",
                int(consensus.groupthink_detected) if consensus else 0,
                json.dumps([d.model_dump() for d in decision.dissents]),
                decision.synthesis,
                json.dumps(decision.action_items),
                int(decision.requires_zero_approval),
                decision.escalation_reason,
                decision.status,
                decision.decided_at,
                decision.approved_at,
            ),
        )
        # Log the event
        self._execute(
            "INSERT INTO council_topics_log (topic_id, event, details) VALUES (?, ?, ?)",
            (decision.topic.id, "decided", f"consensus={consensus.score:.2f}" if consensus else "abstain"),
        )

    def get_decision(self, decision_id: str) -> Optional[CouncilDecision]:
        """Retrieve a decision by ID."""
        cursor = self._execute(
            "SELECT * FROM council_decisions WHERE id = ?", (decision_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_decision(row)

    def list_decisions(
        self,
        status: Optional[str] = None,
        limit: int = 20,
        groupthink_only: bool = False,
    ) -> list[dict]:
        """List recent decisions as summary dicts."""
        sql = "SELECT id, topic_title, topic_category, consensus_score, groupthink_detected, status, decided_at FROM council_decisions"
        conditions = []
        params: list = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if groupthink_only:
            conditions.append("groupthink_detected = 1")

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY decided_at DESC LIMIT ?"
        params.append(limit)

        cursor = self._execute(sql, tuple(params))
        return [dict(row) for row in cursor.fetchall()]

    def update_status(
        self, decision_id: str, status: str, approved_by: str = ""
    ) -> bool:
        """Update decision status (approve/reject)."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        cursor = self._execute(
            "UPDATE council_decisions SET status = ?, approved_at = ? WHERE id = ?",
            (status, now, decision_id),
        )
        if cursor.rowcount > 0:
            self._execute(
                "INSERT INTO council_topics_log (topic_id, event, details) "
                "SELECT topic_id, ?, ? FROM council_decisions WHERE id = ?",
                (status, approved_by, decision_id),
            )
            return True
        return False

    def stats(self) -> dict:
        """Aggregate statistics."""
        cursor = self._execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved, "
            "SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) as rejected, "
            "SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending, "
            "AVG(consensus_score) as avg_consensus, "
            "SUM(CASE WHEN groupthink_detected=1 THEN 1 ELSE 0 END) as groupthink_count "
            "FROM council_decisions"
        )
        row = cursor.fetchone()
        if not row or row["total"] == 0:
            return {"total": 0, "approved": 0, "rejected": 0, "pending": 0,
                    "avg_consensus": 0.0, "groupthink_rate": 0.0}
        total = row["total"]
        return {
            "total": total,
            "approved": row["approved"] or 0,
            "rejected": row["rejected"] or 0,
            "pending": row["pending"] or 0,
            "avg_consensus": round(row["avg_consensus"] or 0.0, 3),
            "groupthink_rate": round((row["groupthink_count"] or 0) / total, 3),
        }

    def _row_to_decision(self, row: sqlite3.Row) -> CouncilDecision:
        """Convert a DB row to a CouncilDecision."""
        from mata_garuda.council.models import (
            AgentVote, ConsensusResult, Dissent, Topic,
        )

        votes_data = json.loads(row["votes_json"])
        dissents_data = json.loads(row["dissents_json"])
        action_items = json.loads(row["action_items_json"])

        return CouncilDecision(
            id=row["id"],
            topic=Topic(
                id=row["topic_id"],
                title=row["topic_title"],
                category=row["topic_category"],
                description=row["topic_description"] or "",
            ),
            votes=[AgentVote(**v) for v in votes_data],
            consensus=ConsensusResult(
                score=row["consensus_score"] or 0.0,
                method=row["consensus_method"] or "jaccard",
                groupthink_detected=bool(row["groupthink_detected"]),
            ),
            dissents=[Dissent(**d) for d in dissents_data],
            synthesis=row["synthesis"] or "",
            action_items=action_items,
            requires_zero_approval=bool(row["requires_zero_approval"]),
            escalation_reason=row["escalation_reason"] or "",
            status=row["status"] or "pending",
            decided_at=row["decided_at"] or "",
            approved_at=row["approved_at"] or "",
        )

    def close(self) -> None:
        self._conn.close()
