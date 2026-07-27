#!/usr/bin/env python3
"""
Daily Ops — daily 08:00 WITA.

# Organo: daily-ops (cron-agent-python) → produce: Telegram briefing (chat Zero) +
#         reflection in memory.db → consuma da: CRM API Fly backend
#
# Ruolo nell'organismo: sveglia il team al mattino con snapshot business.
# Upstream: crm_clients, crm_practices, crm_expiry_alerts (Fly backend)
# Downstream: Zero legge su Telegram, decide priorità giornata.

Phase 1 — Business Orchestration: CRM stats + expiring practices + renewals.
Phase 2 — Daily Ops: compose briefing via Claude SDK narrative synthesis.

Uses deterministic Python for data collection, Claude SDK for narrative synthesis,
Telegram for delivery. Fail-hard if Telegram delivery fails.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main


class DailyOpsJob(AgentJob):
    name = "daily-ops"
    timeout_s = 300
    requires_side_effects = True  # must send Telegram

    async def run(self) -> RunResult:
        today = datetime.now(WITA).strftime("%Y-%m-%d")

        # ── Phase 1: collect data ─────────────────────────────────────────
        data: dict = {"date": today}

        # CRM client stats
        clients = await self.backend_api("/api/crm/clients/stats/overview")
        self.log_step("fetch_clients_stats", outputs=clients, error=None if clients else "failed")
        if clients:
            data["clients"] = {
                "total": clients.get("total_clients", 0),
                "active": clients.get("active_clients", 0),
                "new_this_month": clients.get("new_this_month", 0),
            }

        # Practice stats
        practices = await self.backend_api("/api/crm/practices/stats/overview")
        self.log_step("fetch_practices_stats", outputs=practices, error=None if practices else "failed")
        if practices:
            data["practices"] = {
                "total": practices.get("total_practices", 0),
                "active": practices.get("active_practices", 0),
                "completed_this_month": practices.get("completed_this_month", 0),
                "pending": practices.get("pending_practices", 0),
            }

        # Expiring documents (90 days ahead)
        expiring = await self.backend_api("/api/crm/expiry-alerts", params={"days_ahead": 90})
        self.log_step("fetch_expiry_alerts", outputs=expiring, error=None if expiring else "failed")
        critical_expiring = []
        if expiring and isinstance(expiring, dict):
            items = expiring.get("alerts", []) or expiring.get("items", []) or []
            # Filter critical (<= 7 days)
            for item in items:
                days = item.get("days_remaining", item.get("days_until_expiry", 999))
                if days is not None and days <= 7:
                    critical_expiring.append(item)
            data["expiring"] = {
                "total_90d": len(items),
                "critical_7d": len(critical_expiring),
                "critical_items": [
                    {
                        "client": i.get("client_name", i.get("client", "?")),
                        "doc_type": i.get("document_type", i.get("type", "?")),
                        "days": i.get("days_remaining", i.get("days_until_expiry", "?")),
                    }
                    for i in critical_expiring[:5]
                ],
            }

        # Upcoming renewals
        renewals = await self.backend_api("/api/crm/practices/renewals/upcoming", params={"days": 30})
        self.log_step("fetch_renewals", outputs=renewals, error=None if renewals is not None else "failed")
        if renewals:
            renewal_items = renewals if isinstance(renewals, list) else renewals.get("items", [])
            data["renewals_30d"] = len(renewal_items)

        # ── Phase 2: narrative synthesis ──────────────────────────────────
        synth_prompt = (
            "Compose a concise daily operational briefing in Italian for the Bali Zero team. "
            "Use this JSON data as input. Output MUST be plain text (no markdown headers) "
            "suitable for a Telegram message, 5-8 lines, with emoji bullets (📊 ⚠️ ✅ 📅). "
            "Start with 'Buongiorno team.' and end with 'Buona giornata.'.\n\n"
            f"DATA:\n{data}\n\n"
            "Focus on: critical expiring docs, practice load, renewals this month. "
            "Flag anything needing urgent attention. Be specific with numbers."
        )

        narrative = await self.claude_synthesize(
            prompt=synth_prompt,
            max_turns=1,
            effort="low",
            system_prompt="You are a senior ops coordinator. Output only the final message text, nothing else.",
            adaptive_thinking=True,  # Opus 4.7 auto-modulates thinking depth
        )
        self.log_step("synthesize_narrative", outputs={"len": len(narrative)}, error=None if narrative else "empty")

        if not narrative or narrative.startswith("[synthesis error"):
            # Fallback to deterministic summary
            narrative = self._fallback_summary(data)
            self.log_step("fallback_summary", outputs={"len": len(narrative)})

        # ── Phase 3: delivery ─────────────────────────────────────────────
        header = f"📅 <b>Daily Ops {today}</b>\n\n"
        full_msg = header + narrative
        ok = await self.send_telegram(full_msg)
        self.log_step("telegram_send", outputs={"ok": ok}, side_effect=f"telegram_briefing" if ok else None,
                      error=None if ok else "telegram_failed")

        if not ok:
            return RunResult(
                status="error",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output=narrative,
                error="Telegram delivery failed — briefing not sent",
            )

        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=narrative,
        )

    def _elapsed(self) -> float:
        import time
        return time.time() - self.started_at

    def _fallback_summary(self, data: dict) -> str:
        lines = ["Buongiorno team."]
        if "clients" in data:
            c = data["clients"]
            lines.append(f"📊 Clienti: {c['active']}/{c['total']} attivi, {c['new_this_month']} nuovi questo mese")
        if "practices" in data:
            p = data["practices"]
            lines.append(f"📋 Pratiche: {p['active']} attive, {p['pending']} in attesa, {p['completed_this_month']} completate")
        if "expiring" in data:
            e = data["expiring"]
            lines.append(f"⚠️ Scadenze: {e['critical_7d']} critiche (≤7gg), {e['total_90d']} totali (≤90gg)")
            for item in e.get("critical_items", [])[:3]:
                lines.append(f"   • {item['client']} — {item['doc_type']} ({item['days']}gg)")
        if data.get("renewals_30d"):
            lines.append(f"📅 Rinnovi: {data['renewals_30d']} nei prossimi 30gg")
        lines.append("Buona giornata.")
        return "\n".join(lines)


if __name__ == "__main__":
    main(DailyOpsJob)
