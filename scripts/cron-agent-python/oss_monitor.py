#!/usr/bin/env python3
"""
OSS System Announcements Monitor — every 2h (08:00-22:00 WITA).

# Organo: oss-monitor (cron-agent-python, browser scraper) → produce:
#         Telegram alert (se nuovi annunci) + Redis hash `bz:oss:announcements`
#         consumato da: ops team, compliance-ops, daily-ops
# Consuma da: oss.go.id (public, no auth required for announcements page)
#
# Ruolo: sentinella OSS. Monitora annunci e comunicasi sistema OSS
#         (downtime, nuove procedure, aggiornamenti normativa perizinan).
#         OSS è critico per PT PMA, NIB, perizinan — downtime impatta clienti.

Monitors oss.go.id for:
  - System announcements / pengumuman
  - Maintenance windows
  - New procedure updates
  - Service status changes

Deduplication via Redis hash (url → hash of content).
Alerts only on NEW announcements not seen before.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main
from browser_job import BrowserJob


OSS_ANNOUNCEMENTS_URL = "https://oss.go.id/id/pengumuman"
OSS_BERITA_URL = "https://oss.go.id/id/berita"
OSS_HOME_URL = "https://oss.go.id/id"
REDIS_KEY = "bz:oss:announcements"
REDIS_EXPIRY = 86400 * 30  # 30 days (keep seen announcements)


class OssMonitorJob(BrowserJob):
    name = "oss-monitor"
    target_url = OSS_ANNOUNCEMENTS_URL
    timeout_s = 180
    page_timeout_ms = 20000
    requires_side_effects = False  # only fires side effects if new announcements

    async def run(self) -> RunResult:
        """Fetch OSS announcements, diff against known, alert on new."""
        # Check robots
        if not await self._check_robots(self.target_url):
            return RunResult(status="error", duration_s=self._elapsed(),
                             error="robots.txt disallows")

        # Fetch berita page (contains article slugs in Next.js RSC payload)
        await self.random_delay(1.0, 3.0)
        try:
            page = await self.fetch_page(OSS_BERITA_URL)
            html = page["html"]
        except Exception as e:
            self._record_failure()
            return RunResult(status="error", duration_s=self._elapsed(),
                             side_effects=self._side_effects,
                             error=f"fetch failed: {e}")

        self.log_step("fetch_done", outputs={"html_len": len(html)})

        # Parse announcements from RSC payload
        announcements = self._parse_announcements(html)
        self.log_step("parse_done", outputs={"count": len(announcements)})

        # Deduplicate against Redis
        new_announcements = await self._filter_new(announcements)
        self.log_step("dedup_done", outputs={"new": len(new_announcements), "total": len(announcements)})

        if not new_announcements:
            # No new announcements — silent success
            self._record_success()
            return RunResult(
                status="ok",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output="no_new_announcements",
            )

        # Store new in Redis
        await self._mark_seen(new_announcements)

        # Alert via Telegram
        msg = self._compose_alert(new_announcements)
        ok = await self.send_telegram(msg)
        self.log_step("telegram_send", outputs={"ok": ok},
                      side_effect="oss_alert" if ok else None,
                      error=None if ok else "telegram_failed")

        self._record_success()
        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=json.dumps(new_announcements, default=str),
        )

    def _parse_announcements(self, html: str) -> list[dict]:
        """Extract announcement items from OSS Next.js RSC HTML.

        OSS uses Next.js with RSC streaming — article data is embedded in
        self.__next_f.push payloads as JSON strings containing slugs.
        """
        import json as _json
        announcements = []
        seen_slugs: set = set()

        # Extract Next.js RSC payloads
        payloads = re.findall(r'self\.__next_f\.push\(\[1,(.+?)\]\)', html, re.DOTALL)
        for payload in payloads:
            try:
                decoded = _json.loads(payload)  # payload is a JSON string
            except Exception:
                continue
            # Extract slugs (only Indonesian ones, skip English duplicates)
            slugs = re.findall(r'"slug":"([a-z0-9][a-z0-9\-]{10,}[a-z0-9])"', decoded)
            for slug in slugs:
                # Skip English duplicate slugs (contain apostrophe escapes or English words)
                if slug in seen_slugs:
                    continue
                if any(kw in slug for kw in ["'s-", "women", "commitment-of", "service-declaration:"]):
                    continue
                seen_slugs.add(slug)
                # Convert slug to readable title
                title = slug.replace("-", " ").title()
                announcements.append({
                    "title": title[:300],
                    "date": "",
                    "hash": hashlib.md5(slug.encode()).hexdigest()[:12],
                    "url": f"https://oss.go.id/id/berita/{slug}",
                })

        return announcements[:20]

    async def _filter_new(self, announcements: list[dict]) -> list[dict]:
        """Return only announcements not previously seen (via Redis hash)."""
        if not announcements:
            return []
        try:
            result = subprocess.run(
                ["redis-cli", "HKEYS", REDIS_KEY],
                capture_output=True, text=True, timeout=5
            )
            known: set = set(result.stdout.strip().splitlines()) if result.returncode == 0 else set()
            return [a for a in announcements if a.get("hash") not in known]
        except Exception as e:
            self.logger.warning("redis_filter_error", error=str(e))
            return announcements

    async def _mark_seen(self, announcements: list[dict]) -> None:
        """Mark announcements as seen in Redis."""
        try:
            for ann in announcements:
                h = ann.get("hash", "")
                if h:
                    subprocess.run(
                        ["redis-cli", "HSET", REDIS_KEY, h,
                         json.dumps({"title": ann["title"], "url": ann.get("url", ""), "ts": int(time.time())})],
                        capture_output=True, timeout=5
                    )

                # Intel Lake Wave 3 (2026-05-12): dual-write to local SQLite
                # outbox. Best-effort — failure must not block existing flow.
                try:
                    import hashlib as _h, sys as _sys  # noqa: PLC0415
                    # task #17 (2026-07-26): was a literal "/Users/nuzantara/scripts" —
                    # fingerprints the ops host's username/home layout, and it is this
                    # organism's own catalogued HOME-fork anti-pattern. Derived from
                    # __file__ instead: this file lives at <...>/scripts/cron-agent-python/,
                    # intel_lake_outbox.py lives one level up at <...>/scripts/.
                    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                    from intel_lake_outbox import enqueue as _lake_enqueue  # type: ignore
                    url = ann.get("url", "") or f"oss://announcement/{h}"
                    title = ann.get("title", "")
                    _ch = _h.sha256((title + " " + url).encode()).hexdigest()[:32]
                    _lake_enqueue(
                        "oss_monitor",
                        {
                            "producer_name": "oss_monitor",
                            "canonical_url": url,
                            "content_hash": _ch,
                            "title": title[:500],
                            "summary": ann.get("summary", "")[:2000] if ann.get("summary") else None,
                            "source_domain": "oss.go.id",
                            "language": "id",
                            "jurisdiction": "ID-national",
                            "topic_tags": ["pma", "bkpm", "oss", "regulation", "announcement"],
                            "published_at": ann.get("date") or None,
                            "score": None,
                            "raw_payload": {
                                "redis_hash": h,
                                "type": "announcement",
                            },
                        },
                    )
                except Exception as exc:
                    self.logger.warning("intel_lake_enqueue_failed", error=str(exc), url=ann.get("url", "")[:80])

            subprocess.run(
                ["redis-cli", "EXPIRE", REDIS_KEY, str(REDIS_EXPIRY)],
                capture_output=True, timeout=5
            )
        except Exception as e:
            self.logger.warning("redis_mark_error", error=str(e))

    def _compose_alert(self, new_announcements: list[dict]) -> str:
        now = datetime.now(WITA)
        lines = [
            f"📢 <b>OSS Announcement</b> ({len(new_announcements)} new)",
            f"{now.strftime('%Y-%m-%d %H:%M WITA')}",
            "",
        ]
        for ann in new_announcements[:5]:
            date = f" ({ann['date']})" if ann.get("date") else ""
            lines.append(f"• {ann['title'][:200]}{date}")

        if len(new_announcements) > 5:
            lines.append(f"... +{len(new_announcements) - 5} altri")

        lines.append("")
        lines.append(f"🔗 <a href='https://oss.go.id/id/pengumuman'>oss.go.id/pengumuman</a>")
        return "\n".join(lines)

    def scrape(self, html: str, text: str) -> dict:
        """Not used — run() is fully overridden."""
        return {}


if __name__ == "__main__":
    main(OssMonitorJob)
