#!/usr/bin/env python3
"""
Immigration Regulation Monitor — daily 06:00 WITA.

# Organo: imigrasi-monitor (cron-agent-python, browser scraper) → produce:
#         Telegram alert (nuovi regolamenti) + Intel Stage 1 JSON
#         consumato da: Intel Scraper pipeline, compliance-ops, NLM ingest
# Consuma da: imigrasi.go.id (public), peraturan.go.id (public)
#
# Ruolo: antenna normativa immigrazione. Rileva nuovi circulari, peraturan,
#         e comunicasi dari Ditjen Imigrasi prima che impattino clienti.
#         Ogni nuova normativa → Intel Stage 1 feed → enrichment pipeline.

Monitors:
  - imigrasi.go.id/berita — news/announcements
  - imigrasi.go.id/layanan — service updates
  - peraturan.go.id (filter: imigrasi keyword)

Output:
  - Redis set `bz:imigrasi:seen_urls` for deduplication
  - Intel Stage 1 JSON files in ~/.intel_scraper/incoming/
  - Telegram alert with new regulation summary
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


IMIGRASI_NEWS_URL = "https://www.imigrasi.go.id/berita"
IMIGRASI_PRODUK_HUKUM_URL = "https://www.imigrasi.go.id/produk-hukum/peraturan-pemerintah"
IMIGRASI_WNA_URL = "https://www.imigrasi.go.id/wna/izin-tinggal-keimigrasian"
PERATURAN_URL = "https://peraturan.go.id/search?q=imigrasi&type=peraturan"

REDIS_KEY_SEEN = "bz:imigrasi:seen_urls"
REDIS_EXPIRY = 86400 * 90  # 90 days

# Intel Stage 1 output dir (matches bali-intel-scraper input)
INTEL_INCOMING_DIR = Path.home() / ".intel_scraper" / "incoming"


class ImigrasiMonitorJob(BrowserJob):
    name = "imigrasi-monitor"
    target_url = IMIGRASI_NEWS_URL
    timeout_s = 240
    page_timeout_ms = 20000
    requires_side_effects = False  # only fires if new regulations found

    async def run(self) -> RunResult:
        """Multi-source regulation monitoring."""
        all_items: list[dict] = []

        # Source 1: imigrasi.go.id/berita
        items_berita = await self._fetch_imigrasi_berita()
        all_items.extend(items_berita)
        self.log_step("fetch_berita", outputs={"count": len(items_berita)})

        await self.random_delay(2.0, 4.0)

        # Source 2: imigrasi.go.id/produk-hukum (legal products)
        items_layanan = await self._fetch_imigrasi_produk_hukum()
        all_items.extend(items_layanan)
        self.log_step("fetch_produk_hukum", outputs={"count": len(items_layanan)})

        # Deduplicate by URL
        seen_urls = await self._get_seen_urls()
        new_items = [i for i in all_items if i.get("url") and i["url"] not in seen_urls]
        self.log_step("dedup", outputs={"new": len(new_items), "total": len(all_items)})

        if not new_items:
            self._record_success()
            return RunResult(
                status="ok",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output="no_new_regulations",
            )

        # Mark as seen
        await self._mark_seen([i["url"] for i in new_items])

        # Write Intel Stage 1 feed
        intel_count = self._write_intel_feed(new_items)
        if intel_count > 0:
            self._side_effects.append(f"intel_feed:{intel_count}")
            self.log_step("intel_feed_written", outputs={"count": intel_count})

        # Telegram alert
        msg = self._compose_alert(new_items)
        ok = await self.send_telegram(msg)
        self.log_step("telegram_send", outputs={"ok": ok},
                      side_effect="imigrasi_alert" if ok else None,
                      error=None if ok else "telegram_failed")

        self._record_success()
        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=json.dumps(new_items[:5], default=str),
        )

    async def _fetch_imigrasi_berita(self) -> list[dict]:
        """Fetch imigrasi.go.id/berita news items."""
        if not await self._check_robots(IMIGRASI_NEWS_URL):
            return []
        try:
            page = await self.fetch_page(IMIGRASI_NEWS_URL)
            return self._parse_imigrasi_articles(page["html"], source="imigrasi_berita")
        except Exception as e:
            self.logger.warning("berita_fetch_error", error=str(e))
            return []

    async def _fetch_imigrasi_produk_hukum(self) -> list[dict]:
        """Fetch imigrasi.go.id legal products (peraturan pemerintah)."""
        if not await self._check_robots(IMIGRASI_PRODUK_HUKUM_URL):
            return []
        try:
            page = await self.fetch_page(IMIGRASI_PRODUK_HUKUM_URL)
            return self._parse_imigrasi_articles(page["html"], source="imigrasi_produk_hukum")
        except Exception as e:
            self.logger.warning("produk_hukum_fetch_error", error=str(e))
            return []

    async def _fetch_peraturan(self) -> list[dict]:
        """Fetch peraturan.go.id search for imigrasi regulations."""
        if not await self._check_robots(PERATURAN_URL):
            return []
        try:
            page = await self.fetch_page(PERATURAN_URL)
            return self._parse_peraturan(page["html"])
        except Exception as e:
            self.logger.warning("peraturan_fetch_error", error=str(e))
            return []

    def _parse_imigrasi_articles(self, html: str, source: str) -> list[dict]:
        """Parse article links from imigrasi.go.id."""
        items = []
        seen: set = set()

        # Extract article links with titles
        patterns = [
            # Standard article cards
            re.compile(
                r'<a[^>]+href="(https?://(?:www\.)?imigrasi\.go\.id/[^"]+)"[^>]*>'
                r'\s*(?:<[^>]+>)*\s*([^<]{15,300})\s*(?:</[^>]+>)*\s*</a>',
                re.DOTALL | re.IGNORECASE,
            ),
            # Relative URLs
            re.compile(
                r'<a[^>]+href="(/(?:berita|layanan|info|pengumuman)/[^"]+)"[^>]*>'
                r'\s*(?:<[^>]+>)*\s*([^<]{15,300})\s*(?:</[^>]+>)*\s*</a>',
                re.DOTALL | re.IGNORECASE,
            ),
        ]
        base_url = "https://www.imigrasi.go.id"
        for pattern in patterns:
            for m in pattern.finditer(html[:100000]):
                url = m.group(1)
                if not url.startswith("http"):
                    url = f"{base_url}{url}"
                title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                title = re.sub(r'\s+', ' ', title)
                if (url not in seen and title and len(title) >= 15
                        and "imigrasi.go.id" in url):
                    seen.add(url)
                    items.append({
                        "url": url,
                        "title": title[:300],
                        "source": source,
                        "scraped_at": datetime.now(WITA).isoformat(),
                        "type": "news" if "berita" in url else "service",
                    })
        return items[:15]

    def _parse_peraturan(self, html: str) -> list[dict]:
        """Parse peraturan.go.id search results."""
        items = []
        seen: set = set()
        pattern = re.compile(
            r'<a[^>]+href="(https?://peraturan\.go\.id/[^"]*)"[^>]*>'
            r'\s*(?:<[^>]+>)*\s*([^<]{15,300})\s*',
            re.DOTALL | re.IGNORECASE,
        )
        for m in pattern.finditer(html[:80000]):
            url = m.group(1)
            title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
            title = re.sub(r'\s+', ' ', title)
            if (url not in seen and title and len(title) >= 15
                    and any(kw in title.lower() for kw in ["imigras", "keimigras", "visa", "kitas", "kitap"])):
                seen.add(url)
                items.append({
                    "url": url,
                    "title": title[:300],
                    "source": "peraturan_go_id",
                    "scraped_at": datetime.now(WITA).isoformat(),
                    "type": "regulation",
                })
        return items[:10]

    async def _get_seen_urls(self) -> set:
        """Get previously seen URLs from Redis set."""
        try:
            result = subprocess.run(
                ["redis-cli", "SMEMBERS", REDIS_KEY_SEEN],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return set(result.stdout.strip().splitlines())
        except Exception:
            pass
        return set()

    async def _mark_seen(self, urls: list[str]) -> None:
        """Add URLs to Redis seen set."""
        try:
            for url in urls:
                subprocess.run(
                    ["redis-cli", "SADD", REDIS_KEY_SEEN, url],
                    capture_output=True, timeout=5
                )
            subprocess.run(
                ["redis-cli", "EXPIRE", REDIS_KEY_SEEN, str(REDIS_EXPIRY)],
                capture_output=True, timeout=5
            )
        except Exception as e:
            self.logger.warning("redis_mark_error", error=str(e))

    def _write_intel_feed(self, items: list[dict]) -> int:
        """Write Intel Stage 1 JSON files for pipeline processing."""
        try:
            INTEL_INCOMING_DIR.mkdir(parents=True, exist_ok=True)
            count = 0
            for item in items:
                ts = int(time.time())
                filename = f"imigrasi_{ts}_{hashlib.md5(item['url'].encode()).hexdigest()[:8]}.json"
                feed_file = INTEL_INCOMING_DIR / filename
                feed_file.write_text(json.dumps({
                    "source": item.get("source", "imigrasi"),
                    "url": item["url"],
                    "title": item["title"],
                    "type": item.get("type", "news"),
                    "scraped_at": item.get("scraped_at"),
                    "pipeline": "intel_stage1",
                }, indent=2))
                count += 1

                # Intel Lake Wave 3 (2026-05-12): dual-write to local SQLite
                # outbox so the lake observation table sees this finding.
                # Best-effort — failure must not block the existing flow.
                try:
                    import sys as _sys  # noqa: PLC0415
                    # task #17 (2026-07-26): was a literal "/Users/nuzantara/scripts" —
                    # fingerprints the ops host's username/home layout, and it is this
                    # organism's own catalogued HOME-fork anti-pattern. Derived from
                    # __file__ instead: this file lives at <...>/scripts/cron-agent-python/,
                    # intel_lake_outbox.py lives one level up at <...>/scripts/.
                    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                    from intel_lake_outbox import enqueue as _lake_enqueue  # type: ignore
                    _ch = hashlib.sha256(
                        (item["title"] + " " + item["url"]).encode()
                    ).hexdigest()[:32]
                    _lake_enqueue(
                        "imigrasi_monitor",
                        {
                            "producer_name": "imigrasi_monitor",
                            "canonical_url": item["url"],
                            "content_hash": _ch,
                            "title": item["title"][:500],
                            "summary": item.get("summary", "")[:2000] if item.get("summary") else None,
                            "source_domain": "imigrasi.go.id",
                            "language": "id",
                            "jurisdiction": "ID-national",
                            "topic_tags": ["visa", "immigration", item.get("type", "news")],
                            "published_at": item.get("scraped_at"),
                            "score": None,
                            "raw_payload": {
                                "pipeline": "intel_stage1",
                                "type": item.get("type", "news"),
                            },
                        },
                    )
                except Exception as exc:
                    self.logger.warning("intel_lake_enqueue_failed", error=str(exc), url=item.get("url", "")[:80])
            return count
        except Exception as e:
            self.logger.error("intel_feed_error", error=str(e))
            return 0

    def _compose_alert(self, new_items: list[dict]) -> str:
        now = datetime.now(WITA)
        # Group by type
        regulations = [i for i in new_items if i.get("type") == "regulation"]
        news = [i for i in new_items if i.get("type") != "regulation"]

        lines = [
            f"🛂 <b>Imigrasi Monitor</b> — {len(new_items)} new",
            f"{now.strftime('%Y-%m-%d %H:%M WITA')}",
            "",
        ]

        if regulations:
            lines.append(f"<b>📜 Peraturan ({len(regulations)}):</b>")
            for r in regulations[:3]:
                lines.append(f"• {r['title'][:150]}")

        if news:
            lines.append(f"\n<b>📰 Berita/Layanan ({len(news)}):</b>")
            for n in news[:3]:
                lines.append(f"• {n['title'][:150]}")

        if len(new_items) > 6:
            lines.append(f"\n... +{len(new_items) - 6} altri")

        lines.append(f"\n📦 Intel feed: {len(new_items)} items → pipeline")
        return "\n".join(lines)

    def scrape(self, html: str, text: str) -> dict:
        """Not used — run() is fully overridden."""
        return {}


if __name__ == "__main__":
    main(ImigrasiMonitorJob)
