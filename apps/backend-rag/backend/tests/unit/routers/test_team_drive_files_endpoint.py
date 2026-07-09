"""Regression test for the live 500 on GET /api/drive/files.

Root cause (verified on disk, 2026-07-08):
`backend.app.routers.team_drive.list_files` called
`drive.list_files(folder_id=..., page_size=..., page_token=..., query=q)` but
`TeamDriveService.list_files` (backend/services/integrations/team_drive_service.py)
only accepts `q`, not `query`, and requires `user_email` (no default). Any request
to GET /api/drive/files raised:

    TeamDriveService.list_files() got an unexpected keyword argument 'query'

This test drives the real router handler function directly (no live DB/network)
with a fake `TeamDriveService.list_files` that mimics the REAL signature
(`user_email`, `folder_id`, `q`, `page_size`, `page_token` — no `query` kwarg) and
raises `TypeError` on any unexpected kwarg, exactly like the real method would.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.app.routers.team_drive import list_files


class RealSignatureDrive:
    """Stand-in for TeamDriveService.list_files with the REAL parameter names.

    Raises TypeError on any kwarg that isn't one of the real ones, so a
    regression (e.g. passing `query=` again) fails loudly just like prod.
    """

    def __init__(self) -> None:
        self.received_kwargs: dict[str, Any] | None = None

    async def list_files(
        self,
        user_email: str,
        folder_id: str | None = None,
        q: str | None = None,
        page_size: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        self.received_kwargs = {
            "user_email": user_email,
            "folder_id": folder_id,
            "q": q,
            "page_size": page_size,
            "page_token": page_token,
        }
        return {"files": [], "next_page_token": None}


@pytest.mark.asyncio
async def test_list_files_endpoint_calls_drive_with_q_not_query() -> None:
    """Guilt: the OLD call site (`query=q`) would blow up RealSignatureDrive
    with TypeError, reproducing the live prod 500. The FIXED call site must
    reach RealSignatureDrive.list_files successfully.
    """
    drive = RealSignatureDrive()
    current_user = {"email": "team@balizero.com", "role": "admin"}

    result = await list_files(
        current_user=current_user,
        drive=drive,
        pool=AsyncMock(),
        folder_id=None,
        page_size=50,
        page_token=None,
        q="report",
    )

    assert result.files == []
    assert drive.received_kwargs is not None
    assert drive.received_kwargs["q"] == "report"
    assert drive.received_kwargs["user_email"] == "team@balizero.com"
    # Innocence: no leftover 'query' kwarg anywhere in what was captured.
    assert "query" not in drive.received_kwargs


@pytest.mark.asyncio
async def test_list_files_endpoint_reproduces_bug_with_old_call_shape() -> None:
    """Innocence-of-the-detector: prove RealSignatureDrive actually raises
    TypeError on the OLD (buggy) call shape, so test #1 passing is meaningful
    evidence of the fix and not a tautology.
    """
    drive = RealSignatureDrive()

    with pytest.raises(TypeError, match="query"):
        await drive.list_files(  # type: ignore[call-arg]
            user_email="team@balizero.com",
            folder_id=None,
            page_size=50,
            page_token=None,
            query="report",  # the bug: real method has no 'query' param
        )
