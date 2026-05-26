"""WA Copilot — Sprint 1 S1.12 Baseline Metrics Dashboard + Eval Set Builder.

Closes Sprint 1 with two artifacts:

1. ``--snapshot``: query the 13 baseline/current metrics defined in the
   Codex + DeepSeek round-2 design and emit either a JSON dict or a
   Markdown summary table (baseline → 30d target → current → status).

2. ``--eval-set``: select 50 random conversations that have both
   ``client_id`` and ``practice_id`` populated post-Sprint-1, emit a
   JSONL ground-truth template (operator hand-labels
   ``expected_recommended_action``).

CLI:
    python -m backend.services.wa_copilot.metrics_dashboard \\
        [--snapshot | --eval-set] \\
        [--format json|markdown] \\
        [--output PATH]

Read-only. No DB writes. Safe to run concurrently with S1.3 resolver.

Metric set (Codex + DeepSeek round 2):
    identity_match_pct, practice_link_pct, conversations_total,
    extractions_total, extractions_by_fact_type, entity_links_total,
    action_queue_total, action_queue_by_status, action_queue_by_type,
    action_queue_resolved_ratio, time_to_first_response_median_min,
    team_promises_resolved_ratio, re_engaged_leads_count
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

METRICS_VERSION = "v1.0-2026-05-25"
EXTRACTOR_VERSION = "v1.0-2026-05-25"  # match S1.5 pilot extractor

# Baseline + 30d targets (Codex + DeepSeek round 2 spec).
TARGETS: dict[str, dict[str, Any]] = {
    "identity_match_pct": {
        "baseline": 2.0,
        "target": 60.0,
        "unit": "%",
        "direction": "up",
    },
    "practice_link_pct": {
        "baseline": 0.7,
        "target": 40.0,
        "unit": "%",
        "direction": "up",
    },
    "action_queue_resolved_ratio": {
        "baseline": 0.0,
        "target": 80.0,
        "unit": "%",
        "direction": "up",
    },
    "time_to_first_response_median_min": {
        "baseline": 120.0,
        "target": 30.0,
        "unit": "min",
        "direction": "down",
    },
    "team_promises_resolved_ratio": {
        "baseline": None,
        "target": 55.0,
        "unit": "%",
        "direction": "up",
    },
    "re_engaged_leads_count": {
        "baseline": 0,
        "target": 8,
        "unit": "count",
        "direction": "up",
    },
}

EVAL_SET_SIZE = 50


# --------------------------------------------------------------------------- #
# DSN helpers (reuse pattern from staging_promoter / identity_resolver)
# --------------------------------------------------------------------------- #


def _build_dsn_local() -> str:
    """Resolve a local-proxy DSN, mirroring the pattern used by other S1 tools."""
    db_url = os.environ.get("DATABASE_URL", "")
    if "127.0.0.1:15432" in db_url or "localhost:15432" in db_url:
        return db_url
    fly_url = os.environ.get("DATABASE_URL_FLY", "")
    m = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@", fly_url)
    if not m:
        return db_url
    user, pwd = m.group(1), m.group(2)
    return f"postgresql://{user}:{pwd}@127.0.0.1:15432/nuzantara_rag"


# --------------------------------------------------------------------------- #
# Snapshot data structures
# --------------------------------------------------------------------------- #


@dataclass
class MetricRow:
    name: str
    current: Any
    baseline: Any = None
    target: Any = None
    unit: str = ""
    direction: str = "up"
    status: str = "N/A"  # GREEN | YELLOW | RED | N/A
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Snapshot:
    generated_at: str
    metrics_version: str
    summary: list[MetricRow] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# SQL helpers
# --------------------------------------------------------------------------- #


async def _scalar(conn: asyncpg.Connection, sql: str, *args: Any) -> Any:
    """Fetch single scalar; return None if no row."""
    val = await conn.fetchval(sql, *args)
    return val


async def _fetch_grouped(
    conn: asyncpg.Connection, sql: str, *args: Any
) -> dict[str, int]:
    """Return ``{label: count}`` from a 2-col SQL (label, count)."""
    rows = await conn.fetch(sql, *args)
    return {(r[0] if r[0] is not None else "<null>"): int(r[1]) for r in rows}


# --------------------------------------------------------------------------- #
# Metric queries
# --------------------------------------------------------------------------- #


async def _identity_match_pct(conn: asyncpg.Connection) -> float:
    total = await _scalar(
        conn, "SELECT COUNT(*) FROM whatsapp_message_context"
    )
    if not total:
        return 0.0
    matched = await _scalar(
        conn,
        "SELECT COUNT(*) FROM whatsapp_message_context WHERE client_id IS NOT NULL",
    )
    return round(100.0 * (matched or 0) / total, 2)


async def _practice_link_pct(conn: asyncpg.Connection) -> float:
    total = await _scalar(
        conn,
        "SELECT COUNT(*) FROM whatsapp_message_context WHERE conversation_id IS NOT NULL",
    )
    if not total:
        return 0.0
    linked = await _scalar(
        conn,
        "SELECT COUNT(*) FROM whatsapp_message_context "
        "WHERE conversation_id IS NOT NULL AND practice_id IS NOT NULL",
    )
    return round(100.0 * (linked or 0) / total, 2)


async def _conversations_total(conn: asyncpg.Connection) -> int:
    return int(await _scalar(conn, "SELECT COUNT(*) FROM whatsapp_conversations") or 0)


async def _extractions_total(conn: asyncpg.Connection) -> int:
    return int(
        await _scalar(
            conn,
            "SELECT COUNT(*) FROM whatsapp_extractions WHERE extractor_version=$1",
            EXTRACTOR_VERSION,
        )
        or 0
    )


async def _extractions_by_fact_type(conn: asyncpg.Connection) -> dict[str, int]:
    return await _fetch_grouped(
        conn,
        "SELECT fact_type, COUNT(*) AS n FROM whatsapp_extractions "
        "WHERE extractor_version=$1 GROUP BY fact_type ORDER BY n DESC",
        EXTRACTOR_VERSION,
    )


async def _entity_links_total(conn: asyncpg.Connection) -> int:
    return int(await _scalar(conn, "SELECT COUNT(*) FROM whatsapp_entity_links") or 0)


async def _action_queue_total(conn: asyncpg.Connection) -> int:
    return int(await _scalar(conn, "SELECT COUNT(*) FROM action_queue") or 0)


async def _action_queue_by_status(conn: asyncpg.Connection) -> dict[str, int]:
    return await _fetch_grouped(
        conn,
        "SELECT status, COUNT(*) FROM action_queue GROUP BY status ORDER BY COUNT(*) DESC",
    )


async def _action_queue_by_type(conn: asyncpg.Connection) -> dict[str, int]:
    return await _fetch_grouped(
        conn,
        "SELECT action_type, COUNT(*) FROM action_queue "
        "GROUP BY action_type ORDER BY COUNT(*) DESC",
    )


async def _action_queue_resolved_ratio(conn: asyncpg.Connection) -> float:
    total = await _scalar(conn, "SELECT COUNT(*) FROM action_queue")
    if not total:
        return 0.0
    resolved = await _scalar(
        conn,
        "SELECT COUNT(*) FROM action_queue WHERE status IN ('done','dismissed')",
    )
    return round(100.0 * (resolved or 0) / total, 2)


async def _time_to_first_response_median_min(
    conn: asyncpg.Connection,
) -> float | None:
    """Median TTFR per conversation: first inbound→first outbound delta in minutes.

    Uses ``whatsapp_message_context.conversation_id`` + ``direction`` and the
    ``message_date`` column (capture timestamp on the message itself).
    """
    sql = """
        WITH per_conv AS (
            SELECT conversation_id,
                MIN(message_date) FILTER (WHERE direction='inbound')  AS first_in,
                MIN(message_date) FILTER (WHERE direction='outbound') AS first_out
            FROM whatsapp_message_context
            WHERE conversation_id IS NOT NULL
              AND message_date IS NOT NULL
            GROUP BY conversation_id
        ),
        deltas AS (
            SELECT EXTRACT(EPOCH FROM (first_out - first_in))/60.0 AS ttfr_min
            FROM per_conv
            WHERE first_in IS NOT NULL
              AND first_out IS NOT NULL
              AND first_out >= first_in
        )
        SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ttfr_min) FROM deltas
    """
    val = await _scalar(conn, sql)
    return round(float(val), 2) if val is not None else None


async def _team_promises_resolved_ratio(conn: asyncpg.Connection) -> float:
    total = await _scalar(conn, "SELECT COUNT(*) FROM team_promises")
    if not total:
        return 0.0
    resolved = await _scalar(
        conn, "SELECT COUNT(*) FROM team_promises WHERE resolved IS TRUE"
    )
    return round(100.0 * (resolved or 0) / total, 2)


async def _re_engaged_leads_count(conn: asyncpg.Connection) -> int:
    """Distinct client_ids whose followup_team_commitment was resolved >7d after creation.

    Captures "re-engagement" — actions that sat in the queue for a week+
    and then closed (operator/team revived the lead).
    """
    sql = """
        SELECT COUNT(DISTINCT client_id)
        FROM action_queue
        WHERE action_type = 'followup_team_commitment'
          AND resolved_at IS NOT NULL
          AND resolved_at > created_at + INTERVAL '7 days'
    """
    return int(await _scalar(conn, sql) or 0)


# --------------------------------------------------------------------------- #
# Status calculator
# --------------------------------------------------------------------------- #


def _status_for(value: Any, target: Any, baseline: Any, direction: str) -> str:
    """Return RED/YELLOW/GREEN.

    Direction ``up``: GREEN if value >= target, YELLOW if value >= midpoint, else RED.
    Direction ``down``: GREEN if value <= target, YELLOW if value <= midpoint, else RED.
    """
    if value is None or target is None:
        return "N/A"
    try:
        v = float(value)
        t = float(target)
    except (TypeError, ValueError):
        return "N/A"
    if baseline is None:
        # No baseline: simple GREEN if we hit target, else YELLOW if any progress, else RED.
        if direction == "up":
            return "GREEN" if v >= t else ("YELLOW" if v > 0 else "RED")
        return "GREEN" if v <= t else ("YELLOW" if v > 0 else "RED")
    try:
        b = float(baseline)
    except (TypeError, ValueError):
        b = 0.0
    midpoint = (b + t) / 2.0
    if direction == "up":
        if v >= t:
            return "GREEN"
        if v >= midpoint:
            return "YELLOW"
        return "RED"
    # direction == 'down'
    if v <= t:
        return "GREEN"
    if v <= midpoint:
        return "YELLOW"
    return "RED"


# --------------------------------------------------------------------------- #
# Snapshot orchestrator
# --------------------------------------------------------------------------- #


async def build_snapshot(pool: asyncpg.Pool) -> Snapshot:
    from datetime import datetime, timezone

    snap = Snapshot(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        metrics_version=METRICS_VERSION,
    )

    async with pool.acquire() as conn:
        # Headline metrics (with targets)
        for name, fn in (
            ("identity_match_pct", _identity_match_pct),
            ("practice_link_pct", _practice_link_pct),
            ("action_queue_resolved_ratio", _action_queue_resolved_ratio),
            ("time_to_first_response_median_min", _time_to_first_response_median_min),
            ("team_promises_resolved_ratio", _team_promises_resolved_ratio),
            ("re_engaged_leads_count", _re_engaged_leads_count),
        ):
            current = await fn(conn)
            tgt = TARGETS[name]
            status = _status_for(current, tgt["target"], tgt["baseline"], tgt["direction"])
            snap.summary.append(
                MetricRow(
                    name=name,
                    current=current,
                    baseline=tgt["baseline"],
                    target=tgt["target"],
                    unit=tgt["unit"],
                    direction=tgt["direction"],
                    status=status,
                )
            )

        # Counts (no targets — info only)
        snap.extras["conversations_total"] = await _conversations_total(conn)
        snap.extras["extractions_total"] = await _extractions_total(conn)
        snap.extras["extractions_by_fact_type"] = await _extractions_by_fact_type(conn)
        snap.extras["entity_links_total"] = await _entity_links_total(conn)
        snap.extras["action_queue_total"] = await _action_queue_total(conn)
        snap.extras["action_queue_by_status"] = await _action_queue_by_status(conn)
        snap.extras["action_queue_by_type"] = await _action_queue_by_type(conn)

    return snap


# --------------------------------------------------------------------------- #
# Snapshot formatters
# --------------------------------------------------------------------------- #


def snapshot_to_json(snap: Snapshot) -> str:
    payload: dict[str, Any] = {
        "generated_at": snap.generated_at,
        "metrics_version": snap.metrics_version,
        "summary": [
            {
                "name": r.name,
                "current": r.current,
                "baseline": r.baseline,
                "target": r.target,
                "unit": r.unit,
                "direction": r.direction,
                "status": r.status,
            }
            for r in snap.summary
        ],
        "extras": snap.extras,
    }
    return json.dumps(payload, indent=2, default=str)


def _fmt_value(v: Any, unit: str) -> str:
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.2f}{unit}"
    if isinstance(v, int):
        return f"{v}{unit}" if unit and unit != "count" else str(v)
    return str(v)


def snapshot_to_markdown(snap: Snapshot) -> str:
    lines: list[str] = []
    lines.append(f"# WA Copilot — Baseline Snapshot ({snap.generated_at})")
    lines.append("")
    lines.append(f"_metrics_version: `{snap.metrics_version}`_")
    lines.append("")
    lines.append("## Summary (vs 30d targets)")
    lines.append("")
    lines.append("| Metric | Baseline | Target | Current | Status |")
    lines.append("|---|---|---|---|---|")
    for r in snap.summary:
        lines.append(
            "| "
            + " | ".join(
                [
                    r.name,
                    _fmt_value(r.baseline, r.unit),
                    _fmt_value(r.target, r.unit),
                    _fmt_value(r.current, r.unit),
                    r.status,
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Counts (info)")
    lines.append("")
    lines.append(f"- conversations_total: **{snap.extras.get('conversations_total')}**")
    lines.append(
        f"- extractions_total ({EXTRACTOR_VERSION}): **{snap.extras.get('extractions_total')}**"
    )
    lines.append(f"- entity_links_total: **{snap.extras.get('entity_links_total')}**")
    lines.append(f"- action_queue_total: **{snap.extras.get('action_queue_total')}**")
    lines.append("")
    by_status = snap.extras.get("action_queue_by_status", {})
    if by_status:
        lines.append("### action_queue by status")
        lines.append("")
        for s, n in by_status.items():
            lines.append(f"- {s}: {n}")
        lines.append("")
    by_type = snap.extras.get("action_queue_by_type", {})
    if by_type:
        lines.append("### action_queue by action_type")
        lines.append("")
        for t, n in by_type.items():
            lines.append(f"- {t}: {n}")
        lines.append("")
    by_fact = snap.extras.get("extractions_by_fact_type", {})
    if by_fact:
        lines.append("### extractions by fact_type")
        lines.append("")
        for f, n in by_fact.items():
            lines.append(f"- {f}: {n}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Eval-set builder
# --------------------------------------------------------------------------- #


async def build_eval_set(pool: asyncpg.Pool, size: int = EVAL_SET_SIZE) -> list[dict[str, Any]]:
    """Sample ``size`` random conversations with at minimum a ``client_id`` set.

    Preference cascade (best to broadest), accumulating up to ``size`` rows:
        1. conversations with BOTH ``client_id`` and ``practice_id`` set
        2. conversations with ``client_id`` set only (practice_id NULL —
           operator marks ``expected_practice_id`` MANUAL_TBD post-S1.7)

    Rationale: at S1.12 baseline, only ~3 conversations have both fields
    populated (S1.7 practice-link still pending full-corpus extraction).
    Restricting strictly to "both" produces a 3-row eval set that is
    useless for downstream metric labeling. The cascade keeps the eval
    set at ``size`` rows by widening the pool when needed; rows without
    practice link surface ``practice_id=null`` so the operator can
    flag them for re-labeling after S1.7 graduates to full corpus.
    """
    base_select = """
        SELECT
            e.conversation_id,
            e.client_id,
            cl.full_name AS client_full_name,
            e.practice_id,
            (
                SELECT json_build_object(
                    'id', m.id,
                    'body', LEFT(COALESCE(m.body, m.message_text, ''), 1000),
                    'timestamp', m.message_date
                )
                FROM whatsapp_message_context m
                WHERE m.conversation_id = e.conversation_id
                  AND m.direction = 'inbound'
                  AND m.message_date IS NOT NULL
                ORDER BY m.message_date ASC
                LIMIT 1
            ) AS first_customer_msg
        FROM eligible e
        LEFT JOIN clients cl ON cl.id = e.client_id
    """

    both_sql = f"""
        WITH eligible AS (
            SELECT c.conversation_id, c.client_id, c.practice_id
            FROM whatsapp_conversations c
            WHERE c.client_id IS NOT NULL
              AND c.practice_id IS NOT NULL
            ORDER BY random()
            LIMIT $1
        )
        {base_select}
    """

    client_only_sql = f"""
        WITH eligible AS (
            SELECT c.conversation_id, c.client_id, c.practice_id
            FROM whatsapp_conversations c
            WHERE c.client_id IS NOT NULL
              AND NOT (c.conversation_id = ANY($2::bigint[]))
            ORDER BY random()
            LIMIT $1
        )
        {base_select}
    """

    async with pool.acquire() as conn:
        rows_both = await conn.fetch(both_sql, size)
        rows = list(rows_both)
        if len(rows) < size:
            already = [int(r["conversation_id"]) for r in rows]
            remaining = size - len(rows)
            extra = await conn.fetch(client_only_sql, remaining, already)
            rows = rows + list(extra)

    out: list[dict[str, Any]] = []
    for r in rows:
        first_msg_raw = r["first_customer_msg"]
        # asyncpg returns JSON as str unless a codec is registered.
        if isinstance(first_msg_raw, str):
            try:
                first_msg = json.loads(first_msg_raw)
            except json.JSONDecodeError:
                first_msg = None
        else:
            first_msg = first_msg_raw
        client_id = r["client_id"]
        practice_id = r["practice_id"]
        out.append(
            {
                "conversation_id": int(r["conversation_id"]),
                "client_id": int(client_id) if client_id is not None else None,
                "client_full_name": r["client_full_name"],
                "practice_id": int(practice_id) if practice_id is not None else None,
                "first_customer_msg": first_msg,
                "expected_recommended_action": "MANUAL_TBD",
                "expected_client_id": int(client_id) if client_id is not None else None,
                "expected_practice_id": int(practice_id) if practice_id is not None else None,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


async def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="metrics_dashboard")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--snapshot", action="store_true", help="Emit baseline+current snapshot")
    mode.add_argument(
        "--eval-set",
        action="store_true",
        dest="eval_set",
        help="Emit JSONL eval set of 50 random labeled conversations",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Snapshot output format (ignored for --eval-set; always JSONL)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (stdout if omitted)",
    )
    parser.add_argument(
        "--eval-size",
        type=int,
        default=EVAL_SET_SIZE,
        help=f"Eval set size (default {EVAL_SET_SIZE})",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    dsn = _build_dsn_local()
    if not dsn:
        logger.error("DATABASE_URL or DATABASE_URL_FLY required")
        return 2

    pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=3,
        statement_cache_size=0,
        command_timeout=120,
    )

    try:
        if args.snapshot:
            snap = await build_snapshot(pool)
            text = (
                snapshot_to_markdown(snap)
                if args.format == "markdown"
                else snapshot_to_json(snap)
            )
            if args.output:
                with open(args.output, "w") as f:
                    f.write(text)
                logger.info("snapshot written to %s (%d bytes)", args.output, len(text))
            else:
                sys.stdout.write(text)
                if not text.endswith("\n"):
                    sys.stdout.write("\n")
            return 0

        if args.eval_set:
            records = await build_eval_set(pool, size=args.eval_size)
            jsonl = "\n".join(json.dumps(r, default=str) for r in records) + "\n"
            if args.output:
                with open(args.output, "w") as f:
                    f.write(jsonl)
                logger.info(
                    "eval set (%d records) written to %s", len(records), args.output
                )
            else:
                sys.stdout.write(jsonl)
            return 0
    finally:
        await pool.close()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))
