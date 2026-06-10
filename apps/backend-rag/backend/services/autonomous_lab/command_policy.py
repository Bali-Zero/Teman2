"""Shared command allowlist for autonomous lab planning and execution."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

SAFE_COMMAND_ARG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
SAFE_WORKTREE_COMMAND_PATTERN = re.compile(
    r"^python scripts/agent_start\.py --lane "
    r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127} --task-id "
    r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"
)

PYTEST_AUTONOMOUS_LAB_COMMAND = (
    "cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/autonomous_lab -q"
)
GIT_DIFF_RESEARCH_COMMAND = "git diff --check -- research/operations/autonomous-lab"
GENERIC_GIT_DIFF_CHECK_COMMAND = "git diff --check"
UNSUPPORTED_MOUTH_LINT_COMMAND = "cd apps/mouth && npm run lint"

ALLOWED_VERIFICATION_COMMANDS = frozenset(
    {
        PYTEST_AUTONOMOUS_LAB_COMMAND,
        GIT_DIFF_RESEARCH_COMMAND,
        GENERIC_GIT_DIFF_CHECK_COMMAND,
    }
)
BLOCKED_COMMAND_VERBS = frozenset({"deploy", "merge", "push"})


@dataclass(frozen=True)
class CommandExecutionPlan:
    """A shell-free execution plan for one allowlisted lab command."""

    command: str
    argv: list[str]
    cwd: Path
    env: dict[str, str] | None = None


def require_safe_command_arg(value: str, field_name: str) -> str:
    """Validate a command slug used inside planned command receipts."""
    candidate = value.strip()
    if not SAFE_COMMAND_ARG_PATTERN.match(candidate):
        raise ValueError(f"{field_name} must be a safe slug for planned command receipts")
    return candidate


def build_worktree_command(*, lane: str, task_id: str) -> str:
    """Return the canonical worktree isolation command."""
    safe_lane = require_safe_command_arg(lane, "worktree_lane")
    safe_task_id = require_safe_command_arg(task_id, "task_id")
    return f"python scripts/agent_start.py --lane {safe_lane} --task-id {safe_task_id}"


def is_allowed_worktree_command(command: str) -> bool:
    """Return True when command is the exact autonomous-lab worktree command shape."""
    return bool(SAFE_WORKTREE_COMMAND_PATTERN.match(command.strip()))


def is_allowed_verification_command(command: str) -> bool:
    """Return True when command is an executable autonomous-lab verification command."""
    return command.strip() in ALLOWED_VERIFICATION_COMMANDS


def is_allowed_lab_command(command: str) -> bool:
    """Return True when command may appear in any lab command field."""
    return is_allowed_worktree_command(command) or is_allowed_verification_command(command)


def refusal_reason(command: str) -> str:
    """Return why a command is refused by the lab policy."""
    if contains_blocked_command_verb(command):
        return "blocked_command_verb"
    return "command_not_allowlisted"


def contains_blocked_command_verb(command: str) -> bool:
    """Return True for deploy, merge, and push verbs."""
    tokens = {token for token in re.split(r"[^a-zA-Z0-9_-]+", command.lower()) if token}
    return bool(tokens & BLOCKED_COMMAND_VERBS)


def verification_commands_for_paths(target_paths: list[str]) -> list[str]:
    """Return planned verification commands for repository-relative target paths."""
    commands: list[str] = []
    if any(path.startswith("apps/backend-rag/") for path in target_paths):
        commands.append(PYTEST_AUTONOMOUS_LAB_COMMAND)
    if any(path.startswith("apps/mouth/") for path in target_paths):
        commands.append(UNSUPPORTED_MOUTH_LINT_COMMAND)
    if any(path.startswith("research/") for path in target_paths):
        commands.append(GIT_DIFF_RESEARCH_COMMAND)
    return commands or [GENERIC_GIT_DIFF_CHECK_COMMAND]


def plan_for_allowlisted_command(
    command: str,
    *,
    repo_root: Path,
    backend_root: Path,
) -> CommandExecutionPlan | None:
    """Translate an allowlisted command into shell-free argv."""
    normalized = command.strip()
    if normalized == PYTEST_AUTONOMOUS_LAB_COMMAND:
        env = os.environ.copy()
        env["PYTHONPATH"] = "."
        return CommandExecutionPlan(
            command=normalized,
            argv=[
                _pytest_executable(backend_root),
                "backend/tests/unit/services/autonomous_lab",
                "-q",
            ],
            cwd=backend_root,
            env=env,
        )
    if normalized == GIT_DIFF_RESEARCH_COMMAND:
        return CommandExecutionPlan(
            command=normalized,
            argv=[
                "git",
                "diff",
                "--check",
                "--",
                "research/operations/autonomous-lab",
            ],
            cwd=repo_root,
        )
    if normalized == GENERIC_GIT_DIFF_CHECK_COMMAND:
        return CommandExecutionPlan(
            command=normalized,
            argv=["git", "diff", "--check"],
            cwd=repo_root,
        )
    return None


def _pytest_executable(backend_root: Path) -> str:
    local_pytest = backend_root / ".venv" / "bin" / "pytest"
    if local_pytest.exists():
        return str(local_pytest)
    return "pytest"


__all__ = [
    "ALLOWED_VERIFICATION_COMMANDS",
    "BLOCKED_COMMAND_VERBS",
    "GENERIC_GIT_DIFF_CHECK_COMMAND",
    "GIT_DIFF_RESEARCH_COMMAND",
    "PYTEST_AUTONOMOUS_LAB_COMMAND",
    "SAFE_COMMAND_ARG_PATTERN",
    "SAFE_WORKTREE_COMMAND_PATTERN",
    "UNSUPPORTED_MOUTH_LINT_COMMAND",
    "CommandExecutionPlan",
    "build_worktree_command",
    "contains_blocked_command_verb",
    "is_allowed_lab_command",
    "is_allowed_verification_command",
    "is_allowed_worktree_command",
    "plan_for_allowlisted_command",
    "refusal_reason",
    "require_safe_command_arg",
    "verification_commands_for_paths",
]
