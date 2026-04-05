"""
Predictive Compliance Engine

Scans clients and practices for upcoming document expirations and produces
ComplianceForecast objects enriched with:
  - Recommended action date (based on processing time + buffer)
  - Estimated renewal revenue (from PricingService — NEVER hardcoded)
  - Priority score (urgency × value × complexity)
  - Required documents checklist
  - Active renewal practice detection

Design rules:
  - Rule-based, deterministic — no ML, no randomness.
  - Read-only — does not send notifications. Callers decide what to do.
  - Single batch query — no N+1 on 5000+ clients.
  - Never modifies existing notifier behaviour.
  - Kill switch: system_settings.compliance_forecast_enabled (must be "true").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import asyncpg

from backend.services.compliance.priority_scorer import PriorityResult, calculate_priority
from backend.services.compliance.renewal_rules import RenewalRule, match_rule
from backend.services.compliance.revenue_estimator import estimate_renewal_revenue

logger = logging.getLogger(__name__)

# ── Configuration (all overridable via system_settings) ───────────────────────

_DEFAULT_SCAN_WINDOW_DAYS: int = 365
_KILL_SWITCH_KEY: str = "compliance_forecast_enabled"

# ── Data model ─────────────────────────────────────────────────────────────────


@dataclass
class ComplianceForecast:
    """
    A single predictive compliance item for one client document.

    Produced by PredictiveComplianceEngine.scan().
    """

    # Client / document identity
    client_id: int
    client_name: str
    assigned_to: str | None
    document_type: str              # "visa", "kitas", "passport", "license"
    current_visa_type: str | None

    # Expiry
    expiry_date: date
    days_until_expiry: int

    # Predictive
    matched_rule_id: str
    processing_days: int
    lead_time_start: date           # when the process should BEGIN
    recommended_action_by: date     # when to CONTACT the client
    days_until_action: int          # days from today until recommended_action_by

    # Revenue
    estimated_revenue_idr: int | None
    renewal_pricing_key: str | None

    # Priority
    priority_score: float
    urgency_level: str

    # Context
    required_docs: list[str]
    has_active_renewal_practice: bool
    notes: str

    # Extras (populated when client has passport cross-check issues)
    passport_expires_before_visa: bool = False


@dataclass
class ForecastSummary:
    total_forecasts: int
    by_urgency: dict[str, int]
    total_estimated_revenue_idr: int
    top_revenue_forecasts: list[ComplianceForecast]
    clients_with_active_practice_skipped: int


@dataclass
class ScanResult:
    forecasts: list[ComplianceForecast]
    summary: ForecastSummary
    scan_window_days: int
    generated_at: str


# ── SQL ────────────────────────────────────────────────────────────────────────

# Batch query — 3 document types from clients table joined on active practices
_CLIENT_DOCUMENTS_SQL = """
WITH client_docs AS (
    SELECT
        c.id            AS client_id,
        c.full_name,
        c.assigned_to,
        c.current_visa_type,
        c.passport_expiry,
        'visa'          AS document_type,
        c.visa_expiry_date   AS expiry_date
    FROM clients c
    WHERE c.visa_expiry_date IS NOT NULL
      AND c.visa_expiry_date >= CURRENT_DATE
      AND c.visa_expiry_date <= CURRENT_DATE + ($1::int * INTERVAL '1 day')
      AND c.status = 'active'
      AND c.deleted_at IS NULL

    UNION ALL

    SELECT
        c.id,
        c.full_name,
        c.assigned_to,
        c.current_visa_type,
        c.passport_expiry,
        'kitas'         AS document_type,
        c.kitas_expiry_date  AS expiry_date
    FROM clients c
    WHERE c.kitas_expiry_date IS NOT NULL
      AND c.kitas_expiry_date >= CURRENT_DATE
      AND c.kitas_expiry_date <= CURRENT_DATE + ($1::int * INTERVAL '1 day')
      AND c.status = 'active'
      AND c.deleted_at IS NULL

    UNION ALL

    SELECT
        c.id,
        c.full_name,
        c.assigned_to,
        c.current_visa_type,
        c.passport_expiry,
        'passport'      AS document_type,
        c.passport_expiry    AS expiry_date
    FROM clients c
    WHERE c.passport_expiry IS NOT NULL
      AND c.passport_expiry >= CURRENT_DATE
      AND c.passport_expiry <= CURRENT_DATE + ($1::int * INTERVAL '1 day')
      AND c.status = 'active'
      AND c.deleted_at IS NULL
)
SELECT * FROM client_docs
ORDER BY expiry_date ASC
"""

_PRACTICES_EXPIRY_SQL = """
SELECT
    p.id               AS practice_id,
    p.client_id,
    c.full_name,
    COALESCE(p.assigned_to, c.assigned_to) AS assigned_to,
    c.current_visa_type,
    c.passport_expiry,
    'license'          AS document_type,
    p.expiry_date,
    p.practice_type_code
FROM practices p
JOIN clients c ON c.id = p.client_id
WHERE p.expiry_date IS NOT NULL
  AND p.expiry_date >= CURRENT_DATE
  AND p.expiry_date <= CURRENT_DATE + ($1::int * INTERVAL '1 day')
  AND p.status NOT IN ('cancelled', 'expired', 'renewed', 'completed')
  AND c.status = 'active'
  AND c.deleted_at IS NULL
ORDER BY p.expiry_date ASC
"""

# Check for an already-in-progress renewal for a client's document type
_ACTIVE_RENEWAL_SQL = """
SELECT 1 FROM practices
WHERE client_id = $1
  AND practice_type_code ILIKE $2
  AND status NOT IN ('completed', 'cancelled', 'expired', 'renewed')
LIMIT 1
"""


# ── Engine ─────────────────────────────────────────────────────────────────────


class PredictiveComplianceEngine:
    """
    Scans the database for upcoming document expirations and returns
    ComplianceForecast objects enriched with timeline/revenue/priority data.

    Usage:
        engine = PredictiveComplianceEngine(db_pool, all_prices)
        result = await engine.scan()
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        all_prices: dict[str, Any],
        scan_window_days: int = _DEFAULT_SCAN_WINDOW_DAYS,
    ) -> None:
        """
        Args:
            db_pool:          Active asyncpg connection pool.
            all_prices:       Full pricing dict from PricingService.get_pricing("all").
                              MUST be pre-loaded — do not call inside loops.
            scan_window_days: How far ahead to look (default 365 days).
        """
        self._db_pool = db_pool
        self._all_prices = all_prices
        self._scan_window_days = scan_window_days

    # ── Public API ─────────────────────────────────────────────────────────────

    async def scan(self) -> ScanResult:
        """
        Run the full predictive scan.

        Returns a ScanResult with all forecasts and a summary.
        """
        from datetime import datetime, timezone

        logger.info(
            "PredictiveComplianceEngine: scanning next %d days",
            self._scan_window_days,
        )

        today = date.today()
        forecasts: list[ComplianceForecast] = []
        active_practice_skipped = 0

        async with self._db_pool.acquire() as conn:
            # ── 1. Client document expiries (visa / kitas / passport) ─────────
            try:
                client_rows = await conn.fetch(_CLIENT_DOCUMENTS_SQL, self._scan_window_days)
            except Exception:
                logger.exception("Error querying client documents")
                client_rows = []

            # ── 2. Practice expiries (license / permits) ──────────────────────
            try:
                practice_rows = await conn.fetch(_PRACTICES_EXPIRY_SQL, self._scan_window_days)
            except Exception:
                logger.exception("Error querying practice expiries")
                practice_rows = []

        all_rows = list(client_rows) + list(practice_rows)
        logger.info(
            "PredictiveComplianceEngine: %d client doc rows + %d practice rows = %d total",
            len(client_rows),
            len(practice_rows),
            len(all_rows),
        )

        # ── 3. Build forecasts ────────────────────────────────────────────────
        for row in all_rows:
            row_dict = dict(row)
            forecast = await self._build_forecast(row_dict, today)
            if forecast is None:
                active_practice_skipped += 1
                continue
            forecasts.append(forecast)

        # ── 4. Sort by priority score ─────────────────────────────────────────
        forecasts.sort(key=lambda f: f.priority_score, reverse=True)

        # ── 5. Build summary ──────────────────────────────────────────────────
        by_urgency: dict[str, int] = {}
        total_revenue = 0
        for f in forecasts:
            by_urgency[f.urgency_level] = by_urgency.get(f.urgency_level, 0) + 1
            if f.estimated_revenue_idr:
                total_revenue += f.estimated_revenue_idr

        top_5 = [f for f in forecasts if f.estimated_revenue_idr][:5]

        summary = ForecastSummary(
            total_forecasts=len(forecasts),
            by_urgency=by_urgency,
            total_estimated_revenue_idr=total_revenue,
            top_revenue_forecasts=top_5,
            clients_with_active_practice_skipped=active_practice_skipped,
        )

        logger.info(
            "PredictiveComplianceEngine: %d forecasts, %d skipped (active practice), "
            "estimated revenue Rp %s",
            len(forecasts),
            active_practice_skipped,
            f"{total_revenue:,}",
        )

        return ScanResult(
            forecasts=forecasts,
            summary=summary,
            scan_window_days=self._scan_window_days,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _build_forecast(
        self,
        row: dict[str, Any],
        today: date,
    ) -> ComplianceForecast | None:
        """
        Build one ComplianceForecast from a DB row.

        Returns None if an active renewal practice already exists
        (skip — nothing to do).
        """
        client_id: int = row["client_id"]
        document_type: str = row["document_type"]
        visa_type: str | None = row.get("current_visa_type") or row.get("practice_type_code")
        expiry_date: date = row["expiry_date"]

        # Skip documents with no expiry (should not happen — filtered in SQL)
        if expiry_date is None:
            return None

        # Match rule
        rule: RenewalRule = match_rule(document_type, visa_type)

        # Check for active renewal practice
        has_active = await self._has_active_renewal(client_id, rule)
        if has_active:
            return None  # Already being worked on

        # Timeline calculations
        days_until_expiry = (expiry_date - today).days
        lead_time_start = expiry_date - timedelta(days=rule.lead_time_days)
        recommended_action_by = expiry_date - timedelta(days=rule.recommended_start_days)
        days_until_action = (recommended_action_by - today).days

        # Revenue
        estimated_revenue = estimate_renewal_revenue(rule, self._all_prices)

        # Priority
        priority: PriorityResult = calculate_priority(
            days_until_action=days_until_action,
            estimated_revenue_idr=estimated_revenue,
            complexity=rule.complexity,
        )

        # Passport cross-check
        passport_expiry: date | None = row.get("passport_expiry")
        passport_before_visa = bool(
            passport_expiry
            and document_type in ("visa", "kitas")
            and passport_expiry < expiry_date
        )

        # KITAS → KITAP upgrade detection:
        # If client has had KITAS for 4+ years and matches investor/spouse pattern
        # and rule suggests investor, flag upgrade as possible
        suggested_renewal: str | None = None
        if rule.rule_id == "kitas_investor_extend" and days_until_expiry < 90:
            suggested_renewal = "Consider KITAP upgrade if client has 5+ years continuous KITAS"

        return ComplianceForecast(
            client_id=client_id,
            client_name=row.get("full_name", "Unknown"),
            assigned_to=row.get("assigned_to"),
            document_type=document_type,
            current_visa_type=visa_type,
            expiry_date=expiry_date,
            days_until_expiry=days_until_expiry,
            matched_rule_id=rule.rule_id,
            processing_days=rule.processing_days,
            lead_time_start=lead_time_start,
            recommended_action_by=recommended_action_by,
            days_until_action=days_until_action,
            estimated_revenue_idr=estimated_revenue,
            renewal_pricing_key=rule.renewal_pricing_key,
            priority_score=priority.score,
            urgency_level=priority.urgency_level,
            required_docs=list(rule.required_docs),
            has_active_renewal_practice=False,  # already filtered out
            notes=rule.notes + (f" | Suggested: {suggested_renewal}" if suggested_renewal else ""),
            passport_expires_before_visa=passport_before_visa,
        )

    async def _has_active_renewal(
        self,
        client_id: int,
        rule: RenewalRule,
    ) -> bool:
        """
        Returns True if there's already an in-progress renewal practice
        for this client + document type.
        """
        # Build a LIKE pattern from the rule_id prefix (e.g., "kitas%", "visa%")
        doc_pattern = rule.document_types[0] + "%"

        async with self._db_pool.acquire() as conn:
            try:
                result = await conn.fetchval(_ACTIVE_RENEWAL_SQL, client_id, doc_pattern)
                return result is not None
            except Exception:
                logger.exception(
                    "Error checking active renewal for client %d, pattern '%s'",
                    client_id,
                    doc_pattern,
                )
                return False  # Err on the side of inclusion


# ── Kill switch helper ─────────────────────────────────────────────────────────


async def is_engine_enabled(db_pool: asyncpg.Pool) -> bool:
    """
    Check the kill switch in system_settings.
    Returns True only if compliance_forecast_enabled = "true".
    """
    async with db_pool.acquire() as conn:
        value = await conn.fetchval(
            "SELECT value FROM system_settings WHERE key = $1",
            _KILL_SWITCH_KEY,
        )
    enabled = value == "true"
    if not enabled:
        logger.info(
            "PredictiveComplianceEngine: disabled by kill switch '%s' (value=%r)",
            _KILL_SWITCH_KEY,
            value,
        )
    return enabled
