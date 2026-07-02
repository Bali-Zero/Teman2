"""
Mata Garuda — NLM Daily Rollup (summarize-then-store, council fix #5).

THE PROBLEM (Zero's call 2026-06-30): NLM is a HARD-capped sink (~500 sources/NB).
The per-item feeder, even with the relevance threshold (#3), burns one NLM source
per intel item — a few thousand items would blow the cap. Feeding 5266 backlogged
items one-by-one is exactly what this exists to prevent.

THE CURE (council: Kafka log-compaction / daily-rollup): instead of N sources,
write ONE digest source per (day, domain). The durable per-item record already
lives in the archiver SQLite (#4) — NLM only needs the COMPACTED, queryable
summary. This turns thousands of items into a handful of rollup sources → fits the
cap with room for ~500 DAYS of intel instead of ~500 items.

Reads FROM the archive (the "store" in summarize-then-store), groups by
(date, domain), composes a deterministic digest (NO LLM — a digest of
titles+urls+scores is mechanical, robust, quota-free, hallucination-free), and
pushes one text source per group via the feeder's existing _nlm_add_text (which
carries cap-rollover B2 + auth). Idempotent: a per-(date,domain) ledger row marks
what's been rolled up, so re-runs never double-post.

Stdlib-only (sqlite3). Layer 2.6 — compaction Sink off the archive, NOT the stream
(council: don't re-consume the hot stream; the archive is the system of record).
"""
from __future__ import annotations

import logging
import os
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Optional

from mata_garuda.workers.archiver import DEFAULT_ARCHIVE_PATH, StreamArchive
import subprocess
from mata_garuda.workers.nlm_feeder import (
    NLM_CLI,
    _nlm_at_cap,
    _resolve_writable_nb,
    route_domain_to_notebook,
)

logger = logging.getLogger("mata_garuda.workers")

# Only items scoring >= this make the digest body (keep rollups signal-dense).
ROLLUP_MIN_SCORE = int(os.environ.get("GARUDA_ROLLUP_MIN_SCORE", "3"))
# Domain fallback for un-classified / legacy-null items (the OSINT intel home).
ROLLUP_DEFAULT_DOMAIN = os.environ.get("GARUDA_ROLLUP_DEFAULT_DOMAIN", "ai_research")
MAX_ITEMS_PER_DIGEST = int(os.environ.get("GARUDA_ROLLUP_MAX_LINES", "80"))


def _ensure_ledger(conn: sqlite3.Connection) -> None:
    """Idempotency ledger: one row per (day, domain) already posted to NLM."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rollup_ledger (
            day TEXT NOT NULL,
            domain TEXT NOT NULL,
            notebook_id TEXT,
            source_id TEXT,
            item_count INTEGER,
            posted_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (day, domain)
        )
    """)
    # guarded migration for pre-existing ledgers
    cols = [r[1] for r in conn.execute("PRAGMA table_info(rollup_ledger)").fetchall()]
    if "source_id" not in cols:
        conn.execute("ALTER TABLE rollup_ledger ADD COLUMN source_id TEXT")
    conn.commit()


def _score_ok(raw) -> bool:
    try:
        return int(float(raw)) >= ROLLUP_MIN_SCORE
    except (TypeError, ValueError):
        return True  # un-scored → include (fail-open, same spirit as the feeder)


def _compose_digest(day: str, domain: str, rows: list) -> tuple[str, str]:
    """Build (title, body) for one (day, domain) digest. Deterministic, no LLM."""
    title = f"Intel rollup {day} — {domain} ({len(rows)} items)"
    lines = [
        f"# Bali Zero OSINT intel digest — {day} — domain: {domain}",
        f"# {len(rows)} items (signal score >= {ROLLUP_MIN_SCORE}); compacted by nlm_rollup #5.",
        "",
    ]
    for r in rows[:MAX_ITEMS_PER_DIGEST]:
        sc = (r["score"] or "").strip()
        src = (r["source"] or "").strip()
        tag = f"[{src}{('/'+sc) if sc else ''}]"
        line = f"- {tag} {(r['title'] or '').strip()}"
        url = (r["url"] or "").strip()
        if url:
            line += f"\n  {url}"
        snippet = (r["content"] or "").strip().replace("\n", " ")
        if snippet:
            line += f"\n  {snippet[:240]}"
        lines.append(line)
    if len(rows) > MAX_ITEMS_PER_DIGEST:
        lines.append(f"\n… +{len(rows) - MAX_ITEMS_PER_DIGEST} more items (in archive.db).")
    return title, "\n".join(lines)


def _post_digest(notebook_id: str, title: str, body: str) -> Optional[str]:
    """Post one digest to NLM with its title PRESERVED.

    Uses `nlm source add --text <body> --title <title>` (A/B-verified to keep the
    title) instead of nlm_feeder._nlm_add_text, which writes a temp file and lets
    the temp FILENAME become the source title (the rollup MUST be findable by its
    'Intel rollup <day>' title). Honors cap-rollover via _resolve_writable_nb.
    """
    if not notebook_id:
        return None
    notebook_id = _resolve_writable_nb(notebook_id)
    if _nlm_at_cap(notebook_id):
        logger.warning("[rollup] NB at cap (no overflow room): nb=%s", notebook_id)
        return None
    try:
        result = subprocess.run(
            [NLM_CLI, "source", "add", "--profile", "default", notebook_id,
             "--text", body, "--title", title],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            # parse "Source ID: <uuid>" so we can replace it on a later re-post
            out = (result.stdout or "") + (result.stderr or "")
            sid = ""
            for line in out.splitlines():
                if "Source ID:" in line:
                    sid = line.split("Source ID:", 1)[1].strip()
                    break
            return sid or "posted"   # truthy even if id not parseable
        snippet = ((result.stderr or "") + (result.stdout or "")).replace("\n", " ")[:200]
        logger.warning("[rollup] add rejected nb=%s rc=%d reason=%s",
                       notebook_id, result.returncode, snippet or "(empty)")
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("[rollup] add failed: %s", e)
        return None


def _delete_source(notebook_id: str, source_id: str) -> None:
    """Best-effort delete a prior digest source before re-posting (replace, not
    append) — prevents duplicate 'Intel rollup' sources when a day's archive grew
    after its first digest (caught live 2026-06-30: 3 dupes 499/919/1370)."""
    if not (notebook_id and source_id and source_id != "posted"):
        return
    try:
        subprocess.run(
            [NLM_CLI, "source", "delete", notebook_id, source_id,
             "--confirm", "--profile", "default"],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("[rollup] could not delete prior source %s: %s", source_id, e)


def run_rollup(db_path: Optional[Path] = None, days_back: int = 14) -> dict:
    """Roll up un-posted (day, domain) groups from the archive into NLM digests.

    Returns stats: {groups, posted, skipped_already, items, errors}.
    """
    stats = {"groups": 0, "posted": 0, "skipped_already": 0, "items": 0, "errors": 0}
    path = db_path or DEFAULT_ARCHIVE_PATH
    # Open via StreamArchive so its guarded ALTER (adds `domain` to pre-existing
    # DBs) has definitely run before we SELECT domain — a raw sqlite3.connect
    # skips that migration and dies 'no such column: domain'.
    _archive = StreamArchive(db_path=path)
    conn = _archive._conn
    conn.row_factory = sqlite3.Row
    _ensure_ledger(conn)

    # Candidate items: recent, scored window. Group by (day, domain).
    rows = conn.execute(
        "SELECT date(archived_at) AS day, "
        "       COALESCE(NULLIF(domain,''), ?) AS dom, "
        "       title, url, source, score, content "
        "FROM archive "
        "WHERE date(archived_at) >= date('now', ?) "
        "ORDER BY day DESC, dom",
        (ROLLUP_DEFAULT_DOMAIN, f"-{int(days_back)} days"),
    ).fetchall()

    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        if _score_ok(r["score"]):
            groups[(r["day"], r["dom"])].append(r)

    # Prior ledger: (day,domain) -> (item_count, source_id) for skip/replace logic.
    prior = {(g["day"], g["domain"]): (g["item_count"], g["source_id"])
             for g in conn.execute(
                 "SELECT day, domain, item_count, source_id FROM rollup_ledger").fetchall()}

    for (day, domain), items in sorted(groups.items()):
        stats["groups"] += 1
        old = prior.get((day, domain))
        old_sid = None
        if old is not None:
            old_count, old_sid = old
            if old_count == len(items):
                stats["skipped_already"] += 1   # unchanged → nothing to do
                continue
            # day grew since the last digest → REPLACE (delete old, post fresh)
            logger.info("[rollup] %s/%s grew %s→%d — replacing digest",
                        day, domain, old_count, len(items))
        nb_key, notebook_id = route_domain_to_notebook(domain)
        if not notebook_id:
            # unroutable domain → fall back to the OSINT intel home
            nb_key, notebook_id = route_domain_to_notebook(ROLLUP_DEFAULT_DOMAIN)
        if not notebook_id:
            logger.warning("[rollup] no notebook for domain=%s — skipping %s", domain, day)
            continue
        title, body = _compose_digest(day, domain, items)
        try:
            new_sid = _post_digest(notebook_id, title, body)
            if new_sid:
                # replace: remove the stale prior digest so NLM keeps ONE per day
                if old_sid:
                    _delete_source(notebook_id, old_sid)
                conn.execute(
                    "INSERT OR REPLACE INTO rollup_ledger "
                    "(day, domain, notebook_id, source_id, item_count) "
                    "VALUES (?,?,?,?,?)",
                    (day, domain, notebook_id, new_sid, len(items)),
                )
                conn.commit()
                stats["posted"] += 1
                stats["items"] += len(items)
                logger.info("[rollup] posted %s/%s (%d items) → %s",
                            day, domain, len(items), nb_key)
            else:
                stats["errors"] += 1  # cap reached / nlm reject → retry next run
        except Exception as e:  # noqa: BLE001
            logger.error("[rollup] error posting %s/%s: %s", day, domain, e)
            stats["errors"] += 1

    _archive.close()
    return stats


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    days_back = int(os.environ.get("GARUDA_ROLLUP_DAYS_BACK", "14"))
    try:
        stats = run_rollup(days_back=days_back)
        print(f"[rollup] {stats}")
        return 0
    except Exception as e:  # noqa: BLE001
        logger.error(f"[rollup] FATAL: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
