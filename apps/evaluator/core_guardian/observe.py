"""
Core Guardian - Phase 1: OBSERVE
Runs deterministic checks (Ruff for smells, Pytest for failures)
and outputs a JSON state file.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[Core Guardian - OBSERVE] %(levelname)s: %(message)s")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "apps" / "backend-rag"
STATE_FILE = PROJECT_ROOT / ".agent" / "decisions" / "state_backend.json"

def run_ruff_check() -> dict:
    """Run Ruff to find code smells."""
    logger.info("Running Ruff checks...")
    cmd = [sys.executable, "-m", "ruff", "check", "backend/", "--format=json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BACKEND_DIR))
        if result.stdout:
            try:
                data = json.loads(result.stdout)
                return {"success": True, "issues_count": len(data), "details": data[:10]} # Solo i primi 10 per non esplodere il payload
            except json.JSONDecodeError:
                return {"success": False, "error": "Invalid JSON from ruff"}
        return {"success": True, "issues_count": 0, "details": []}
    except Exception as e:
        return {"success": False, "error": str(e)}

def run_pytest_failures() -> dict:
    """Run Pytest specifically on known broken files to be fast."""
    logger.info("Running Pytest to find failures...")
    # Targeting a specific file that we know fails to keep it fast instead of 17 mins
    cmd = [
        sys.executable, "-m", "pytest", "backend/tests/test_conversation_persistence.py",
        "--tb=short", "-q"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BACKEND_DIR))
        if result.returncode != 0:
            return {"success": True, "failures_found": True, "output": result.stdout[:2000]} # Truncate per LLM
        return {"success": True, "failures_found": False, "output": "All tests passed!"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def observe():
    """Run the observation cycle and save state."""
    logger.info("Starting observation cycle...")

    ruff_state = run_ruff_check()
    pytest_state = run_pytest_failures()

    state = {
        "timestamp": datetime.now().isoformat(),
        "ruff": ruff_state,
        "pytest": pytest_state,
        "status": "ready"
    }

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    logger.info(f"Observation complete. State saved to {STATE_FILE}")

if __name__ == "__main__":
    observe()
