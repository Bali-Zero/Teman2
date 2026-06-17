"""Policy-bound local sandbox runner for Autonomous Lab verification commands."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.services.autonomous_lab.command_policy import (
    ADMIN_DASHBOARD_LINT_COMMAND,
    GENERIC_GIT_DIFF_CHECK_COMMAND,
    GIT_DIFF_RESEARCH_COMMAND,
    PYTEST_AUTONOMOUS_LAB_COMMAND,
    CommandExecutionPlan,
    expected_env_for_allowlisted_command,
    is_allowed_verification_command,
    refusal_reason,
)
from backend.services.autonomous_lab.receipt_safety import (
    receipt_safe_command_output,
    receipt_safe_evidence,
)

DEFAULT_SANDBOX_TIMEOUT_SECONDS = 600
DEFAULT_OUTPUT_LIMIT = 12_000
DEFAULT_ENV_ALLOWLIST = frozenset({"CI", "NODE_ENV", "PATH", "PYTHONPATH"})

SubprocessRun = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class SandboxCommandResult:
    """Receipt-safe result for one sandboxed command plan."""

    command: str
    argv: tuple[str, ...]
    cwd: Path
    returncode: int
    stdout_reference: str
    stderr_reference: str
    timed_out: bool = False
    executed: bool = True
    allowed: bool = True

    def to_receipt(self) -> dict[str, Any]:
        """Return the JSON-safe runner result."""
        command = self.command
        argv = list(self.argv)
        if not self.allowed or not self.executed:
            command = receipt_safe_evidence(self.command, force_fingerprint=True)
            argv = [
                receipt_safe_evidence(arg, force_fingerprint=True)
                for arg in self.argv
            ]
        return {
            "command": command,
            "allowed": self.allowed,
            "executed": self.executed,
            "argv": argv,
            "cwd": str(self.cwd),
            "returncode": self.returncode,
            "timed_out": self.timed_out,
            "stdout": self.stdout_reference,
            "stderr": self.stderr_reference,
        }


class LocalWorktreeSandboxRunner:
    """Execute allowlisted command plans inside the current worktree boundary."""

    def __init__(
        self,
        *,
        repo_root: Path,
        timeout_seconds: int = DEFAULT_SANDBOX_TIMEOUT_SECONDS,
        output_limit: int = DEFAULT_OUTPUT_LIMIT,
        env_allowlist: frozenset[str] = DEFAULT_ENV_ALLOWLIST,
        run_func: SubprocessRun | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.timeout_seconds = timeout_seconds
        self.output_limit = output_limit
        self.env_allowlist = env_allowlist
        self._run = run_func or subprocess.run

    def run(self, plan: CommandExecutionPlan) -> SandboxCommandResult:
        """Run one shell-free plan with timeout and receipt-safe output references."""
        self._assert_plan_within_repo(plan)
        refusal = self._plan_refusal_reason(plan)
        if refusal is not None:
            return SandboxCommandResult(
                command=plan.command,
                argv=tuple(str(arg) for arg in plan.argv),
                cwd=plan.cwd,
                returncode=126,
                stdout_reference=receipt_safe_command_output("", source="stdout"),
                stderr_reference=receipt_safe_command_output(
                    f"sandbox_refusal:{refusal}",
                    source="stderr",
                    limit=self.output_limit,
                ),
                executed=False,
                allowed=False,
            )
        try:
            completed = self._run(
                list(plan.argv),
                cwd=plan.cwd,
                env=plan.env,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
            return SandboxCommandResult(
                command=plan.command,
                argv=tuple(str(arg) for arg in plan.argv),
                cwd=plan.cwd,
                returncode=int(completed.returncode),
                stdout_reference=receipt_safe_command_output(
                    completed.stdout or "",
                    source="stdout",
                    limit=self.output_limit,
                ),
                stderr_reference=receipt_safe_command_output(
                    completed.stderr or "",
                    source="stderr",
                    limit=self.output_limit,
                ),
            )
        except subprocess.TimeoutExpired as exc:
            stdout = _timeout_output_to_text(exc.stdout)
            stderr = _timeout_output_to_text(exc.stderr)
            return SandboxCommandResult(
                command=plan.command,
                argv=tuple(str(arg) for arg in plan.argv),
                cwd=plan.cwd,
                returncode=124,
                stdout_reference=receipt_safe_command_output(
                    stdout,
                    source="stdout",
                    limit=self.output_limit,
                ),
                stderr_reference=receipt_safe_command_output(
                    stderr,
                    source="stderr",
                    limit=self.output_limit,
                ),
                timed_out=True,
            )
        except OSError:
            return SandboxCommandResult(
                command=plan.command,
                argv=tuple(str(arg) for arg in plan.argv),
                cwd=plan.cwd,
                returncode=127,
                stdout_reference=receipt_safe_command_output("", source="stdout"),
                stderr_reference=receipt_safe_command_output(
                    "sandbox_execution_error",
                    source="stderr",
                    limit=self.output_limit,
                ),
                executed=False,
                allowed=False,
            )

    def _assert_plan_within_repo(self, plan: CommandExecutionPlan) -> None:
        if not plan.argv:
            raise ValueError("sandbox command plan must include argv")
        cwd = plan.cwd.resolve()
        if not cwd.is_relative_to(self.repo_root):
            raise ValueError("sandbox command cwd must stay inside the Lab worktree")

    def _plan_refusal_reason(self, plan: CommandExecutionPlan) -> str | None:
        if not is_allowed_verification_command(plan.command):
            return refusal_reason(plan.command)
        shape_refusal = self._command_shape_refusal_reason(plan)
        if shape_refusal is not None:
            return shape_refusal
        env_keys = set((plan.env or {}).keys())
        unsafe_env_keys = sorted(env_keys - self.env_allowlist)
        if unsafe_env_keys:
            return "env_key_not_allowlisted"
        expected_env = expected_env_for_allowlisted_command(plan.command)
        if expected_env is None or (plan.env or {}) != expected_env:
            return "env_value_not_allowlisted"
        return None

    def _command_shape_refusal_reason(self, plan: CommandExecutionPlan) -> str | None:
        command = plan.command.strip()
        argv = [str(arg) for arg in plan.argv]
        cwd = plan.cwd.resolve()
        backend_root = (self.repo_root / "apps" / "backend-rag").resolve()

        if command == GENERIC_GIT_DIFF_CHECK_COMMAND:
            if cwd != self.repo_root:
                return "cwd_not_allowlisted"
            if argv != ["git", "diff", "--check"]:
                return "argv_not_allowlisted"
            return None

        if command == GIT_DIFF_RESEARCH_COMMAND:
            if cwd != self.repo_root:
                return "cwd_not_allowlisted"
            if argv != [
                "git",
                "diff",
                "--check",
                "--",
                "research/operations/autonomous-lab",
            ]:
                return "argv_not_allowlisted"
            return None

        if command == PYTEST_AUTONOMOUS_LAB_COMMAND:
            if cwd != backend_root:
                return "cwd_not_allowlisted"
            if argv != [
                str(backend_root / ".venv" / "bin" / "pytest"),
                "backend/tests/unit/services/autonomous_lab",
                "-q",
            ]:
                return "argv_not_allowlisted"
            return None

        if command == ADMIN_DASHBOARD_LINT_COMMAND:
            npm = shutil.which("npm")
            if npm is None:
                return "executable_not_found"
            if cwd != (self.repo_root / "apps" / "admin-dashboard").resolve():
                return "cwd_not_allowlisted"
            if argv != [npm, "run", "lint"]:
                return "argv_not_allowlisted"
            return None

        return "command_not_allowlisted"


def _timeout_output_to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


__all__ = [
    "DEFAULT_ENV_ALLOWLIST",
    "DEFAULT_OUTPUT_LIMIT",
    "DEFAULT_SANDBOX_TIMEOUT_SECONDS",
    "LocalWorktreeSandboxRunner",
    "SandboxCommandResult",
]
