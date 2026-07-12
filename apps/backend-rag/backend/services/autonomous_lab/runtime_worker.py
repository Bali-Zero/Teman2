"""Pro-only runtime worker for Autonomous Lab queue items.

The v1 Lab control plane can enqueue durable work from Air/Mini/Pro, but only
the Pro may claim and execute run work. This module activates the verification
runner slice without starting an H24 daemon or enabling promotion/deploy.
"""

from __future__ import annotations

import asyncio
import socket
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from backend.services.autonomous_lab.command_policy import (
    CommandExecutionPlan,
    plan_for_allowlisted_command,
    refusal_reason,
    verification_commands_for_paths,
)
from backend.services.autonomous_lab.receipt_safety import (
    receipt_safe_evidence,
    safe_sha256_fingerprint,
)
from backend.services.autonomous_lab.state_store import (
    AsyncConnection,
    AutonomousLabStateStore,
    LabMachineRole,
    LabRunRecord,
)

DEFAULT_COMMAND_TIMEOUT_SECONDS = 120
DEFAULT_MAX_VERIFICATION_COMMANDS = 12


class LabWorkerStatus(str, Enum):
    """High-level outcome for one queue worker tick."""

    IDLE = "idle"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUSED = "refused"
    MARK_FAILED = "mark_failed"


@dataclass(frozen=True)
class VerificationCommandResult:
    """Receipt-safe result for one planned verification command."""

    command: str
    allowed: bool
    executed: bool
    returncode: int | None
    duration_ms: int = 0
    refusal: str | None = None
    stdout_chars: int = 0
    stderr_chars: int = 0
    stdout_fingerprint: str | None = None
    stderr_fingerprint: str | None = None

    @property
    def failed(self) -> bool:
        """Return True when this command blocks the run."""
        return (not self.allowed) or (self.executed and self.returncode != 0)

    def to_receipt(self) -> dict[str, Any]:
        """Return a DB-safe command receipt without raw output."""
        return {
            "command": self.command,
            "allowed": self.allowed,
            "executed": self.executed,
            "returncode": self.returncode,
            "duration_ms": self.duration_ms,
            "refusal": self.refusal,
            "stdout_chars": self.stdout_chars,
            "stderr_chars": self.stderr_chars,
            "stdout_fingerprint": self.stdout_fingerprint,
            "stderr_fingerprint": self.stderr_fingerprint,
        }


@dataclass(frozen=True)
class LabWorkerConfig:
    """Bounded execution policy for one Pro worker tick."""

    worker_id: str
    repo_root: Path
    backend_root: Path
    execute_verification: bool
    command_timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS
    max_verification_commands: int = DEFAULT_MAX_VERIFICATION_COMMANDS


@dataclass(frozen=True)
class LabWorkerTickResult:
    """Receipt-safe outcome for one worker tick."""

    status: LabWorkerStatus
    worker_id: str
    run_id: str | None = None
    claimed: bool = False
    marked: bool = False
    commands: tuple[VerificationCommandResult, ...] = ()
    message: str = ""
    placement: LabMachineRole = LabMachineRole.PRO_RUNTIME
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Return True for non-error tick outcomes."""
        return self.status in {LabWorkerStatus.IDLE, LabWorkerStatus.SUCCEEDED}

    def to_receipt(self) -> dict[str, Any]:
        """Return a durable receipt without raw command output."""
        return {
            "ok": self.ok,
            "status": self.status.value,
            "worker_id": self.worker_id,
            "run_id": self.run_id,
            "claimed": self.claimed,
            "marked": self.marked,
            "placement": self.placement.value,
            "message": receipt_safe_evidence(self.message, force_fingerprint=True)
            if self.message
            else "",
            "commands": [command.to_receipt() for command in self.commands],
            "metadata": dict(self.metadata),
        }


class LabRunStateStore(Protocol):
    """State-store subset used by the runtime worker."""

    placement: Any

    async def claim_next_run(
        self,
        conn: AsyncConnection,
        *,
        worker_id: str,
        machine_role: LabMachineRole | str | None = None,
    ) -> LabRunRecord | None: ...

    async def heartbeat_run(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        worker_id: str,
    ) -> bool: ...

    async def mark_run_succeeded(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        worker_id: str,
        summary: Mapping[str, Any] | None = None,
    ) -> bool: ...

    async def mark_run_failed(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        worker_id: str,
        error: str,
    ) -> bool: ...


CommandExecutor = Callable[[CommandExecutionPlan], Awaitable[VerificationCommandResult]]


async def run_worker_once(
    conn: AsyncConnection,
    *,
    config: LabWorkerConfig,
    store: LabRunStateStore | None = None,
    executor: CommandExecutor | None = None,
) -> LabWorkerTickResult:
    """Claim one pending run and execute its allowlisted verification plan."""
    state_store = store or AutonomousLabStateStore()
    role = LabMachineRole.PRO_RUNTIME
    run = await state_store.claim_next_run(
        conn,
        worker_id=config.worker_id,
        machine_role=role,
    )
    if run is None:
        return LabWorkerTickResult(
            status=LabWorkerStatus.IDLE,
            worker_id=config.worker_id,
            claimed=False,
            placement=role,
            message="no pending autonomous lab run",
        )

    await state_store.heartbeat_run(conn, run_id=run.run_id, worker_id=config.worker_id)
    commands = _verification_commands_for_run(run, config)
    if isinstance(commands, str):
        return await _fail_claimed_run(
            conn,
            state_store=state_store,
            config=config,
            run=run,
            status=LabWorkerStatus.REFUSED,
            commands=(),
            message=commands,
        )

    # The execution kill-switch is a worker-level gate, so refuse before any
    # per-command planning. Planning resolves the verification binaries
    # (pytest/npm) against the host; if it ran first, a disabled-execution
    # invocation on a host that cannot resolve those binaries would be
    # misreported as a command-policy refusal instead of "execution disabled".
    if not config.execute_verification:
        return await _fail_claimed_run(
            conn,
            state_store=state_store,
            config=config,
            run=run,
            status=LabWorkerStatus.REFUSED,
            commands=(),
            message="verification execution disabled for runtime worker invocation",
        )

    planned = _plan_commands(commands, config)
    if any(not result.allowed for result in planned):
        return await _fail_claimed_run(
            conn,
            state_store=state_store,
            config=config,
            run=run,
            status=LabWorkerStatus.REFUSED,
            commands=tuple(planned),
            message="verification command refused by Autonomous Lab command policy",
        )

    command_executor = executor or (
        lambda plan: execute_command_plan(
            plan,
            timeout_seconds=config.command_timeout_seconds,
        )
    )
    results = tuple([await command_executor(plan) for plan in _plans_only(commands, config)])
    failed = [result for result in results if result.failed]
    if failed:
        return await _fail_claimed_run(
            conn,
            state_store=state_store,
            config=config,
            run=run,
            status=LabWorkerStatus.FAILED,
            commands=results,
            message="one or more Autonomous Lab verification commands failed",
        )

    summary = {
        "result": "verification_passed",
        "command_count": len(results),
        "target_path_count": len(run.target_paths),
        "commands": [result.to_receipt() for result in results],
    }
    marked = await state_store.mark_run_succeeded(
        conn,
        run_id=run.run_id,
        worker_id=config.worker_id,
        summary=summary,
    )
    return LabWorkerTickResult(
        status=LabWorkerStatus.SUCCEEDED if marked else LabWorkerStatus.MARK_FAILED,
        worker_id=config.worker_id,
        run_id=run.run_id,
        claimed=True,
        marked=marked,
        commands=results,
        placement=role,
        message="autonomous lab verification succeeded"
        if marked
        else "verification passed but success transition missed owner scope",
        metadata={"target_path_count": len(run.target_paths)},
    )


async def execute_command_plan(
    plan: CommandExecutionPlan,
    *,
    timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> VerificationCommandResult:
    """Execute one allowlisted command plan without shell expansion."""
    started = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *plan.argv,
        cwd=str(plan.cwd),
        env=plan.env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_raw, stderr_raw = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_seconds,
        )
        returncode = proc.returncode
        refusal = None
    except asyncio.TimeoutError:
        proc.kill()
        stdout_raw, stderr_raw = await proc.communicate()
        returncode = 124
        refusal = "timeout"

    stdout_text = stdout_raw.decode("utf-8", errors="replace")
    stderr_text = stderr_raw.decode("utf-8", errors="replace")
    return VerificationCommandResult(
        command=plan.command,
        allowed=True,
        executed=True,
        returncode=returncode,
        duration_ms=int((time.monotonic() - started) * 1000),
        refusal=refusal,
        stdout_chars=len(stdout_text),
        stderr_chars=len(stderr_text),
        stdout_fingerprint=_fingerprint_or_none(stdout_text),
        stderr_fingerprint=_fingerprint_or_none(stderr_text),
    )


def default_worker_id(prefix: str = "autonomous-lab-worker") -> str:
    """Return a stable, low-cardinality worker id for the current process."""
    hostname = socket.gethostname().replace(".", "-")
    return f"{prefix}:{hostname}"


def _verification_commands_for_run(
    run: LabRunRecord,
    config: LabWorkerConfig,
) -> list[str] | str:
    commands = verification_commands_for_paths(list(run.target_paths))
    if len(commands) > config.max_verification_commands:
        return "verification command count exceeds Autonomous Lab worker bound"
    return commands


def _plan_commands(
    commands: list[str],
    config: LabWorkerConfig,
) -> list[VerificationCommandResult]:
    results: list[VerificationCommandResult] = []
    for command in commands:
        plan = plan_for_allowlisted_command(
            command,
            repo_root=config.repo_root,
            backend_root=config.backend_root,
        )
        if plan is None:
            results.append(
                VerificationCommandResult(
                    command=command,
                    allowed=False,
                    executed=False,
                    returncode=None,
                    refusal=refusal_reason(command),
                )
            )
            continue
        results.append(
            VerificationCommandResult(
                command=command,
                allowed=True,
                executed=False,
                returncode=None,
            )
        )
    return results


def _plans_only(
    commands: list[str],
    config: LabWorkerConfig,
) -> list[CommandExecutionPlan]:
    plans: list[CommandExecutionPlan] = []
    for command in commands:
        plan = plan_for_allowlisted_command(
            command,
            repo_root=config.repo_root,
            backend_root=config.backend_root,
        )
        if plan is None:
            raise ValueError(f"unexpected refused command after policy preflight: {command}")
        plans.append(plan)
    return plans


async def _fail_claimed_run(
    conn: AsyncConnection,
    *,
    state_store: LabRunStateStore,
    config: LabWorkerConfig,
    run: LabRunRecord,
    status: LabWorkerStatus,
    commands: tuple[VerificationCommandResult, ...],
    message: str,
) -> LabWorkerTickResult:
    marked = await state_store.mark_run_failed(
        conn,
        run_id=run.run_id,
        worker_id=config.worker_id,
        error=message,
    )
    return LabWorkerTickResult(
        status=status if marked else LabWorkerStatus.MARK_FAILED,
        worker_id=config.worker_id,
        run_id=run.run_id,
        claimed=True,
        marked=marked,
        commands=commands,
        placement=LabMachineRole.PRO_RUNTIME,
        message=message if marked else "failed run transition missed owner scope",
        metadata={"target_path_count": len(run.target_paths)},
    )


def _fingerprint_or_none(value: str) -> str | None:
    if not value:
        return None
    return safe_sha256_fingerprint(value)


__all__ = [
    "DEFAULT_COMMAND_TIMEOUT_SECONDS",
    "DEFAULT_MAX_VERIFICATION_COMMANDS",
    "CommandExecutor",
    "LabRunStateStore",
    "LabWorkerConfig",
    "LabWorkerStatus",
    "LabWorkerTickResult",
    "VerificationCommandResult",
    "default_worker_id",
    "execute_command_plan",
    "run_worker_once",
]
