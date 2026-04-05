#!/usr/bin/env python3
"""Naga Claims DB — stats dashboard.

Shows growth metrics, quality indicators, and domain coverage.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/naga_stats.py
    PYTHONPATH=. python scripts/naga_stats.py --watch   # refresh every 30s
    PYTHONPATH=. python scripts/naga_stats.py --json    # machine-readable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone

import asyncpg

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag",
)


async def fetch_stats(conn: asyncpg.Connection) -> dict:
    stats: dict = {}

    # --- Totals ---
    stats["sessions_total"] = await conn.fetchval("SELECT COUNT(*) FROM naga_sessions")
    stats["claims_total"] = await conn.fetchval("SELECT COUNT(*) FROM naga_claims")
    stats["sources_total"] = await conn.fetchval("SELECT COUNT(*) FROM naga_sources")
    stats["evidence_total"] = await conn.fetchval("SELECT COUNT(*) FROM naga_claim_evidence")

    # --- Claims quality ---
    row = await conn.fetchrow("""
        SELECT
            ROUND(AVG(confidence)::numeric, 3)   AS avg_conf,
            ROUND(MIN(confidence)::numeric, 3)   AS min_conf,
            ROUND(MAX(confidence)::numeric, 3)   AS max_conf,
            ROUND(STDDEV(confidence)::numeric, 3) AS stddev_conf
        FROM naga_claims
    """)
    stats["confidence"] = dict(row) if row else {}

    # --- Confidence buckets ---
    buckets = await conn.fetch("""
        SELECT
            CASE
                WHEN confidence >= 0.8 THEN 'high   (>=0.8)'
                WHEN confidence >= 0.6 THEN 'medium (0.6-0.8)'
                WHEN confidence >= 0.4 THEN 'low    (0.4-0.6)'
                ELSE                        'weak   (<0.4)'
            END AS bucket,
            COUNT(*) AS n
        FROM naga_claims
        GROUP BY bucket
        ORDER BY bucket
    """)
    stats["confidence_buckets"] = {r["bucket"]: r["n"] for r in buckets}

    # --- Verification levels ---
    levels = await conn.fetch("""
        SELECT verification_level, COUNT(*) AS n
        FROM naga_claims
        GROUP BY verification_level
        ORDER BY n DESC
    """)
    stats["verification_levels"] = {r["verification_level"]: r["n"] for r in levels}

    # --- Domain breakdown ---
    domains = await conn.fetch("""
        SELECT domain, COUNT(*) AS n
        FROM naga_claims
        GROUP BY domain
        ORDER BY n DESC
    """)
    stats["domains"] = {r["domain"]: r["n"] for r in domains}

    # --- Sessions per tier ---
    tiers = await conn.fetch("""
        SELECT tier, COUNT(*) AS sessions, SUM(claims_extracted) AS claims
        FROM naga_sessions
        GROUP BY tier
        ORDER BY sessions DESC
    """)
    stats["tiers"] = [dict(r) for r in tiers]

    # --- Growth: claims per day ---
    daily = await conn.fetch("""
        SELECT
            DATE(valid_as_of) AS day,
            COUNT(*)          AS claims_added
        FROM naga_claims
        GROUP BY day
        ORDER BY day DESC
        LIMIT 7
    """)
    stats["daily_growth"] = [{"day": str(r["day"]), "claims": r["claims_added"]} for r in daily]

    # --- Top sessions by claims ---
    top_sessions = await conn.fetch("""
        SELECT
            s.query,
            s.tier,
            s.domain,
            s.claims_extracted,
            s.avg_confidence,
            s.duration_ms,
            s.completed_at
        FROM naga_sessions s
        ORDER BY s.claims_extracted DESC
        LIMIT 10
    """)
    stats["top_sessions"] = [dict(r) for r in top_sessions]

    # --- Avg claims/session, avg duration ---
    perf = await conn.fetchrow("""
        SELECT
            ROUND(AVG(claims_extracted)::numeric, 1) AS avg_claims_per_session,
            ROUND(AVG(duration_ms)::numeric, 0)      AS avg_duration_ms,
            ROUND(AVG(sources_found)::numeric, 1)    AS avg_sources_per_session
        FROM naga_sessions
        WHERE status = 'completed'
    """)
    stats["performance"] = dict(perf) if perf else {}

    # --- Evidence coverage (claims with at least 1 source) ---
    stats["claims_with_evidence"] = await conn.fetchval("""
        SELECT COUNT(DISTINCT claim_id) FROM naga_claim_evidence
    """)

    # --- Unique URLs in sources ---
    stats["unique_urls"] = await conn.fetchval("""
        SELECT COUNT(DISTINCT url) FROM naga_sources
    """)

    return stats


def render(stats: dict) -> str:
    lines = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines.append(f"\n{'='*65}")
    lines.append(f"  NAGA CLAIMS DB — STATS  ({now})")
    lines.append(f"{'='*65}")

    # Totals
    lines.append("\n  TOTALS")
    lines.append(f"  {'Sessions':<28} {stats['sessions_total']:>8}")
    lines.append(f"  {'Claims':<28} {stats['claims_total']:>8}")
    lines.append(f"  {'Sources (URLs)':<28} {stats['sources_total']:>8}  (unique: {stats['unique_urls']})")
    lines.append(f"  {'Evidence links':<28} {stats['evidence_total']:>8}")
    lines.append(f"  {'Claims with evidence':<28} {stats['claims_with_evidence']:>8}")

    # Performance
    p = stats.get("performance", {})
    if p:
        lines.append("\n  PERFORMANCE (completed sessions)")
        lines.append(f"  {'Avg claims/session':<28} {p.get('avg_claims_per_session', '?'):>8}")
        lines.append(f"  {'Avg duration':<28} {int(p.get('avg_duration_ms', 0) or 0) // 1000:>7}s")
        lines.append(f"  {'Avg sources/session':<28} {p.get('avg_sources_per_session', '?'):>8}")

    # Confidence
    c = stats.get("confidence", {})
    if c:
        lines.append("\n  CONFIDENCE SCORES")
        lines.append(f"  {'Average':<28} {c.get('avg_conf', '?'):>8}")
        lines.append(f"  {'Min / Max':<28} {c.get('min_conf', '?'):>4} / {c.get('max_conf', '?')}")
        lines.append(f"  {'Std dev':<28} {c.get('stddev_conf', '?'):>8}")

    # Buckets
    buckets = stats.get("confidence_buckets", {})
    if buckets:
        lines.append("\n  CONFIDENCE DISTRIBUTION")
        total = stats["claims_total"] or 1
        for label, n in sorted(buckets.items()):
            bar = "█" * int(n / total * 30)
            lines.append(f"  {label:<28} {n:>5}  {bar}")

    # Tiers
    tiers = stats.get("tiers", [])
    if tiers:
        lines.append("\n  BY TIER")
        for t in tiers:
            lines.append(f"  {t['tier']:<12} sessions={t['sessions']}  claims={t['claims'] or 0}")

    # Domains
    domains = stats.get("domains", {})
    if domains:
        lines.append("\n  BY DOMAIN")
        for dom, n in domains.items():
            lines.append(f"  {dom:<20} {n:>6} claims")

    # Verification levels
    vl = stats.get("verification_levels", {})
    if vl:
        lines.append("\n  VERIFICATION STATUS")
        for level, n in vl.items():
            lines.append(f"  {level:<28} {n:>6}")

    # Daily growth
    daily = stats.get("daily_growth", [])
    if daily:
        lines.append("\n  DAILY GROWTH (last 7 days)")
        for d in daily:
            bar = "▓" * min(d["claims"] // 5, 40)
            lines.append(f"  {d['day']}  {d['claims']:>5}  {bar}")

    # Top sessions
    top = stats.get("top_sessions", [])
    if top:
        lines.append("\n  TOP SESSIONS BY CLAIMS")
        for s in top[:5]:
            dur = int((s.get("duration_ms") or 0) // 1000)
            conf = s.get("avg_confidence") or 0
            query = (s.get("query") or "")[:50]
            lines.append(
                f"  [{s.get('tier','?'):5}] {s.get('claims_extracted',0):>3}cl  "
                f"conf={float(conf):.2f}  {dur:>4}s  {query}"
            )

    lines.append(f"\n{'='*65}\n")
    return "\n".join(lines)


async def main_async(as_json: bool, watch: bool, interval: int) -> None:
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2)

    try:
        while True:
            async with pool.acquire() as conn:
                stats = await fetch_stats(conn)

            if as_json:
                # Convert non-serializable types
                def default(o):
                    if hasattr(o, "isoformat"):
                        return o.isoformat()
                    return str(o)
                print(json.dumps(stats, default=default, indent=2))
            else:
                print(render(stats))

            if not watch:
                break

            print(f"  [refreshing in {interval}s — Ctrl+C to stop]\n")
            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        pass
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Naga Claims DB — stats dashboard")
    parser.add_argument("--watch", action="store_true", help="Refresh every N seconds")
    parser.add_argument("--interval", type=int, default=30, help="Watch interval in seconds (default: 30)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    args = parser.parse_args()

    asyncio.run(main_async(as_json=args.as_json, watch=args.watch, interval=args.interval))


if __name__ == "__main__":
    main()
