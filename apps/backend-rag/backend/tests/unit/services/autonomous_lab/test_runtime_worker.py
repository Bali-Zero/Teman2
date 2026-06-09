from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from backend.services.autonomous_lab.command_policy import CommandExecutionPlan
from backend.services.autonomous_lab.receipt_safety import safe_sha256_fingerprint
from backend.services.autonomous_lab.runtime_worker import (
    LabWorkerConfig,
    LabWorkerStatus,
    VerificationCommandResult,
    run_worker_once,
)
from backend.services.autonomous_lab.state_store import (
    AsyncConnection,
    AutonomousLabStateStore,
    LabMachineRole,
    LabRunRecord,
    LabRunStatus,
    resolve_runtime_placement,
)


class FakeConn:
    pass


class FakeAsyncConnection:
    def __init__(self) -> None:
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *args: Any) -> Any:
        self.fetchrow_calls.append((query, args))
        return {"updated_count": 1, "event_id": 123}

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        raise AssertionError("fetch not expected")

    async def execute(self, query: str, *args: Any) -> str:
        raise AssertionError("execute not expected")


class FakeStore:
    def __init__(self, run: LabRunRecord | None, *, transition_updates: bool = True) -> None:
        self.run = run
        self.transition_updates = transition_updates
        self.placement = resolve_runtime_placement("Nuzantara", "nuzantara")
        self.claims: list[tuple[str, LabMachineRole | str | None]] = []
        self.heartbeats: list[tuple[str, str]] = []
        self.succeeded: list[dict[str, Any]] = []
        self.failed: list[dict[str, Any]] = []

    async def claim_next_run(
        self,
        conn: AsyncConnection,
        *,
        worker_id: str,
        machine_role: LabMachineRole | str | None = None,
    ) -> LabRunRecord | None:
        self.claims.append((worker_id, machine_role))
        return self.run

    async def heartbeat_run(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        worker_id: str,
    ) -> bool:
        self.heartbeats.append((run_id, worker_id))
        return self.transition_updates

    async def mark_run_succeeded(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        worker_id: str,
        summary: dict[str, Any] | None = None,
    ) -> bool:
        self.succeeded.append({"run_id": run_id, "worker_id": worker_id, "summary": summary or {}})
        return self.transition_updates

    async def mark_run_failed(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        worker_id: str,
        error: str,
    ) -> bool:
        self.failed.append({"run_id": run_id, "worker_id": worker_id, "error": error})
        return self.transition_updates


def _run_record(target_paths: tuple[str, ...]) -> LabRunRecord:
    return LabRunRecord(
        run_id="runtime-worker-test",
        idempotency_key="runtime-worker-test:v1",
        status=LabRunStatus.RUNNING,
        objective="evidence_fingerprint:sha256:1111-2222; chars:20",
        receipt={"run_id": "runtime-worker-test", "blocked": False},
        target_paths=target_paths,
        metadata={"lane": "ops"},
        priority=10,
        attempts=1,
        max_attempts=3,
        inserted=False,
    )


def _config(*, execute_verification: bool = True) -> LabWorkerConfig:
    repo_root = Path(__file__).resolve().parents[7]
    return LabWorkerConfig(
        worker_id="worker-test",
        repo_root=repo_root,
        backend_root=repo_root / "apps" / "backend-rag",
        execute_verification=execute_verification,
    )


@pytest.mark.asyncio
async def test_worker_idle_when_no_pending_run() -> None:
    store = FakeStore(None)

    result = await run_worker_once(FakeConn(), config=_config(), store=store)

    assert result.status == LabWorkerStatus.IDLE
    assert result.ok is True
    assert result.claimed is False
    assert store.claims == [("worker-test", LabMachineRole.PRO_RUNTIME)]
    assert store.succeeded == []
    assert store.failed == []


@pytest.mark.asyncio
async def test_worker_refuses_non_allowlisted_verification_without_execution() -> None:
    store = FakeStore(_run_record(("apps/mouth/src/lib/api/crm/crm.api.ts",)))
    executor_called = False

    async def executor(_plan: CommandExecutionPlan) -> VerificationCommandResult:
        nonlocal executor_called
        executor_called = True
        raise AssertionError("refused command must not reach executor")

    result = await run_worker_once(
        FakeConn(),
        config=_config(),
        store=store,
        executor=executor,
    )

    assert result.status == LabWorkerStatus.REFUSED
    assert result.ok is False
    assert executor_called is False
    assert store.succeeded == []
    assert (
        store.failed[0]["error"] == "verification command refused by Autonomous Lab command policy"
    )
    assert result.commands[0].command == "cd apps/mouth && npm run lint"
    assert result.commands[0].refusal == "command_not_allowlisted"


@pytest.mark.asyncio
async def test_worker_requires_execution_enabled_after_claim() -> None:
    store = FakeStore(
        _run_record(("apps/backend-rag/backend/services/autonomous_lab/runtime_worker.py",))
    )

    result = await run_worker_once(
        FakeConn(), config=_config(execute_verification=False), store=store
    )

    assert result.status == LabWorkerStatus.REFUSED
    assert (
        store.failed[0]["error"] == "verification execution disabled for runtime worker invocation"
    )
    assert store.succeeded == []


@pytest.mark.asyncio
async def test_worker_executes_allowlisted_commands_and_marks_success() -> None:
    store = FakeStore(
        _run_record(("apps/backend-rag/backend/services/autonomous_lab/runtime_worker.py",))
    )
    executed: list[list[str]] = []
    raw_stdout = "RAW_STDOUT_VALUE_MUST_NOT_LEAK"

    async def executor(plan: CommandExecutionPlan) -> VerificationCommandResult:
        executed.append(plan.argv)
        return VerificationCommandResult(
            command=plan.command,
            allowed=True,
            executed=True,
            returncode=0,
            stdout_chars=len(raw_stdout),
            stdout_fingerprint=safe_sha256_fingerprint(raw_stdout),
        )

    result = await run_worker_once(
        FakeConn(),
        config=_config(),
        store=store,
        executor=executor,
    )

    receipt = result.to_receipt()

    assert result.status == LabWorkerStatus.SUCCEEDED
    assert result.ok is True
    assert len(executed) == 1
    assert store.failed == []
    assert store.succeeded[0]["summary"]["result"] == "verification_passed"
    assert raw_stdout not in str(receipt)
    assert "stdout_fingerprint" in str(receipt)


@pytest.mark.asyncio
async def test_worker_marks_failed_when_allowlisted_command_fails() -> None:
    store = FakeStore(
        _run_record(("apps/backend-rag/backend/services/autonomous_lab/runtime_worker.py",))
    )

    async def executor(plan: CommandExecutionPlan) -> VerificationCommandResult:
        return VerificationCommandResult(
            command=plan.command,
            allowed=True,
            executed=True,
            returncode=1,
            stderr_chars=12,
            stderr_fingerprint=safe_sha256_fingerprint("test failed"),
        )

    result = await run_worker_once(
        FakeConn(),
        config=_config(),
        store=store,
        executor=executor,
    )

    assert result.status == LabWorkerStatus.FAILED
    assert result.ok is False
    assert store.succeeded == []
    assert store.failed[0]["error"] == "one or more Autonomous Lab verification commands failed"


@pytest.mark.asyncio
async def test_real_store_accepts_worker_success_summary_without_raw_output() -> None:
    raw_stdout = "RAW_STDOUT_VALUE_MUST_NOT_LEAK"
    conn = FakeAsyncConnection()
    with patch(
        "backend.services.autonomous_lab.state_store.current_runtime_placement",
        return_value=resolve_runtime_placement("Nuzantara", "nuzantara"),
    ):
        store = AutonomousLabStateStore()

    marked = await store.mark_run_succeeded(
        conn,
        run_id="runtime-worker-test",
        worker_id="worker-test",
        summary={
            "result": "verification_passed",
            "command_count": 1,
            "commands": [
                VerificationCommandResult(
                    command=(
                        "cd apps/backend-rag && PYTHONPATH=. "
                        "pytest backend/tests/unit/services/autonomous_lab -q"
                    ),
                    allowed=True,
                    executed=True,
                    returncode=0,
                    stdout_chars=len(raw_stdout),
                    stdout_fingerprint=safe_sha256_fingerprint(raw_stdout),
                ).to_receipt()
            ],
        },
    )

    payload = str(conn.fetchrow_calls[0][1])

    assert marked is True
    assert raw_stdout not in payload
    assert "RAW_STDOUT_VALUE_MUST_NOT_LEAK" not in payload
    assert "evidence_fingerprint:sha256:" in payload
