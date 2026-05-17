"""Tests for CRM Workspace AI snapshot persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from backend.services.crm.tax_company_pilot import TaxCompanyPilotWorkspaceAiFact
from backend.services.crm.workspace_ai_snapshots import (
    AUTO_APPROVE_POLICY_VERSION,
    WorkspaceAiSnapshotCreate,
    WorkspaceAiSnapshotResponse,
    approve_workspace_ai_snapshot,
    auto_approve_workspace_ai_snapshots,
    create_workspace_ai_snapshot,
    evaluate_workspace_ai_auto_approve_snapshot,
    fetch_workspace_ai_review_queue,
)


class _FakeAcquire:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *_exc_info: object) -> None:
        return None


class _FakePool:
    def __init__(self, *, review_rows: list[dict[str, Any]] | None = None) -> None:
        self.conn = _FakeConn(review_rows=review_rows)

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self.conn)


class _FakeConn:
    def __init__(self, *, review_rows: list[dict[str, Any]] | None = None) -> None:
        self.args: tuple[Any, ...] | None = None
        self.fetch_args: tuple[Any, ...] | None = None
        self.approve_args: tuple[Any, ...] | None = None
        self.approved_ids: list[str] = []
        self._review_rows = review_rows

    async def fetchrow(self, _query: str, *args: Any) -> dict[str, Any]:
        self.args = args
        if "UPDATE crm_workspace_ai_snapshots" in _query:
            self.approve_args = args
            self.approved_ids.append(str(args[0]))
            return _snapshot_row(
                snapshot_id=args[0],
                status="approved",
                approved_by=args[1],
                approved_at=datetime(2026, 5, 13, tzinfo=timezone.utc),
            )

        facts_arg = args[7]
        assert isinstance(facts_arg, str)
        return {
            "id": "draft-1",
            "company_id": args[0],
            "client_id": args[1],
            "company_name": args[2],
            "provider": args[3],
            "notebook_id": args[4],
            "note_id": args[5],
            "source_file_ids": args[6],
            "facts": facts_arg,
            "status": "draft",
            "created_by": args[8],
            "approved_by": None,
            "approved_at": None,
            "created_at": datetime(2026, 5, 12, tzinfo=timezone.utc),
        }

    async def fetch(self, _query: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_args = args
        if self._review_rows is not None:
            return self._review_rows
        return [_snapshot_row(snapshot_id="snapshot-draft", status=args[0])]


def _snapshot_row(
    *,
    snapshot_id: str,
    status: str,
    approved_by: str | None = None,
    approved_at: datetime | None = None,
    facts: list[dict[str, Any]] | None = None,
    source_file_ids: list[str] | None = None,
) -> dict[str, Any]:
    safe_source_file_ids = source_file_ids or ["drive-file-1"]
    return {
        "id": snapshot_id,
        "company_id": 7,
        "client_id": 3,
        "company_name": "OCEAN CLOTHES AND SHOES PT",
        "provider": "gemini",
        "notebook_id": None,
        "note_id": "crm-drive-autowatcher:v1:7:test",
        "source_file_ids": safe_source_file_ids,
        "facts": json.dumps(
            facts
            or [
                {
                    "category": "identity",
                    "label": "Company evidence",
                    "detail": "Company source documents are indexed for review.",
                    "source_file_ids": safe_source_file_ids,
                    "confidence": "medium",
                }
            ]
        ),
        "status": status,
        "created_by": "crm-drive-autowatcher",
        "approved_by": approved_by,
        "approved_at": approved_at,
        "created_at": datetime(2026, 5, 12, tzinfo=timezone.utc),
    }


@pytest.mark.asyncio
async def test_create_workspace_ai_snapshot_serializes_facts_for_jsonb() -> None:
    pool = _FakePool()
    payload = WorkspaceAiSnapshotCreate(
        company_id=1762,
        client_id=146,
        company_name="PT FRA Real Estate Consulting",
        provider="gemini",
        note_id="crm-drive-autowatcher:v1:1762:test",
        source_file_ids=["drive-file-1"],
        facts=[
            TaxCompanyPilotWorkspaceAiFact(
                category="identity",
                label="Company evidence",
                detail="Company source documents are indexed for review.",
                source_file_ids=["drive-file-1"],
                confidence="medium",
            )
        ],
    )

    response = await create_workspace_ai_snapshot(
        pool,  # type: ignore[arg-type]
        payload,
        created_by="test",
    )

    assert response.status == "draft"
    assert response.facts[0].category == "identity"
    assert pool.conn.args is not None
    assert json.loads(pool.conn.args[7])[0]["category"] == "identity"


@pytest.mark.asyncio
async def test_fetch_workspace_ai_review_queue_returns_draft_snapshots() -> None:
    pool = _FakePool()

    result = await fetch_workspace_ai_review_queue(
        pool,  # type: ignore[arg-type]
        status="draft",
        limit=10,
    )

    assert result[0].id == "snapshot-draft"
    assert result[0].status == "draft"
    assert result[0].facts[0].label == "Company evidence"
    assert pool.conn.fetch_args == ("draft", 10)


@pytest.mark.asyncio
async def test_approve_workspace_ai_snapshot_marks_draft_approved() -> None:
    pool = _FakePool()

    result = await approve_workspace_ai_snapshot(
        pool,  # type: ignore[arg-type]
        snapshot_id="snapshot-approve",
        approved_by="team@balizero.com",
    )

    assert result.status == "approved"
    assert result.approved_by == "team@balizero.com"
    assert result.approved_at == "2026-05-13T00:00:00+00:00"
    assert pool.conn.approve_args == ("snapshot-approve", "team@balizero.com")


def _snapshot_response(
    *,
    facts: list[TaxCompanyPilotWorkspaceAiFact],
    snapshot_id: str = "snapshot-policy",
    source_file_ids: list[str] | None = None,
) -> WorkspaceAiSnapshotResponse:
    return WorkspaceAiSnapshotResponse(
        id=snapshot_id,
        company_id=7,
        client_id=3,
        company_name="OCEAN CLOTHES AND SHOES PT",
        provider="gemini",
        note_id="crm-drive-autowatcher:v1:7:test",
        source_file_ids=["drive-file-1"] if source_file_ids is None else source_file_ids,
        facts=facts,
        status="draft",
        created_by="crm-drive-autowatcher",
        created_at="2026-05-12T00:00:00+00:00",
    )


def test_auto_approve_policy_allows_factual_structural_snapshot() -> None:
    snapshot = _snapshot_response(
        facts=[
            TaxCompanyPilotWorkspaceAiFact(
                category="identity",
                label="Company document inventory",
                detail="NPWP company document is present in indexed source evidence.",
                source_file_ids=["drive-file-1"],
                confidence="low",
            )
        ]
    )

    decision = evaluate_workspace_ai_auto_approve_snapshot(snapshot)

    assert decision.eligible is True
    assert decision.policy_version == AUTO_APPROVE_POLICY_VERSION
    assert decision.reason == "factual_structural_snapshot"
    assert decision.blocked_reasons == []


@pytest.mark.parametrize(
    ("fact", "expected_reason"),
    [
        (
            TaxCompanyPilotWorkspaceAiFact(
                category="compliance",
                label="Tax recommendation",
                detail="Client should file an amended tax return next month.",
                source_file_ids=["drive-file-1"],
                confidence="confirmed",
            ),
            "blocked_category:compliance",
        ),
        (
            TaxCompanyPilotWorkspaceAiFact(
                category="identity",
                label="Raw Drive source",
                detail="Evidence is visible at https://drive.google.com/file/d/raw-id/view.",
                source_file_ids=["drive-file-1"],
                confidence="confirmed",
            ),
            "raw_drive_reference",
        ),
        (
            TaxCompanyPilotWorkspaceAiFact(
                category="identity",
                label="Company profile",
                detail="Profile document is indexed.",
                source_file_ids=[],
                confidence="confirmed",
            ),
            "missing_explicit_evidence",
        ),
    ],
)
def test_auto_approve_policy_blocks_risky_or_weak_snapshots(
    fact: TaxCompanyPilotWorkspaceAiFact,
    expected_reason: str,
) -> None:
    snapshot = _snapshot_response(
        facts=[fact],
        source_file_ids=[] if expected_reason == "missing_explicit_evidence" else None,
    )

    decision = evaluate_workspace_ai_auto_approve_snapshot(snapshot)

    assert decision.eligible is False
    assert expected_reason in decision.blocked_reasons


@pytest.mark.asyncio
async def test_auto_approve_workspace_ai_snapshots_dry_run_does_not_update() -> None:
    pool = _FakePool(
        review_rows=[
            _snapshot_row(
                snapshot_id="safe-snapshot",
                status="draft",
                facts=[
                    {
                        "category": "identity",
                        "label": "Company document inventory",
                        "detail": "NPWP company document is present in indexed source evidence.",
                        "source_file_ids": ["drive-file-1"],
                        "confidence": "low",
                    }
                ],
            ),
            _snapshot_row(
                snapshot_id="blocked-snapshot",
                status="draft",
                facts=[
                    {
                        "category": "next_action",
                        "label": "Tax next action",
                        "detail": "Client should submit a tax correction.",
                        "source_file_ids": ["drive-file-2"],
                        "confidence": "confirmed",
                    }
                ],
                source_file_ids=["drive-file-2"],
            ),
        ]
    )

    result = await auto_approve_workspace_ai_snapshots(
        pool,  # type: ignore[arg-type]
        limit=10,
        dry_run=True,
    )

    assert result.dry_run is True
    assert result.evaluated == 2
    assert result.eligible_count == 1
    assert result.blocked_count == 1
    assert result.approved_count == 0
    assert pool.conn.approved_ids == []


@pytest.mark.asyncio
async def test_auto_approve_workspace_ai_snapshots_apply_reuses_approve_path() -> None:
    pool = _FakePool(
        review_rows=[
            _snapshot_row(
                snapshot_id="safe-snapshot",
                status="draft",
                facts=[
                    {
                        "category": "identity",
                        "label": "Company document inventory",
                        "detail": "NPWP company document is present in indexed source evidence.",
                        "source_file_ids": ["drive-file-1"],
                        "confidence": "low",
                    }
                ],
            )
        ]
    )

    result = await auto_approve_workspace_ai_snapshots(
        pool,  # type: ignore[arg-type]
        limit=10,
        dry_run=False,
    )

    expected_actor = f"system:auto-approve:{AUTO_APPROVE_POLICY_VERSION}"
    assert result.dry_run is False
    assert result.evaluated == 1
    assert result.approved_count == 1
    assert result.decisions[0].approved is True
    assert pool.conn.approved_ids == ["safe-snapshot"]
    assert pool.conn.approve_args == ("safe-snapshot", expected_actor)
