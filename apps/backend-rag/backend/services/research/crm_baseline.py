"""CRM baseline extractor — leads count + source coverage over 90 days.

Uses `clients.lead_source` column (schema discovered 2026-04-22: there is
NO `utm_source` column in the Bali Zero CRM). Coverage metric computes
how many rows in the last 90d have `lead_source IS NOT NULL`.

Social definition (for `leads_social_90d`): instagram, linkedin, tiktok,
youtube, threads, twitter, x, x_social_listening. Explicitly EXCLUDES
whatsapp (DM channel, measured separately), referral (word of mouth),
website (direct organic).

Key finding from the Day-1 baseline (2026-04-22):
    WhatsApp dominates lead flow (~307/324 = 95%); social marketing
    contribution is ~1.5% today. This is the honest baseline against
    which the SOTA 90-day loop will measure uplift.

The old `utm_coverage_pct` key name is preserved in the return dict to
match `BaselineSnapshot.crm` schema — rename is cosmetic-only and would
ripple through baseline_builder + Task 5 driver.
"""

from __future__ import annotations

from typing import Any

SOCIAL_SOURCE_VALUES = (
    "instagram",
    "linkedin",
    "tiktok",
    "youtube",
    "threads",
    "twitter",
    "x",
    "x_social_listening",
    "facebook",
)


async def fetch_crm_baseline(db_pool: Any) -> dict[str, Any]:
    """Pull total 90d leads, social-attributed subset, and `lead_source` coverage.

    Returns dict with keys:
        leads_total_90d: int
        leads_social_90d: int
        utm_coverage_pct: float  (0.0-1.0) — fraction of 90d rows with
                                  non-null lead_source
    """
    # Build a PG array literal of social channel values for the IN clause
    # (asyncpg prefers explicit literals for short static lists).
    social_in_list = ",".join(f"'{v}'" for v in SOCIAL_SOURCE_VALUES)

    sql_total = """
        SELECT COUNT(*) FROM clients
         WHERE created_at > NOW() - INTERVAL '90 days'
    """
    sql_social = f"""
        SELECT COUNT(*) FROM clients
         WHERE created_at > NOW() - INTERVAL '90 days'
           AND lead_source IN ({social_in_list})
    """
    sql_coverage = """
        SELECT COALESCE(
            AVG(CASE WHEN lead_source IS NOT NULL AND lead_source <> '' THEN 1.0 ELSE 0.0 END),
            0.0
        )
        FROM clients
        WHERE created_at > NOW() - INTERVAL '90 days'
    """
    async with db_pool.acquire() as conn:
        total = await conn.fetchval(sql_total)
        social = await conn.fetchval(sql_social)
        coverage = await conn.fetchval(sql_coverage)
    return {
        "leads_total_90d": int(total or 0),
        "leads_social_90d": int(social or 0),
        "utm_coverage_pct": float(coverage or 0.0),
    }
