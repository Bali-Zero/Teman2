"""
Core Guardian V4 — Unified Risk Scorer

Aggregates findings from 5 quality checks into a single 0-100 risk score.
Weights reflect security impact: RBAC > API contract > cache > dead code.

Thresholds:
  >60  → auto-fix eligible
  >80  → auto-fix + Telegram alert
  >95  → block deploy (write sentinel file)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("guardian.risk_scorer")

# --- Weights (must sum to 1.0) ---
WEIGHTS: dict[str, float] = {
    "rbac": 0.40,
    "api_contract": 0.30,
    "cache": 0.20,
    "dead_code": 0.10,
}

# Per-check normalization: raw count → 0-100 score
# Each multiplier represents "how bad is one finding?"
MULTIPLIERS: dict[str, int] = {
    "rbac": 15,          # Each unprotected mutation endpoint = 15 pts
    "api_contract": 10,  # Each ghost endpoint = 10 pts
    "cache": 5,          # Each missing invalidation = 5 pts
    "dead_code": 3,      # Each dead code finding = 3 pts
}

# --- Thresholds ---
THRESHOLD_AUTO_FIX = 60
THRESHOLD_AUTO_FIX_ALERT = 80
THRESHOLD_BLOCK_DEPLOY = 95

# Sentinel file for deploy blocking
_AGENT_DIR = Path(__file__).resolve().parent.parent.parent.parent / ".agent" / "decisions"
DEPLOY_BLOCKED_FILE = _AGENT_DIR / "deploy_blocked.json"


def compute_risk_score(audit_results: dict[str, int]) -> dict[str, int]:
    """Compute unified risk score from raw audit finding counts.

    Args:
        audit_results: {
            "rbac": <number of RBAC errors>,
            "api_contract": <number of ghost endpoints>,
            "cache": <number of missing cache invalidations>,
            "dead_code": <number of dead code findings>,
        }

    Returns:
        {
            "overall": 0-100,
            "rbac": 0-100,
            "api_contract": 0-100,
            "cache": 0-100,
            "dead_code": 0-100,
        }
    """
    scores: dict[str, int] = {}

    for check_name in WEIGHTS:
        raw_count = audit_results.get(check_name, 0)
        multiplier = MULTIPLIERS.get(check_name, 1)
        # Normalize: raw_count * multiplier, capped at 100
        scores[check_name] = min(100, raw_count * multiplier)

    # Weighted overall score
    overall = 0.0
    for check_name, weight in WEIGHTS.items():
        overall += scores[check_name] * weight

    scores["overall"] = min(100, round(overall))
    return scores


def get_threshold_action(score: int) -> str:
    """Determine the action level based on risk score.

    Returns:
        "none" | "auto_fix" | "auto_fix_alert" | "block_deploy"
    """
    if score >= THRESHOLD_BLOCK_DEPLOY:
        return "block_deploy"
    elif score >= THRESHOLD_AUTO_FIX_ALERT:
        return "auto_fix_alert"
    elif score >= THRESHOLD_AUTO_FIX:
        return "auto_fix"
    return "none"


def write_deploy_block(score: int, details: dict) -> None:
    """Write deploy_blocked.json sentinel file when score > 95."""
    DEPLOY_BLOCKED_FILE.parent.mkdir(parents=True, exist_ok=True)
    block_data = {
        "blocked_at": datetime.now(timezone.utc).isoformat(),
        "risk_score": score,
        "reason": f"Guardian risk score {score} exceeds threshold {THRESHOLD_BLOCK_DEPLOY}",
        "details": details,
    }
    try:
        with open(DEPLOY_BLOCKED_FILE, "w") as f:
            json.dump(block_data, f, indent=2)
        logger.warning(f"DEPLOY BLOCKED: risk score {score} > {THRESHOLD_BLOCK_DEPLOY}")
    except OSError as e:
        logger.error(f"Failed to write deploy block sentinel: {e}")


def clear_deploy_block() -> None:
    """Remove deploy_blocked.json when score drops below threshold."""
    try:
        if DEPLOY_BLOCKED_FILE.exists():
            DEPLOY_BLOCKED_FILE.unlink()
            logger.info("Deploy block cleared")
    except OSError:
        pass
