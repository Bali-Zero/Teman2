"""One-shot Visa Oracle SESSIONS purge worker (migration 317's enforcement arm).

Distinct from `retention_worker.py` (visa DECISIONS + evaluate-idempotency
replay records), which is policy-table-gated (`visa_decision_retention_policies`,
a Zero-approved-policy authority) and runs its deletes through SECURITY
DEFINER SQL functions under a dedicated least-privilege retention role.
`visa_oracle_sessions` has no such policy row — its retention duration is the
plain `expires_at` DEFAULT migration 317 set directly (30 days, Owner ruling
2026-08-25), so this worker just calls the router's own
`_purge_expired_sessions` helper (bounded DELETE, excludes handed-off rows)
against the SAME runtime database pool `_persist_session_create` already
writes through — no separate DSN/role, because there is no separate
sensitivity tier to gate here.

Reuses the SAME external-scheduler shape as `retention_worker.py` /
`visa-oracle-retention-run.sh` (one-shot, --apply-gated, run from launchd via
`scripts/cron-wrapper.sh` so a crashed API process cannot silently stop
purging) — see `infra/launchagents/wrappers/visa-oracle-sessions-purge-run.sh`
and `infra/launchagents/com.nuzantara.visa-oracle-sessions-purge.15min.plist.example`.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

import asyncpg

from backend.app.routers.visa_oracle import _purge_expired_sessions

logger = logging.getLogger("visa_engine.visa_oracle_sessions_purge_worker")

DSN_ENV = "DATABASE_URL"

_EXPIRED_NON_HANDOFF_COUNT_SQL = """
    SELECT count(*) FROM visa_oracle_sessions
     WHERE expires_at < NOW()
       AND NOT COALESCE(handoff_triggered, false)
"""


async def _expired_non_handoff_count(db_pool: asyncpg.Pool) -> int:
    """Read-only backlog count — same predicate the purge deletes on, PII-free."""
    async with db_pool.acquire() as conn:
        return int(await conn.fetchval(_EXPIRED_NON_HANDOFF_COUNT_SQL))


async def run(args: argparse.Namespace) -> int:
    database_url = os.environ.get(args.database_url_env, "").strip()
    if not database_url:
        raise RuntimeError(f"${args.database_url_env} is required")
    db_pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    deleted_total = 0
    try:
        if args.apply:
            for _ in range(args.max_batches):
                deleted = await _purge_expired_sessions(db_pool, limit=args.limit)
                deleted_total += deleted
                if deleted < args.limit:
                    break
        remaining = await _expired_non_handoff_count(db_pool)
    finally:
        await db_pool.close()

    # PII-free: counts only, never a session_id, quiz_answers, message or ip_hash.
    logger.info(
        "visa_oracle_sessions_purge_result apply=%s deleted=%d remaining=%d limit=%d max_batches=%d",
        args.apply,
        deleted_total,
        remaining,
        args.limit,
        args.max_batches,
    )
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--max-batches", type=int, default=5)
    parser.add_argument("--database-url-env", default=DSN_ENV)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(run(_parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
