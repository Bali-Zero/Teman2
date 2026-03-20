"""
Core Guardian V3 — CRON ORCHESTRATOR

Scheduled via OpenClaw cron. Runs Scout → Surgeon pipeline.
Frequency: every 4h
Cost: $0 (deterministic fixers only, no LLM in auto mode)

Flow:
1. Run Scout to find SAFE candidates
2. Pick the best candidate (lowest violation count = easiest fix)
3. Run Surgeon on it
4. Report result via Telegram
5. If successful, pick next candidate (max 3 per run)

Safety:
- MAX_FIXES_PER_RUN = 3 (don't overwhelm the repo)
- Only SAFE codes with deterministic fixers
- Surgeon has its own circuit breaker (3 fails → 24h stop)
- No git push — branches stay local for review

Usage:
  python cron_guardian.py              # auto mode: scout → surgeon
  python cron_guardian.py --scout-only # just scout, no fixes
  python cron_guardian.py --dry-run    # scout + surgeon dry-run
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from scout import scout_run, run_ruff_json, analyze_violations, SAFE_RULES
from surgeon import surgeon_run, DETERMINISTIC_FIXERS, load_state, check_circuit_breaker
from watchdog import (
    AGENT_DIR,
    BACKEND_DIR,
    BASELINE_FILE,
    safe_load_json,
    send_telegram_alert,
)

logging.basicConfig(
    level=logging.INFO,
    format="[Guardian %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("guardian")

MAX_FIXES_PER_RUN = 3
CRON_LOG_FILE = AGENT_DIR / "cron_guardian.log"


def find_fixable_candidates() -> list[dict]:
    """Run Scout analysis and return candidates that have deterministic fixers."""
    violations = run_ruff_json()
    if not violations:
        return []

    ranked = analyze_violations(violations)

    # Filter: SAFE classification + has a deterministic fixer + low count (easiest first)
    candidates = []
    seen_files = set()
    for item in ranked:
        code = item["code"]
        filepath = item["file"]
        if (
            item["classification"] == "SAFE"
            and code in DETERMINISTIC_FIXERS
            and filepath not in seen_files
            and "/tests/" not in filepath
        ):
            # Convert absolute path to relative (from apps/backend-rag/)
            rel_path = filepath
            if "apps/backend-rag/" in filepath:
                rel_path = filepath.split("apps/backend-rag/")[1]
            candidates.append({
                "code": code,
                "file": rel_path,
                "abs_file": filepath,
                "count": item["count"],
            })
            seen_files.add(filepath)

    # Sort by count ascending (fix easiest files first)
    candidates.sort(key=lambda x: x["count"])
    return candidates


def run_guardian(scout_only: bool = False, dry_run: bool = False) -> dict:
    """Main orchestrator. Returns summary dict."""
    logger.info("=== Core Guardian Cron Run ===")
    start = datetime.now(timezone.utc)

    # 0. Check circuit breaker
    state = load_state()
    breaker_msg = check_circuit_breaker(state)
    if breaker_msg:
        logger.warning(f"Circuit breaker active: {breaker_msg}")
        send_telegram_alert(f"Guardian SKIPPED: {breaker_msg}")
        return {"status": "skipped", "reason": breaker_msg}

    # 1. Check baseline exists
    baseline = safe_load_json(BASELINE_FILE)
    if not baseline:
        logger.warning("No baseline. Run watchdog first.")
        return {"status": "skipped", "reason": "no baseline"}

    # 2. Find candidates
    candidates = find_fixable_candidates()
    logger.info(f"Found {len(candidates)} fixable candidates")

    if not candidates:
        logger.info("No fixable candidates. Done.")
        return {"status": "ok", "candidates": 0, "fixed": 0}

    if scout_only:
        report = "\n".join(f"  {c['code']} {c['file']} ({c['count']}x)" for c in candidates[:10])
        logger.info(f"Scout-only mode. Candidates:\n{report}")
        return {"status": "ok", "candidates": len(candidates), "fixed": 0, "mode": "scout-only"}

    # 3. Fix candidates (up to MAX_FIXES_PER_RUN)
    results = []
    for candidate in candidates[:MAX_FIXES_PER_RUN]:
        code = candidate["code"]
        target = candidate["file"]
        count = candidate["count"]

        logger.info(f"Fixing {code} in {target} ({count} violations)")

        result = surgeon_run(
            task_description=f"Fix {code}: timezone-aware datetime",
            target_file=target,
            ruff_code=code,
            dry_run=dry_run,
        )

        results.append({
            "file": target,
            "code": code,
            "success": result["success"],
            "branch": result.get("branch", ""),
            "message": result["message"][:100],
        })

        if not result["success"]:
            logger.warning(f"Fix failed: {result['message'][:100]}")
            # Don't stop on failure — Surgeon's circuit breaker handles that
        else:
            logger.info(f"Fix OK: {result.get('branch', 'dry-run')}")

    # 4. Summary
    fixed = sum(1 for r in results if r["success"])
    failed = len(results) - fixed
    duration = (datetime.now(timezone.utc) - start).total_seconds()

    summary = {
        "status": "ok",
        "candidates": len(candidates),
        "attempted": len(results),
        "fixed": fixed,
        "failed": failed,
        "duration_s": round(duration),
        "results": results,
    }

    # 5. Telegram report
    tg_lines = [f"Guardian: {fixed}/{len(results)} fixed ({len(candidates)} candidates)"]
    for r in results:
        icon = "✅" if r["success"] else "❌"
        fname = r["file"].split("/")[-1]
        tg_lines.append(f"{icon} {r['code']} {fname}")
    if fixed > 0:
        tg_lines.append(f"Duration: {round(duration)}s")
    send_telegram_alert("\n".join(tg_lines))

    # 6. Log to file
    try:
        log_entry = {
            "timestamp": start.isoformat(),
            "summary": summary,
        }
        with open(CRON_LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        pass

    logger.info(f"=== Guardian Complete: {fixed} fixed, {failed} failed, {duration:.0f}s ===")
    return summary


if __name__ == "__main__":
    scout_only = "--scout-only" in sys.argv
    dry_run = "--dry-run" in sys.argv

    result = run_guardian(scout_only=scout_only, dry_run=dry_run)
    print(json.dumps(result, indent=2))
