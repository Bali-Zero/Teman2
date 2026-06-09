from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.routers import autonomous_lab
from backend.app.utils.internal_api_auth import verify_internal_api_key


def _build_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    enabled: bool = True,
) -> TestClient:
    monkeypatch.setattr(settings, "autonomous_lab_enabled", enabled)
    monkeypatch.setattr(settings, "autonomous_lab_receipt_dir", str(tmp_path / "receipts"))

    app = FastAPI()
    app.include_router(autonomous_lab.router)

    async def _ok() -> dict[str, str]:
        return {"service": "autonomous-lab-test"}

    app.dependency_overrides[verify_internal_api_key] = _ok
    return TestClient(app)


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
        "intake_normalizer",
        "hypothesis_composer",
        "context_builder",
        "reviewer",
        "verification_planner",
    ]
    assert body["receipt"]["execution_policy"]["shell_commands_executed"] == []
    assert body["receipt"]["final_review"]["approved"] is True


def test_draft_endpoint_can_persist_orchestration_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path)
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


def test_draft_endpoint_hides_when_feature_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _build_client(monkeypatch, tmp_path, enabled=False)

    response = client.post("/api/autonomous-lab/drafts", json=_payload())

    assert response.status_code == 404


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
