#!/usr/bin/env python3
"""
Pajak (Tax) Regulation Monitor — daily 08:00 WITA.

# Organo: pajak-monitor (cron-agent-python, browser scraper) → produce:
#         Telegram alert (nuove normative) + Intel Stage 1 JSON
# Consuma da: pajak.go.id (DJP — Direktorat Jenderal Pajak) public pages
#
# Ruolo: antenna normativa fiscale. Monitora nuove peraturan pajak
#         rilevanti per clienti Bali Zero (PPN, PPh, PBJT, incentivi).
#         Ogni nuova normativa fiscale → Intel Stage 1 pipeline → enrichment.

Monitors:
  - pajak.go.id/peraturan-terbaru (new tax regulations)
  - pajak.go.id/siaran-pers (press releases)

Output:
  - Redis set `bz:pajak:seen_urls` for deduplication
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

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main, web_search
from browser_job import BrowserJob

PAJAK_PERATURAN_URL = "https://pajak.go.id/id/index-peraturan"
PAJAK_SIARAN_PERS_URL = "https://pajak.go.id/id/siaran-pers-page"

REDIS_KEY_SEEN = "bz:pajak:seen_urls"
REDIS_EXPIRY = 86400 * 90  # 90 days

INTEL_INCOMING_DIR = Path.home() / ".intel_scraper" / "incoming"

# Tax keywords relevant to Bali Zero clients
# Broad coverage: any DJP regulation is potentially relevant
RELEVANT_KEYWORDS = [
    "ppn", "vat", "pph", "withholding", "pbjt",
    "wna", "warga negara asing", "foreign", "asing",
    "bea", "cukai", "fiskal", "tax holiday",
    "penanaman modal", "investasi", "pt pma",
    # Broad tax/regulation terms — catch all DJP content
    "pajak", "perpajakan", "kurs", "tarif", "peraturan",
    "kebijakan", "pmk", "kep-", "per-", "djp",
]


class PajakMonitorJob(BrowserJob):
    name = "pajak-monitor"
    target_url = "https://pajak.go.id"
    timeout_s = 240
    requires_side_effects = False

    async def run(self) -> RunResult:
        """Multi-source tax regulation monitoring."""
        all_items: list[dict] = []

        # Source 1: pajak.go.id peraturan terbaru
        items_peraturan = await self._fetch_page_items(
            PAJAK_PERATURAN_URL, source="pajak_peraturan"
        )
        all_items.extend(items_peraturan)
        self.log_step("fetch_peraturan", outputs={"count": len(items_peraturan)})

        await self.random_delay(2.0, 4.0)

        # Source 2: pajak.go.id siaran pers
        items_siaran = await self._fetch_page_items(
            PAJAK_SIARAN_PERS_URL, source="pajak_siaran_pers"
        )
        all_items.extend(items_siaran)
        self.log_step("fetch_siaran_pers", outputs={"count": len(items_siaran)})

        # Source 3: Brave web search for latest DJP regulations
        search_items = await self._search_djp_updates()
        all_items.extend(search_items)
        self.log_step("search_djp", outputs={"count": len(search_items)})

        # Filter by relevance (tax topics relevant to Bali Zero)
        relevant = [i for i in all_items if self._is_relevant(i.get("title", ""))]
        self.log_step("relevance_filter", outputs={"relevant": len(relevant), "total": len(all_items)})

        # Deduplicate
        seen_urls = await self._get_seen_urls()
        new_items = [i for i in relevant if i.get("url") and i["url"] not in seen_urls]
        self.log_step("dedup", outputs={"new": len(new_items), "total": len(relevant)})

        if not new_items:
            self._record_success()
            return RunResult(
                status="ok",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output="no_new_regulations",
            )

        # Mark seen + write Intel feed
        await self._mark_seen([i["url"] for i in new_items])
        intel_count = self._write_intel_feed(new_items)
        if intel_count > 0:
            self._side_effects.append(f"intel_feed:{intel_count}")

        # Telegram alert
        msg = self._compose_alert(new_items)
        ok = await self.send_telegram(msg)
        self.log_step("telegram_send", side_effect="pajak_alert" if ok else None)

        self._record_success()
        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=json.dumps(new_items[:3], default=str),
        )

    async def _fetch_page_items(self, url: str, source: str) -> list[dict]:
        """Fetch and parse items from a pajak.go.id page."""
        if not await self._check_robots(url):
            return []
        try:
            await self.random_delay(1.0, 2.0)
            page = await self.fetch_page(url)
            return self._parse_pajak_html(page["html"], source=source, base_url=url)
        except Exception as e:
            self.logger.warning("fetch_error", url=url, error=str(e))
            return []

    def _parse_pajak_html(self, html: str, source: str, base_url: str) -> list[dict]:
        """Parse pajak.go.id Drupal HTML for regulation/news links.

        pajak.go.id is a Drupal 9 site (not Next.js).
        Pattern: <a href="/id/peraturan/slug">REG-NUM</a> followed by <span>TITLE</span>
        """
        items = []
        seen: set = set()
        base_domain = "https://pajak.go.id"

        # Primary: Drupal pattern — link + span title immediately after
        for m in re.finditer(
            r'href="(/id/(?:peraturan|siaran-pers|berita)[^"]+)"[^>]*>[^<]*</a>'
            r'.*?<span[^>]*>([^<]{10,})</span>',
            html[:200000], re.DOTALL | re.IGNORECASE
        ):
            href = m.group(1)
            if href.startswith("/"):
                href = f"{base_domain}{href}"
            title = m.group(2).strip()
            title = re.sub(r'\s+', ' ', title)
            if href not in seen and len(title) > 10:
                seen.add(href)
                items.append({
                    "url": href,
                    "title": title[:300],
                    "source": source,
                    "scraped_at": datetime.now(WITA).isoformat(),
                    "type": "tax_regulation" if "/peraturan/" in href else "tax_news",
                })

        # Fallback: any pajak.go.id content links with meaningful titles
        if not items:
            for m in re.finditer(
                r'<a[^>]+href="(/id/(?:peraturan|siaran-pers-page|berita-page|siaran-pers|berita)[^"]*)"[^>]*>(.*?)</a>',
                html[:200000], re.DOTALL | re.IGNORECASE
            ):
                href = m.group(1)
                if href.startswith("/"):
                    href = f"{base_domain}{href}"
                title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                title = re.sub(r'\s+', ' ', title)
                # Derive title from slug if link text is just a regulation number
                if len(title) < 15:
                    slug = href.split("/")[-1]
                    title = slug.replace("-", " ").title()
                if href not in seen and len(title) > 10:
                    seen.add(href)
                    items.append({
                        "url": href,
                        "title": title[:300],
                        "source": source,
                        "scraped_at": datetime.now(WITA).isoformat(),
                        "type": "tax_regulation" if "/peraturan/" in href else "tax_news",
                    })

        return items[:10]

    async def _search_djp_updates(self) -> list[dict]:
        """Use web_search to find latest DJP regulation news."""
        try:
            results = await web_search(
                "DJP Direktorat Jenderal Pajak peraturan terbaru 2025",
                count=5,
                freshness="pw",
                logger=self.logger,
            )
            items = []
            for r in results:
                if "pajak" in r.get("url", "").lower() or "djp" in r.get("url", "").lower():
                    items.append({
                        "url": r["url"],
                        "title": r.get("title", "?")[:300],
                        "source": "web_search",
                        "scraped_at": datetime.now(WITA).isoformat(),
                        "type": "tax_news",
                    })
            return items[:5]
        except Exception as e:
            self.logger.warning("search_error", error=str(e))
            return []

    def _is_relevant(self, title: str) -> bool:
        """Check if a regulation title is relevant to Bali Zero clients."""
        title_lower = title.lower()
        return any(kw in title_lower for kw in RELEVANT_KEYWORDS)

    async def _get_seen_urls(self) -> set:
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
        try:
            for url in urls:
                subprocess.run(["redis-cli", "SADD", REDIS_KEY_SEEN, url], capture_output=True, timeout=5)
            subprocess.run(["redis-cli", "EXPIRE", REDIS_KEY_SEEN, str(REDIS_EXPIRY)], capture_output=True, timeout=5)
        except Exception:
            pass

    def _write_intel_feed(self, items: list[dict]) -> int:
        try:
            INTEL_INCOMING_DIR.mkdir(parents=True, exist_ok=True)
            count = 0
            for item in items:
                ts = int(time.time())
                fn = f"pajak_{ts}_{hashlib.md5(item['url'].encode()).hexdigest()[:8]}.json"
                (INTEL_INCOMING_DIR / fn).write_text(json.dumps({
                    "source": item.get("source", "pajak"),
                    "url": item["url"],
                    "title": item["title"],
                    "type": item.get("type", "tax_regulation"),
                    "scraped_at": item.get("scraped_at"),
                    "pipeline": "intel_stage1",
                }, indent=2))
                count += 1

                # Intel Lake Wave 3 (2026-05-12): dual-write to local SQLite
                # outbox. Best-effort — failure must not block existing flow.
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
                        "pajak_monitor",
                        {
                            "producer_name": "pajak_monitor",
                            "canonical_url": item["url"],
                            "content_hash": _ch,
                            "title": item["title"][:500],
                            "summary": item.get("summary", "")[:2000] if item.get("summary") else None,
                            "source_domain": "pajak.go.id",
                            "language": "id",
                            "jurisdiction": "ID-national",
                            "topic_tags": ["tax", "pajak", item.get("type", "tax_regulation")],
                            "published_at": item.get("scraped_at"),
                            "score": None,
                            "raw_payload": {
                                "pipeline": "intel_stage1",
                                "type": item.get("type", "tax_regulation"),
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
        import html as _html
        lines = [
            f"💰 <b>Pajak Monitor</b> — {len(new_items)} new",
            f"{now.strftime('%Y-%m-%d %H:%M WITA')}",
            "",
        ]
        for item in new_items[:5]:
            title = _html.escape(item["title"][:150])
            lines.append(f"• {title}")
        if len(new_items) > 5:
            lines.append(f"... +{len(new_items) - 5} altri")
        lines.append(f"\n📦 Intel feed: {len(new_items)} items")
        return "\n".join(lines)

    def scrape(self, html: str, text: str) -> dict:
        return {}

    def _elapsed(self) -> float:
        return time.time() - self.started_at


if __name__ == "__main__":
    main(PajakMonitorJob)
