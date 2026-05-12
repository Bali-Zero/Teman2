"""Tests for CRM Workspace AI snapshot persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from backend.services.crm.tax_company_pilot import TaxCompanyPilotWorkspaceAiFact
from backend.services.crm.workspace_ai_snapshots import (
    WorkspaceAiSnapshotCreate,
    create_workspace_ai_snapshot,
)


class _FakeAcquire:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *_exc_info: object) -> None:
        return None


class _FakePool:
    def __init__(self) -> None:
        self.conn = _FakeConn()

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self.conn)


class _FakeConn:
    def __init__(self) -> None:
        self.args: tuple[Any, ...] | None = None

    async def fetchrow(self, _query: str, *args: Any) -> dict[str, Any]:
        self.args = args
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
