#!/usr/bin/env python3
"""CRM-Guardian Phase 1 — bulk enqueue eligible clients.

Phase 1 production-flip companion to the cli worker. The LaunchAgent
`com.balizero.crm-guardian-cli-worker` runs every 5min/5jobs (Option C,
2026-05-18). The queue is empty after pilot+production-flip closure → worker
sits idle. This script fills it.

Scopes (CLI flag):
  full           — clients.google_drive_folder_id IS NOT NULL
                   AND ai_summary IS NULL  (≈1882 today)
  active-linked  — full  +  EXISTS active client_company_links
                   (≈727 today, ≈ planning's "706")  [default]
  vip-only       — full  +  prior summary has profile.tier='VIP'
                   (small, used for re-runs only)

Priority follows summary_queue._priority_for_tier():
  VIP → 1, archive → 100, else → 50. Most eligibles have no prior summary,
  so they land at priority=50; this is intentional (worker uses ORDER BY
  priority ASC, enqueued_at ASC and we want roughly FIFO).

Safety: --dry-run (no INSERT, preview counts) + --limit N (default 50).
Idempotent vs LaunchAgent: enqueue_client() relies on the unique-pending
index on (client_id) WHERE status IN ('pending','running'). Calling this
script twice does NOT double-enqueue.

Audit: each run writes JSON to ~/.crm_guardian/enqueue_runs/<timestamp>.json
with scope, args, per-client outcome, total counts.

Usage:
    # 1. preview (no writes)
    python scripts/crm_guardian_enqueue_eligible.py --dry-run --limit 50
    # 2. small step (idempotent if re-run)
    python scripts/crm_guardian_enqueue_eligible.py --limit 10
    # 3. wider step
    python scripts/crm_guardian_enqueue_eligible.py --limit 100
    # 4. full bulk (after observation gates pass)
    python scripts/crm_guardian_enqueue_eligible.py --scope active-linked
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_RAG = REPO_ROOT / "apps" / "backend-rag"
sys.path.insert(0, str(BACKEND_RAG))

from backend.services.crm_guardian.summary_queue import (  # noqa: E402
    enqueue_client,
)

LOG = logging.getLogger("crm_guardian.bulk_enqueue")

ENQUEUE_RUNS_DIR = Path.home() / ".crm_guardian" / "enqueue_runs"
ENQUEUE_RUNS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# DB helpers (mirror cli worker pattern — same env resolution)
# ---------------------------------------------------------------------------

def _resolve_db_url() -> str:
    """Resolve local flyctl-proxy DATABASE_URL.

    Mirrors `crm_guardian_gemini_cli_worker._resolve_db_url`. Reads
    ~/.nuzantara-secrets.env, prefers DATABASE_URL_LOCAL, falls back to
    DATABASE_URL (rewriting .internal:5432 → localhost:15432).
    """
    secrets = Path.home() / ".nuzantara-secrets.env"
    if not secrets.exists():
        raise RuntimeError(f"Secrets file not found: {secrets}")

    raw_local: str | None = None
    raw_remote: str | None = None
    for line in secrets.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key == "DATABASE_URL_LOCAL":
            raw_local = value
        elif key == "DATABASE_URL":
            raw_remote = value

    if raw_local:
        return raw_local
    if raw_remote:
        return re.sub(r"@[^:/]+(\.internal)?:\d+", "@localhost:15432", raw_remote)
    raise RuntimeError(
        "DATABASE_URL_LOCAL or DATABASE_URL not found in ~/.nuzantara-secrets.env",
    )


# ---------------------------------------------------------------------------
# Scope queries
# ---------------------------------------------------------------------------

# Returns rows ordered by:
#   1. clients with prior VIP summary first (priority will be 1)
#   2. then by id ASC (stable, predictable, near-FIFO if id is monotonic)
#
# Each scope filters on:
#   - google_drive_folder_id IS NOT NULL  (worker requirement, summary_queue.py:110)
#   - ai_summary IS NULL                  (avoid re-enqueueing already done)
#   - NOT EXISTS row in crm_guardian_summary_queue with status IN
#     ('pending','running','success')    (true skip — keep error/skipped to allow retry-after-fix)
#
# We exclude 'success' to avoid re-enqueueing the 5 production-flip clients
# (queue ids 6, 8, 10, 11, 12). We leave 'error'/'skipped' enqueuable in case
# Antonello later wants to retry id=7 (266 pydantic error pre-repo-fix) or
# id=9 (283 ENOENT pre-repo-fix) — but those are now success in queue 11/12,
# so they have a different exclusion: client_id with ANY 'success' row.

_SCOPE_PREDICATES: dict[str, str] = {
    "full": """
        c.google_drive_folder_id IS NOT NULL
        AND c.ai_summary IS NULL
    """,
    "active-linked": """
        c.google_drive_folder_id IS NOT NULL
        AND c.ai_summary IS NULL
        AND EXISTS (
            SELECT 1 FROM client_company_links ccl
            WHERE ccl.client_id = c.id AND ccl.status = 'active'
        )
    """,
    "vip-only": """
        c.google_drive_folder_id IS NOT NULL
        AND c.ai_summary IS NULL
        AND (c.ai_summary -> 'profile' ->> 'tier') = 'VIP'
    """,
}


def _scope_sql(scope: str, limit: int | None) -> str:
    pred = _SCOPE_PREDICATES[scope]
    limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""
    return f"""
        SELECT
            c.id,
            c.full_name,
            (c.ai_summary -> 'profile' ->> 'tier') AS prior_tier
        FROM clients c
        WHERE {pred}
          AND NOT EXISTS (
              SELECT 1 FROM crm_guardian_summary_queue q
              WHERE q.client_id = c.id
                AND q.status IN ('pending', 'running', 'success')
          )
        ORDER BY
            CASE WHEN (c.ai_summary -> 'profile' ->> 'tier') = 'VIP' THEN 0 ELSE 1 END,
            c.id ASC
        {limit_clause};
    """


async def _count_scope(conn: asyncpg.Connection, scope: str) -> int:
    sql = f"""
        SELECT COUNT(*) FROM clients c
        WHERE {_SCOPE_PREDICATES[scope]}
          AND NOT EXISTS (
              SELECT 1 FROM crm_guardian_summary_queue q
              WHERE q.client_id = c.id
                AND q.status IN ('pending', 'running', 'success')
          );
    """
    return await conn.fetchval(sql)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def bulk_enqueue(
    *,
    scope: str,
    limit: int | None,
    dry_run: bool,
    force: bool,
) -> dict[str, Any]:
    db_url = _resolve_db_url()
    started_at = datetime.now(timezone.utc)
    run_id = started_at.strftime("%Y%m%d-%H%M%S")

    audit: dict[str, Any] = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "scope": scope,
        "limit": limit,
        "dry_run": dry_run,
        "force": force,
        "rows": [],
    }

    conn = await asyncpg.connect(db_url)
    try:
        # 1. Total eligible (no LIMIT) for visibility
        total_eligible = await _count_scope(conn, scope)
        audit["total_eligible"] = total_eligible

        # 2. Candidate rows (with LIMIT if any)
        rows = await conn.fetch(_scope_sql(scope, limit))
        audit["candidate_count"] = len(rows)

        LOG.info(
            "scope=%s total_eligible=%d candidates_after_limit=%d dry_run=%s",
            scope, total_eligible, len(rows), dry_run,
        )

        if dry_run:
            # Preview only — no INSERT. Surface first 10 client ids so the
            # operator can sanity-check selection.
            preview = [
                {
                    "client_id": r["id"],
                    "full_name": r["full_name"],
                    "prior_tier": r["prior_tier"],
                }
                for r in rows[:10]
            ]
            audit["preview_first_10"] = preview
            audit["counters"] = {
                "would_enqueue": len(rows),
                "inserted": 0,
                "already_pending": 0,
                "skipped_disabled": 0,
                "client_not_found": 0,
            }
            return audit

        # 3. Real enqueue
        counters = {
            "inserted": 0,
            "already_pending": 0,
            "skipped_disabled": 0,
            "client_not_found": 0,
        }
        for r in rows:
            result = await enqueue_client(
                conn,
                r["id"],
                enqueued_by=f"bulk_enqueue:{scope}:{run_id}",
                force=force,
            )
            counters[result["action"]] = counters.get(result["action"], 0) + 1
            audit["rows"].append({
                "client_id": r["id"],
                "full_name": r["full_name"],
                **{k: v for k, v in result.items() if k != "client_id"},
            })
            # Hard-stop early if invariant is disabled — every call will
            # return skipped_disabled, no point banging the DB.
            if (
                result["action"] == "skipped_disabled"
                and counters["skipped_disabled"] >= 3
                and not force
            ):
                LOG.warning(
                    "I10b_summary_queue disabled — bailing after 3 skipped (use --force to override)",
                )
                audit["early_exit"] = "invariant_disabled"
                break

        audit["counters"] = counters

        return audit
    finally:
        await conn.close()
        audit["finished_at"] = datetime.now(timezone.utc).isoformat()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def _write_audit(audit: dict[str, Any]) -> Path:
    out = ENQUEUE_RUNS_DIR / f"{audit['run_id']}.json"
    out.write_text(json.dumps(audit, indent=2, ensure_ascii=False))
    return out


def _print_summary(audit: dict[str, Any]) -> None:
    cnt = audit.get("counters", {})
    msg = (
        f"\nscope={audit['scope']} dry_run={audit['dry_run']} "
        f"total_eligible={audit['total_eligible']} candidates={audit['candidate_count']}\n"
        f"  inserted          = {cnt.get('inserted', 0)}\n"
        f"  already_pending   = {cnt.get('already_pending', 0)}\n"
        f"  skipped_disabled  = {cnt.get('skipped_disabled', 0)}\n"
        f"  client_not_found  = {cnt.get('client_not_found', 0)}\n"
    )
    if audit.get("early_exit"):
        msg += f"  early_exit        = {audit['early_exit']}\n"
    if audit.get("preview_first_10"):
        msg += "  preview (first 10):\n"
        for p in audit["preview_first_10"]:
            tier = p.get("prior_tier") or "—"
            msg += f"    [{p['client_id']:>5}] {p['full_name']} (prior_tier={tier})\n"
    sys.stdout.write(msg)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--scope",
        choices=list(_SCOPE_PREDICATES.keys()),
        default="active-linked",
        help="Eligibility predicate. Default: active-linked (~727).",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max rows to enqueue this run. Use 0 for unlimited. Default 50.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview rows + counts without INSERT.",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Bypass I10b_summary_queue enabled check (debug only).",
    )
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    _setup_logging(args.verbose)

    limit_arg: int | None = args.limit if args.limit > 0 else None
    audit = asyncio.run(
        bulk_enqueue(
            scope=args.scope,
            limit=limit_arg,
            dry_run=args.dry_run,
            force=args.force,
        )
    )

    out_path = _write_audit(audit)
    _print_summary(audit)
    sys.stdout.write(f"  audit_json        = {out_path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
