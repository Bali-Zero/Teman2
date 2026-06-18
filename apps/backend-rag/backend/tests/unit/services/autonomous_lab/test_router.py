from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.routers import autonomous_lab
from backend.app.utils.internal_api_auth import verify_internal_api_key
from backend.services.autonomous_lab.scheduler import build_lab_scheduler_status
from backend.services.autonomous_lab.state_store import resolve_runtime_placement
from backend.services.autonomous_lab.worker import LabWorkerTickResult


def _build_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    enabled: bool = True,
    persistence_enabled: bool = False,
    db_pool: Any | None = None,
) -> TestClient:
    monkeypatch.setattr(settings, "autonomous_lab_enabled", enabled)
    monkeypatch.setattr(settings, "autonomous_lab_persistence_enabled", persistence_enabled)
    monkeypatch.setattr(settings, "autonomous_lab_receipt_dir", str(tmp_path / "receipts"))

    app = FastAPI()
    if db_pool is not None:
        app.state.db_pool = db_pool
    app.include_router(autonomous_lab.router)

    async def _ok() -> dict[str, str]:
        return {"service": "autonomous-lab-test"}

    app.dependency_overrides[verify_internal_api_key] = _ok
    return TestClient(app)


class RouterFakeConnection:
    def __init__(
        self,
        *,
        fetchrow_results: list[Any] | None = None,
        fetch_results: list[list[Any]] | None = None,
    ) -> None:
        self.fetchrow_results = fetchrow_results or []
        self.fetch_results = fetch_results or []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *args: Any) -> Any:
        self.fetchrow_calls.append((query, args))
        if not self.fetchrow_results:
            return None
        return self.fetchrow_results.pop(0)

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self.fetch_calls.append((query, args))
        if not self.fetch_results:
            return []
        return self.fetch_results.pop(0)

    async def execute(self, query: str, *args: Any) -> str:
        raise AssertionError(f"router contract should use fetchrow/fetch here: {query}")


class RouterFakePool:
    def __init__(self, conn: RouterFakeConnection) -> None:
        self.conn = conn

    def acquire(self) -> RouterFakePool:
        return self

    async def __aenter__(self) -> RouterFakeConnection:
        return self.conn

    async def __aexit__(self, *_exc: Any) -> None:
        return None


class RouterIdleWorker:
    async def tick(
        self,
        _conn: RouterFakeConnection,
        *,
        worker_id: str,
    ) -> LabWorkerTickResult:
        return LabWorkerTickResult.idle(worker_id=worker_id)


def _payload(raw_phrase: str = "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR") -> dict:
    return {
        "created_at": "2026-06-09T08:30:00+00:00",
        "objective": "complete the bounded autonomous lab fleet",
        "task_id": "router-lab-test",
        "worktree_lane": "ops",
        "target_paths": [
            "apps/backend-rag/backend/services/autonomous_lab/planner.py",
            "apps/backend-rag/backend/tests/unit/services/autonomous_lab/test_router.py",
        ],
        "materials": [
            {
                "material_id": "m1",
                "source_type": "operator_note",
                "source_uri": "note://local/router-test",
                "title": "Router test material",
                "text": f"Lab should use deterministic review and verification. {raw_phrase}",
                "captured_at": "2026-06-09T08:30:00+00:00",
                "metadata": {"scope": "unit-test"},
            }
        ],
    }


def _run_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "run_id": "lab-runtime-test",
        "idempotency_key": "lab-runtime-test:v1",
        "status": "paused",
        "objective": "RAW_PRIVATE_OBJECTIVE_SHOULD_NOT_APPEAR",
        "receipt": {"run_id": "lab-runtime-test", "blocked": False},
        "target_paths": ["apps/backend-rag/backend/services/autonomous_lab/state_store.py"],
        "metadata": {"last_checkpoint_stage": "curate"},
        "priority": 10,
        "attempts": 1,
        "max_attempts": 3,
        "inserted": False,
    }
    row.update(overrides)
    return row


def _pro_scheduler_status(**kwargs: Any) -> Any:
    return build_lab_scheduler_status(
        **kwargs,
        placement=resolve_runtime_placement("Nuzantara", "nuzantara"),
    )


def test_draft_endpoint_returns_receipt_safe_agent_fleet(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw_phrase = "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR"
    client = _build_client(monkeypatch, tmp_path)

    response = client.post("/api/autonomous-lab/drafts", json=_payload(raw_phrase))

    assert response.status_code == 202, response.text
    body = response.json()
    receipt_text = json.dumps(body["receipt"], sort_keys=True)

    assert body["accepted"] is True
    assert body["run_id"] == "router-lab-test"
    assert body["blocked"] is False
    assert raw_phrase not in receipt_text
    assert [member["role"] for member in body["receipt"]["agent_fleet"]] == [
        "frontier_watchtower",
        "intake_normalizer",
        "hypothesis_composer",
        "context_builder",
        "reviewer",
        "verification_planner",
    ]
    assert body["receipt"]["execution_policy"]["shell_commands_executed"] == []
    assert body["receipt"]["final_review"]["approved"] is True


def test_status_endpoint_returns_control_room_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)

    response = client.get("/api/autonomous-lab/status")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == "autonomous-lab-v1-runtime-contract"
    assert body["doctrine"] == "state + sandbox + evaluator + curator"
    assert [stage["id"] for stage in body["stages"]] == [
        "watch",
        "intake",
        "plan",
        "worker",
        "arena",
        "tribunal",
        "curator",
        "archive",
    ]
    assert body["runtime_placement"]["machine_role"] in {
        "air_m5_cockpit",
        "pro_runtime",
        "mini_scheduler",
        "unknown",
    }
    assert body["operational_plan"]["version"] == "autonomous-lab-v1-control-plane"


def test_runs_endpoint_returns_paused_dry_run_without_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)

    response = client.get("/api/autonomous-lab/runs")

    assert response.status_code == 200, response.text
    body = response.json()
    run = body["runs"][0]
    assert body["execution_allowed"] is False
    assert body["manual_promotion_required"] is True
    assert run["paused_at_stage"] == "curate"
    assert run["execution_allowed"] is False
    assert run["manual_promotion_required"] is True
    assert run["sandbox_policy"]["production_writes_allowed"] is False
    assert run["sandbox_policy"]["deploy_merge_push_allowed"] is False
    assert all(checkpoint["executed"] is False for checkpoint in run["checkpoints"])
    assert all(checkpoint["external_calls"] == 0 for checkpoint in run["checkpoints"])


def test_scheduler_endpoint_reports_readiness_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(autonomous_lab, "build_lab_scheduler_status", _pro_scheduler_status)
    client = _build_client(monkeypatch, tmp_path)

    response = client.get("/api/autonomous-lab/scheduler")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == "autonomous-lab-v1-h24-scheduler"
    assert body["db_available"] is False
    assert body["state"] == "db_unavailable"
    assert body["can_tick"] is False
    assert body["autonomous_execution_allowed"] is False
    assert "db_required" in body["safeguards"]


def test_scheduler_tick_requires_runtime_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(autonomous_lab, "build_lab_scheduler_status", _pro_scheduler_status)
    client = _build_client(monkeypatch, tmp_path)

    response = client.post("/api/autonomous-lab/scheduler/tick", json={})

    assert response.status_code == 503, response.text
    body = response.json()
    assert body["detail"]["scheduler"]["state"] == "db_unavailable"
    assert body["detail"]["scheduler"]["can_tick"] is False


def test_scheduler_tick_runs_one_bounded_worker_tick(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(autonomous_lab, "build_lab_scheduler_status", _pro_scheduler_status)
    monkeypatch.setattr(autonomous_lab, "AutonomousLabWorker", RouterIdleWorker)
    conn = RouterFakeConnection()
    client = _build_client(monkeypatch, tmp_path, db_pool=RouterFakePool(conn))

    response = client.post(
        "/api/autonomous-lab/scheduler/tick",
        json={"worker_id": "lab-worker:test"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scheduler"]["state"] == "ready"
    assert body["scheduler"]["can_tick"] is True
    assert body["tick"]["worker_id"] == "lab-worker:test"
    assert body["tick"]["status"] == "skipped"
    assert body["tick"]["run_id"] is None


def test_run_detail_endpoint_requires_runtime_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)

    response = client.get("/api/autonomous-lab/runs/lab-runtime-test")

    assert response.status_code == 503
    assert "runtime database is unavailable" in response.text


def test_run_detail_endpoint_returns_receipt_safe_persisted_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    conn = RouterFakeConnection(fetchrow_results=[_run_row()])
    client = _build_client(monkeypatch, tmp_path, db_pool=RouterFakePool(conn))

    response = client.get("/api/autonomous-lab/runs/lab-runtime-test")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run"]["run_id"] == "lab-runtime-test"
    assert body["run"]["status"] == "paused"
    assert body["run"]["objective_reference"].startswith("evidence_fingerprint:sha256:")
    assert "RAW_PRIVATE_OBJECTIVE_SHOULD_NOT_APPEAR" not in json.dumps(body, sort_keys=True)
    assert "FROM autonomous_lab_runs" in conn.fetchrow_calls[0][0]


def test_run_events_endpoint_returns_receipt_safe_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    conn = RouterFakeConnection(
        fetch_results=[
            [
                {
                    "event_id": 42,
                    "run_id": "lab-runtime-test",
                    "event_type": "run_paused",
                    "payload": {"run_id": "lab-runtime-test", "stage": "curate"},
                    "status": "pending",
                    "attempts": 0,
                }
            ]
        ]
    )
    client = _build_client(monkeypatch, tmp_path, db_pool=RouterFakePool(conn))

    response = client.get("/api/autonomous-lab/runs/lab-runtime-test/events?limit=999")

    assert response.status_code == 422

    response = client.get("/api/autonomous-lab/runs/lab-runtime-test/events?limit=500")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["events"][0]["event_type"] == "run_paused"
    assert body["events"][0]["payload"]["stage"] == "curate"
    assert conn.fetch_calls[0][1] == ("lab-runtime-test", 500)


def test_curator_decision_endpoint_records_idempotent_safe_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    conn = RouterFakeConnection(
        fetchrow_results=[
            {
                "run_id": "lab-runtime-test",
                "status": "pending",
                "updated_count": 1,
                "existing_count": 0,
                "event_id": 77,
            }
        ]
    )
    client = _build_client(monkeypatch, tmp_path, db_pool=RouterFakePool(conn))

    response = client.post(
        "/api/autonomous-lab/runs/lab-runtime-test/decision",
        json={
            "decision": "approve",
            "note": "token=abcdef1234567890 RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["decision"]["changed"] is True
    assert body["decision"]["status"] == "pending"
    assert body["promotion_allowed"] is False
    sql, args = conn.fetchrow_calls[0]
    assert "status = 'paused'" in sql
    assert "'curator_decision_recorded'" in sql
    assert "abcdef1234567890" not in str(args)
    assert "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR" not in str(args)
    assert "evidence_fingerprint:sha256:" in str(args)


def test_curator_decision_endpoint_conflicts_when_run_is_not_paused(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    conn = RouterFakeConnection(fetchrow_results=[None])
    client = _build_client(monkeypatch, tmp_path, db_pool=RouterFakePool(conn))

    response = client.post(
        "/api/autonomous-lab/runs/lab-runtime-test/decision",
        json={"decision": "request_changes"},
    )

    assert response.status_code == 409
    assert "paused lab run" in response.text


def test_cancel_endpoint_is_explicit_and_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    conn = RouterFakeConnection(
        fetchrow_results=[
            {
                "run_id": "lab-runtime-test",
                "status": "cancelled",
                "updated_count": 1,
                "existing_count": 0,
                "event_id": 88,
            }
        ]
    )
    client = _build_client(monkeypatch, tmp_path, db_pool=RouterFakePool(conn))

    response = client.post(
        "/api/autonomous-lab/runs/lab-runtime-test/cancel",
        json={"reason": "+62 812 3456 7890 RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cancel"]["changed"] is True
    assert body["cancel"]["status"] == "cancelled"
    assert body["promotion_allowed"] is False
    sql, args = conn.fetchrow_calls[0]
    assert "status IN ('pending', 'paused')" in sql
    assert "'run_cancelled'" in sql
    assert "+62 812 3456 7890" not in str(args)
    assert "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR" not in str(args)


def test_sandbox_policy_endpoint_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)

    response = client.get("/api/autonomous-lab/sandbox-policy")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == "autonomous-lab-v1-sandbox-policy"
    assert body["require_policy_before_execution"] is True
    assert body["network"]["mode"] == "deny_all"
    assert body["network"]["allow_localhost"] is False
    assert body["filesystem"]["repo_read_only"] is True
    assert body["production_writes_allowed"] is False
    assert body["deploy_merge_push_allowed"] is False
    assert body["raw_data_persistence_allowed"] is False


def test_shadow_run_endpoint_returns_end_to_end_receipt_without_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)

    response = client.get("/api/autonomous-lab/shadow-run")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == "autonomous-lab-v1-shadow-run"
    assert body["watch_tick"]["signal_count"] == 3
    assert body["watch_tick"]["external_calls"] == 0
    assert body["evaluation_report"]["verdict"] == "needs_review"
    assert body["curator_decision"]["promotion_allowed"] is False
    assert body["execution_allowed"] is False
    assert body["external_calls"] == 0
    assert [event["stage"] for event in body["timeline"]] == [
        "watch",
        "normalize",
        "compose",
        "experiment",
        "verify",
        "curate",
    ]


def test_draft_endpoint_can_persist_orchestration_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path, persistence_enabled=True)
    payload = _payload()
    payload["persist_receipt"] = True
    payload["target_paths"].append("scripts/autonomous_lab_run.py")

    response = client.post("/api/autonomous-lab/drafts", json=payload)

    assert response.status_code == 202, response.text
    body = response.json()
    receipt_path = Path(body["receipt_path"])
    event_path = Path(body["event_path"])

    assert receipt_path.exists()
    assert event_path.exists()
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["run"]["run_id"] == (
        "router-lab-test"
    )
    assert json.loads(event_path.read_text(encoding="utf-8"))["run_id"] == "router-lab-test"


def test_draft_endpoint_can_persist_lab_ui_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path, persistence_enabled=True)
    payload = _payload()
    payload["persist_receipt"] = True
    payload["target_paths"] = [
        "apps/admin-dashboard/app/autonomous-lab/page.tsx",
        "apps/admin-dashboard/lib/autonomous-lab.ts",
    ]

    response = client.post("/api/autonomous-lab/drafts", json=payload)

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["blocked"] is False
    receipt = json.loads(Path(body["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["run"]["simulation_plan"]["target_paths"] == payload["target_paths"]


def test_draft_endpoint_refuses_persistence_when_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)
    payload = _payload()
    payload["persist_receipt"] = True

    response = client.post("/api/autonomous-lab/drafts", json=payload)

    assert response.status_code == 403
    assert "persistence is disabled" in response.text


def test_draft_endpoint_hides_when_feature_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path, enabled=False)

    response = client.post("/api/autonomous-lab/drafts", json=_payload())

    assert response.status_code == 404

    status_response = client.get("/api/autonomous-lab/status")
    assert status_response.status_code == 404


def test_draft_endpoint_requires_internal_api_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "autonomous_lab_enabled", True)
    monkeypatch.setattr(settings, "autonomous_lab_receipt_dir", str(tmp_path / "receipts"))

    app = FastAPI()
    app.include_router(autonomous_lab.router)
    client = TestClient(app)

    response = client.post("/api/autonomous-lab/drafts", json=_payload())

    assert response.status_code == 401


def test_draft_endpoint_rejects_unsafe_target_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)
    payload = _payload()
    payload["target_paths"] = ["../outside.py"]

    response = client.post("/api/autonomous-lab/drafts", json=payload)

    assert response.status_code == 422
    assert "path traversal" in response.text


def test_draft_endpoint_rejects_control_character_target_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)
    payload = _payload()
    payload["target_paths"] = [
        "apps/backend-rag/backend/services/autonomous_lab/planner.py\nBAD"
    ]

    response = client.post("/api/autonomous-lab/drafts", json=payload)

    assert response.status_code == 422
    assert "control characters" in response.text


def test_draft_endpoint_accepts_lab_ui_target_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)
    payload = _payload()
    payload["target_paths"] = [
        "apps/admin-dashboard/app/autonomous-lab/page.tsx",
        "apps/admin-dashboard/lib/autonomous-lab.ts",
    ]

    response = client.post("/api/autonomous-lab/drafts", json=payload)

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["blocked"] is False
    assert (
        "cd apps/admin-dashboard && npm run lint"
        in body["receipt"]["run"]["simulation_plan"]["verification_commands"]
    )


def test_draft_endpoint_rejects_non_lab_admin_dashboard_target_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)
    payload = _payload()
    payload["target_paths"] = ["apps/admin-dashboard/app/legal/page.tsx"]

    response = client.post("/api/autonomous-lab/drafts", json=payload)

    assert response.status_code == 422
    assert "outside the autonomous lab write set" in response.text


def test_draft_endpoint_rejects_unsafe_task_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)
    payload = _payload()
    payload["task_id"] = "bad; fly deploy"

    response = client.post("/api/autonomous-lab/drafts", json=payload)

    assert response.status_code == 422
    assert "task_id" in response.text


def test_draft_endpoint_rejects_oversized_material_before_orchestration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)
    payload = _payload()
    payload["materials"][0]["text"] = "x" * 20_001

    response = client.post("/api/autonomous-lab/drafts", json=payload)

    assert response.status_code == 422


def test_draft_endpoint_surfaces_workspace_write_blocker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)
    payload = _payload()
    payload["materials"][0]["metadata"]["requires_google_workspace_write"] = "true"

    response = client.post("/api/autonomous-lab/drafts", json=payload)

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["blocked"] is True
    assert "google_workspace_write_block" in body["failed_blockers"]
    assert "google_workspace_write_request" in body["failed_blockers"]
