"""E33 Guarantee Scanner — Day-90 / annual-maintenance alert generation.

Entry point for the cron layer (`app/routers/cron_notifiers.py`,
POST /api/cron/notifiers/e33-guarantee-scan), following the same
service-per-endpoint pattern as StalePracticeNotifier / LKPMDeadlineNotifier.

Flow (mirrors the run_compliance_forecast integration):
  1. E33CaseRepository.list_open_guarantee_cases() — non-terminal cases at
     ITAS_ACTIVE or later (coarse DB-side filter).
  2. E33Case.build_case_forecasts(today=today) — pure per-case computation
     of the Day-90 guarantee gate and the annual-maintenance recurrence.
  3. AlertsEngine.generate_alerts(forecasts) — the EXISTING compliance
     organ handles dedup, severity promotion (Day 30 → 60 → 75 escalation
     rides the stable compliance_item_ref), persistence to
     compliance_alerts, and team dispatch.

Legge 5: nothing here is client-facing. Alerts are persisted and dispatched
through the same team channels the existing compliance-forecast flow uses —
no WhatsApp/client notifications are sent by this scanner.

Kill switch: system_settings.e33_guarantee_scan_enabled must be "true"
(same blocked-by-default posture as visa_expiry_notifier_enabled).

UNPROVISIONED vs DISABLED (2026-07-25)
--------------------------------------
The switch has THREE meaningful states, not two. A missing row and a row set
to "false" both block the scan, but they mean opposite things operationally:

- **UNPROVISIONED** (no row): nobody ever decided. The organ was built and
  deployed — table, scanner, cron endpoint — and then left un-armed without
  anyone noticing, because "blocked" reads like a decision. This is the
  superscar-#2 shape ("esiste != armato"): the failure is invisible precisely
  because it looks identical to the healthy fail-closed state.
- **DISABLED** (row exists, value != "true"): somebody decided, and the
  decision is recorded and auditable.

``resolve_scan_switch`` reports which one it is so the endpoint and the logs
can too. Nothing about the fail-closed behaviour changes: both non-ENABLED
states block, and an absent row still blocks.
"""

from __future__ import annotations

import logging
from datetime import date
from enum import Enum
from typing import Any

import asyncpg

from backend.services.crm.e33_case_repository import E33CaseRepository

logger = logging.getLogger(__name__)

_KILL_SWITCH_KEY: str = "e33_guarantee_scan_enabled"

#: The exact stored value that arms the scan. Anything else blocks.
_ENABLED_VALUE: str = "true"


class ScanSwitchState(str, Enum):
    """Resolved state of the E33 guarantee-scan kill switch."""

    #: No row for the key — the organ was never armed (nor deliberately disabled).
    UNPROVISIONED = "unprovisioned"
    #: Row exists but is not the enabling value — a recorded decision to hold.
    DISABLED = "disabled"
    #: Row exists and arms the scan.
    ENABLED = "enabled"

    @property
    def is_enabled(self) -> bool:
        """True only for :attr:`ENABLED` — both other states fail closed."""
        return self is ScanSwitchState.ENABLED


async def resolve_scan_switch(db_pool: asyncpg.Pool) -> ScanSwitchState:
    """Resolve the kill switch into one of three explicit states.

    Distinguishes "never provisioned" from "deliberately disabled" — see the
    module docstring. Fail-closed is unchanged: only the exact string
    ``"true"`` yields :attr:`ScanSwitchState.ENABLED`.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT value FROM system_settings WHERE key = $1",
            _KILL_SWITCH_KEY,
        )

    if row is None:
        logger.warning(
            "E33GuaranteeScanner: kill switch '%s' has NO ROW in system_settings — "
            "the scanner is un-armed, not disabled. The Day-90 guarantee gate is "
            "therefore not being monitored for any open E33 case. Arming it is a "
            "one-line value change on that key (owner decision).",
            _KILL_SWITCH_KEY,
        )
        return ScanSwitchState.UNPROVISIONED

    value = row["value"]
    if value == _ENABLED_VALUE:
        return ScanSwitchState.ENABLED

    logger.info(
        "E33GuaranteeScanner: disabled by kill switch '%s' (value=%r) — "
        "an explicit recorded decision, not a missing arming step.",
        _KILL_SWITCH_KEY,
        value,
    )
    return ScanSwitchState.DISABLED


async def is_scan_enabled(db_pool: asyncpg.Pool) -> bool:
    """Check the kill switch in system_settings. Blocked unless "true".

    Thin boolean view over :func:`resolve_scan_switch`, kept for callers that
    only need the yes/no.
    """
    return (await resolve_scan_switch(db_pool)).is_enabled


class E33GuaranteeScanner:
    """Scans open E33 cases and feeds due forecasts into the AlertsEngine."""

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        *,
        pricing_service: Any = None,
        alerts_engine: Any = None,
    ) -> None:
        """
        Args:
            db_pool:         Active asyncpg connection pool.
            pricing_service: Optional pre-loaded PricingService (shared with
                             the caller to avoid a second lookup).
            alerts_engine:   Optional pre-built AlertsEngine (tests/dry runs).
        """
        self._db_pool = db_pool
        self._pricing_service = pricing_service
        self._alerts_engine = alerts_engine

    def _engine(self) -> Any:
        if self._alerts_engine is not None:
            return self._alerts_engine
        from backend.services.compliance.alert_wiring import build_alerts_engine
        from backend.services.pricing.pricing_service import get_pricing_service

        pricing = self._pricing_service or get_pricing_service()
        return build_alerts_engine(self._db_pool, pricing_service=pricing)

    async def scan(self, *, today: date | None = None) -> dict[str, Any]:
        """Run one scan pass. ``today`` is injectable for deterministic tests."""
        today = today or date.today()
        repo = E33CaseRepository(self._db_pool)
        cases = await repo.list_open_guarantee_cases()

        forecasts = []
        for case in cases:
            try:
                forecasts.extend(case.build_case_forecasts(today=today))
            except Exception as exc:  # resilience: one bad case doesn't kill the batch
                logger.error(
                    "E33 forecast build failed for case %s: %s (skipping)",
                    case.case_id,
                    exc,
                )

        alerts = await self._engine().generate_alerts(forecasts)

        result = {
            "status": "ok",
            "scan_date": today.isoformat(),
            "cases_scanned": len(cases),
            "forecasts_built": len(forecasts),
            "alerts_generated": len(alerts),
        }
        logger.info("E33GuaranteeScanner: %s", result)
        return result


__all__ = [
    "E33GuaranteeScanner",
    "ScanSwitchState",
    "is_scan_enabled",
    "resolve_scan_switch",
]
