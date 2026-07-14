#!/usr/bin/env python3
"""Aggregate-only Intake quality and drain-capacity gate.

The report separates three concepts that are easy to conflate:

* recognition coverage: classified documents that did not end as ``unknown``;
* verified field acceptance: human-approved vs human-corrected field labels;
* disposal capacity: completed documents per hour compared with arrivals.

No document text, filename, phone, client id, or extracted value is selected or
printed. Raw HITL values remain in the Pro's local Postgres (Symbiosis Law 2).
Default mode is read-only reporting; ``--enforce`` only changes the exit code.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Any

import asyncpg

DEFAULT_DSN = "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
ACTIVE_STATUSES = ("pending", "ocr_done", "extracted", "validated")

OVERVIEW_SQL = """
SELECT
    count(*) FILTER (WHERE created_at >= now() - make_interval(hours => $1)) AS arrivals,
    count(*) FILTER (
        WHERE status = 'done'
          AND updated_at >= now() - make_interval(hours => $1)
    ) AS completions,
    count(*) FILTER (WHERE status = ANY($3::text[])) AS backlog,
    count(*) FILTER (
        WHERE status = 'dead'
          AND updated_at >= now() - make_interval(hours => $1)
    ) AS dead,
    count(*) FILTER (
        WHERE created_at >= now() - make_interval(hours => $1)
          AND stage_output->'classify' ? 'doc_type'
    ) AS classified,
    count(*) FILTER (
        WHERE created_at >= now() - make_interval(hours => $1)
          AND stage_output->'classify' ? 'doc_type'
          AND COALESCE(stage_output->'classify'->>'doc_type', 'unknown') <> 'unknown'
    ) AS recognized,
    percentile_cont(0.50) WITHIN GROUP (
        ORDER BY extract(epoch FROM (updated_at - created_at))
    ) FILTER (
        WHERE status = 'done'
          AND updated_at >= now() - make_interval(hours => $1)
    ) AS completion_p50_seconds,
    percentile_cont(0.95) WITHIN GROUP (
        ORDER BY extract(epoch FROM (updated_at - created_at))
    ) FILTER (
        WHERE status = 'done'
          AND updated_at >= now() - make_interval(hours => $1)
    ) AS completion_p95_seconds,
    percentile_cont(0.95) WITHIN GROUP (
        ORDER BY extract(epoch FROM (now() - created_at))
    ) FILTER (WHERE status = ANY($3::text[])) AS backlog_age_p95_seconds
FROM intake_queue
WHERE ($2::text IS NULL OR source = $2)
"""

CORRECTIONS_SQL = """
SELECT
    count(*) FILTER (WHERE c.outcome = 'approved') AS approved_fields,
    count(*) FILTER (WHERE c.outcome = 'corrected') AS corrected_fields,
    count(*) FILTER (WHERE c.outcome = 'auto_committed') AS auto_fields
FROM intake_corrections c
JOIN intake_queue q ON q.id = c.queue_id
WHERE c.verified_at >= now() - make_interval(hours => $1)
  AND c.field_name NOT LIKE '\\_\\_%' ESCAPE '\\'
  AND ($2::text IS NULL OR q.source = $2)
"""

STAGE_SQL = """
SELECT m.stage,
       count(*) AS samples,
       round(avg(m.latency_ms))::bigint AS avg_ms,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY m.latency_ms))::bigint AS p95_ms
FROM intake_stage_metrics m
JOIN intake_queue q ON q.id = m.queue_id
WHERE m.ts >= now() - make_interval(hours => $1)
  AND ($2::text IS NULL OR q.source = $2)
GROUP BY m.stage
ORDER BY m.stage
"""


@dataclass(frozen=True)
class Targets:
    recognition_pct: float = 95.0
    verified_field_acceptance_pct: float = 97.0
    minimum_verified_fields: int = 100
    backlog_drain_ratio: float = 1.10
    maximum_dead: int = 0


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(100.0 * numerator / denominator, 2)


def build_metrics(
    overview: dict[str, Any],
    corrections: dict[str, Any],
    *,
    hours: int,
) -> dict[str, Any]:
    """Normalize aggregate SQL rows and derive rate metrics."""
    arrivals = int(overview.get("arrivals") or 0)
    completions = int(overview.get("completions") or 0)
    classified = int(overview.get("classified") or 0)
    recognized = int(overview.get("recognized") or 0)
    approved = int(corrections.get("approved_fields") or 0)
    corrected = int(corrections.get("corrected_fields") or 0)
    human_labels = approved + corrected
    arrival_rate = arrivals / hours
    completion_rate = completions / hours
    drain_ratio = completion_rate / arrival_rate if arrival_rate > 0 else None
    return {
        "window_hours": hours,
        "arrivals": arrivals,
        "completions": completions,
        "arrivals_per_hour": round(arrival_rate, 2),
        "completions_per_hour": round(completion_rate, 2),
        "backlog": int(overview.get("backlog") or 0),
        "dead": int(overview.get("dead") or 0),
        "classified": classified,
        "recognized": recognized,
        "recognition_coverage_pct": _pct(recognized, classified),
        "approved_fields": approved,
        "corrected_fields": corrected,
        "auto_committed_fields": int(corrections.get("auto_fields") or 0),
        "human_verified_fields": human_labels,
        "verified_field_acceptance_pct": _pct(approved, human_labels),
        "backlog_drain_ratio": round(drain_ratio, 3)
        if drain_ratio is not None
        else None,
        "completion_p50_seconds": _optional_float(
            overview.get("completion_p50_seconds")
        ),
        "completion_p95_seconds": _optional_float(
            overview.get("completion_p95_seconds")
        ),
        "backlog_age_p95_seconds": _optional_float(
            overview.get("backlog_age_p95_seconds")
        ),
    }


def _optional_float(value: Any) -> float | None:
    return round(float(value), 2) if value is not None else None


def evaluate_targets(metrics: dict[str, Any], targets: Targets) -> dict[str, str]:
    """Return PASS/FAIL/INSUFFICIENT_SAMPLE for each explicit operating target."""
    recognition = metrics.get("recognition_coverage_pct")
    verified = metrics.get("verified_field_acceptance_pct")
    human_labels = int(metrics.get("human_verified_fields") or 0)
    drain_ratio = metrics.get("backlog_drain_ratio")
    backlog = int(metrics.get("backlog") or 0)
    dead = int(metrics.get("dead") or 0)
    return {
        "recognition_coverage": (
            "INSUFFICIENT_SAMPLE"
            if recognition is None
            else "PASS"
            if float(recognition) >= targets.recognition_pct
            else "FAIL"
        ),
        "verified_field_acceptance": (
            "INSUFFICIENT_SAMPLE"
            if human_labels < targets.minimum_verified_fields or verified is None
            else "PASS"
            if float(verified) >= targets.verified_field_acceptance_pct
            else "FAIL"
        ),
        "backlog_drain": (
            "PASS"
            if backlog == 0
            else "INSUFFICIENT_SAMPLE"
            if drain_ratio is None
            else "PASS"
            if float(drain_ratio) >= targets.backlog_drain_ratio
            else "FAIL"
        ),
        "dead_letter": "PASS" if dead <= targets.maximum_dead else "FAIL",
    }


async def collect_report(
    *,
    dsn: str,
    source: str | None,
    hours: int,
    targets: Targets,
) -> dict[str, Any]:
    """Collect aggregate metrics from the local Intake database."""
    conn = await asyncpg.connect(dsn)
    try:
        overview_row = await conn.fetchrow(
            OVERVIEW_SQL, hours, source, list(ACTIVE_STATUSES)
        )
        correction_row = await conn.fetchrow(CORRECTIONS_SQL, hours, source)
        stage_rows = await conn.fetch(STAGE_SQL, hours, source)
    finally:
        await conn.close()
    metrics = build_metrics(dict(overview_row), dict(correction_row), hours=hours)
    stages = [
        {
            "stage": row["stage"],
            "samples": int(row["samples"]),
            "avg_ms": int(row["avg_ms"] or 0),
            "p95_ms": int(row["p95_ms"] or 0),
        }
        for row in stage_rows
    ]
    return {
        "source": source or "all",
        "metrics": metrics,
        "targets": asdict(targets),
        "gate": evaluate_targets(metrics, targets),
        "stage_latency": stages,
    }


def _render_text(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    gate = report["gate"]
    lines = [
        f"Intake capacity/quality — source={report['source']} window={metrics['window_hours']}h",
        (
            f"flow: arrivals={metrics['arrivals']} ({metrics['arrivals_per_hour']}/h) "
            f"completed={metrics['completions']} ({metrics['completions_per_hour']}/h) "
            f"backlog={metrics['backlog']} drain_ratio={metrics['backlog_drain_ratio']}"
        ),
        (
            f"recognition: {metrics['recognized']}/{metrics['classified']} "
            f"known={metrics['recognition_coverage_pct']}% gate={gate['recognition_coverage']}"
        ),
        (
            f"verified fields: approved={metrics['approved_fields']} "
            f"corrected={metrics['corrected_fields']} "
            f"acceptance={metrics['verified_field_acceptance_pct']}% "
            f"gate={gate['verified_field_acceptance']}"
        ),
        (
            f"safety: dead={metrics['dead']} gate={gate['dead_letter']} "
            f"backlog_gate={gate['backlog_drain']}"
        ),
    ]
    for stage in report["stage_latency"]:
        lines.append(
            f"stage {stage['stage']}: n={stage['samples']} avg={stage['avg_ms']}ms "
            f"p95={stage['p95_ms']}ms"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--source", default="whatsapp")
    parser.add_argument("--all-sources", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("--recognition-target", type=float, default=95.0)
    parser.add_argument("--field-acceptance-target", type=float, default=97.0)
    parser.add_argument("--minimum-verified-fields", type=int, default=100)
    parser.add_argument("--drain-ratio-target", type=float, default=1.10)
    return parser


async def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.hours <= 0:
        raise ValueError("--hours must be positive")
    targets = Targets(
        recognition_pct=args.recognition_target,
        verified_field_acceptance_pct=args.field_acceptance_target,
        minimum_verified_fields=args.minimum_verified_fields,
        backlog_drain_ratio=args.drain_ratio_target,
    )
    report = await collect_report(
        dsn=os.getenv("INTAKE_DATABASE_URL", DEFAULT_DSN),
        source=None if args.all_sources else args.source,
        hours=args.hours,
        targets=targets,
    )
    rendered = (
        json.dumps(report, indent=2, sort_keys=True)
        if args.json
        else _render_text(report)
    )
    sys.stdout.write(rendered + "\n")
    if args.enforce and "FAIL" in report["gate"].values():
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
