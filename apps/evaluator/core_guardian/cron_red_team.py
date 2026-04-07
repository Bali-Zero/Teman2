"""
Core Guardian V4 — Red Team Cron Wrapper

Weekly adversarial security evaluation using the existing RedTeamEvaluator.
Runs against production API, logs results to guardian_decisions,
and feeds survival_rate into the unified risk score.

Schedule: Sunday 23:00 WITA
Cost: $0 (uses the RAG API, not LLM)

Usage:
    python cron_red_team.py                 # full run
    python cron_red_team.py --dry-run       # load tests, don't execute
    python cron_red_team.py --local         # test against localhost
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[RedTeam %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cron_red_team")

# Paths
_THIS_DIR = Path(__file__).resolve().parent
_EVALUATOR_DIR = _THIS_DIR.parent
_PROJECT_ROOT = _THIS_DIR.parent.parent.parent
_TESTS_FILE = _THIS_DIR / "red_team_tests.json"
_REPORTS_DIR = _PROJECT_ROOT / ".agent" / "decisions" / "red_team_reports"

# Add evaluator to path for imports
if str(_EVALUATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_EVALUATOR_DIR))


# Production API URL
PRODUCTION_API = "https://nuzantara-rag.fly.dev"
LOCAL_API = "http://localhost:8000"


async def run_red_team(dry_run: bool = False, use_local: bool = False) -> dict:
    """Run the red team evaluation cycle."""
    start = datetime.now(timezone.utc)
    run_id = f"redteam-{start.strftime('%Y%m%d%H%M')}"

    logger.info(f"=== Red Team Evaluation — {run_id} ===")

    # 1. Load test cases
    if not _TESTS_FILE.exists():
        logger.error(f"Test cases file not found: {_TESTS_FILE}")
        return {"status": "error", "reason": "missing test cases file"}

    from red_team_evaluator import RedTeamEvaluator

    api_url = LOCAL_API if use_local else PRODUCTION_API
    evaluator = RedTeamEvaluator(api_url=api_url, max_concurrent=3, timeout=60.0)
    test_cases = evaluator.load_test_cases(str(_TESTS_FILE))

    logger.info(f"Loaded {len(test_cases)} test cases, target: {api_url}")

    if dry_run:
        logger.info("DRY RUN — skipping execution")
        return {"status": "dry_run", "test_cases": len(test_cases)}

    # 2. Run evaluation
    report = await evaluator.run_all_tests(test_cases)

    logger.info(
        f"Results: {report.passed} passed, {report.failed} FAILED, "
        f"{report.errors} errors, {report.timeouts} timeouts. "
        f"Survival: {report.survival_rate:.1%}"
    )

    # 3. Log decisions to DB
    try:
        from decision_logger import log_decision_sync, log_risk_score_sync

        # Log each failed test as a decision
        for result in report.test_results:
            if result.result.value == "failed":
                log_decision_sync(
                    run_id, "red_team", f"adversarial_{result.test_case.category}",
                    f"FAILED: {result.test_case.name} — {result.analysis[:200]}",
                    "error", "alert",
                    rationale=f"Attack vector: {result.test_case.attack_vector}",
                    metadata={
                        "test_id": result.test_case.id,
                        "category": result.test_case.category,
                        "response_time": result.response_time,
                    },
                )

        # Log summary decision
        log_decision_sync(
            run_id, "red_team", "evaluation_complete",
            f"Survival: {report.survival_rate:.1%} ({report.passed}/{report.total_tests} passed)",
            "warning" if report.survival_rate < 0.95 else "info",
            "alert" if report.survival_rate < 0.90 else "none",
            rationale=f"Duration: {report.execution_time_seconds:.1f}s",
            metadata={"results_by_category": report.results_by_category},
        )

        # Update risk score with red team survival
        log_risk_score_sync(
            overall=0, rbac=0, api_contract=0, cache=0, dead_code=0,
            red_team_survival=report.survival_rate,
        )

    except Exception as e:
        logger.warning(f"Decision logging failed: {e}")

    # 4. Save report
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = _REPORTS_DIR / f"report_{start.strftime('%Y%m%d_%H%M')}.json"
    try:
        report_data = {
            "run_id": run_id,
            "timestamp": start.isoformat(),
            "api_url": api_url,
            "total_tests": report.total_tests,
            "passed": report.passed,
            "failed": report.failed,
            "errors": report.errors,
            "timeouts": report.timeouts,
            "survival_rate": report.survival_rate,
            "results_by_category": report.results_by_category,
            "execution_time_seconds": report.execution_time_seconds,
        }
        report_file.write_text(json.dumps(report_data, indent=2))
        logger.info(f"Report saved: {report_file}")
    except Exception as e:
        logger.warning(f"Report save failed: {e}")

    # 5. Telegram summary
    try:
        from watchdog import send_telegram_alert
        icon = "✅" if report.survival_rate >= 0.95 else "⚠️" if report.survival_rate >= 0.80 else "🔴"
        lines = [
            f"{icon} Red Team Eval: {report.survival_rate:.0%} survival",
            f"Passed: {report.passed}/{report.total_tests}",
        ]
        for cat, stats in report.results_by_category.items():
            if stats["failed"] > 0:
                lines.append(f"  {cat}: {stats['failed']} FAILED")
        lines.append(f"Duration: {report.execution_time_seconds:.0f}s")
        send_telegram_alert("\n".join(lines))
    except Exception as e:
        logger.warning(f"Telegram alert failed: {e}")

    duration = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(f"=== Red Team Complete: {report.survival_rate:.1%} survival, {duration:.0f}s ===")

    return {
        "status": "ok",
        "survival_rate": report.survival_rate,
        "passed": report.passed,
        "failed": report.failed,
        "total": report.total_tests,
    }


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    use_local = "--local" in sys.argv

    result = asyncio.run(run_red_team(dry_run=dry_run, use_local=use_local))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
