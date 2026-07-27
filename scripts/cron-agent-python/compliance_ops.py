#!/usr/bin/env python3
"""
Compliance Ops — every 6h (00, 06, 12, 18 WITA).

# Organo: compliance-ops (cron-agent-python) → produce: Telegram summary
#         (counts + critical items) + reflection memory.db
# Consuma da: crm_expiry_alerts, crm_practices API (Fly backend)
#
# Ruolo: guardiano delle scadenze. Tocca soldi/clienti/legal — zona sensibile.
#         Nessun LLM nel path (deterministic per fedelta'). Vede documenti
#         critici prima che scadano e notifica con abbastanza anticipo per
#         agire (7d/30d threshold).

Phase 1 — Compliance Autopilot:
  - Expiring documents: critical (<=7d), warning (<=30d)
  - Unpaid invoices >30d old

Phase 2 — Practice Lifecycle:
  - Stale practices (no update 14+ days)
  - Practices with pending docs >7d
  - Completed practices missing invoice

Telegram summary with counts and top critical items.
Fail-hard if we can't reach CRM API.
"""
from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main


class ComplianceOpsJob(AgentJob):
    name = "compliance-ops"
    timeout_s = 300
    requires_side_effects = True  # must send Telegram summary

    async def run(self) -> RunResult:
        # PR-C4 (2026-04-30): session_id was captured but never used for fork/resume.
        # Removed get_or_create_session — it spawns claude --print which times out
        # every run (30s) and CLAUDE.md says "no LLM in compliance — deterministic".
        today = datetime.now(WITA).strftime("%Y-%m-%d")

        # ── Phase 1: Compliance ──────────────────────────────────────────
        # Expiry summary (fast signal)
        expiry_summary = await self.backend_api("/api/crm/expiry-alerts/summary")
        self.log_step("fetch_expiry_summary", outputs=expiry_summary,
                      error=None if expiry_summary else "failed")
        if expiry_summary is None:
            # Fail hard: can't reach CRM
            await self.send_telegram(
                "❌ <b>compliance-ops</b> — CRM backend unreachable\n"
                f"{datetime.now(WITA).strftime('%H:%M WITA')}"
            )
            return RunResult(
                status="error",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                error="CRM backend unreachable (expiry-alerts/summary failed)",
            )

        counts = expiry_summary.get("counts", {})
        urgent = expiry_summary.get("urgent_alerts", [])

        # Expiring detail (for critical items — only if urgent present)
        critical_items = []
        if counts.get("red", 0) > 0 or counts.get("expired", 0) > 0:
            expiry_detail = await self.backend_api(
                "/api/crm/expiry-alerts", params={"days_ahead": 14}
            )
            self.log_step("fetch_expiry_detail", outputs={"count": len(expiry_detail or [])})
            if expiry_detail:
                items = expiry_detail if isinstance(expiry_detail, list) else expiry_detail.get("items", [])
                for item in items[:10]:
                    days = item.get("days_remaining", item.get("days_until_expiry", 999))
                    if days is not None and days <= 7:
                        critical_items.append({
                            "client": item.get("client_name", item.get("client", "?")),
                            "doc_type": item.get("document_type", item.get("type", "?")),
                            "days": days,
                        })

        # ── Phase 2: Practice Lifecycle ──────────────────────────────────
        practices_stats = await self.backend_api("/api/crm/practices/stats/overview")
        self.log_step("fetch_practices_stats", outputs=practices_stats,
                      error=None if practices_stats else "failed")

        # Active practices (to scan for stale)
        active_practices = await self.backend_api("/api/crm/practices/active")
        self.log_step("fetch_active_practices",
                      outputs={"count": len(active_practices) if isinstance(active_practices, list) else 0},
                      error=None if active_practices is not None else "failed")

        stale_count = 0
        pending_docs_count = 0
        missing_invoice_count = 0
        stale_practices: list[dict] = []

        if isinstance(active_practices, list):
            now = datetime.now(WITA)
            stale_threshold = now - timedelta(days=14)
            pending_threshold = now - timedelta(days=7)

            for p in active_practices:
                # Stale: no update in 14+ days
                updated_at = p.get("updated_at") or p.get("last_modified")
                if updated_at:
                    try:
                        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                        if ts < stale_threshold.replace(tzinfo=ts.tzinfo):
                            stale_count += 1
                            stale_practices.append({
                                "id": p.get("id"),
                                "client": p.get("client_name", "?"),
                                "practice_type": p.get("practice_type", "?"),
                                "days_since": (now.replace(tzinfo=ts.tzinfo) - ts).days,
                            })
                    except Exception:
                        pass

                # Pending docs
                if p.get("status") in ("awaiting_documents", "docs_pending"):
                    updated_at = p.get("updated_at")
                    if updated_at:
                        try:
                            ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                            if ts < pending_threshold.replace(tzinfo=ts.tzinfo):
                                pending_docs_count += 1
                        except Exception:
                            pass

                # Completed without invoice (heuristic: status completed but no invoice_id)
                if p.get("status") == "completed" and not p.get("invoice_id"):
                    missing_invoice_count += 1

        # ── Assemble report ──────────────────────────────────────────────
        report_data = {
            "expiry_counts": counts,
            "critical_count": len(critical_items),
            "critical_items": critical_items[:5],
            "practices_total": practices_stats.get("total_practices", 0) if practices_stats else 0,
            "practices_active": practices_stats.get("active_practices", 0) if practices_stats else 0,
            "stale_count": stale_count,
            "stale_items": stale_practices[:3],
            "pending_docs_count": pending_docs_count,
            "missing_invoice_count": missing_invoice_count,
        }

        # ── Build Telegram message (deterministic, no LLM needed) ────────
        msg = self._compose_message(report_data)

        # ── Send ─────────────────────────────────────────────────────────
        ok = await self.send_telegram(msg)
        self.log_step("telegram_send", outputs={"ok": ok},
                      side_effect="compliance_summary" if ok else None,
                      error=None if ok else "telegram_failed")

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

    def _compose_message(self, data: dict) -> str:
        now = datetime.now(WITA)
        counts = data["expiry_counts"]
        total_alerts = counts.get("red", 0) + counts.get("yellow", 0) + counts.get("expired", 0)

        # Determine severity icon
        if counts.get("expired", 0) > 0 or counts.get("red", 0) > 0:
            icon = "🔴"
        elif counts.get("yellow", 0) > 0 or data["stale_count"] > 5:
            icon = "🟡"
        else:
            icon = "🟢"

        lines = [
            f"{icon} <b>Compliance Report</b>",
            f"{now.strftime('%Y-%m-%d %H:%M WITA')}",
            "",
            "<b>Phase 1 — Documenti</b>",
            f"🔴 Scaduti: {counts.get('expired', 0)}",
            f"⚠️ Critici (≤7d): {counts.get('red', 0)}",
            f"🟡 Warning (≤30d): {counts.get('yellow', 0)}",
            f"✅ Verdi: {counts.get('green', 0)}",
        ]

        if data["critical_items"]:
            lines.append("")
            lines.append("<b>Scadenze critiche:</b>")
            for item in data["critical_items"]:
                lines.append(f"• {item['client']} — {item['doc_type']} ({item['days']}d)")

        lines.extend([
            "",
            "<b>Phase 2 — Pratiche</b>",
            f"📋 Totali attive: {data['practices_active']}",
            f"🕐 Stale (&gt;14d): {data['stale_count']}",
            f"📂 Pending docs (&gt;7d): {data['pending_docs_count']}",
            f"💰 Senza fattura: {data['missing_invoice_count']}",
        ])

        if data["stale_items"]:
            lines.append("")
            lines.append("<b>Pratiche stale top:</b>")
            for p in data["stale_items"]:
                lines.append(f"• #{p['id']} {p['client']} — {p['practice_type']} ({p['days_since']}d)")

        # Action required
        needs_action = (
            counts.get("expired", 0) > 0 or
            counts.get("red", 0) > 0 or
            data["missing_invoice_count"] > 0
        )
        if needs_action:
            lines.append("")
            lines.append("👉 <b>Azione richiesta.</b>")

        return "\n".join(lines)

    def _elapsed(self) -> float:
        return time.time() - self.started_at


if __name__ == "__main__":
    main(ComplianceOpsJob)
