"""
Core Guardian V4 — Auto-Rollback Engine

Creates pre-fix snapshots using git tags, validates post-fix with tests,
and reverts automatically if validation fails.

Uses git tags (not stash) because tags survive process crashes and are
visible across worktrees.

Circuit breaker: 3 consecutive rollbacks → self-disable + Telegram alert.
"""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("guardian.rollback")

# Import shared utilities from watchdog
from watchdog import (  # noqa: E402
    AGENT_DIR,
    BACKEND_DIR,
    PROJECT_ROOT,
    VENV_PYTHON,
    atomic_write_json,
    build_test_env,
    safe_load_json,
    send_telegram_alert,
)

ROLLBACK_STATE_FILE = AGENT_DIR / "rollback_state.json"
ROLLBACK_BREAKER_THRESHOLD = 3
TAG_PREFIX = "pre-fix/"


class RollbackEngine:
    """Pre-fix snapshot creation and automatic rollback on failure."""

    def __init__(self) -> None:
        self._state = self._load_state()

    def _load_state(self) -> dict:
        state = safe_load_json(ROLLBACK_STATE_FILE)
        if state is None:
            state = {"consecutive_rollbacks": 0, "total_rollbacks": 0, "disabled": False}
        return state

    def _save_state(self) -> None:
        atomic_write_json(ROLLBACK_STATE_FILE, self._state)

    # --- Pre-fix Snapshot ---

    def create_pre_fix_snapshot(self, branch_name: str) -> str | None:
        """Create a git tag at current HEAD before any fix is applied.

        Returns tag name like 'pre-fix/cg-fix-DTZ005-abc123' or None on failure.
        """
        tag_name = f"{TAG_PREFIX}{branch_name}"

        try:
            # Delete existing tag if leftover from failed run
            subprocess.run(
                ["git", "tag", "-d", tag_name],
                cwd=str(PROJECT_ROOT), capture_output=True, timeout=10,
            )

            # Create lightweight tag at HEAD
            result = subprocess.run(
                ["git", "tag", tag_name, "HEAD"],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                logger.error(f"Failed to create snapshot tag: {result.stderr}")
                return None

            logger.info(f"Pre-fix snapshot created: {tag_name}")
            return tag_name

        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}")
            return None

    # --- Post-fix Validation ---

    def validate_post_fix(
        self,
        modified_files: list[str],
        baseline_passed: int,
    ) -> dict:
        """Run targeted pytest on tests related to modified files.

        Returns {ok: bool, passed: int, failed: int, details: str}
        """
        # Find test files related to modified source files
        test_targets = self._find_related_tests(modified_files)

        if not test_targets:
            # No targeted tests — run the full suite
            test_targets = ["backend/tests/"]

        env = build_test_env()
        cmd = [
            str(VENV_PYTHON), "-m", "pytest",
            *test_targets,
            "--tb=short", "-q", "--timeout=60",
        ]

        try:
            result = subprocess.run(
                cmd, cwd=str(BACKEND_DIR),
                capture_output=True, text=True, timeout=300, env=env,
            )

            # Parse output for pass/fail counts
            passed = 0
            failed = 0
            for line in result.stdout.splitlines():
                if "passed" in line:
                    m = re.search(r"(\d+) passed", line)
                    if m:
                        passed = int(m.group(1))
                if "failed" in line:
                    m = re.search(r"(\d+) failed", line)
                    if m:
                        failed = int(m.group(1))

            ok = result.returncode == 0 and passed >= (baseline_passed - 2)

            return {
                "ok": ok,
                "passed": passed,
                "failed": failed,
                "details": result.stdout[-500:] if not ok else "All tests passed",
            }

        except subprocess.TimeoutExpired:
            return {"ok": False, "passed": 0, "failed": 0, "details": "Test suite timed out (300s)"}
        except Exception as e:
            return {"ok": False, "passed": 0, "failed": 0, "details": f"Test execution error: {e}"}

    def _find_related_tests(self, modified_files: list[str]) -> list[str]:
        """Find test files that correspond to modified source files."""
        test_files = []
        for src_file in modified_files:
            # backend/app/routers/foo.py → backend/tests/unit/app/routers/test_foo.py
            # backend/services/bar.py → backend/tests/unit/services/test_bar.py
            src_path = Path(src_file)
            test_name = f"test_{src_path.stem}.py"

            # Search for matching test files
            test_dir = BACKEND_DIR / "backend" / "tests"
            if test_dir.exists():
                for candidate in test_dir.rglob(test_name):
                    test_files.append(str(candidate.relative_to(BACKEND_DIR)))

        return test_files[:10]  # Cap to avoid running too many

    # --- Rollback ---

    def rollback_to_snapshot(self, tag_name: str, branch_name: str) -> bool:
        """Revert main branch to pre-fix state using the snapshot tag.

        Returns True on success, False on failure.
        """
        breaker = self.check_rollback_breaker()
        if breaker:
            logger.warning(f"Rollback breaker active: {breaker}")
            return False

        try:
            # 1. Verify tag exists and resolve its commit
            verify = subprocess.run(
                ["git", "rev-parse", "--verify", f"refs/tags/{tag_name}"],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=10,
            )
            if verify.returncode != 0:
                logger.error(f"Snapshot tag {tag_name} does not exist — cannot rollback")
                return False

            # 2. Reset HEAD to the snapshot tag
            result = subprocess.run(
                ["git", "reset", "--hard", tag_name],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                logger.error(f"git reset failed: {result.stderr}")
                return False

            # 2. Delete the fix branch
            subprocess.run(
                ["git", "branch", "-D", branch_name],
                cwd=str(PROJECT_ROOT), capture_output=True, timeout=10,
            )

            # 3. Clean up the tag
            subprocess.run(
                ["git", "tag", "-d", tag_name],
                cwd=str(PROJECT_ROOT), capture_output=True, timeout=10,
            )

            # 4. Update state
            self._state["consecutive_rollbacks"] = self._state.get("consecutive_rollbacks", 0) + 1
            self._state["total_rollbacks"] = self._state.get("total_rollbacks", 0) + 1
            self._state["last_rollback_at"] = datetime.now(timezone.utc).isoformat()
            self._state["last_rollback_branch"] = branch_name
            self._save_state()

            logger.info(f"Rolled back to {tag_name}, deleted branch {branch_name}")

            # 5. Check if breaker should fire
            if self._state["consecutive_rollbacks"] >= ROLLBACK_BREAKER_THRESHOLD:
                self._activate_breaker()

            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def record_success(self) -> None:
        """Record a successful fix (resets consecutive rollback counter and disabled flag)."""
        self._state["consecutive_rollbacks"] = 0
        self._state["disabled"] = False
        self._save_state()

    # --- Circuit Breaker ---

    def check_rollback_breaker(self) -> str | None:
        """Check if rollback circuit breaker is active.

        Returns reason string if active, None if OK.
        """
        if self._state.get("disabled"):
            return (
                f"Self-disabled after {ROLLBACK_BREAKER_THRESHOLD} consecutive rollbacks. "
                f"Last: {self._state.get('last_rollback_branch', 'unknown')}"
            )
        return None

    def _activate_breaker(self) -> None:
        """Activate the rollback circuit breaker — disable CG."""
        self._state["disabled"] = True
        self._state["disabled_at"] = datetime.now(timezone.utc).isoformat()
        self._save_state()

        msg = (
            f"GUARDIAN SELF-DISABLED\n"
            f"{ROLLBACK_BREAKER_THRESHOLD} consecutive rollbacks detected.\n"
            f"Last branch: {self._state.get('last_rollback_branch', '?')}\n"
            f"Manual review required. Reset with:\n"
            f"python -c \"import json; f=open('{ROLLBACK_STATE_FILE}','w'); "
            f"json.dump({{'disabled':False,'consecutive_rollbacks':0}},f)\""
        )
        logger.critical(msg)
        send_telegram_alert(msg)

    def reset_breaker(self) -> None:
        """Manual reset of the rollback circuit breaker."""
        self._state["disabled"] = False
        self._state["consecutive_rollbacks"] = 0
        self._save_state()
        logger.info("Rollback circuit breaker reset")

    # --- Tag Cleanup ---

    def cleanup_old_tags(self, max_age_hours: int = 24) -> int:
        """Remove pre-fix tags older than max_age_hours.

        Checks each tag's commit timestamp and only removes tags
        pointing to commits older than the threshold.
        """
        try:
            result = subprocess.run(
                ["git", "tag", "-l", f"{TAG_PREFIX}*"],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return 0

            import time as _time
            cutoff = _time.time() - (max_age_hours * 3600)
            removed = 0

            for tag in result.stdout.strip().split("\n"):
                if not tag:
                    continue

                # Get the commit timestamp for this tag
                ts_result = subprocess.run(
                    ["git", "log", "-1", "--format=%ct", tag],
                    cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=10,
                )
                if ts_result.returncode != 0:
                    continue

                try:
                    commit_ts = int(ts_result.stdout.strip())
                except (ValueError, TypeError):
                    continue

                if commit_ts < cutoff:
                    subprocess.run(
                        ["git", "tag", "-d", tag],
                        cwd=str(PROJECT_ROOT), capture_output=True, timeout=10,
                    )
                    removed += 1

            if removed:
                logger.info(f"Cleaned up {removed} pre-fix tags older than {max_age_hours}h")
            return removed

        except Exception:
            return 0
