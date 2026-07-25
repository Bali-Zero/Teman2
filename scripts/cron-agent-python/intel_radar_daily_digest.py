#!/usr/bin/env python3
"""
Intel Radar — daily digest (18:00 WITA).

# Organo: intel-radar-daily-digest (cron-agent-python) →
#   produce: 1 Telegram digest/day to Zero
#           + UPDATE intel_radar_findings SET processed=true
#           + NOTIFY intel_radar_batch_ready (Postgres) for downstream consumers
# Consuma: intel_radar_findings WHERE processed=false (last 24h)
#
# Ruolo: rifrazione editoriale. Le ricerche orarie del radar accumulano
#         findings in DB silenziosamente. Una volta al giorno, alle 18:00 WITA,
#         questo job legge le findings non-processate, le raggruppa per tier
#         (L1/L2/L3) + per dominio prevalente, manda 1 messaggio Telegram a
#         Zero (executive summary) e marca processed=true. Lo scraper poi pesca.
#
# Replaces: l'orario Telegram di intel_radar.py (rimosso nel refactor 2026-04-26).
#           Frequenza: 24× → 1× al giorno (riduzione spam Telegram, aumento qualità).

Idempotency: marking processed=true is the watermark. Re-running the same day
won't re-notify (zero unprocessed rows). The daemon never DELETEs findings —
only flips the boolean. Decay is owned by E.6 (PR-1.5).

Usage:
    python3 intel_radar_daily_digest.py             # normal run
    python3 intel_radar_daily_digest.py --dry-run   # SELECT only, no UPDATE/notify
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main


class IntelRadarDailyDigestJob(AgentJob):
    name = "intel-radar-daily-digest"
    timeout_s = 60
    requires_side_effects = True  # we always either send digest or log "no findings"

    def __init__(self, dry_run: bool = False) -> None:
        super().__init__()
        self.dry_run = dry_run

    async def run(self) -> RunResult:
        try:
            import asyncpg
        except ImportError:
            return RunResult(
                status="error",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output="asyncpg_missing",
            )

        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            return RunResult(
                status="error",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output="database_url_missing",
            )

        try:
            conn = await asyncpg.connect(dsn, timeout=10)
        except Exception as exc:
            self.logger.error("db_connect_failed", error=str(exc))
            return RunResult(
                status="error",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output=f"db_connect_failed: {exc}",
            )

        try:
            # SELECT unprocessed findings from last 24h.
            # Order by tier (L1 first) then observed_at (newest first) for digest readability.
            rows = await conn.fetch(
                """
                SELECT id, query, query_tier, url, canonical_url, title, description,
                       source_domain, observed_at, source
                FROM intel_radar_findings
                WHERE processed = FALSE
                  AND observed_at > NOW() - INTERVAL '24 hours'
                ORDER BY
                    CASE query_tier WHEN 'L1' THEN 1 WHEN 'L2' THEN 2 ELSE 3 END,
                    observed_at DESC
                """
            )
            self.log_step("fetch_done", outputs={"rows": len(rows)})

            if not rows:
                self.log_step(
                    "no_unprocessed_findings",
                    outputs={"rows": 0},
                    side_effect="no_unprocessed_findings",
                )
                return RunResult(
                    status="ok",
                    duration_s=self._elapsed(),
                    side_effects=self._side_effects,
                    output="no_unprocessed_findings",
                )

            # Build digest message — grouped by tier, top 5 per tier by observed_at.
            msg = self._compose_message(rows)

            if self.dry_run:
                self.log_step("dry_run", outputs={"would_send": True, "msg_chars": len(msg)})
                print(msg)
                return RunResult(
                    status="ok",
                    duration_s=self._elapsed(),
                    side_effects=self._side_effects,
                    output=f"dry_run: {len(rows)} rows",
                )

            # Send Telegram. tier=digest: a scheduled daily report is exactly
            # tg_notify.py's "informative" tier by name and by content — never
            # actionable-now.
            ok = await self.send_telegram(msg, tier="digest")
            self.log_step(
                "telegram_send",
                outputs={"ok": ok, "rows": len(rows)},
                side_effect="intel_radar_daily_digest" if ok else None,
            )

            # Mark processed = TRUE (transactional, all or nothing).
            ids = [r["id"] for r in rows]
            await conn.execute(
                """
                UPDATE intel_radar_findings
                SET processed = TRUE, processed_at = NOW()
                WHERE id = ANY($1::uuid[])
                """,
                ids,
            )
            self.log_step("mark_processed", outputs={"updated": len(ids)})

            # Emit NOTIFY for downstream consumers (intel-scraper supervisor, future).
            await conn.execute(
                "SELECT pg_notify('intel_radar_batch_ready', $1)",
                json.dumps({"count": len(ids), "ts": datetime.now(timezone.utc).isoformat()}),
            )
            self.log_step("notify_emit", outputs={"channel": "intel_radar_batch_ready"})

            return RunResult(
                status="ok",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output=f"digest_sent: {len(rows)} findings",
            )
        finally:
            await conn.close()

    def _compose_message(self, rows: list) -> str:
        """Compose Telegram HTML digest message.

        Layout:
          Header: count + window
          Per-tier section (L1/L2/L3): top 3-5 findings each, with title + domain
          Footer: total + handoff hint
        """
        import html as _html

        now = datetime.now(WITA)
        by_tier: dict[str, list] = defaultdict(list)
        domain_counter: Counter = Counter()

        for r in rows:
            by_tier[r["query_tier"]].append(r)
            if r["source_domain"]:
                domain_counter[r["source_domain"]] += 1

        lines: list[str] = [
            f"📰 <b>Intel Radar — Daily Digest</b>",
            f"<i>{now.strftime('%a %d %b %Y, %H:%M WITA')}</i>",
            f"{len(rows)} findings · "
            + " · ".join(f"{tier}={len(by_tier.get(tier, []))}" for tier in ("L1", "L2", "L3")),
            "",
        ]

        tier_labels = {
            "L1": "🔵 <b>L1 — Core</b> (visa/kitas/KBLI/OSS/pajak)",
            "L2": "🟢 <b>L2 — Adjacent</b> (banking/property/tourism)",
            "L3": "🟡 <b>L3 — Lateral</b> (rupiah/ASEAN/macro)",
        }
        for tier in ("L1", "L2", "L3"):
            tier_rows = by_tier.get(tier, [])
            if not tier_rows:
                continue
            lines.append(tier_labels[tier])
            for r in tier_rows[:5]:
                title = _html.escape((r["title"] or "?")[:120])
                domain = r["source_domain"] or "—"
                lines.append(f"  • <b>{title}</b>")
                lines.append(f"    <i>{_html.escape(domain)}</i>")
            if len(tier_rows) > 5:
                lines.append(f"  <i>… +{len(tier_rows) - 5} more</i>")
            lines.append("")

        if domain_counter:
            top_domains = ", ".join(f"{d} ({c})" for d, c in domain_counter.most_common(3))
            lines.append(f"<i>Top domains:</i> {_html.escape(top_domains)}")

        lines.append("")
        lines.append("<i>↓ Handoff to scraper queue (auto)</i>")

        return "\n".join(lines)

    def _elapsed(self) -> float:
        import time
        return time.time() - self.started_at


def _run_dry_run() -> int:
    """Synchronous entry-point for --dry-run flag (no AgentJob ledger overhead)."""
    job = IntelRadarDailyDigestJob(dry_run=True)
    asyncio.run(job.run())
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Intel Radar daily digest")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print digest without UPDATE/notify/Telegram")
    args, _unknown = parser.parse_known_args()

    if args.dry_run:
        sys.exit(_run_dry_run())

    main(IntelRadarDailyDigestJob)
