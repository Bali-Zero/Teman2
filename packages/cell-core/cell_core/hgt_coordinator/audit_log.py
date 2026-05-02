"""SQLite audit log for HGT coordinator proposals.

Sync ``sqlite3`` (not ``aiosqlite``) chosen on purpose: this is a
propose-only audit log with ≤100 rows/day expected, single-writer
(coordinator runs on a heartbeat), and the OpenClaw CLI reads/writes the
DB sequentially. Adding async would buy us nothing — the bottleneck is
the Redis Stream read upstream, not the SQLite write. Per ADR doctrine
"JSONL canonical / SQLite per-machine outside git tree" (see
``docs/escalations/federation-bus.md``), the DB lives under
``data/hgt_coordinator/proposals.db`` which is .gitignored.

Schema is intentionally narrow:

    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP NOT NULL,
    skill_name TEXT NOT NULL,
    source_cells TEXT NOT NULL,         -- JSON array
    target_candidates TEXT NOT NULL,    -- JSON array
    confidence REAL NOT NULL,
    transfer_rationale TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending|approved|rejected|deferred
    resolved_at TIMESTAMP NULL,
    resolved_by TEXT NULL                -- 'human:<name>' | 'kimi-k2.6' | NULL

Idempotency: ``record_proposal`` is best-effort idempotent on
``(skill_name, observation_window_days, date(created_at))`` via a
de-dup query — if a proposal for the same skill in the same window
already exists in the last 24h with status='pending', the new one is
skipped (returning the existing row's id). Operators can override by
calling ``record_proposal(..., force=True)``.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence

from cell_core.hgt_coordinator.proposal import Proposal

logger = logging.getLogger("cell_core.hgt_coordinator.audit_log")

# Resolution path — env override for CI / per-machine layout.
_DEFAULT_REL_PATH = "data/hgt_coordinator/proposals.db"
DEFAULT_AUDIT_LOG_PATH = Path(
    os.environ.get(
        "HGT_COORDINATOR_AUDIT_LOG",
        Path.cwd() / _DEFAULT_REL_PATH,
    )
).resolve()


def audit_log_path(override: Path | str | None = None) -> Path:
    """Resolve audit-log path with optional override; ensures parent dir.

    Args:
        override: explicit path (str or Path), or None to use the env
            var ``HGT_COORDINATOR_AUDIT_LOG`` or the default
            ``./data/hgt_coordinator/proposals.db``.

    Returns:
        Absolute :class:`Path` with parent directory created.
    """
    if override is not None:
        path = Path(override).resolve()
    else:
        path = DEFAULT_AUDIT_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP NOT NULL,
    skill_name TEXT NOT NULL,
    source_cells TEXT NOT NULL,
    target_candidates TEXT NOT NULL,
    confidence REAL NOT NULL,
    transfer_rationale TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    resolved_at TIMESTAMP NULL,
    resolved_by TEXT NULL,
    domain TEXT NOT NULL DEFAULT 'generic',
    total_uses INTEGER NOT NULL DEFAULT 0,
    avg_confidence REAL NOT NULL DEFAULT 0.0,
    std_confidence REAL NOT NULL DEFAULT 0.0,
    observation_window_days INTEGER NOT NULL DEFAULT 7,
    recommended_action TEXT NOT NULL DEFAULT 'propose'
);

CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_skill_window ON proposals(skill_name, observation_window_days);
CREATE INDEX IF NOT EXISTS idx_proposals_created_at ON proposals(created_at);
"""


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection with sane defaults for a propose-only log.

    - ``isolation_level=None`` → autocommit; we explicitly BEGIN/COMMIT
      around multi-statement writes when needed.
    - Row factory is :class:`sqlite3.Row` so callers can dict-access
      columns without remembering positional order.
    - WAL is overkill for this volume but harmless and makes
      concurrent readers (CLI ``list_pending`` + heartbeat write)
      safe.
    """
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
    finally:
        conn.close()


def init_db(path: Path | str | None = None) -> Path:
    """Initialise schema; idempotent. Returns the resolved path."""
    resolved = audit_log_path(path)
    with _connect(resolved) as conn:
        conn.executescript(_SCHEMA_SQL)
    logger.debug("hgt_coordinator audit log ready at %s", resolved)
    return resolved


def record_proposal(
    proposal: Proposal,
    *,
    path: Path | str | None = None,
    force: bool = False,
) -> int:
    """Persist a proposal; return its row id.

    Idempotency: skip if a *pending* proposal for the same
    (skill_name, observation_window_days) exists in the last 24h, unless
    ``force=True``.
    """
    resolved = init_db(path)
    with _connect(resolved) as conn:
        if not force:
            existing = conn.execute(
                """
                SELECT id FROM proposals
                WHERE skill_name = ?
                  AND observation_window_days = ?
                  AND status = 'pending'
                  AND datetime(created_at) > datetime('now', '-1 day')
                ORDER BY id DESC LIMIT 1
                """,
                (proposal.skill_name, proposal.observation_window_days),
            ).fetchone()
            if existing is not None:
                logger.debug(
                    "skipping duplicate proposal for %s (existing id=%s)",
                    proposal.skill_name,
                    existing["id"],
                )
                return int(existing["id"])

        cur = conn.execute(
            """
            INSERT INTO proposals (
                created_at, skill_name, source_cells, target_candidates,
                confidence, transfer_rationale, status, domain, total_uses,
                avg_confidence, std_confidence, observation_window_days,
                recommended_action
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal.observed_at.isoformat(),
                proposal.skill_name,
                json.dumps(list(proposal.source_cells)),
                json.dumps(list(proposal.target_cell_candidates)),
                float(proposal.confidence),
                proposal.transfer_rationale,
                proposal.domain,
                int(proposal.total_uses),
                float(proposal.avg_confidence),
                float(proposal.std_confidence),
                int(proposal.observation_window_days),
                proposal.recommended_action,
            ),
        )
        row_id = cur.lastrowid
    if row_id is None:
        # Defensive — sqlite3 always populates lastrowid for INSERT.
        raise RuntimeError("SQLite returned no lastrowid for INSERT")
    logger.info(
        "hgt_coordinator recorded proposal id=%s for skill=%s (action=%s)",
        row_id,
        proposal.skill_name,
        proposal.recommended_action,
    )
    return int(row_id)


def list_pending(
    path: Path | str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    """Return pending proposals oldest-first; cap at ``limit``."""
    resolved = init_db(path)
    with _connect(resolved) as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, skill_name, source_cells, target_candidates,
                   confidence, transfer_rationale, status, domain, total_uses,
                   avg_confidence, std_confidence, observation_window_days,
                   recommended_action
            FROM proposals
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def mark_resolved(
    proposal_id: int,
    *,
    new_status: str,
    resolved_by: str,
    path: Path | str | None = None,
) -> bool:
    """Resolve a proposal; returns True if a row was updated.

    Args:
        proposal_id: row id from ``record_proposal``.
        new_status: must be one of ``approved`` | ``rejected`` | ``deferred``.
        resolved_by: free-form ID of the resolver (e.g. ``"human:zero"``,
            ``"kimi-k2.6"``).
    """
    if new_status not in {"approved", "rejected", "deferred"}:
        raise ValueError(
            f"new_status must be approved|rejected|deferred, got {new_status!r}"
        )
    resolved_path = init_db(path)
    now = datetime.now(timezone.utc).isoformat()
    with _connect(resolved_path) as conn:
        cur = conn.execute(
            """
            UPDATE proposals
               SET status = ?,
                   resolved_at = ?,
                   resolved_by = ?
             WHERE id = ?
               AND status = 'pending'
            """,
            (new_status, now, resolved_by, int(proposal_id)),
        )
        return cur.rowcount > 0


def _row_to_dict(row: sqlite3.Row) -> dict[str, object]:
    """Convert a Row to a dict; deserialise JSON columns."""
    out: dict[str, object] = {k: row[k] for k in row.keys()}
    for json_col in ("source_cells", "target_candidates"):
        raw = out.get(json_col)
        if isinstance(raw, str):
            try:
                out[json_col] = json.loads(raw)
            except json.JSONDecodeError:
                # Defensive — keep the raw string so the audit log isn't
                # made unreadable by one bad row.
                logger.warning("malformed JSON in column %s row %s", json_col, out.get("id"))
    return out


# Optional helper — useful in tests and for the OpenClaw CLI.
def fetch_all(
    path: Path | str | None = None,
    limit: int = 200,
) -> Sequence[dict[str, object]]:
    """Return up to ``limit`` proposals (any status) oldest-first."""
    resolved = init_db(path)
    with _connect(resolved) as conn:
        rows = conn.execute(
            """
            SELECT * FROM proposals
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]
