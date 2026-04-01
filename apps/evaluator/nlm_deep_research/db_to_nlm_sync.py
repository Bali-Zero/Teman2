"""DB→NLM Sync Pipeline.

Extracts aggregate data from Nuzantara Postgres, renders it as narrative
Markdown, and uploads to NotebookLM notebooks for operational grounding.

Architecture:
    1. EXTRACT — SQL aggregate queries via asyncpg
    2. RENDER  — Python f-string templates → Markdown
    3. DIFF    — SHA256 hash comparison; skip unchanged sources
    4. UPLOAD  — nlm CLI: source_delete old + source_add new
    5. VERIFY  — Sanity query against NLM
    6. LOG     — State persistence + Telegram alert on failure

Usage:
    PYTHONPATH=. python -m apps.evaluator.nlm_deep_research.db_to_nlm_sync \
        --db-url "postgresql://..." \
        --nb-ops-id "..." --nb-intel-id "..." --nb-telemetry-id "..." \
        [--dry-run] [--force] [--log-level INFO]

Schedule: cron 04:30 WITA daily (after pg backup, before KB ingest)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Any, Optional

import asyncpg

from apps.evaluator.nlm_deep_research.db_nlm_state import (
    DBNLMLockError,
    DBNLMPIDLock,
    DBNLMStatePersistence,
    DBNLMSyncState,
)
from apps.evaluator.nlm_deep_research.db_nlm_templates import (
    render_client_segments,
    render_company_overview,
    render_compliance_radar,
    render_portfolio_snapshot,
    render_practices_pipeline,
    render_recent_changes,
    render_revenue_dashboard,
    render_system_health,
    render_tax_compliance,
    render_team_activity,
)

logger = logging.getLogger(__name__)

# NLM CLI binary
NLM_CLI = "nlm"

# Telegram alert config
TG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "413539912")


# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------

SQL_CLIENT_STATS = """
SELECT
    COUNT(*) FILTER (WHERE status = 'active' AND deleted_at IS NULL) AS active,
    COUNT(*) FILTER (WHERE status = 'prospect' AND deleted_at IS NULL) AS prospect,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days' AND deleted_at IS NULL) AS new_7d,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days' AND deleted_at IS NULL) AS new_30d,
    COUNT(*) FILTER (WHERE deleted_at IS NULL) AS total
FROM clients
"""

SQL_CLIENT_SEGMENTS = """
SELECT
    pt.category,
    COUNT(DISTINCT p.client_id) AS clients,
    COALESCE(SUM(p.quoted_price), 0) AS pipeline_value
FROM practices p
JOIN practice_types pt ON p.practice_type_id = pt.id
WHERE p.status NOT IN ('completed', 'cancelled')
  AND p.client_id IN (SELECT id FROM clients WHERE deleted_at IS NULL)
GROUP BY pt.category
ORDER BY clients DESC
"""

SQL_NATIONALITIES = """
SELECT
    COALESCE(NULLIF(nationality, ''), 'Unknown') AS nationality,
    COUNT(*) AS count
FROM clients
WHERE deleted_at IS NULL AND status = 'active'
GROUP BY nationality
ORDER BY count DESC
LIMIT 15
"""

SQL_PRACTICES_BY_STATUS = """
SELECT status, COUNT(*) AS count
FROM practices
WHERE client_id IN (SELECT id FROM clients WHERE deleted_at IS NULL)
GROUP BY status
ORDER BY count DESC
"""

SQL_BOTTLENECKS = """
SELECT
    pt.name AS practice_type,
    p.status,
    COUNT(*) AS count,
    AVG(EXTRACT(EPOCH FROM (NOW() - p.updated_at)) / 86400) AS avg_days_in_status
FROM practices p
JOIN practice_types pt ON p.practice_type_id = pt.id
WHERE p.status NOT IN ('completed', 'cancelled')
GROUP BY pt.name, p.status
HAVING AVG(EXTRACT(EPOCH FROM (NOW() - p.updated_at)) / 86400) > 7
ORDER BY avg_days_in_status DESC
LIMIT 15
"""

SQL_AVG_DURATION = """
SELECT
    pt.name AS practice_type,
    COUNT(*) AS completed,
    AVG(EXTRACT(EPOCH FROM (p.completion_date - p.start_date)) / 86400) AS avg_days
FROM practices p
JOIN practice_types pt ON p.practice_type_id = pt.id
WHERE p.status = 'completed'
  AND p.completion_date IS NOT NULL
  AND p.start_date IS NOT NULL
GROUP BY pt.name
ORDER BY avg_days DESC
"""

SQL_EXPIRING = """
SELECT
    p.client_id,
    pt.name AS practice_type,
    p.expiry_date,
    EXTRACT(DAY FROM (p.expiry_date - NOW())) AS days_remaining
FROM practices p
JOIN practice_types pt ON p.practice_type_id = pt.id
WHERE p.expiry_date IS NOT NULL
  AND p.expiry_date > NOW()
  AND p.expiry_date <= NOW() + $1::interval
  AND p.status NOT IN ('cancelled', 'completed')
ORDER BY p.expiry_date ASC
"""

SQL_MISSING_DOCS = """
SELECT
    p.client_id,
    pt.name AS practice_type,
    jsonb_array_length(COALESCE(p.missing_documents::jsonb, '[]'::jsonb)) AS missing_count
FROM practices p
JOIN practice_types pt ON p.practice_type_id = pt.id
WHERE p.status NOT IN ('completed', 'cancelled')
  AND jsonb_array_length(COALESCE(p.missing_documents::jsonb, '[]'::jsonb)) > 0
ORDER BY missing_count DESC
LIMIT 20
"""

SQL_INTERACTIONS_BY_MEMBER = """
SELECT
    COALESCE(NULLIF(team_member, ''), 'unassigned') AS team_member,
    COUNT(*) AS count
FROM interactions
WHERE interaction_date > NOW() - INTERVAL '30 days'
GROUP BY team_member
ORDER BY count DESC
"""

SQL_INTERACTIONS_BY_CHANNEL = """
SELECT
    COALESCE(channel, 'unknown') AS channel,
    COUNT(*) AS count
FROM interactions
WHERE interaction_date > NOW() - INTERVAL '30 days'
GROUP BY channel
ORDER BY count DESC
"""

SQL_SENTIMENT = """
SELECT
    COALESCE(sentiment, 'unknown') AS sentiment,
    COUNT(*) AS count
FROM interactions
WHERE interaction_date > NOW() - INTERVAL '30 days'
GROUP BY sentiment
ORDER BY count DESC
"""

SQL_NEW_CLIENTS_7D = """
SELECT id, nationality, created_at
FROM clients
WHERE created_at > NOW() - INTERVAL '7 days'
  AND deleted_at IS NULL
ORDER BY created_at DESC
LIMIT 20
"""

SQL_COMPLETED_7D = """
SELECT
    p.id, pt.name AS practice_type,
    p.completion_date, p.actual_price, p.client_id
FROM practices p
JOIN practice_types pt ON p.practice_type_id = pt.id
WHERE p.completion_date > NOW() - INTERVAL '7 days'
  AND p.status = 'completed'
ORDER BY p.completion_date DESC
LIMIT 20
"""

SQL_NEW_PRACTICES_7D = """
SELECT
    p.id, pt.name AS practice_type,
    p.client_id, p.quoted_price, p.created_at
FROM practices p
JOIN practice_types pt ON p.practice_type_id = pt.id
WHERE p.created_at > NOW() - INTERVAL '7 days'
ORDER BY p.created_at DESC
LIMIT 20
"""

SQL_MONTHLY_REVENUE = """
SELECT
    TO_CHAR(p.completion_date, 'YYYY-MM') AS month,
    COALESCE(SUM(p.actual_price), 0) AS revenue,
    COUNT(*) AS practices_completed
FROM practices p
WHERE p.status = 'completed'
  AND p.completion_date IS NOT NULL
  AND p.completion_date > NOW() - INTERVAL '12 months'
GROUP BY TO_CHAR(p.completion_date, 'YYYY-MM')
ORDER BY month DESC
"""

SQL_UNPAID_AGING = """
SELECT
    CASE
        WHEN EXTRACT(DAY FROM (NOW() - p.created_at)) < 30 THEN '0-30 days'
        WHEN EXTRACT(DAY FROM (NOW() - p.created_at)) < 60 THEN '30-60 days'
        WHEN EXTRACT(DAY FROM (NOW() - p.created_at)) < 90 THEN '60-90 days'
        ELSE '90+ days'
    END AS bucket,
    COUNT(*) AS count,
    COALESCE(SUM(p.quoted_price - COALESCE(p.paid_amount, 0)), 0) AS total_outstanding
FROM practices p
WHERE p.payment_status IN ('unpaid', 'partial')
  AND p.status NOT IN ('cancelled')
GROUP BY bucket
ORDER BY bucket
"""

SQL_TOP_SERVICES = """
SELECT
    pt.name AS practice_type,
    COUNT(*) AS count,
    COALESCE(SUM(p.actual_price), 0) AS total_revenue,
    COALESCE(AVG(p.actual_price), 0) AS avg_price
FROM practices p
JOIN practice_types pt ON p.practice_type_id = pt.id
WHERE p.status = 'completed' AND p.actual_price IS NOT NULL
GROUP BY pt.name
ORDER BY total_revenue DESC
LIMIT 10
"""

SQL_CLIENTS_BY_NATIONALITY = """
SELECT
    COALESCE(NULLIF(c.nationality, ''), 'Unknown') AS nationality,
    COUNT(DISTINCT c.id) AS count,
    AVG(sub.practice_count) AS avg_practices,
    AVG(sub.total_revenue) AS avg_revenue
FROM clients c
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) AS practice_count,
        COALESCE(SUM(actual_price), 0) AS total_revenue
    FROM practices
    WHERE client_id = c.id AND status = 'completed'
) sub ON TRUE
WHERE c.deleted_at IS NULL AND c.status = 'active'
GROUP BY nationality
ORDER BY count DESC
LIMIT 15
"""

SQL_CLIENTS_BY_TYPE = """
SELECT
    COALESCE(client_type, 'unknown') AS client_type,
    COUNT(*) AS count
FROM clients
WHERE deleted_at IS NULL
GROUP BY client_type
"""

SQL_CLIENTS_BY_STATUS = """
SELECT status, COUNT(*) AS count
FROM clients
WHERE deleted_at IS NULL
GROUP BY status
ORDER BY count DESC
"""

SQL_COMPANIES_BY_TYPE = """
SELECT
    COALESCE(company_type, 'Unknown') AS company_type,
    COUNT(*) AS count
FROM companies
GROUP BY company_type
ORDER BY count DESC
"""

SQL_COMPANIES_BY_STATUS = """
SELECT status, COUNT(*) AS count
FROM companies
GROUP BY status
ORDER BY count DESC
"""

SQL_TOP_KBLI = """
SELECT
    kbli_code,
    COALESCE(kbli_description, '') AS kbli_description,
    COUNT(*) AS count
FROM companies
WHERE kbli_code IS NOT NULL AND kbli_code != ''
GROUP BY kbli_code, kbli_description
ORDER BY count DESC
LIMIT 15
"""

SQL_TAX_BY_STATUS = """
SELECT
    compliance_status,
    COUNT(*) AS count
FROM tax_records
GROUP BY compliance_status
ORDER BY count DESC
"""

SQL_UPCOMING_FILINGS = """
SELECT
    entity_type, entity_id,
    CASE
        WHEN is_ppn_registered THEN 'PPN'
        WHEN is_pph21_registered THEN 'PPh21'
        WHEN is_pph25_registered THEN 'PPh25'
        ELSE 'Other'
    END AS tax_type,
    next_filing_date
FROM tax_records
WHERE next_filing_date IS NOT NULL
  AND next_filing_date > NOW()
  AND next_filing_date <= NOW() + INTERVAL '60 days'
ORDER BY next_filing_date ASC
LIMIT 20
"""

SQL_DB_STATS = """
SELECT
    (SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active') AS active_connections,
    pg_size_pretty(pg_database_size(current_database())) AS db_size,
    COALESCE(
        (SELECT EXTRACT(EPOCH FROM (NOW() - query_start))
         FROM pg_stat_activity
         WHERE state = 'active' AND query NOT LIKE '%pg_stat%'
         ORDER BY query_start ASC LIMIT 1),
        0
    ) AS longest_query_seconds
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _records_to_dicts(records: list[asyncpg.Record]) -> list[dict[str, Any]]:
    """Convert asyncpg Records to plain dicts."""
    return [dict(r) for r in records]


def _record_to_dict(record: Optional[asyncpg.Record]) -> dict[str, Any]:
    """Convert a single asyncpg Record to dict."""
    return dict(record) if record else {}


async def _safe_query(
    conn: asyncpg.Connection,
    sql: str,
    *args: Any,
    fetch_one: bool = False,
) -> Any:
    """Execute a query with error handling."""
    try:
        if fetch_one:
            row = await conn.fetchrow(sql, *args)
            return _record_to_dict(row)
        rows = await conn.fetch(sql, *args)
        return _records_to_dicts(rows)
    except Exception:
        logger.exception("Query failed: %s", sql[:80])
        return {} if fetch_one else []


def _nlm_source_add(
    notebook_id: str,
    title: str,
    content: str,
    timeout: int = 60,
) -> Optional[str]:
    """Add a text source to NLM notebook. Returns source_id or None."""
    cmd = [
        NLM_CLI, "source", "add",
        notebook_id,
        "--title", title,
        "--text", content,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.error("nlm source add failed: %s", result.stderr.strip())
            return None
        # nlm CLI outputs plain text: "Source ID: <uuid>"
        output = result.stdout.strip()
        for line in output.splitlines():
            if line.startswith("Source ID:"):
                source_id = line.split(":", 1)[1].strip()
                logger.info("Source added: %s → %s", title, source_id)
                return source_id
        logger.warning("nlm source add: could not parse source_id from: %s", output[:200])
        return None
    except Exception:
        logger.exception("nlm source add error for '%s'", title)
        return None


def _nlm_source_delete(
    notebook_id: str,
    source_id: str,
    timeout: int = 30,
) -> bool:
    """Delete a source from NLM notebook."""
    cmd = [
        NLM_CLI, "source", "delete",
        source_id,
        "--confirm",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning("nlm source delete failed: %s", result.stderr.strip())
            return False
        logger.info("Source deleted: %s", source_id)
        return True
    except Exception:
        logger.exception("nlm source delete error for '%s'", source_id)
        return False


def _send_telegram_alert(message: str) -> None:
    """Send failure alert to Telegram."""
    if not TG_BOT_TOKEN:
        return
    try:
        subprocess.run(
            [
                "curl", "-s", "-X", "POST",
                f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                "-d", f"chat_id={TG_CHAT_ID}",
                "-d", f"text={message}",
            ],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        logger.warning("Telegram alert failed")


# ---------------------------------------------------------------------------
# Source Definitions — maps source name to (notebook_key, query_fn, render_fn)
# ---------------------------------------------------------------------------

SourceSpec = tuple[str, str]  # (notebook_key, source_title)

SOURCE_REGISTRY: dict[str, SourceSpec] = {
    "portfolio_snapshot": ("ops", "Client Portfolio Snapshot"),
    "practices_pipeline": ("ops", "Practices Pipeline Status"),
    "compliance_radar": ("ops", "Compliance & Expiry Radar"),
    "team_activity": ("ops", "Team Activity Report"),
    "recent_changes": ("ops", "Recent Changes (7 Days)"),
    "revenue_dashboard": ("intel", "Revenue Dashboard"),
    "client_segments": ("intel", "Client Segments Analysis"),
    "company_overview": ("intel", "Company Portfolio Overview"),
    "tax_compliance": ("intel", "Tax Compliance Overview"),
    "system_health": ("telemetry", "System Health Snapshot"),
}


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

async def run_sync(
    db_url: str,
    nb_ids: dict[str, str],  # {"ops": "...", "intel": "...", "telemetry": "..."}
    state: DBNLMSyncState,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Execute the full DB→NLM sync pipeline.

    Returns:
        Summary dict with counts and errors.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    results: dict[str, Any] = {
        "date": today,
        "sources_processed": 0,
        "sources_uploaded": 0,
        "sources_skipped": 0,
        "sources_failed": 0,
        "errors": [],
    }

    # --- 1. Connect to DB ---
    logger.info("Connecting to database...")
    try:
        conn = await asyncpg.connect(db_url, timeout=30)
    except Exception as e:
        msg = f"DB connection failed: {e}"
        logger.error(msg)
        state.record_db_failure()
        results["errors"].append(msg)
        return results

    state.reset_db_cb()
    logger.info("Connected to database")

    try:
        # --- 2. Extract & Render all sources ---
        sources: dict[str, str] = {}

        # Portfolio Snapshot
        client_stats = await _safe_query(conn, SQL_CLIENT_STATS, fetch_one=True)
        segments = await _safe_query(conn, SQL_CLIENT_SEGMENTS)
        nationalities = await _safe_query(conn, SQL_NATIONALITIES)
        sources["portfolio_snapshot"] = render_portfolio_snapshot(
            client_stats, segments, nationalities, today,
        )

        # Practices Pipeline
        by_status = await _safe_query(conn, SQL_PRACTICES_BY_STATUS)
        bottlenecks = await _safe_query(conn, SQL_BOTTLENECKS)
        avg_duration = await _safe_query(conn, SQL_AVG_DURATION)
        sources["practices_pipeline"] = render_practices_pipeline(
            by_status, bottlenecks, avg_duration, today,
        )

        # Compliance Radar
        exp_30 = await _safe_query(conn, SQL_EXPIRING, timedelta(days=30))
        exp_60 = await _safe_query(conn, SQL_EXPIRING, timedelta(days=60))
        exp_90 = await _safe_query(conn, SQL_EXPIRING, timedelta(days=90))
        missing_docs = await _safe_query(conn, SQL_MISSING_DOCS)
        sources["compliance_radar"] = render_compliance_radar(
            exp_30, exp_60, exp_90, missing_docs, today,
        )

        # Team Activity
        by_member = await _safe_query(conn, SQL_INTERACTIONS_BY_MEMBER)
        by_channel = await _safe_query(conn, SQL_INTERACTIONS_BY_CHANNEL)
        sentiment = await _safe_query(conn, SQL_SENTIMENT)
        sources["team_activity"] = render_team_activity(
            by_member, by_channel, sentiment, today,
        )

        # Recent Changes
        new_clients = await _safe_query(conn, SQL_NEW_CLIENTS_7D)
        completed = await _safe_query(conn, SQL_COMPLETED_7D)
        new_practices = await _safe_query(conn, SQL_NEW_PRACTICES_7D)
        sources["recent_changes"] = render_recent_changes(
            new_clients, completed, new_practices, today,
        )

        # Revenue Dashboard
        monthly_rev = await _safe_query(conn, SQL_MONTHLY_REVENUE)
        unpaid = await _safe_query(conn, SQL_UNPAID_AGING)
        top_services = await _safe_query(conn, SQL_TOP_SERVICES)
        sources["revenue_dashboard"] = render_revenue_dashboard(
            monthly_rev, unpaid, top_services, today,
        )

        # Client Segments
        clients_by_nat = await _safe_query(conn, SQL_CLIENTS_BY_NATIONALITY)
        clients_by_type = await _safe_query(conn, SQL_CLIENTS_BY_TYPE)
        clients_by_status = await _safe_query(conn, SQL_CLIENTS_BY_STATUS)
        sources["client_segments"] = render_client_segments(
            clients_by_nat, clients_by_type, clients_by_status, today,
        )

        # Company Overview
        companies_by_type = await _safe_query(conn, SQL_COMPANIES_BY_TYPE)
        companies_by_status = await _safe_query(conn, SQL_COMPANIES_BY_STATUS)
        top_kbli = await _safe_query(conn, SQL_TOP_KBLI)
        sources["company_overview"] = render_company_overview(
            companies_by_type, companies_by_status, top_kbli, today,
        )

        # Tax Compliance
        tax_by_status = await _safe_query(conn, SQL_TAX_BY_STATUS)
        upcoming_filings = await _safe_query(conn, SQL_UPCOMING_FILINGS)
        sources["tax_compliance"] = render_tax_compliance(
            tax_by_status, upcoming_filings, today,
        )

        # System Health
        db_stats = await _safe_query(conn, SQL_DB_STATS, fetch_one=True)
        sources["system_health"] = render_system_health(
            db_stats, {"total_collections": "N/A", "total_vectors": "N/A"}, today,
        )

    finally:
        await conn.close()
        logger.info("Database connection closed")

    # --- 3. Diff & Upload ---
    for source_name, content in sources.items():
        results["sources_processed"] += 1
        spec = SOURCE_REGISTRY.get(source_name)
        if not spec:
            logger.warning("Unknown source: %s", source_name)
            continue

        nb_key, title = spec
        notebook_id = nb_ids.get(nb_key, "")
        if not notebook_id:
            logger.warning("No notebook ID for %s — skipping %s", nb_key, source_name)
            results["sources_skipped"] += 1
            continue

        # Check if content changed
        if not force and not state.is_source_changed(source_name, content):
            logger.info("Source %s unchanged — skipping", source_name)
            state.record_skip()
            results["sources_skipped"] += 1
            continue

        if dry_run:
            logger.info("[DRY-RUN] Would upload %s → %s (%d bytes)",
                        source_name, nb_key, len(content))
            results["sources_skipped"] += 1
            continue

        # Delete old source if exists
        old_hash = state.source_hashes.get(source_name)
        if old_hash and old_hash.nlm_source_id:
            _nlm_source_delete(notebook_id, old_hash.nlm_source_id)

        # Upload new source
        source_id = _nlm_source_add(notebook_id, title, content)
        if source_id:
            state.record_upload(source_name, content, source_id)
            results["sources_uploaded"] += 1
            logger.info("Uploaded %s → %s (source_id=%s)", source_name, nb_key, source_id)
        else:
            state.record_nlm_failure()
            results["sources_failed"] += 1
            results["errors"].append(f"Failed to upload {source_name}")

    return results


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="DB→NLM Sync: export Postgres aggregates to NotebookLM",
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get(
            "DATABASE_URL",
            "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag",
        ),
        help="PostgreSQL connection URL",
    )
    parser.add_argument("--nb-ops-id", default=os.environ.get("NB_OPS_ID", ""))
    parser.add_argument("--nb-intel-id", default=os.environ.get("NB_INTEL_ID", ""))
    parser.add_argument("--nb-telemetry-id", default=os.environ.get("NB_TELEMETRY_ID", ""))
    parser.add_argument("--dry-run", action="store_true", help="Generate MDs but don't upload")
    parser.add_argument("--force", action="store_true", help="Upload even if unchanged")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load state
    persistence = DBNLMStatePersistence()
    state = persistence.load()

    # Update notebook IDs from args or state
    nb_ids = {
        "ops": args.nb_ops_id or state.nb_ops_id,
        "intel": args.nb_intel_id or state.nb_intel_id,
        "telemetry": args.nb_telemetry_id or state.nb_telemetry_id,
    }

    if not any(nb_ids.values()):
        logger.error(
            "No notebook IDs configured. Pass --nb-ops-id, --nb-intel-id, "
            "--nb-telemetry-id or set NB_OPS_ID, NB_INTEL_ID, NB_TELEMETRY_ID env vars."
        )
        sys.exit(1)

    # PID lock
    try:
        with DBNLMPIDLock():
            state.increment_run()

            # Persist notebook IDs
            state.nb_ops_id = nb_ids.get("ops", "") or state.nb_ops_id
            state.nb_intel_id = nb_ids.get("intel", "") or state.nb_intel_id
            state.nb_telemetry_id = nb_ids.get("telemetry", "") or state.nb_telemetry_id

            # Run sync
            results = asyncio.run(run_sync(
                db_url=args.db_url,
                nb_ids=nb_ids,
                state=state,
                dry_run=args.dry_run,
                force=args.force,
            ))

            # Update final status
            if results["sources_failed"] == 0 and results["errors"] == []:
                state.last_run_status = "success"
                state.reset_nlm_cb()
            elif results["sources_uploaded"] > 0:
                state.last_run_status = "partial"
            else:
                state.last_run_status = "error"

            persistence.save(state)

            # Log summary
            logger.info(
                "Sync complete: %d processed, %d uploaded, %d skipped, %d failed",
                results["sources_processed"],
                results["sources_uploaded"],
                results["sources_skipped"],
                results["sources_failed"],
            )

            if results["errors"]:
                error_msg = (
                    f"⚠️ DB→NLM Sync partial failure:\n"
                    f"Uploaded: {results['sources_uploaded']}, "
                    f"Failed: {results['sources_failed']}\n"
                    f"Errors: {'; '.join(results['errors'][:3])}"
                )
                _send_telegram_alert(error_msg)

    except DBNLMLockError as e:
        logger.warning(str(e))
        sys.exit(0)
    except Exception as e:
        logger.exception("DB→NLM sync crashed: %s", e)
        state.last_run_status = "error"
        persistence.save(state)
        _send_telegram_alert(f"🔴 DB→NLM Sync CRASHED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
