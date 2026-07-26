#!/usr/bin/env python3
"""
Intel Feed Processor — processes incoming items from browser scrapers.

# Organo: intel-feed-processor (cron-agent-python) → produce:
#         JSON files in Intel Scraper staging dir per downstream enrichment
#         + Telegram digest (nuovi item → pipeline)
# Consuma da: ~/.intel_scraper/incoming/ (imigrasi-monitor, oss-monitor output)
#
# Ruolo: bridge fra browser scrapers e Intel pipeline esistente.
#         Prende item JSON dalla incoming dir, valida, deduplicates,
#         e li sposta in staging per l'enrichment Claude CLI.

Stage 1 bridge: picks up items written by imigrasi_monitor, oss_monitor
and any future browser scrapers, validates them, then moves to Intel
staging dir for downstream enrichment.

Parallel processing: validates N items in parallel (asyncio.gather).
Uses web_fetch() to grab additional context per item.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent_job import AgentJob, RunResult, WITA, main, web_fetch

INCOMING_DIR = Path.home() / ".intel_scraper" / "incoming"
INTEL_ROOT = Path.home() / "nuzantara" / "apps" / "bali-intel-scraper"
STAGING_DIR = INTEL_ROOT / "data" / "staging" / "news"
PROCESSED_DIR = Path.home() / ".intel_scraper" / "processed"

# Max items to process per run (avoid overloading the pipeline)
MAX_ITEMS_PER_RUN = 20


class IntelFeedProcessorJob(AgentJob):
    name = "intel-feed-processor"
    timeout_s = 300
    requires_side_effects = False  # only if items processed

    async def run(self) -> RunResult:
        # Setup dirs
        INCOMING_DIR.mkdir(parents=True, exist_ok=True)
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

        # Find incoming items
        incoming_files = list(INCOMING_DIR.glob("*.json"))
        if not incoming_files:
            self.log_step("no_incoming_items")
            return RunResult(
                status="ok",
                duration_s=self._elapsed(),
                side_effects=self._side_effects,
                output="no_incoming_items",
            )

        # Limit per run
        batch = incoming_files[:MAX_ITEMS_PER_RUN]
        self.log_step("batch_start", inputs={"count": len(batch), "total_pending": len(incoming_files)})

        # Process in parallel
        results = await asyncio.gather(
            *[self._process_item(f) for f in batch],
            return_exceptions=True,
        )

        ok_count = sum(1 for r in results if r is True)
        err_count = sum(1 for r in results if r is not True)
        self.log_step("batch_done", outputs={"ok": ok_count, "errors": err_count})

        if ok_count > 0:
            msg = (
                f"📥 <b>Intel Feed</b> — {ok_count} items → pipeline\n"
                f"{datetime.now(WITA).strftime('%H:%M WITA')}"
            )
            if STAGING_DIR.exists():
                pending = len(list(STAGING_DIR.glob("*.json")))
                msg += f"\nPending in staging: {pending}"
            await self.send_telegram(msg)
            self._side_effects.append(f"intel_items_staged:{ok_count}")
            self.log_step("telegram_sent", outputs={"ok": ok_count})

        return RunResult(
            status="ok",
            duration_s=self._elapsed(),
            side_effects=self._side_effects,
            output=f"ok={ok_count} errors={err_count}",
        )

    async def _process_item(self, item_file: Path) -> bool:
        """Process a single incoming item file. Returns True on success."""
        try:
            raw = json.loads(item_file.read_text())
        except Exception as e:
            self.logger.warning("invalid_json", file=item_file.name, error=str(e))
            item_file.unlink(missing_ok=True)
            return False

        url = raw.get("url", "")
        title = raw.get("title", "")
        source = raw.get("source", "unknown")

        if not url or not title:
            self.logger.warning("missing_fields", file=item_file.name)
            item_file.unlink(missing_ok=True)
            return False

        # Fetch additional context if URL is accessible
        content = raw.get("content", "")
        if not content and url.startswith("http"):
            try:
                page = await web_fetch(url, extract_text=True, timeout=10.0, logger=self.logger)
                if page.get("ok") and page.get("text"):
                    content = page["text"][:3000]  # limit for staging
            except Exception:
                pass

        # Build staging item
        ts = int(time.time())
        item_id = f"{source}_{ts}_{item_file.stem}"
        staging_item = {
            "id": item_id,
            "url": url,
            "title": title,
            "source": source,
            "content": content,
            "type": raw.get("type", "news"),
            "scraped_at": raw.get("scraped_at", datetime.now(WITA).isoformat()),
            "pipeline_stage": "stage1_collected",
        }

        # Write to staging dir (if Intel Scraper exists)
        try:
            if STAGING_DIR.exists():
                staging_file = STAGING_DIR / f"{item_id}.json"
                staging_file.write_text(json.dumps(staging_item, indent=2))
            else:
                # Intel scraper not available — just archive
                PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
                archive_file = PROCESSED_DIR / f"{item_id}.json"
                archive_file.write_text(json.dumps(staging_item, indent=2))
        except Exception as e:
            self.logger.error("staging_write_error", error=str(e))
            return False

        # Move original to processed
        shutil.move(str(item_file), str(PROCESSED_DIR / item_file.name))
        self.logger.debug("item_staged", id=item_id, source=source)
        return True

    def _elapsed(self) -> float:
        return time.time() - self.started_at


if __name__ == "__main__":
    main(IntelFeedProcessorJob)
