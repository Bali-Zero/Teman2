#!/usr/bin/env python3
"""
coverage_trend.py — Test coverage trend tracker for Nuzantara backend.

Runs pytest with --cov, stores coverage % in a rolling history file,
detects regressions (>2% drop), sends Telegram alert, and writes
.last.json for Sentinel monitoring.

Schedule: daily (registered in job_registry.json as coverage_trend).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[coverage_trend %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("coverage_trend")

# --- Paths ---

def find_project_root() -> Path:
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / ".git").exists() and (current / "apps" / "backend-rag").exists():
            return current
        current = current.parent
    env_root = os.environ.get("NUZANTARA_ROOT")
    if env_root and Path(env_root).exists():
        return Path(env_root)
    logger.error("Cannot find project root. Set NUZANTARA_ROOT.")
    sys.exit(1)


PROJECT_ROOT = find_project_root()
BACKEND_DIR = PROJECT_ROOT / "apps" / "backend-rag"
VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"
AGENT_DIR = PROJECT_ROOT / ".agent" / "decisions"
HISTORY_FILE = AGENT_DIR / "coverage_history.json"
STATE_DIR = AGENT_DIR / "state"

REGRESSION_THRESHOLD = 2.0  # Alert if coverage drops > 2%
HISTORY_MAX = 30  # Keep last 30 data points


# --- Sentinel state write ---

def write_last_json(status: str, detail: str = "") -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "job": "coverage_trend",
        "status": status,
        "detail": detail,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    target = STATE_DIR / "coverage_trend.last.json"
    fd, tmp = tempfile.mkstemp(dir=str(STATE_DIR), suffix=".tmp", prefix="coverage_trend")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(target))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# --- Telegram ---

def send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = "1125336968"
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping alert")
        return
    import urllib.request
    try:
        payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")


# --- Coverage run ---

def _safe_load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=path.stem)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def run_coverage() -> float | None:
    """Run pytest --cov and return overall coverage % or None on error."""
    cov_json = Path(tempfile.mktemp(suffix=".json", prefix="cov-"))
    cmd = [
        str(VENV_PYTHON), "-m", "pytest",
        "backend/tests/",
        f"--cov=backend",
        f"--cov-report=json:{cov_json}",
        "--no-header", "-q",
        "--timeout=120",
        "--tb=no",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=str(BACKEND_DIR), timeout=720,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": os.environ.get("HOME", ""),
                "PYTHONPATH": ".",
                "ENVIRONMENT": "test",
                "VIRTUAL_ENV": str(BACKEND_DIR / ".venv"),
            },
        )
        if not cov_json.exists():
            logger.warning("Coverage JSON not generated")
            return None
        data = json.loads(cov_json.read_text())
        total = data.get("totals", {}).get("percent_covered")
        return round(float(total), 2) if total is not None else None
    except subprocess.TimeoutExpired:
        logger.error("Coverage run timed out")
        return None
    except Exception as e:
        logger.error(f"Coverage run failed: {e}")
        return None
    finally:
        try:
            cov_json.unlink(missing_ok=True)
        except OSError:
            pass


# --- Main ---

def main() -> None:
    logger.info("=== coverage_trend start ===")

    current_pct = run_coverage()
    if current_pct is None:
        logger.error("Coverage measurement failed")
        write_last_json("failed", "coverage run error")
        return

    logger.info(f"Coverage: {current_pct}%")

    # Load history
    history = _safe_load_json(HISTORY_FILE) or {"runs": []}
    runs: list[dict] = history.get("runs", [])

    # Check for regression
    regression = False
    if runs:
        prev_pct = runs[-1].get("pct", 0.0)
        drop = prev_pct - current_pct
        if drop > REGRESSION_THRESHOLD:
            logger.warning(f"Coverage regression: {prev_pct}% → {current_pct}% (drop={drop:.1f}%)")
            send_telegram(
                f"Coverage Regression Detected\n"
                f"Coverage: {current_pct:.1f}% (was {prev_pct:.1f}%, drop={drop:.1f}%)\n"
                f"Threshold: {REGRESSION_THRESHOLD}%"
            )
            regression = True
        elif current_pct > prev_pct:
            logger.info(f"Coverage improved: {prev_pct}% → {current_pct}%")
        else:
            logger.info(f"Coverage stable: {current_pct}%")

    # Append to history and trim
    runs.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "pct": current_pct,
    })
    history["runs"] = runs[-HISTORY_MAX:]
    _atomic_write(HISTORY_FILE, history)

    status = "failed" if regression else "ok"
    detail = f"{current_pct:.1f}%"
    write_last_json(status, detail)
    logger.info(f"=== coverage_trend complete: {detail} ===")


if __name__ == "__main__":
    main()
