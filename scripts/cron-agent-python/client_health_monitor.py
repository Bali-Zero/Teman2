#!/usr/bin/env python3
"""
Client Health Monitor — daily 14:00 WITA.

# Organo: client-health-monitor (cron-agent-python) → produce: Telegram
#         summary (chat Zero) + separate burnout alert (owner-only, se RED)
#         + reflection memory.db
# Consuma da: crm_clients, crm_analytics team_performance (Fly backend)
#
# Ruolo: sentinella relazionale. L'organismo monitora il carico umano
#         sulla squadra — un membro overloaded e' churn risk per il cliente
#         e health risk per la persona. Nessun LLM nel path (threshold
#         deterministici da CLAUDE.md policy).

Reports client engagement health:
- Client stats (total, active, by status, by team)
- Team performance (conversion rate, revenue, active load)
- Burnout signals (overloaded team members = churn risk indicator)
- Top team by load (for redistribution suggestions)

Telegram summary with team metrics + action flags.
Fail-hard if CRM unreachable.
"""
from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main


# Thresholds (match CLAUDE.md burnout policy)
BURNOUT_ACTIVE_THRESHOLD = 15  # >15 active practices = overload
BURNOUT_ACTIVE_YELLOW = 10     # >10 = warning
CHURN_INACTIVE_RATIO_THRESHOLD = 0.7  # if inactive/total > 70% on a team member


class ClientHealthMonitor(AgentJob):
    name = "client-health-monitor"
    timeout_s = 180
    requires_side_effects = True  # must send Telegram summary

    async def run(self) -> RunResult:
        # ── Collect ──────────────────────────────────────────────────────
        clients_overview = await self.backend_api("/api/crm/clients/stats/overview")
        self.log_step("fetch_clients_stats", outputs=clients_overview,
                      error=None if clients_overview else "failed")

        if not clients_overview:
            # Fail hard: can't reach CRM
            await self.send_telegram(
                "❌ <b>client-health-monitor</b> — CRM unreachable\n"
                f"{datetime.now(WITA).strftime('%H:%M WITA')}"
            )
            return RunResult(
                status="error",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                error="CRM clients/stats/overview failed",
            )

        team_performance = await self.backend_api("/api/crm/analytics/team/performance")
        self.log_step("fetch_team_performance", outputs={"count": len(team_performance) if team_performance else 0},
                      error=None if team_performance else "skipped_or_failed")

        # ── Analyze ──────────────────────────────────────────────────────
        total_clients = clients_overview.get("total", 0)
        by_status = clients_overview.get("by_status", {})
        by_team = clients_overview.get("by_team_member", [])

        # Top 5 team by load
        top_team = sorted(by_team, key=lambda t: t.get("count", 0), reverse=True)[:5]

        # Burnout detection
        burnout_red: list[dict] = []
        burnout_yellow: list[dict] = []

        if team_performance and isinstance(team_performance, list):
            for member in team_performance:
                active = member.get("active_clients", 0)
                email = member.get("member_email", "?")
                conv_rate = member.get("conversion_rate", 0)
                revenue = member.get("revenue_generated", 0)

                if active >= BURNOUT_ACTIVE_THRESHOLD:
                    burnout_red.append({
                        "member": email.split("@")[0],
                        "active": active,
                        "conversion_rate": conv_rate,
                    })
                elif active >= BURNOUT_ACTIVE_YELLOW:
                    burnout_yellow.append({
                        "member": email.split("@")[0],
                        "active": active,
                        "conversion_rate": conv_rate,
                    })

        # Churn indicators
        inactive = by_status.get("inactive", 0)
        active = by_status.get("active", 0)
        churn_rate_pct = (inactive / total_clients * 100) if total_clients else 0

        # Top revenue performer
        top_revenue_member = None
        if team_performance:
            by_rev = sorted(team_performance, key=lambda m: m.get("revenue_generated", 0) or 0, reverse=True)
            if by_rev:
                top_revenue_member = by_rev[0]

        # ── Compose message ──────────────────────────────────────────────
        msg = self._compose_message(
            total_clients=total_clients,
            by_status=by_status,
            churn_rate_pct=churn_rate_pct,
            top_team=top_team,
            burnout_red=burnout_red,
            burnout_yellow=burnout_yellow,
            top_revenue_member=top_revenue_member,
        )

        # ── Deliver ──────────────────────────────────────────────────────
        ok = await self.send_telegram(msg)
        self.log_step("telegram_send", outputs={"ok": ok},
                      side_effect="client_health_summary" if ok else None,
                      error=None if ok else "telegram_failed")

        # Burnout alert (separate message to owner if RED)
        if burnout_red:
            burnout_msg = self._compose_burnout_alert(burnout_red)
            await self.send_telegram(burnout_msg)
            self._side_effects.append("burnout_alert")
            self.log_step("burnout_alert_sent", outputs={"count": len(burnout_red)})

        if not ok:
            return RunResult(
                status="error",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output=msg,
                error="Telegram delivery failed",
            )

        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=msg,
        )

    def _compose_message(
        self,
        total_clients: int,
        by_status: dict,
        churn_rate_pct: float,
        top_team: list[dict],
        burnout_red: list[dict],
        burnout_yellow: list[dict],
        top_revenue_member: dict | None,
    ) -> str:
        now = datetime.now(WITA)

        # Overall icon
        if burnout_red:
            icon = "🔴"
        elif burnout_yellow or churn_rate_pct > 10:
            icon = "🟡"
        else:
            icon = "🟢"

        lines = [
            f"{icon} <b>Client Health Report</b>",
            f"{now.strftime('%Y-%m-%d %H:%M WITA')}",
            "",
            "<b>Client stats</b>",
            f"📊 Totale: <b>{total_clients}</b>",
        ]

        # Status breakdown
        for status in ("active", "prospect", "lead", "inactive"):
            if status in by_status:
                pct = by_status[status] / total_clients * 100 if total_clients else 0
                emoji = {"active": "✅", "prospect": "🟦", "lead": "🆕", "inactive": "⚪"}[status]
                lines.append(f"{emoji} {status.capitalize()}: {by_status[status]} ({pct:.1f}%)")

        lines.append(f"📉 Churn rate: {churn_rate_pct:.1f}%")

        # Top team by load
        if top_team:
            lines.append("")
            lines.append("<b>Top 5 team (by client load)</b>")
            for m in top_team:
                email = m.get("assigned_to", "?")
                name = email.split("@")[0] if "@" in email else email
                count = m.get("count", 0)
                lines.append(f"• {name}: {count} clienti")

        # Burnout warnings
        if burnout_red:
            lines.append("")
            lines.append("🚨 <b>BURNOUT RED</b> (>15 active)")
            for b in burnout_red:
                lines.append(f"• {b['member']}: {b['active']} active (conv: {b['conversion_rate']:.0f}%)")

        if burnout_yellow:
            lines.append("")
            lines.append("⚠️ <b>BURNOUT YELLOW</b> (10-15 active)")
            for b in burnout_yellow:
                lines.append(f"• {b['member']}: {b['active']} active")

        # Top revenue
        if top_revenue_member:
            email = top_revenue_member.get("member_email", "?")
            name = email.split("@")[0]
            rev = top_revenue_member.get("revenue_generated", 0)
            rev_m = rev / 1_000_000 if rev else 0
            lines.append("")
            lines.append(f"💰 Top revenue: <b>{name}</b> — {rev_m:.0f}M IDR")

        # Action flag
        if burnout_red:
            lines.append("")
            lines.append("👉 Considera redistribuzione carichi.")

        return "\n".join(lines)

    def _compose_burnout_alert(self, burnout_red: list[dict]) -> str:
        lines = [
            "🚨 <b>BURNOUT RISK ALERT</b>",
            "Team members with >15 active practices:",
            "",
        ]
        for b in burnout_red:
            lines.append(f"• <b>{b['member']}</b> — {b['active']} active (conv: {b['conversion_rate']:.0f}%)")
        lines.append("")
        lines.append("👉 Considera redistribuzione. Questo messaggio va solo a owner.")
        return "\n".join(lines)

    def _elapsed(self) -> float:
        return time.time() - self.started_at


if __name__ == "__main__":
    main(ClientHealthMonitor)
