#!/usr/bin/env python3
"""Bounded dry-run runner for autonomous lab verification plans."""
# ruff: noqa: E402, I001

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "scripts"
BACKEND_ROOT = REPO_ROOT / "apps" / "backend-rag"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from autonomous_lab_draft import build_run, load_input
from backend.services.autonomous_lab.command_policy import (
    CommandExecutionPlan,
    plan_for_allowlisted_command as build_allowlisted_command_plan,
    refusal_reason,
)
from backend.services.autonomous_lab.receipt_safety import receipt_safe_evidence
from backend.services.autonomous_lab.sandbox_runner import LocalWorktreeSandboxRunner


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the autonomous lab draft input JSON.",
    )
    parser.add_argument(
        "--execute-verification",
        action="store_true",
        help="Execute only allowlisted planner verification commands.",
    )
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Return 0 even if planner blocker gates fail.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)
    try:
        payload = load_input(args.input)
        _, run = build_run(payload)
    except (OSError, TypeError, ValueError) as exc:
        json.dump(
            summarize_input_validation_error(
                exc,
                execute_verification=args.execute_verification,
            ),
            sys.stdout,
            indent=2,
            sort_keys=True,
        )
        sys.stdout.write("\n")
        return 1

    verification = build_verification_summary(
        run.simulation_plan.verification_commands,
        execute=args.execute_verification,
    )
    summary = summarize_run(
        run,
        execute_verification=args.execute_verification,
        verification=verification,
    )
    json.dump(summary, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    if summary["unsafe_verification_refused"]:
        return 3
    if summary["verification_failed"]:
        return 4
    if summary["blocked"] and not args.allow_blocked:
        return 2
    return 0


def build_verification_summary(
    commands: list[str],
    *,
    execute: bool,
) -> dict[str, Any]:
    """Return dry-run or execution results for planner verification commands."""
    command_plans = [plan_for_allowlisted_command(command) for command in commands]
    refused = [
        {
            "command": _receipt_command_reference(command, allowed=plan is not None),
            "reason": refusal_reason(command),
        }
        for command, plan in zip(commands, command_plans, strict=True)
        if plan is None
    ]

    if not execute:
        return {
            "execute_requested": False,
            "refused_commands": refused,
            "results": [
                {
                    "command": _receipt_command_reference(command, allowed=plan is not None),
                    "allowed": plan is not None,
                    "executed": False,
                    "returncode": None,
                }
                for command, plan in zip(commands, command_plans, strict=True)
            ],
        }

    if refused:
        return {
            "execute_requested": True,
            "refused_commands": refused,
            "results": [
                {
                    "command": _receipt_command_reference(command, allowed=plan is not None),
                    "allowed": plan is not None,
                    "executed": False,
                    "returncode": None,
                }
                for command, plan in zip(commands, command_plans, strict=True)
            ],
        }

    return {
        "execute_requested": True,
        "refused_commands": [],
        "results": [
            execute_command_plan(plan)
            for plan in command_plans
            if plan is not None
        ],
    }


def summarize_run(
    run: Any,
    *,
    execute_verification: bool,
    verification: dict[str, Any],
) -> dict[str, Any]:
    """Build the receipt-safe lab run summary emitted to stdout."""
    failed_blockers = [
        gate.name
        for gate in run.safety_gates
        if gate.severity.value == "blocker" and not gate.passed
    ]
    unsafe_refused = bool(verification["refused_commands"])
    verification_failed = any(
        result["executed"] and result["returncode"] != 0
        for result in verification["results"]
    )
    return {
        "ok": not failed_blockers and not unsafe_refused and not verification_failed,
        "mode": "execute-verification" if execute_verification else "dry-run",
        "blocked": bool(failed_blockers),
        "failed_blockers": failed_blockers,
        "unsafe_verification_refused": unsafe_refused,
        "verification_failed": verification_failed,
        "run_id": run.run_id,
        "worktree_command": run.simulation_plan.worktree_command,
        "verification_commands": [
            _receipt_verification_command_reference(command)
            for command in run.simulation_plan.verification_commands
        ],
        "verification": verification,
        "receipt": _receipt_with_safe_verification_commands(run.to_receipt()),
    }


def summarize_input_validation_error(
    exc: BaseException,
    *,
    execute_verification: bool,
) -> dict[str, Any]:
    """Build a receipt-safe CLI error when the input cannot form a Lab run."""
    return {
        "ok": False,
        "mode": "execute-verification" if execute_verification else "dry-run",
        "blocked": True,
        "failed_blockers": ["input_validation"],
        "unsafe_verification_refused": False,
        "verification_failed": False,
        "error_reference": receipt_safe_evidence(str(exc), force_fingerprint=True),
        "verification": {
            "execute_requested": execute_verification,
            "refused_commands": [],
            "results": [],
        },
    }


def plan_for_allowlisted_command(command: str) -> CommandExecutionPlan | None:
    """Translate one allowlisted planner command into shell-free argv."""
    return build_allowlisted_command_plan(
        command,
        repo_root=REPO_ROOT,
        backend_root=BACKEND_ROOT,
    )


def _receipt_command_reference(command: str, *, allowed: bool) -> str:
    if allowed:
        return command
    return receipt_safe_evidence(command, force_fingerprint=True)


def _receipt_verification_command_reference(command: str) -> str:
    return _receipt_command_reference(
        command,
        allowed=plan_for_allowlisted_command(command) is not None,
    )


def _receipt_with_safe_verification_commands(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _receipt_with_safe_verification_commands_for_key(str(key), child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_receipt_with_safe_verification_commands(child) for child in value]
    return value


def _receipt_with_safe_verification_commands_for_key(key: str, value: Any) -> Any:
    if key in {"verification_commands", "planned_only_commands"} and isinstance(value, list):
        return [
            _receipt_verification_command_reference(command)
            if isinstance(command, str)
            else _receipt_with_safe_verification_commands(command)
            for command in value
        ]
    return _receipt_with_safe_verification_commands(value)


def execute_command_plan(plan: CommandExecutionPlan) -> dict[str, Any]:
    """Execute an allowlisted command plan without a shell."""
    runner = LocalWorktreeSandboxRunner(
        repo_root=REPO_ROOT,
        run_func=subprocess.run,
    )
    return runner.run(plan).to_receipt()


if __name__ == "__main__":
    raise SystemExit(main())
