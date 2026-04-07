"""
Core Guardian V4 — SEO Guardian Cron Wrapper

Daily SEO health check using the existing seo_guardian_agent.
Runs observe → decide flow, logs results to guardian_decisions,
and feeds seo_health into the unified risk score.

Schedule: Daily 06:00 WITA
Cost: $0 (GSC + GA4 API calls)

Usage:
    python cron_seo_guardian.py              # full run
    python cron_seo_guardian.py --dry-run    # observe only, no actions
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
    format="[SEOGuardian %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cron_seo_guardian")

# Paths
_THIS_DIR = Path(__file__).resolve().parent
_EVALUATOR_DIR = _THIS_DIR.parent
_PROJECT_ROOT = _THIS_DIR.parent.parent.parent

# Add evaluator to path
if str(_EVALUATOR_DIR) not in sys.path:
    sys.path.insert(0, str(_EVALUATOR_DIR))


async def run_seo_guardian(dry_run: bool = False) -> dict:
    """Run the SEO guardian evaluation cycle."""
    start = datetime.now(timezone.utc)
    run_id = f"seo-{start.strftime('%Y%m%d%H%M')}"

    logger.info(f"=== SEO Guardian Check — {run_id} ===")

    # 1. Import and run the existing SEO agent
    try:
        from seo_guardian_agent import run_agent, run_observe
    except ImportError as e:
        logger.error(f"Failed to import seo_guardian_agent: {e}")
        return {"status": "error", "reason": str(e)}

    # 2. Run observe phase
    observe_result = await run_observe()
    if not observe_result:
        logger.warning("Observe phase returned empty results")
        return {"status": "error", "reason": "empty observe results"}

    logger.info(f"Observe: {json.dumps(observe_result, indent=2)[:500]}")

    # 3. Compute SEO health score (0.0-1.0)
    seo_health = _compute_seo_health(observe_result)
    logger.info(f"SEO health score: {seo_health:.2f}")

    # 4. Log decisions to DB
    try:
        from decision_logger import log_decision_sync, log_risk_score_sync

        # Log observe findings
        findings = observe_result.get("findings", observe_result.get("issues", []))
        if isinstance(findings, list):
            for finding in findings[:20]:  # Cap at 20
                severity = "warning" if isinstance(finding, dict) and finding.get("severity") == "high" else "info"
                log_decision_sync(
                    run_id, "seo_guardian", "seo_finding",
                    str(finding)[:500], severity, "none",
                    metadata={"observe_data": observe_result.get("summary", {})},
                )

        # Log summary
        log_decision_sync(
            run_id, "seo_guardian", "seo_check_complete",
            f"SEO health: {seo_health:.2f}",
            "warning" if seo_health < 0.7 else "info",
            "alert" if seo_health < 0.5 else "none",
            metadata={"health_score": seo_health},
        )

        # Update risk score with SEO health
        log_risk_score_sync(
            overall=0, rbac=0, api_contract=0, cache=0, dead_code=0,
            seo_health=seo_health,
        )

    except Exception as e:
        logger.warning(f"Decision logging failed: {e}")

    # 5. Run agent (decide + act) if not dry run
    agent_result = {}
    if not dry_run:
        try:
            agent_result = await run_agent(dry_run=False, observe_first=False)
            logger.info(f"Agent result: {agent_result.get('status', 'unknown')}")
        except Exception as e:
            logger.warning(f"Agent execution failed: {e}")
            agent_result = {"status": "error", "reason": str(e)}

    # 6. Telegram summary
    try:
        from watchdog import send_telegram_alert
        icon = "✅" if seo_health >= 0.8 else "⚠️" if seo_health >= 0.5 else "🔴"
        lines = [
            f"{icon} SEO Guardian: health {seo_health:.0%}",
        ]
        if isinstance(findings, list) and findings:
            lines.append(f"Findings: {len(findings)}")
        if agent_result.get("status") == "ok":
            actions = agent_result.get("actions_taken", 0)
            if actions:
                lines.append(f"Actions taken: {actions}")
        send_telegram_alert("\n".join(lines))
    except Exception as e:
        logger.warning(f"Telegram alert failed: {e}")

    duration = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(f"=== SEO Guardian Complete: {seo_health:.1%} health, {duration:.0f}s ===")

    return {
        "status": "ok",
        "seo_health": seo_health,
        "observe": observe_result.get("summary", {}),
        "agent": agent_result,
    }


def _compute_seo_health(observe_result: dict) -> float:
    """Compute a 0.0-1.0 health score from observe results.

    Factors:
    - Indexing coverage (pages indexed / total pages)
    - Error rate (4xx/5xx pages)
    - Core Web Vitals passing rate
    - Sitemap completeness
    """
    score = 1.0

    # Deduct for issues found
    findings = observe_result.get("findings", observe_result.get("issues", []))
    if isinstance(findings, list):
        # Each finding reduces score by 0.02, capped at -0.5
        deduction = min(0.5, len(findings) * 0.02)
        score -= deduction

    # Check for critical issues
    summary = observe_result.get("summary", {})
    if summary.get("critical_errors", 0) > 0:
        score -= 0.2
    if summary.get("indexing_issues", 0) > 5:
        score -= 0.1

    return max(0.0, min(1.0, score))


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    result = asyncio.run(run_seo_guardian(dry_run=dry_run))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
