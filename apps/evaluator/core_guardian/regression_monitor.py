"""
Core Guardian V4 — Regression Monitor

Spawned as a background process after a surgeon merge.
Polls the backend health endpoint for 1 hour and rolls back
if response time increases >20% or error rate exceeds 5%.

Uses a 3-consecutive-checks window to avoid false positives
from transient latency spikes.

Usage:
    python regression_monitor.py --branch <name> --tag <snapshot_tag> --duration 3600
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

logging.basicConfig(
    level=logging.INFO,
    format="[RegMon %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("regression_monitor")

# Import shared paths
try:
    from watchdog import (  # noqa: I001
        AGENT_DIR,
        BASELINE_FILE,
        PROJECT_ROOT,
        safe_load_json,
        send_telegram_alert,
    )
except ImportError:
    # Fallback paths if run from a different cwd
    _root = Path(__file__).resolve().parent.parent.parent.parent
    AGENT_DIR = _root / ".agent" / "decisions"
    PROJECT_ROOT = _root
    BASELINE_FILE = AGENT_DIR / "baseline.json"

    def safe_load_json(fp):
        try:
            return json.loads(fp.read_text())
        except Exception:
            return None

    def send_telegram_alert(msg):
        logger.warning(f"ALERT (no Telegram): {msg}")


# --- Config ---

HEALTH_URL = os.environ.get(
    "GUARDIAN_HEALTH_URL", "http://localhost:8000/health/detailed"
)
POLL_INTERVAL = 300  # 5 minutes
REGRESSION_THRESHOLD_PCT = 20  # Response time increase > 20%
ERROR_RATE_THRESHOLD_PCT = 5  # Error rate > 5%
CONSECUTIVE_BAD_CHECKS = 3  # 3 bad checks in a row = regression


class RegressionMonitor:
    """Post-merge regression detector."""

    def __init__(self, branch: str, tag: str, duration: int = 3600) -> None:
        self.branch = branch
        self.tag = tag
        self.duration = duration
        self.checks: list[dict] = []

    def _probe_health(self) -> dict:
        """Probe the health endpoint and return metrics."""
        t0 = time.monotonic()
        try:
            req = Request(HEALTH_URL, headers={"Accept": "application/json"})
            with urlopen(req, timeout=30) as resp:
                elapsed_ms = (time.monotonic() - t0) * 1000
                status = resp.status
                body = json.loads(resp.read())
                return {
                    "ok": status == 200 and body.get("status") != "error",
                    "response_ms": round(elapsed_ms, 1),
                    "status_code": status,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        except URLError as e:
            elapsed_ms = (time.monotonic() - t0) * 1000
            return {
                "ok": False,
                "response_ms": round(elapsed_ms, 1),
                "status_code": 0,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "ok": False,
                "response_ms": 0,
                "status_code": 0,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def collect_baseline(self) -> dict:
        """Collect a baseline from the first 2 probes."""
        probes = []
        for _ in range(2):
            probe = self._probe_health()
            probes.append(probe)
            time.sleep(10)

        ok_probes = [p for p in probes if p["ok"]]
        if not ok_probes:
            return {"avg_response_ms": 1000.0, "error_rate": 1.0}

        avg_ms = sum(p["response_ms"] for p in ok_probes) / len(ok_probes)
        error_rate = 1.0 - (len(ok_probes) / len(probes))

        return {"avg_response_ms": avg_ms, "error_rate": error_rate}

    def monitor(self) -> dict:
        """Main monitoring loop. Returns result dict."""
        logger.info(f"Regression monitor started for branch={self.branch}, duration={self.duration}s")

        # Collect baseline
        baseline = self.collect_baseline()
        logger.info(f"Baseline: avg_response={baseline['avg_response_ms']:.0f}ms, error_rate={baseline['error_rate']:.1%}")

        threshold_ms = baseline["avg_response_ms"] * (1 + REGRESSION_THRESHOLD_PCT / 100)
        consecutive_bad = 0
        start = time.monotonic()

        while (time.monotonic() - start) < self.duration:
            time.sleep(POLL_INTERVAL)

            check = self._probe_health()
            self.checks.append(check)

            is_bad = False

            # Check response time regression
            if check["ok"] and check["response_ms"] > threshold_ms:
                is_bad = True
                logger.warning(
                    f"Response time {check['response_ms']:.0f}ms > threshold {threshold_ms:.0f}ms"
                )

            # Check error (individual check failure)
            if not check["ok"]:
                is_bad = True
                logger.warning(f"Health check failed: {check.get('error', 'non-200 status')}")

            # Check aggregate error rate over all checks so far
            if len(self.checks) >= 3:
                recent = self.checks[-3:]
                error_rate = sum(1 for c in recent if not c["ok"]) / len(recent) * 100
                if error_rate > ERROR_RATE_THRESHOLD_PCT:
                    is_bad = True
                    logger.warning(f"Error rate {error_rate:.0f}% > threshold {ERROR_RATE_THRESHOLD_PCT}%")

            if is_bad:
                consecutive_bad += 1
                logger.info(f"Bad check {consecutive_bad}/{CONSECUTIVE_BAD_CHECKS}")
            else:
                consecutive_bad = 0
                logger.info(f"Check OK: {check['response_ms']:.0f}ms")

            # Regression detected
            if consecutive_bad >= CONSECUTIVE_BAD_CHECKS:
                logger.warning(f"REGRESSION DETECTED after {CONSECUTIVE_BAD_CHECKS} consecutive bad checks")
                self._handle_regression(baseline)
                return {
                    "status": "regression_detected",
                    "branch": self.branch,
                    "checks": len(self.checks),
                    "baseline_ms": baseline["avg_response_ms"],
                    "threshold_ms": threshold_ms,
                }

        logger.info(f"Monitoring complete. {len(self.checks)} checks, no regression detected.")
        self._cleanup_tag()

        return {
            "status": "ok",
            "branch": self.branch,
            "checks": len(self.checks),
            "baseline_ms": baseline["avg_response_ms"],
        }

    def _handle_regression(self, baseline: dict) -> None:
        """Rollback and alert on regression detection.

        Acquires the guardian lock before rollback to prevent races
        with watchdog/surgeon that may be running concurrently.
        """
        # Acquire guardian lock to prevent concurrent git operations
        lock_fd = -1
        try:
            from watchdog import acquire_lock, release_lock
            lock_fd = acquire_lock()
            if lock_fd < 0:
                logger.warning("Cannot acquire guardian lock — skipping rollback, alerting only")
        except ImportError:
            pass

        # Try rollback
        rollback_success = False
        if self.tag and lock_fd >= 0:
            try:
                from rollback_engine import RollbackEngine
                engine = RollbackEngine()
                rollback_success = engine.rollback_to_snapshot(self.tag, self.branch)
            except Exception as e:
                logger.error(f"Rollback failed: {e}")

        # Release lock
        if lock_fd >= 0:
            try:
                release_lock(lock_fd)
            except Exception:
                pass

        # Log decision
        try:
            from decision_logger import log_decision_sync
            log_decision_sync(
                f"regmon-{self.branch}", "regression_monitor", "regression_detected",
                f"Performance regression after merge of {self.branch}",
                "error", "rollback" if rollback_success else "alert",
                rationale=(
                    f"Baseline: {baseline['avg_response_ms']:.0f}ms, "
                    f"Last {CONSECUTIVE_BAD_CHECKS} checks exceeded threshold"
                ),
                rollback_plan=f"Reverted to tag {self.tag}" if rollback_success else "Manual rollback needed",
                metadata={"checks": self.checks[-CONSECUTIVE_BAD_CHECKS:]},
            )
        except Exception:
            pass

        # Telegram alert
        action = "auto-rolled back" if rollback_success else "MANUAL ROLLBACK NEEDED"
        send_telegram_alert(
            f"REGRESSION DETECTED — {action}\n"
            f"Branch: {self.branch}\n"
            f"Baseline: {baseline['avg_response_ms']:.0f}ms\n"
            f"Tag: {self.tag or 'none'}"
        )

    def _cleanup_tag(self) -> None:
        """Remove snapshot tag after successful monitoring period."""
        if self.tag:
            import subprocess
            subprocess.run(
                ["git", "tag", "-d", self.tag],
                cwd=str(PROJECT_ROOT), capture_output=True, timeout=10,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-merge regression monitor")
    parser.add_argument("--branch", required=True, help="Branch name that was merged")
    parser.add_argument("--tag", required=True, help="Pre-fix snapshot tag")
    parser.add_argument("--duration", type=int, default=3600, help="Monitoring duration in seconds")
    args = parser.parse_args()

    monitor = RegressionMonitor(args.branch, args.tag, args.duration)
    result = monitor.monitor()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
