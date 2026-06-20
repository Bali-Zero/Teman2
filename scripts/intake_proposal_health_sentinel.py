#!/usr/bin/env python3
"""Intake proposal-health sentinel — the done-deadlock guardian (Defect 3).

WHY THIS EXISTS
  The intake pipeline can leave an ``intake_queue`` row at ``status='done'`` while
  its only ``document_routing_proposal`` is ``superseded`` (a re-process bumped /
  superseded the prior proposal but the fresh one was never persisted, e.g. an
  ``ON CONFLICT DO NOTHING`` collision, or the worker died mid-route). Such a row
  is a DEAD DOCUMENT: ``done`` is not claimable by the worker, and ``superseded``
  never appears in ``/review`` — so a received KTP/passport/akta is silently lost.
  This was found tracing adit's wa-mirror→/review path (2026-06-20): 319 of his
  documents were in exactly this state.

  PR #1587 fixes the route stage so this stops *being created*. This sentinel is
  the SEPARATE guardian that DETECTS the invariant violation if it ever recurs by
  another path (a future code change, a manual DB edit, a half-finished reprocess)
  and — only with --heal — repairs it with the same safe transition the route
  guard uses (superseded-orphan → review_pending).

INVARIANT (the thing this protects)
  A queue row that has reached a terminal worker state (``done``) MUST have at
  least one *live* proposal — i.e. one whose status is NOT ``superseded``
  (``review_pending`` | ``review_claimed`` | ``routed`` | ``rejected``). A ``done``
  row whose every proposal is ``superseded`` is an illegal state.

MODES
  default (report-only): count violations, emit a Telegram alert (cooldowned),
    exit 0 always — a monitoring run must never take the pipeline down.
  --heal: additionally revive each orphan's most-recent superseded proposal back
    to ``review_pending`` so it re-enters /review. Idempotent and bounded by
    --limit. Heal is OPT-IN — the default is a signaller, not an auto-actuator
    (superscar #2 antidote: reconciliation-report, not blind self-repair).

PII / Law 2: runs on the Pro against the LOCAL nuzantara_dev. No cloud, no PII in
  the alert body (only counts + queue ids).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import asyncpg

logger = logging.getLogger("intake.proposal_health_sentinel")

DEFAULT_DSN = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"

# A "live" proposal is anything that is NOT superseded. These are the states that
# legitimately satisfy the invariant for a done row.
_LIVE_STATUSES = ("review_pending", "review_claimed", "routed", "rejected")

# The violation: queue is terminal (done) yet has at least one proposal AND none
# of them is live. (A done row with ZERO proposals at all is a different class —
# legacy no-proposal — reported separately so the two are never conflated.)
COUNT_SQL = """
WITH q AS (
    SELECT iq.id
    FROM intake_queue iq
    WHERE iq.status = 'done'
)
SELECT
    count(*) FILTER (
        WHERE EXISTS (SELECT 1 FROM document_routing_proposal p WHERE p.queue_id = q.id)
          AND NOT EXISTS (
              SELECT 1 FROM document_routing_proposal p
              WHERE p.queue_id = q.id AND p.status = ANY($1::text[])
          )
    ) AS superseded_orphans,
    count(*) FILTER (
        WHERE NOT EXISTS (SELECT 1 FROM document_routing_proposal p WHERE p.queue_id = q.id)
    ) AS no_proposal_at_all
FROM q
"""

# The ids of superseded-orphan queues (done + has proposal + none live).
ORPHAN_IDS_SQL = """
SELECT iq.id
FROM intake_queue iq
WHERE iq.status = 'done'
  AND EXISTS (SELECT 1 FROM document_routing_proposal p WHERE p.queue_id = iq.id)
  AND NOT EXISTS (
      SELECT 1 FROM document_routing_proposal p
      WHERE p.queue_id = iq.id AND p.status = ANY($1::text[])
  )
ORDER BY iq.id
LIMIT $2
"""

# Revive: flip the most-recent superseded proposal of a queue back to
# review_pending and clear its lease. Same safe transition the route guard uses.
HEAL_SQL = """
UPDATE document_routing_proposal p
   SET status           = 'review_pending',
       lease_owner      = NULL,
       lease_expires_at = NULL,
       claim_token      = NULL
 WHERE p.id = (
     SELECT p2.id FROM document_routing_proposal p2
     WHERE p2.queue_id = $1 AND p2.status = 'superseded'
     ORDER BY p2.id DESC
     LIMIT 1
 )
   AND NOT EXISTS (
       SELECT 1 FROM document_routing_proposal p3
       WHERE p3.queue_id = $1 AND p3.status = ANY($2::text[])
   )
RETURNING p.id
"""


def _dsn() -> str:
    return os.getenv("INTAKE_DATABASE_URL", os.getenv("DATABASE_URL", DEFAULT_DSN))


def _send_alert(message: str, level: str) -> None:
    """Best-effort Telegram alert via the shared sentinel alerter (cooldowned).

    Never raises — a monitoring run must not fail because alerting is unavailable.
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from sentinel_lib.alerter import send_alert  # type: ignore

        send_alert(message, level=level)
    except Exception as exc:  # noqa: BLE001 — alerting is best-effort
        logger.warning("alert dispatch failed (%s): %s", type(exc).__name__, message)


async def run(heal: bool, limit: int) -> int:
    pool = await asyncpg.create_pool(dsn=_dsn(), min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(COUNT_SQL, list(_LIVE_STATUSES))
            orphans = int(row["superseded_orphans"])
            no_proposal = int(row["no_proposal_at_all"])

            logger.info(
                "intake invariant check: superseded_orphans=%d no_proposal=%d (done rows)",
                orphans, no_proposal,
            )

            healed = 0
            if heal and orphans:
                ids = [r["id"] for r in await conn.fetch(ORPHAN_IDS_SQL, list(_LIVE_STATUSES), limit)]
                for qid in ids:
                    revived = await conn.fetchval(HEAL_SQL, qid, list(_LIVE_STATUSES))
                    if revived is not None:
                        healed += 1
                logger.warning(
                    "healed %d superseded-orphan queues back to review_pending "
                    "(limit=%d, remaining=%d)",
                    healed, limit, max(0, orphans - healed),
                )

        if orphans or no_proposal:
            verb = f"healed {healed}/{orphans}" if heal else "DETECTED"
            _send_alert(
                f"⚠️ intake invariant violated ({verb}): "
                f"{orphans} done-rows with only superseded proposals "
                f"(dead in /review), {no_proposal} done-rows with no proposal at all. "
                f"{'Run with --heal to revive.' if not heal else ''}".strip(),
                level="WARNING" if orphans else "INFO",
            )
        else:
            logger.info("intake invariant OK — no dead documents.")
        return 0
    finally:
        await pool.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Intake proposal-health sentinel — detects (and optionally heals) "
        "done-rows whose only proposal is superseded (dead in /review)."
    )
    p.add_argument(
        "--heal",
        action="store_true",
        help="revive superseded-orphans back to review_pending (default: report-only)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=500,
        help="max orphans to heal per run (default 500; report counts are unbounded)",
    )
    return p


async def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=os.getenv("INTAKE_SENTINEL_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    return await run(heal=args.heal, limit=args.limit)


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
