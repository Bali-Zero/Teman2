#!/usr/bin/env python3
"""
Daily Indexing Sweep — Phase 1 (Articles) + Phase 2 (KBLI)
Runs from: /Users/nuzantara/Desktop/nuzantara
Activate venv first: source apps/backend-rag/.venv/bin/activate
"""
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[Sweep] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path("/Users/nuzantara/Desktop/nuzantara")
EVALUATOR = PROJECT_ROOT / "apps" / "evaluator"
VENV_PYTHON = PROJECT_ROOT / "apps" / "backend-rag" / ".venv" / "bin" / "python"

ARTICLES_SCRIPT = EVALUATOR / "articles_indexing_submit.py"
KBLI_SCRIPT = EVALUATOR / "kbli_indexing_submit.py"
ARTICLES_STATE = EVALUATOR / "articles_indexing_state.json"
KBLI_STATE = EVALUATOR / "indexing_state.json"

QUOTA_PER_RUN = 200  # articles uses 1 SA, KBLI uses up to 3 SAs

def run_phase(label: str, script: Path, args: list[str]) -> tuple[int, str]:
    """Run a phase script and return (returncode, stdout)."""
    cmd = [str(VENV_PYTHON), str(script)] + args
    logger.info("Running %s: %s", label, " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=600,  # 10 min max
    )
    output = result.stdout + result.stderr
    logger.info("%s output:\n%s", label, output[-3000:])  # last 3k chars
    return result.returncode, output


def read_state(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"submitted": [], "failed": [], "total_submitted": 0, "last_run": None}


def main():
    logger.info("=== Daily Indexing Sweep | %s ===", datetime.now().isoformat())

    # --- Phase 1: Articles ---
    logger.info("\n=== PHASE 1: Articles ===")
    articles_before = read_state(ARTICLES_STATE)
    before_count = len(articles_before.get("submitted", []))

    rc1, out1 = run_phase("Articles", ARTICLES_SCRIPT, ["--batch", "200"])

    articles_after = read_state(ARTICLES_STATE)
    after_count = len(articles_after.get("submitted", []))
    articles_submitted_today = after_count - before_count
    articles_failed = len(articles_after.get("failed", []))

    logger.info("Phase 1 done: +%d submitted (%d total, %d failed)",
                articles_submitted_today, after_count, articles_failed)

    time.sleep(2)

    # --- Phase 2: KBLI (all 3 SAs) ---
    logger.info("\n=== PHASE 2: KBLI ===")
    kbli_before = read_state(KBLI_STATE)
    kbli_before_count = len(kbli_before.get("submitted", []))

    rc2, out2 = run_phase("KBLI", KBLI_SCRIPT, [])

    kbli_after = read_state(KBLI_STATE)
    kbli_after_count = len(kbli_after.get("submitted", []))
    kbli_submitted_today = kbli_after_count - kbli_before_count
    kbli_failed = len(kbli_after.get("failed", []))

    logger.info("Phase 2 done: +%d submitted (%d/1563 total, %d failed)",
                kbli_submitted_today, kbli_after_count, kbli_failed)

    # --- Summary ---
    total_quota_used = articles_submitted_today + kbli_submitted_today

    # Estimate articles backlog (approximate: discover() handles exact count)
    kbli_remaining = 1563 - kbli_after_count

    summary = f"""
=== DAILY INDEXING SWEEP COMPLETE ===
Date: {datetime.now().strftime("%Y-%m-%d %H:%M WITA")}

PHASE 1 — Articles:
  Submitted today:   {articles_submitted_today}
  Total submitted:   {after_count}
  Failed:            {articles_failed}
  Phase 1 exit code: {rc1}

PHASE 2 — KBLI:
  Submitted today:   {kbli_submitted_today} (3 SAs × 200 = 600 max)
  Total submitted:   {kbli_after_count}/1563
  Remaining backlog: {kbli_remaining}
  Failed:            {kbli_failed}
  Phase 2 exit code: {rc2}

QUOTA:
  Articles (SA-1):   {articles_submitted_today}/200
  KBLI (3 SAs):      {kbli_submitted_today}/600
  Total today:       {total_quota_used}
"""
    print(summary)
    logger.info(summary)

    # Save summary to file
    summary_path = EVALUATOR / f"sweep_report_{datetime.now().strftime('%Y-%m-%d')}.txt"
    summary_path.write_text(summary)
    logger.info("Report saved: %s", summary_path)

    return 0 if rc1 == 0 and rc2 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
