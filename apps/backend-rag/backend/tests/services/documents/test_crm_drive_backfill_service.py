"""Tests for CRM Drive backfill over existing documents."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class _AcquireContext:
    def __init__(self, conn: _FakeConn) -> None:
        self.conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self.conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakePool:
    def __init__(self, rows: list[dict]) -> None:
        self.conn = _FakeConn(rows)

    def acquire(self) -> _AcquireContext:
        return _AcquireContext(self.conn)


class _FakeConn:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.fetch_calls: list[tuple[str, tuple]] = []

    async def fetch(self, query: str, *args):
        self.fetch_calls.append((query, args))
        return self.rows


@pytest.mark.asyncio
async def test_backfill_links_completed_existing_document_without_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.services.documents.crm_drive_backfill_service import run_crm_drive_backfill

    monkeypatch.delenv("CRM_KG_ENABLED", raising=False)
    pool = _FakePool(
        [
            {
                "document_id": 10,
                "client_id": 42,
                "file_id": "drive-completed",
                "file_name": "passport.pdf",
                "document_type": "passport",
                "document_category": "immigration",
                "practice_id": None,
                "google_drive_file_url": "https://drive/file",
                "file_url": None,
                "ocr_status": "completed",
                "ocr_extracted_data": {"passport_number": "AB123", "full_name": "Anna"},
                "has_kg_node": False,
            },
        ],
    )

    with patch(
        "backend.services.knowledge_graph.document_linker.kg_link_document",
        new_callable=AsyncMock,
        return_value={"ok": True, "nodes": 3, "edges": 2},
    ) as mock_kg, patch(
        "backend.services.documents.ocr_dispatcher_service.dispatch_ocr_by_folder",
        new_callable=AsyncMock,
    ) as mock_dispatch:
        result = await run_crm_drive_backfill(pool, limit=5, dry_run=False)

    assert result["processed"] == 1
    assert result["kg_linked"] == 1
    assert result["ocr_dispatched"] == 0
    mock_dispatch.assert_not_called()
    mock_kg.assert_called_once()
    assert mock_kg.call_args.kwargs["file_id"] == "drive-completed"
    assert mock_kg.call_args.kwargs["client_id"] == 42
    assert mock_kg.call_args.kwargs["extracted_fields"]["passport_number"] == "AB123"


@pytest.mark.asyncio
async def test_backfill_links_completed_json_string_without_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.services.documents.crm_drive_backfill_service import run_crm_drive_backfill

    monkeypatch.delenv("CRM_KG_ENABLED", raising=False)
    pool = _FakePool(
        [
            {
                "document_id": 13,
                "client_id": 43,
                "file_id": "drive-json-completed",
                "file_name": "visa.pdf",
                "document_type": "visa",
                "document_category": "immigration",
                "practice_id": None,
                "google_drive_file_url": "https://drive/file",
                "file_url": None,
                "ocr_status": "completed",
                "ocr_extracted_data": '{"visa_type":"C1","full_name":"Anna"}',
                "has_kg_node": False,
            },
        ],
    )

    with patch(
        "backend.services.knowledge_graph.document_linker.kg_link_document",
        new_callable=AsyncMock,
        return_value={"ok": True, "nodes": 2, "edges": 1},
    ) as mock_kg, patch(
        "backend.services.documents.ocr_dispatcher_service.dispatch_ocr_by_folder",
        new_callable=AsyncMock,
    ) as mock_dispatch:
        result = await run_crm_drive_backfill(pool, limit=5, dry_run=False)

    assert result["processed"] == 1
    assert result["kg_linked"] == 1
    assert result["ocr_dispatched"] == 0
    mock_dispatch.assert_not_called()
    assert mock_kg.call_args.kwargs["extracted_fields"]["visa_type"] == "C1"


@pytest.mark.asyncio
async def test_backfill_dispatches_pending_existing_document_to_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.services.documents.crm_drive_backfill_service import run_crm_drive_backfill

    monkeypatch.delenv("CRM_KG_ENABLED", raising=False)
    pool = _FakePool(
        [
            {
                "document_id": 11,
                "client_id": 42,
                "file_id": "drive-pending",
                "file_name": "scan_001.pdf",
                "document_type": "unknown",
                "document_category": "tax",
                "practice_id": 7,
                "google_drive_file_url": None,
                "file_url": None,
                "ocr_status": "pending",
                "ocr_extracted_data": None,
                "has_kg_node": False,
            },
        ],
    )

    with patch(
        "backend.services.documents.ocr_dispatcher_service.dispatch_ocr_by_folder",
        new_callable=AsyncMock,
        return_value={
            "dispatched": True,
            "handler": "npwp",
            "result": {"success": True, "extracted": {"npwp": "01.234"}},
        },
    ) as mock_dispatch, patch(
        "backend.services.knowledge_graph.document_linker.kg_link_document",
        new_callable=AsyncMock,
        return_value={"ok": True, "nodes": 3, "edges": 2},
    ) as mock_kg:
        result = await run_crm_drive_backfill(pool, limit=5, dry_run=False)

    assert result["processed"] == 1
    assert result["ocr_dispatched"] == 1
    assert result["kg_linked"] == 1
    mock_dispatch.assert_called_once()
    assert mock_dispatch.call_args.kwargs["folder_name"] == "03_Tax"
    mock_kg.assert_called_once()
    assert mock_kg.call_args.kwargs["document_type"] == "npwp"


@pytest.mark.asyncio
async def test_backfill_does_not_double_link_when_dispatcher_kg_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.services.documents.crm_drive_backfill_service import run_crm_drive_backfill

    monkeypatch.setenv("CRM_KG_ENABLED", "true")
    pool = _FakePool(
        [
            {
                "document_id": 14,
                "client_id": 44,
                "file_id": "drive-pending",
                "file_name": "npwp.pdf",
                "document_type": "unknown",
                "document_category": "tax",
                "practice_id": 7,
                "google_drive_file_url": None,
                "file_url": None,
                "ocr_status": "pending",
                "ocr_extracted_data": None,
                "has_kg_node": False,
            },
        ],
    )

    with patch(
        "backend.services.documents.ocr_dispatcher_service.dispatch_ocr_by_folder",
        new_callable=AsyncMock,
        return_value={
            "dispatched": True,
            "handler": "npwp",
            "result": {"success": True, "extracted": {"npwp": "01.234"}},
        },
    ) as mock_dispatch, patch(
        "backend.services.knowledge_graph.document_linker.kg_link_document",
        new_callable=AsyncMock,
    ) as mock_kg:
        result = await run_crm_drive_backfill(pool, limit=5, dry_run=False)

    assert result["processed"] == 1
    assert result["ocr_dispatched"] == 1
    assert result["kg_linked"] == 0
    mock_dispatch.assert_called_once()
    mock_kg.assert_not_called()


@pytest.mark.asyncio
async def test_backfill_dry_run_only_counts_candidates() -> None:
    from backend.services.documents.crm_drive_backfill_service import run_crm_drive_backfill

    pool = _FakePool(
        [
            {
                "document_id": 12,
                "client_id": 42,
                "file_id": "drive-any",
                "file_name": "passport.pdf",
                "document_type": "passport",
                "document_category": "immigration",
                "practice_id": None,
                "google_drive_file_url": None,
                "file_url": None,
                "ocr_status": None,
                "ocr_extracted_data": None,
                "has_kg_node": False,
            },
        ],
    )

    with patch(
        "backend.services.documents.ocr_dispatcher_service.dispatch_ocr_by_folder",
        new_callable=AsyncMock,
    ) as mock_dispatch, patch(
        "backend.services.knowledge_graph.document_linker.kg_link_document",
        new_callable=AsyncMock,
    ) as mock_kg:
        result = await run_crm_drive_backfill(pool, limit=5, dry_run=True)

    assert result["candidate_count"] == 1
    assert result["processed"] == 0
    assert result["dry_run"] is True
    mock_dispatch.assert_not_called()
    mock_kg.assert_not_called()
