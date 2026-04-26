#!/usr/bin/env python3
"""
Daily Google Search Console Indexing Sweep
===========================================
Submette articoli + KBLI a Google Indexing API con quota tracking.

Phase 1: Articles (max 200/day)
Phase 2: KBLI (max 600/day via 3 SAs × 200 each)

Legge stato da articles_indexing_state.json e kbli_indexing_submit.py state,
straccia via API, aggiorna stato, invia summary Telegram.

Usage:
    python scripts/daily_indexing_sweep.py              # esecuzione completa
    python scripts/daily_indexing_sweep.py --dry-run    # preview
    python scripts/daily_indexing_sweep.py --status     # mostra quota/stato
"""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[DailySweep] %(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

PROJECT_ROOT = Path(__file__).parent.parent
ARTICLES_STATE_PATH = PROJECT_ROOT / "apps" / "evaluator" / "articles_indexing_state.json"
KBLI_STATE_PATH = PROJECT_ROOT / "apps" / "evaluator" / "indexing_state.json"  # from kbli_indexing_submit.py

ARTICLES_SCRIPT = PROJECT_ROOT / "apps" / "evaluator" / "articles_indexing_submit.py"
KBLI_SCRIPT = PROJECT_ROOT / "apps" / "evaluator" / "kbli_indexing_submit.py"

DAILY_LIMIT_ARTICLES = 200
DAILY_LIMIT_KBLI = 600  # 3 SAs × 200 each

TELEGRAM_NOTIFY = True  # set False to disable


async def send_telegram(text: str) -> None:
    """Invia notifica a Telegram (async)."""
    if not TELEGRAM_NOTIFY:
        logger.info("Telegram disabled, skipping: %s", text[:80])
        return

    # Usa OpenClaw bridge per evitare di hardcodare token
    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", "http://localhost:18789/telegram/send",
             "-H", "Content-Type: application/json",
             "-d", json.dumps({"text": text})],
            timeout=10,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info("✅ Telegram sent")
        else:
            logger.warning("⚠️ Telegram failed: %s", result.stderr[:100])
    except Exception as e:
        logger.warning("⚠️ Telegram error: %s", str(e)[:100])


def load_state(state_path: Path) -> dict[str, Any]:
    """Carica stato da file JSON."""
    if state_path.exists():
        try:
            with open(state_path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Failed to load state from %s: %s", state_path, e)
    return {"submitted": [], "failed": []}


def run_phase_articles(dry_run: bool = False) -> dict[str, Any]:
    """
    Phase 1: Articoli. Sottomette fino a DAILY_LIMIT_ARTICLES.
    Ritorna: {"ok": int, "failed": int, "skipped": int, "remaining": int}
    """
    logger.info("=" * 70)
    logger.info("PHASE 1: ARTICLES (max %d/day)", DAILY_LIMIT_ARTICLES)
    logger.info("=" * 70)

    cmd = [sys.executable, str(ARTICLES_SCRIPT)]
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend(["--batch", str(DAILY_LIMIT_ARTICLES)])

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout
        )
        if result.returncode != 0:
            logger.error("Articles script failed:\n%s", result.stderr[-500:])
            return {"ok": 0, "failed": 0, "skipped": 0, "remaining": 0}

        # Parse output per trovare OK/failed counts
        # Format della riga: "Batch done. OK: X, Failed: Y, Rate limits: Z | Total: A/B (C%)"
        output = result.stdout + result.stderr
        logger.info("Articles output:\n%s", output[-500:])

        # Estrai numeri dalla riga di summary
        import re
        match = re.search(r"OK: (\d+), Failed: (\d+).*Total: (\d+)/(\d+)", output)
        if match:
            ok_count = int(match.group(1))
            failed_count = int(match.group(2))
            done = int(match.group(3))
            total = int(match.group(4))
            remaining = total - done
            logger.info("✅ Phase 1 done: %d OK, %d failed | %d/%d total (%d remaining)",
                       ok_count, failed_count, done, total, remaining)
            return {
                "ok": ok_count,
                "failed": failed_count,
                "skipped": 0,
                "remaining": remaining,
                "total": total,
            }
    except subprocess.TimeoutExpired:
        logger.error("Articles script timeout (>10min)")
        return {"ok": 0, "failed": 0, "skipped": 0, "remaining": 0}
    except Exception as e:
        logger.error("Articles phase error: %s", e)
        return {"ok": 0, "failed": 0, "skipped": 0, "remaining": 0}

    return {"ok": 0, "failed": 0, "skipped": 0, "remaining": 0}


def run_phase_kbli(dry_run: bool = False) -> dict[str, Any]:
    """
    Phase 2: KBLI. Sottomette fino a DAILY_LIMIT_KBLI (3 SAs × 200).
    Ritorna: {"ok": int, "failed": int, "skipped": int, "remaining": int}
    """
    logger.info("=" * 70)
    logger.info("PHASE 2: KBLI (max %d/day via 3 SAs)", DAILY_LIMIT_KBLI)
    logger.info("=" * 70)

    cmd = [sys.executable, str(KBLI_SCRIPT)]
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend(["--batch", str(DAILY_LIMIT_KBLI)])

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=900,  # 15 min timeout
        )
        if result.returncode != 0:
            logger.error("KBLI script failed:\n%s", result.stderr[-500:])
            return {"ok": 0, "failed": 0, "skipped": 0, "remaining": 0}

        output = result.stdout + result.stderr
        logger.info("KBLI output:\n%s", output[-800:])

        # Parse output per trovare ok_count, fail_count, rate_limit_hits
        # Format: "✅ Batch complete: X OK, Y failed, Z rate limit hits"
        import re
        match = re.search(r"Batch complete: (\d+) OK, (\d+) failed", output)
        if match:
            ok_count = int(match.group(1))
            failed_count = int(match.group(2))

            # Estrai pending da status output (cerca "Pending: N")
            pending_match = re.search(r"Pending:\s+(\d+)", output)
            remaining = int(pending_match.group(1)) if pending_match else 0

            logger.info("✅ Phase 2 done: %d OK, %d failed | %d remaining",
                       ok_count, failed_count, remaining)
            return {
                "ok": ok_count,
                "failed": failed_count,
                "skipped": 0,
                "remaining": remaining,
            }
    except subprocess.TimeoutExpired:
        logger.error("KBLI script timeout (>15min)")
        return {"ok": 0, "failed": 0, "skipped": 0, "remaining": 0}
    except Exception as e:
        logger.error("KBLI phase error: %s", e)
        return {"ok": 0, "failed": 0, "skipped": 0, "remaining": 0}

    return {"ok": 0, "failed": 0, "skipped": 0, "remaining": 0}


async def run_sweep(dry_run: bool = False) -> None:
    """Esegue il sweep completo: Phase 1 (articles) → Phase 2 (KBLI)."""
    started = datetime.now()
    logger.info("🚀 Daily Indexing Sweep started at %s", started.isoformat())

    # Phase 1: Articles
    phase1_result = run_phase_articles(dry_run=dry_run)
    await asyncio.sleep(1)  # small delay tra fasi

    # Phase 2: KBLI
    phase2_result = run_phase_kbli(dry_run=dry_run)

    # Summary
    duration = (datetime.now() - started).total_seconds()
    summary = f"""
📊 Daily Indexing Sweep Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 **Articles Phase**
  OK:        {phase1_result.get('ok', 0)}
  Failed:    {phase1_result.get('failed', 0)}
  Remaining: {phase1_result.get('remaining', 0)}

📗 **KBLI Phase** (3 SAs)
  OK:        {phase2_result.get('ok', 0)}
  Failed:    {phase2_result.get('failed', 0)}
  Remaining: {phase2_result.get('remaining', 0)}

⏱️  Duration: {duration:.0f}s
🔗 More: apps/evaluator/{ARTICLES_STATE_PATH.name}, {KBLI_STATE_PATH.name}
"""

    logger.info(summary)
    await send_telegram(summary.strip())


def show_status() -> None:
    """Mostra stato attuale (quota usate, remaining, eta)."""
    print("\n" + "=" * 70)
    print("INDEXING STATUS")
    print("=" * 70)

    # Articles
    articles_state = load_state(ARTICLES_STATE_PATH)
    articles_submitted = len(articles_state.get("submitted", []))
    articles_failed = len(articles_state.get("failed", []))
    print(f"\n📝 ARTICLES (daily limit: {DAILY_LIMIT_ARTICLES})")
    print(f"   Submitted: {articles_submitted}")
    print(f"   Failed:    {articles_failed}")
    print(f"   Last run:  {articles_state.get('last_run', 'never')}")

    # KBLI
    kbli_state = load_state(KBLI_STATE_PATH)
    kbli_submitted = len(kbli_state.get("submitted", []))
    kbli_failed = len(kbli_state.get("failed", []))
    print(f"\n📗 KBLI (daily limit: {DAILY_LIMIT_KBLI})")
    print(f"   Submitted: {kbli_submitted}")
    print(f"   Failed:    {kbli_failed}")
    print(f"   Last run:  {kbli_state.get('last_run', 'never')}")

    print("\n" + "=" * 70)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Daily Google Search Console Indexing Sweep"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without submitting")
    parser.add_argument("--status", action="store_true", help="Show current status")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    await run_sweep(dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
