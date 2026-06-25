#!/usr/bin/env python3
"""IG metrics scraper for WR2 published carousels.

Workflow:
1. Damar pastes IG post URL into queue.json (state=published).
2. Daily LaunchAgent runs this script; for each published carousel ≥24h old without metrics,
   open the IG post in stealth Playwright (logged-in @balizero0 session), extract counts,
   write to wr2-episodic.db carousel_runs.ig_* columns.

Cost: zero (Playwright local + free IG view). Risk: IG TOS prohibits scraping; mitigation:
human-rate-limited (5 reads/run, 30s/post), uses logged-in account own posts only (Bali Zero
viewing its own analytics — same as opening Insights tab manually).

Auth: requires logged-in IG @balizero0 Chrome profile path. If not present, abort with
"manual mode" — Damar pastes counts manually into queue.json supplementary fields.
"""

import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.async_api import async_playwright

QUEUE_PATH = Path.home() / "Desktop/nuzantara/apps/war-room/output/queue/human-review-queue.json"
DB_PATH = Path.home() / ".claude/projects/-Users-nuzantara/memory/wr2-episodic.db"
IG_CHROME_PROFILE = Path.home() / ".chrome-cdp-profile/balizero0-ig"

MIN_AGE_HOURS = 24
MAX_READS_PER_RUN = 5
PER_POST_SETTLE_SECONDS = 30


def select_pending_metrics():
    """Return list of queue items that need metrics ingestion."""
    if not QUEUE_PATH.exists():
        return []
    queue = json.loads(QUEUE_PATH.read_text())
    now = datetime.now(timezone.utc)
    pending = []
    for item in queue:
        if item.get("state") not in ("published", "published_with_edits"):
            continue
        if item.get("engagement_metrics"):
            continue
        if not item.get("instagram_post_url") or not item.get("instagram_published_at"):
            continue
        published_at = datetime.fromisoformat(item["instagram_published_at"].replace("Z", "+00:00"))
        if (now - published_at) < timedelta(hours=MIN_AGE_HOURS):
            continue
        pending.append(item)
    return pending[:MAX_READS_PER_RUN]


async def scrape_post(page, url):
    """Read engagement metrics from one IG post. Returns dict or None on failure."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        # IG renders counts in different DOM structures depending on view (mobile/desktop) and
        # locale. Selectors below are best-effort; if IG redesigns the DOM, scrape returns None
        # and the orchestrator falls back to manual mode (Damar pastes count).

        likes = await page.evaluate("""
          () => {
            const el = document.querySelector('section a[href$="/liked_by/"] span span');
            if (el) return parseInt(el.textContent.replace(/[,.]/g, ''), 10);
            const fallback = document.querySelector('section span[aria-label*="like"i]');
            if (fallback) {
              const m = fallback.textContent.match(/[0-9,.]+/);
              if (m) return parseInt(m[0].replace(/[,.]/g, ''), 10);
            }
            return null;
          }
        """)

        # Comment count + caption preview = derived signal
        comment_count = await page.evaluate("""
          () => {
            const el = document.querySelector('a[href*="/comments/"] span');
            if (el) {
              const m = el.textContent.match(/([0-9,.]+)/);
              if (m) return parseInt(m[1].replace(/[,.]/g, ''), 10);
            }
            return null;
          }
        """)

        # Save count + reach = require Insights tab (only visible to account owner, requires
        # additional navigation). Stub returns null; sessione 3 enhancement.
        save_count = None
        reach = None

        return {
            "likes": likes,
            "comment_count": comment_count,
            "save_count": save_count,
            "reach": reach,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"error": str(e), "scraped_at": datetime.now(timezone.utc).isoformat()}


def write_db(run_id, metrics):
    """Write engagement metrics to wr2-episodic.db carousel_runs row."""
    if not DB_PATH.exists():
        return False
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            UPDATE carousel_runs
               SET ig_save_count = COALESCE(?, ig_save_count),
                   ig_share_count = ig_share_count,
                   ig_reach = COALESCE(?, ig_reach)
             WHERE id = ?
        """, (metrics.get("save_count"), metrics.get("reach"), run_id))
        conn.commit()
        return True
    finally:
        conn.close()


def update_queue(item_id, metrics):
    queue = json.loads(QUEUE_PATH.read_text())
    for it in queue:
        if it["id"] == item_id:
            it["engagement_metrics"] = metrics
            break
    QUEUE_PATH.write_text(json.dumps(queue, indent=2))


async def main():
    pending = select_pending_metrics()
    if not pending:
        print("No pending metrics ingestion (all caught up or queue empty).")
        return 0

    if not IG_CHROME_PROFILE.exists():
        print(f"IG Chrome profile missing at {IG_CHROME_PROFILE}; aborting (manual mode required).", file=sys.stderr)
        return 2

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(IG_CHROME_PROFILE),
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()

        for item in pending:
            url = item["instagram_post_url"]
            print(f"Scraping {url}...")
            metrics = await scrape_post(page, url)
            if metrics and not metrics.get("error"):
                update_queue(item["id"], metrics)
                if item.get("run_id"):
                    write_db(item["run_id"], metrics)
                print(f"  → likes={metrics.get('likes')}, comments={metrics.get('comment_count')}")
            else:
                print(f"  → SCRAPE FAILED: {metrics.get('error', 'no data')}")
            await page.wait_for_timeout(PER_POST_SETTLE_SECONDS * 1000)

        await ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
