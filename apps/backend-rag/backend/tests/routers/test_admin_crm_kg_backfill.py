"""Tests for admin CRM KG Drive backfill trigger."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import BackgroundTasks


def _request_with_pool(pool: object) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db_pool=pool)))


@pytest.mark.asyncio
async def test_backfill_drive_documents_dry_run_returns_summary() -> None:
    from backend.app.routers.admin_crm_kg import trigger_backfill_drive_documents

    with patch(
        "backend.services.documents.crm_drive_backfill_service.run_crm_drive_backfill",
        new_callable=AsyncMock,
        return_value={"dry_run": True, "candidate_count": 3},
    ) as mock_backfill:
        result = await trigger_backfill_drive_documents(
            request=_request_with_pool(object()),
            background_tasks=BackgroundTasks(),
            limit=10,
            dry_run=True,
            client_id=42,
            allow_ocr=False,
        )

    assert result == {"dry_run": True, "candidate_count": 3}
    mock_backfill.assert_called_once()
    assert mock_backfill.call_args.kwargs["limit"] == 10
    assert mock_backfill.call_args.kwargs["dry_run"] is True
    assert mock_backfill.call_args.kwargs["client_id"] == 42
    assert mock_backfill.call_args.kwargs["allow_ocr"] is False


@pytest.mark.asyncio
async def test_backfill_drive_documents_live_runs_in_background() -> None:
    from backend.app.routers.admin_crm_kg import trigger_backfill_drive_documents

    background_tasks = BackgroundTasks()
    with patch(
        "backend.services.documents.crm_drive_backfill_service.run_crm_drive_backfill",
        new_callable=AsyncMock,
    ) as mock_backfill:
        result = await trigger_backfill_drive_documents(
            request=_request_with_pool(object()),
            background_tasks=background_tasks,
            limit=5,
            dry_run=False,
            client_id=None,
            allow_ocr=False,
        )

    assert result["status"] == "started"
    assert result["dry_run"] is False
    assert result["allow_ocr"] is False
    assert len(background_tasks.tasks) == 1
    mock_backfill.assert_not_called()


@pytest.mark.asyncio
async def test_backfill_drive_documents_live_requires_explicit_ocr_flag() -> None:
    from backend.app.routers.admin_crm_kg import trigger_backfill_drive_documents

    background_tasks = BackgroundTasks()
    with patch(
        "backend.services.documents.crm_drive_backfill_service.run_crm_drive_backfill",
        new_callable=AsyncMock,
    ) as mock_backfill:
        result = await trigger_backfill_drive_documents(
            request=_request_with_pool(object()),
            background_tasks=background_tasks,
            limit=5,
            dry_run=False,
            client_id=None,
            allow_ocr=True,
        )

    assert result["status"] == "started"
    assert result["allow_ocr"] is True

    task = background_tasks.tasks[0]
    await task.func(*task.args, **task.kwargs)
    assert mock_backfill.call_args.kwargs["allow_ocr"] is True
