"""WR2 orchestrator per-step observability — writers for `wr2_orchestrator_metrics`.

Migration 203 (2026-05-27, `apps/backend-rag/backend/db/migrations_v2/203_wr2_orchestrator_metrics.sql`)
created this table with a full per-step schema (cascade tier, cost, latency,
retry) and it had ZERO production writer — self-attested pipeline health was
the only signal (research/operations/2026-07-14-wr2-deep-audit.md §1: "quality
contracts are self-attested... a self-attested instruction is not an enforced
contract"). Live DB check 2026-07-14: 46 rows total, all from a manual test
harness between 2026-05-26 and 2026-06-03 (`session_id LIKE 'manual-%'`) —
the table has been an invisible fossil for six weeks.

GROUNDING NOTE (2026-07-14, discovered while wiring this): the table's FK
(`carousel_id REFERENCES wr2_carousel_runs`) points at a table the CURRENT
production autonomous pipeline does not use for its own identity — pipeline
scripts (`wr2_draft_generator.py`, `wr2_image_generator.py`,
`wr2_html_render_apply.py`) key everything off `war_room_drafts.id`
(draft_id), a DIFFERENT table. `wr2_carousel_runs` is populated today only at
PUBLISH time via a find-or-create-by-topic idiom that already exists twice in
this repo (`wr2_ig_publish.py::_resolve_carousel_id`,
`apps/backend-rag/backend/app/routers/wr2_publish.py::_resolve_carousel_id`).
`resolve_carousel_id()` below mirrors that SAME idiom (reused, not
reinvented) so a metrics row recorded early in the pipeline (brief/image/
render) and the ledger row a later publish-time call resolves both land on
the SAME carousel_id for the same topic — one identity per topic, not a
second, disconnected identity model.

Connection pattern: `asyncpg.connect(DATABASE_URL)` per call, matching the
existing idiom in `wr2_supervisor.py` / `wr2_html_render_apply.py` (short-lived
CLI/cron script lifetime — CLAUDE.md Golden Rule 10's persistent-client
mandate targets long-running FastAPI request handlers, not one-shot scripts).
Call sites that already hold an open `asyncpg.Connection` (e.g.
`wr2_draft_generator.py::_process_one`) should pass it via `conn=` to avoid
opening a redundant connection.

FAIL-OPEN-LOUD CONTRACT: every public function here catches its own
exceptions, logs at WARNING, and returns a sentinel (None / False) — NEVER
raises to the caller. A metrics-recording failure must never turn a healthy
render into a failed one. This is the explicit design constraint from the
task brief and is enforced by the guilt tests in
`scripts/tests/test_wr2_orchestrator_metrics.py`.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
from typing import Any

import asyncpg

logger = logging.getLogger("wr2.orchestrator_metrics")

# Mirrors the migration 203 CHECK constraint verbatim — keep in sync.
VALID_STEPS = frozenset(
    {
        "brief_interpreter",
        "storyboarder",
        "image_prompt_author",
        "layout_composer",
        "critic",
        "playwright_render",
        "telegram_gate",
        "ig_publisher",
    }
)

# Mirrors the migration 203 CHECK constraint on `tier` verbatim.
VALID_TIERS = frozenset({1, 2, 3, 4})


def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL not set")
    return dsn


async def resolve_carousel_id(
    conn: asyncpg.Connection | None,
    *,
    topic: str,
    session_id: str,
    state: str = "drafted",
) -> str | None:
    """Find-or-create a `wr2_carousel_runs` row for `topic`.

    Mirrors the SAME find-or-create-by-topic idiom already used at publish
    time by `wr2_ig_publish.py::_resolve_carousel_id` and
    `wr2_publish.py::_resolve_carousel_id` — reused here (not reinvented) so
    metrics recorded early in the pipeline resolve to the same carousel_id a
    later publish-time call would find for the same topic.

    `conn=None` opens (and closes) a fresh connection — use this at call
    sites where a long-running step may have left the caller's own
    connection idle-closed by the pg-proxy (e.g. after a multi-minute
    Playwright render; `wr2_html_render_apply.py::_apply_one` reconnects
    `main_conn` for exactly this reason right after the render).

    Fail-open: returns None (never raises) on any DB error. Callers must
    treat None as "skip this metrics write", never as a render-blocking
    condition.
    """
    if not topic or not topic.strip():
        logger.warning("resolve_carousel_id SKIPPED: empty topic")
        return None
    owns_conn = conn is None
    try:
        if owns_conn:
            conn = await asyncpg.connect(_dsn(), timeout=10)
        row = await conn.fetchrow(
            "SELECT carousel_id FROM wr2_carousel_runs WHERE topic = $1 "
            "ORDER BY created_at DESC LIMIT 1",
            topic,
        )
        if row is not None:
            return str(row["carousel_id"])
        topic_hash = hashlib.sha256(topic.encode("utf-8")).hexdigest()
        new_row = await conn.fetchrow(
            "INSERT INTO wr2_carousel_runs (topic, topic_hash, state, session_id) "
            "VALUES ($1, $2, $3, $4) RETURNING carousel_id",
            topic,
            topic_hash,
            state,
            session_id,
        )
        return str(new_row["carousel_id"])
    except Exception as exc:  # noqa: BLE001 — fail-open-loud, see module docstring
        logger.warning("resolve_carousel_id FAILED for topic=%r: %s", topic[:80], exc)
        return None
    finally:
        if owns_conn and conn is not None:
            try:
                await conn.close()
            except Exception:  # noqa: BLE001 — closing a dead connection must not raise either
                pass


async def record_step(
    *,
    carousel_id: str | None,
    step_name: str,
    step_index: int,
    success: bool,
    model: str | None = None,
    tier: int = 1,
    latency_ms: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    cost_usd_figurative: float = 0.0,
    retry_count: int = 0,
    error_class: str | None = None,
    error_message: str | None = None,
    conn: asyncpg.Connection | None = None,
) -> bool:
    """Write one `wr2_orchestrator_metrics` row.

    FAIL-OPEN-LOUD: any failure (bad DSN, connection refused, FK violation
    because `carousel_id` doesn't exist, unknown `step_name`) is caught,
    logged at WARNING, and swallowed. NEVER raises. Returns True iff the row
    was actually written — callers in the pipeline should log/ignore the
    return value, never branch a render's control flow on it.

    `carousel_id=None` (e.g. `resolve_carousel_id` itself failed upstream) is
    a no-op, logged at WARNING, not an exception — the FK is NOT NULL so a
    write would fail anyway; skipping avoids a doomed round-trip.
    """
    if carousel_id is None:
        logger.warning(
            "record_step SKIPPED (no carousel_id) step=%s idx=%s", step_name, step_index
        )
        return False
    if step_name not in VALID_STEPS:
        logger.warning(
            "record_step SKIPPED (step_name=%r not in %s)", step_name, sorted(VALID_STEPS)
        )
        return False
    if tier not in VALID_TIERS:
        logger.warning("record_step SKIPPED (tier=%r not in %s)", tier, sorted(VALID_TIERS))
        return False

    owns_conn = conn is None
    try:
        if owns_conn:
            conn = await asyncpg.connect(_dsn(), timeout=10)
        await conn.execute(
            """
            INSERT INTO wr2_orchestrator_metrics
                (carousel_id, step_name, step_index, model, tier, latency_ms,
                 tokens_in, tokens_out, cost_usd_figurative, retry_count,
                 success, error_class, error_message)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            carousel_id,
            step_name,
            step_index,
            model,
            tier,
            latency_ms,
            tokens_in,
            tokens_out,
            cost_usd_figurative,
            retry_count,
            success,
            error_class,
            (error_message[:2000] if error_message else None),
        )
        return True
    except Exception as exc:  # noqa: BLE001 — fail-open-loud, see module docstring
        logger.warning(
            "record_step FAILED (metrics only, caller's render is UNAFFECTED) "
            "step=%s idx=%s carousel_id=%s: %s",
            step_name, step_index, carousel_id, exc,
        )
        return False
    finally:
        if owns_conn and conn is not None:
            try:
                await conn.close()
            except Exception:  # noqa: BLE001 — closing a dead connection must not raise either
                pass


async def _report(limit: int) -> None:
    conn = await asyncpg.connect(_dsn(), timeout=10)
    try:
        rows = await conn.fetch(
            """
            SELECT created_at, step_name, tier, model, latency_ms, retry_count,
                   success, cost_usd_figurative, carousel_id, error_class
              FROM wr2_orchestrator_metrics
             ORDER BY created_at DESC
             LIMIT $1
            """,
            limit,
        )
    finally:
        await conn.close()
    if not rows:
        print("wr2_orchestrator_metrics: no rows (table is empty)")
        return
    for r in rows:
        status = "OK" if r["success"] else f"FAIL({r['error_class'] or '?'})"
        print(
            f"{r['created_at']}  {r['step_name']:<18} tier={r['tier']} "
            f"model={(r['model'] or '-'):<20} latency={r['latency_ms'] if r['latency_ms'] is not None else '-'}ms "
            f"retry={r['retry_count']} {status:<20} cost=${r['cost_usd_figurative']} "
            f"carousel={str(r['carousel_id'])[:8]}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="wr2_orchestrator_metrics reporter — the table was invisible before this "
        "module existed (see module docstring); --report is the minimum viable window into it."
    )
    parser.add_argument(
        "--report",
        type=int,
        nargs="?",
        const=20,
        default=None,
        metavar="N",
        help="print the latest N rows (default 20) and exit",
    )
    args = parser.parse_args(argv)
    if args.report is not None:
        asyncio.run(_report(args.report))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
