"""QuotaMonitor — soft-cap + daily-spike detection on war_room_costs.

Design §14 Rischi / §23.4 Costi.

Soft caps (default, $/mese):
    imagen_ultra:    $5 (one cover/day × 30 × $0.06 = $1.8 → generous)
    imagen_fast:     $10 (5 slides/day × 30 × $0.02 = $3.0)
    fireworks_flux:  $5
    deepseek_api:    $5
    others:          $5

Daily spike: today's total > 3× rolling-average of the previous 7 days.
Alert to Telegram when either condition triggers. Dedup via
``notified_at`` tracking in a new ``war_room_quota_alerts`` ledger
(stored in-memory for now — cron process keeps it between sweeps
via the DB; a dedicated PG table is Sprint 13 scope).

For this sprint we implement detection + alert and accept that if the
cron runs N times per day, N alerts may fire for the same condition.
The alerter sends at most one message per cost_type per sweep.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from backend.services.review.telegram_adapter import TelegramReviewAdapter
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger(__name__)


DEFAULT_SOFT_CAPS_USD: dict[str, float] = {
    "imagen_ultra": 5.0,
    "imagen_fast": 10.0,
    "imagen_other": 5.0,
    "fireworks_flux": 5.0,
    "deepseek_api": 5.0,
    "claude_cli": 0.0,      # OAuth flat-rate; track for observability only
    "gemini_cli": 0.0,
    "ollama_local": 0.0,
    "other": 5.0,
}

DEFAULT_SPIKE_MULTIPLIER = 3.0
DEFAULT_SPIKE_MIN_ABS_USD = 0.5       # ignore spikes under $0.50 abs


@dataclass
class QuotaReport:
    cost_type: str
    total_30d_usd: float
    soft_cap_usd: float
    over_soft_cap: bool
    today_usd: float
    rolling_avg_7d_usd: float
    daily_spike: bool


@dataclass
class QuotaMonitorResult:
    ran_at: datetime
    reports: list[QuotaReport] = field(default_factory=list)
    alerts_sent: int = 0
    errors: list[str] = field(default_factory=list)


class QuotaMonitor:
    """Watches war_room_costs. Alerts on soft-cap breach or daily spike."""

    def __init__(
        self,
        repo: WarRoomRepository,
        telegram: TelegramReviewAdapter,
        owner_chat_id: str | int,
        *,
        soft_caps_usd: dict[str, float] | None = None,
        spike_multiplier: float = DEFAULT_SPIKE_MULTIPLIER,
        spike_min_abs_usd: float = DEFAULT_SPIKE_MIN_ABS_USD,
    ) -> None:
        self.repo = repo
        self.telegram = telegram
        self.owner_chat_id = str(owner_chat_id)
        self.soft_caps = {
            **DEFAULT_SOFT_CAPS_USD,
            **(soft_caps_usd or {}),
        }
        self.spike_multiplier = spike_multiplier
        self.spike_min_abs = spike_min_abs_usd

    async def sweep_once(
        self,
        *,
        now: datetime | None = None,
    ) -> QuotaMonitorResult:
        now = now or datetime.now(timezone.utc)
        result = QuotaMonitorResult(ran_at=now)

        try:
            totals_30d = await self._cost_totals_by_type(days=30)
            today_by_type = await self._cost_totals_by_type_on_date(now.date())
            prior_7d = await self._daily_cost_series(days=7, skip_today=True)
        except Exception as exc:  # noqa: BLE001
            result.errors.append(
                f"fetch: {type(exc).__name__}: {exc}",
            )
            return result

        all_types = set(totals_30d) | set(today_by_type) | set(self.soft_caps)
        for cost_type in sorted(all_types):
            total_30d = float(totals_30d.get(cost_type, 0.0))
            today = float(today_by_type.get(cost_type, 0.0))
            prior = prior_7d.get(cost_type, [])
            rolling_avg = (sum(prior) / len(prior)) if prior else 0.0
            soft_cap = float(self.soft_caps.get(cost_type, 0.0))

            over_soft = soft_cap > 0 and total_30d > soft_cap
            spike = (
                today >= self.spike_min_abs
                and rolling_avg > 0
                and today > rolling_avg * self.spike_multiplier
            )

            report = QuotaReport(
                cost_type=cost_type,
                total_30d_usd=total_30d,
                soft_cap_usd=soft_cap,
                over_soft_cap=over_soft,
                today_usd=today,
                rolling_avg_7d_usd=rolling_avg,
                daily_spike=spike,
            )
            result.reports.append(report)

            if over_soft or spike:
                sent = await self._send_alert(report)
                if sent:
                    result.alerts_sent += 1

        return result

    # ── DB helpers ─────────────────────────────────────────────

    async def _cost_totals_by_type(self, *, days: int) -> dict[str, float]:
        rows = await self.repo.fetch_safe(
            """
            SELECT cost_type, COALESCE(SUM(cost_usd), 0)::float AS total
              FROM war_room_costs
             WHERE occurred_at > NOW() - make_interval(days => $1)
             GROUP BY cost_type;
            """,
            days,
        )
        return {row["cost_type"]: float(row["total"] or 0) for row in rows}

    async def _cost_totals_by_type_on_date(
        self, day: date,
    ) -> dict[str, float]:
        rows = await self.repo.fetch_safe(
            """
            SELECT cost_type, COALESCE(SUM(cost_usd), 0)::float AS total
              FROM war_room_costs
             WHERE DATE(occurred_at AT TIME ZONE 'UTC') = $1
             GROUP BY cost_type;
            """,
            day,
        )
        return {row["cost_type"]: float(row["total"] or 0) for row in rows}

    async def _daily_cost_series(
        self,
        *,
        days: int,
        skip_today: bool = True,
    ) -> dict[str, list[float]]:
        """Per-type list of daily totals for the last ``days`` days (excluding today)."""
        rows = await self.repo.fetch_safe(
            """
            SELECT cost_type,
                   DATE(occurred_at AT TIME ZONE 'UTC') AS day,
                   COALESCE(SUM(cost_usd), 0)::float    AS total
              FROM war_room_costs
             WHERE occurred_at > NOW() - make_interval(days => $1)
             GROUP BY cost_type, day
             ORDER BY cost_type ASC, day ASC;
            """,
            days + (1 if skip_today else 0),
        )
        today = datetime.now(timezone.utc).date()
        out: dict[str, list[float]] = {}
        for row in rows:
            if skip_today and row["day"] == today:
                continue
            out.setdefault(row["cost_type"], []).append(float(row["total"] or 0))
        return out

    # ── Alerting ───────────────────────────────────────────────

    async def _send_alert(self, report: QuotaReport) -> bool:
        icon = "🚨" if report.over_soft_cap else "⚡"
        lines = [
            f"{icon} <b>War Room quota — {_escape_html(report.cost_type)}</b>",
        ]
        if report.over_soft_cap:
            lines.append(
                f"30d totale: ${report.total_30d_usd:.2f} "
                f"(soft cap ${report.soft_cap_usd:.2f})"
            )
        if report.daily_spike:
            lines.append(
                f"Spike oggi: ${report.today_usd:.3f} "
                f"vs media 7gg ${report.rolling_avg_7d_usd:.3f}"
            )
        sr = await self.telegram.send_message(
            chat_id=self.owner_chat_id,
            text="\n".join(lines),
        )
        return sr.ok


def _escape_html(value: str) -> str:
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
