#!/usr/bin/env python3
"""
Weekly Query Analytics Report Generator

Generates a weekly summary of RAG query analytics and outputs it as JSON
or sends it via the configured notification channel.

Usage:
    # Generate report to stdout (JSON)
    python scripts/automation/weekly_query_analytics_report.py

    # Generate report for last 14 days
    python scripts/automation/weekly_query_analytics_report.py --days 14

    # Save to file
    python scripts/automation/weekly_query_analytics_report.py --output /tmp/weekly_report.json

Automation:
    Add to crontab for weekly execution (every Monday at 8am):
    0 8 * * 1 cd /app && python scripts/automation/weekly_query_analytics_report.py --output /tmp/weekly_report.json
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _out(msg: str = "") -> None:
    """Write to stdout (CLI output, not logging)."""
    sys.stdout.write(msg + "\n")


async def generate_weekly_report(database_url: str, days: int = 7) -> dict:
    """
    Generate a comprehensive weekly analytics report.

    Args:
        database_url: PostgreSQL connection URL
        days: Lookback period in days

    Returns:
        Report dictionary
    """
    conn = await asyncpg.connect(database_url)

    try:
        # 1. Overall stats
        overall = await conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total_queries,
                COUNT(*) FILTER (WHERE chunks_retrieved_count = 0) AS failed_queries,
                COUNT(*) FILTER (WHERE chunks_retrieved_count > 0) AS successful_queries,
                ROUND(AVG(execution_time_ms)::numeric, 0) AS avg_latency_ms,
                ROUND(AVG(token_usage_total)::numeric, 0) AS avg_tokens,
                ROUND(SUM(cost_usd)::numeric, 4) AS total_cost_usd,
                COUNT(DISTINCT user_id) AS unique_users,
                COUNT(DISTINCT session_id) AS unique_sessions
            FROM query_analytics
            WHERE created_at >= NOW() - ($1 || ' days')::interval
            """,
            str(days),
        )

        # 2. Top failed queries
        failed = await conn.fetch(
            """
            SELECT
                query_text,
                COUNT(*) AS fail_count,
                MAX(created_at) AS last_seen
            FROM query_analytics
            WHERE chunks_retrieved_count = 0
              AND created_at >= NOW() - ($1 || ' days')::interval
            GROUP BY query_text
            ORDER BY fail_count DESC
            LIMIT 10
            """,
            str(days),
        )

        # 3. Collection hit rates
        collections = await conn.fetch(
            """
            SELECT
                col AS collection_name,
                COUNT(*) AS total_queries,
                COUNT(*) FILTER (WHERE chunks_retrieved_count > 0) AS successful,
                ROUND(
                    COUNT(*) FILTER (WHERE chunks_retrieved_count > 0)::numeric
                    / NULLIF(COUNT(*), 0) * 100, 1
                ) AS hit_rate_percent
            FROM query_analytics,
                 LATERAL unnest(collections_queried) AS col
            WHERE created_at >= NOW() - ($1 || ' days')::interval
            GROUP BY col
            ORDER BY total_queries DESC
            """,
            str(days),
        )

        # 4. Satisfaction
        satisfaction = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE user_feedback = 'thumbs_up') AS thumbs_up,
                COUNT(*) FILTER (WHERE user_feedback = 'thumbs_down') AS thumbs_down,
                COUNT(*) FILTER (WHERE user_feedback IS NOT NULL) AS total_feedback,
                ROUND(
                    COUNT(*) FILTER (WHERE user_feedback = 'thumbs_up')::numeric
                    / NULLIF(COUNT(*) FILTER (WHERE user_feedback IS NOT NULL), 0) * 100, 1
                ) AS satisfaction_percent
            FROM query_analytics
            WHERE created_at >= NOW() - ($1 || ' days')::interval
            """,
            str(days),
        )

        # 5. Daily volume
        daily = await conn.fetch(
            """
            SELECT
                date_trunc('day', created_at) AS day,
                COUNT(*) AS queries,
                COUNT(*) FILTER (WHERE chunks_retrieved_count = 0) AS failed,
                ROUND(AVG(execution_time_ms)::numeric, 0) AS avg_latency_ms
            FROM query_analytics
            WHERE created_at >= NOW() - ($1 || ' days')::interval
            GROUP BY day
            ORDER BY day
            """,
            str(days),
        )

        # 6. Top models used
        models = await conn.fetch(
            """
            SELECT
                model_used,
                COUNT(*) AS query_count,
                ROUND(AVG(execution_time_ms)::numeric, 0) AS avg_latency_ms,
                ROUND(SUM(cost_usd)::numeric, 4) AS total_cost
            FROM query_analytics
            WHERE created_at >= NOW() - ($1 || ' days')::interval
              AND model_used IS NOT NULL
            GROUP BY model_used
            ORDER BY query_count DESC
            """,
            str(days),
        )

        # Build report
        total_queries = overall["total_queries"] or 0
        failed_queries = overall["failed_queries"] or 0
        success_rate = round((1 - failed_queries / max(total_queries, 1)) * 100, 1)

        report = {
            "report_type": "weekly_query_analytics",
            "period_days": days,
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_queries": total_queries,
                "successful_queries": overall["successful_queries"] or 0,
                "failed_queries": failed_queries,
                "success_rate_percent": success_rate,
                "avg_latency_ms": int(overall["avg_latency_ms"] or 0),
                "avg_tokens_per_query": int(overall["avg_tokens"] or 0),
                "total_cost_usd": float(overall["total_cost_usd"] or 0),
                "unique_users": overall["unique_users"] or 0,
                "unique_sessions": overall["unique_sessions"] or 0,
            },
            "satisfaction": {
                "thumbs_up": satisfaction["thumbs_up"] or 0,
                "thumbs_down": satisfaction["thumbs_down"] or 0,
                "total_feedback": satisfaction["total_feedback"] or 0,
                "satisfaction_percent": float(satisfaction["satisfaction_percent"] or 0),
            },
            "top_failed_queries": [
                {
                    "query": r["query_text"],
                    "fail_count": r["fail_count"],
                    "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
                }
                for r in failed
            ],
            "collection_hit_rates": [
                {
                    "collection": r["collection_name"],
                    "total_queries": r["total_queries"],
                    "successful": r["successful"],
                    "hit_rate_percent": float(r["hit_rate_percent"] or 0),
                }
                for r in collections
            ],
            "daily_volume": [
                {
                    "date": r["day"].strftime("%Y-%m-%d") if r["day"] else None,
                    "queries": r["queries"],
                    "failed": r["failed"],
                    "avg_latency_ms": int(r["avg_latency_ms"] or 0),
                }
                for r in daily
            ],
            "models_used": [
                {
                    "model": r["model_used"],
                    "query_count": r["query_count"],
                    "avg_latency_ms": int(r["avg_latency_ms"] or 0),
                    "total_cost_usd": float(r["total_cost"] or 0),
                }
                for r in models
            ],
        }

        return report

    finally:
        await conn.close()


def format_report_text(report: dict) -> str:
    """Format report as human-readable text for notifications."""
    s = report["summary"]
    sat = report["satisfaction"]

    lines = [
        f"📊 WEEKLY QUERY ANALYTICS REPORT ({report['period_days']} days)",
        f"Generated: {report['generated_at'][:10]}",
        "",
        "── SUMMARY ──",
        f"  Total Queries:    {s['total_queries']}",
        f"  Success Rate:     {s['success_rate_percent']}%",
        f"  Failed Queries:   {s['failed_queries']}",
        f"  Avg Latency:      {s['avg_latency_ms']}ms",
        f"  Total Cost:       ${s['total_cost_usd']:.4f}",
        f"  Unique Users:     {s['unique_users']}",
        "",
        "── SATISFACTION ──",
        f"  👍 {sat['thumbs_up']}  👎 {sat['thumbs_down']}  ({sat['satisfaction_percent']}%)",
        "",
    ]

    if report["top_failed_queries"]:
        lines.append("── TOP FAILED QUERIES ──")
        for i, q in enumerate(report["top_failed_queries"][:5], 1):
            lines.append(f"  {i}. [{q['fail_count']}x] {q['query'][:80]}")
        lines.append("")

    if report["collection_hit_rates"]:
        lines.append("── COLLECTION HIT RATES ──")
        for c in report["collection_hit_rates"]:
            bar = "█" * int(c["hit_rate_percent"] / 10) + "░" * (
                10 - int(c["hit_rate_percent"] / 10)
            )
            lines.append(
                f"  {c['collection']:<25} {bar} {c['hit_rate_percent']}% ({c['total_queries']} queries)"
            )
        lines.append("")

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="Generate weekly query analytics report")
    parser.add_argument("--days", type=int, default=7, help="Lookback period in days")
    parser.add_argument("--output", type=str, help="Output file path (JSON)")
    parser.add_argument(
        "--text", action="store_true", help="Output human-readable text instead of JSON"
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    logger.info(f"Generating weekly report for last {args.days} days...")
    report = await generate_weekly_report(database_url, days=args.days)

    output = format_report_text(report) if args.text else json.dumps(report, indent=2, default=str)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        logger.info(f"Report saved to {args.output}")
    else:
        _out(output)

    logger.info(
        f"Report complete: {report['summary']['total_queries']} queries, "
        f"{report['summary']['success_rate_percent']}% success rate"
    )


if __name__ == "__main__":
    asyncio.run(main())
