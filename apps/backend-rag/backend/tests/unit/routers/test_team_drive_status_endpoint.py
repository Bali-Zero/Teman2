"""Regression test for the live 500 on GET /api/drive/status.

Root cause (verified on disk, 2026-07-08):
`backend.app.routers.team_drive.drive_status` called `drive.get_connection_info()`,
but `TeamDriveService` (backend/services/integrations/team_drive_service.py) has no
such method — it never did. Every request to GET /api/drive/status raised:

    'TeamDriveService' object has no attribute 'get_connection_info'

This test drives the real router handler function directly (no live DB/network)
with a fake drive object that mimics the REAL `TeamDriveService` public surface
(`is_configured`, `service_account_available`, `list_files` — no
`get_connection_info`) so a regression that reintroduces the phantom call fails
loudly, exactly like prod did.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.routers.team_drive import drive_status


class RealSurfaceDrive:
    """Stand-in for TeamDriveService with the REAL attribute surface.

    Deliberately has NO `get_connection_info` — matches the real class on
    disk. Any call to a nonexistent attribute raises AttributeError, exactly
    like the real TeamDriveService instance did in prod.
    """

    def __init__(self, *, sa_available: bool = True, files: list[dict[str, Any]] | None = None) -> None:
        self.service_account_available = sa_available
        self._files = files if files is not None else [{"id": "f1", "name": "report.pdf"}]
        self.list_files_calls: list[dict[str, Any]] = []

    def is_configured(self) -> bool:
        return True

    async def list_files(
        self,
        folder_id: str | None = None,
        page_size: int = 50,
    ) -> dict[str, Any]:
        self.list_files_calls.append({"folder_id": folder_id, "page_size": page_size})
        return {"files": self._files}


@pytest.mark.asyncio
async def test_drive_status_endpoint_does_not_call_phantom_get_connection_info() -> None:
    """Guilt: RealSurfaceDrive has no get_connection_info, so the OLD handler
    body (`drive.get_connection_info()`) would raise AttributeError,
    reproducing the live prod 500. The FIXED handler must return a full
    status dict without ever touching that attribute.
    """
    drive = RealSurfaceDrive(sa_available=True)
    current_user = {"email": "team@balizero.com", "role": "admin"}

    result = await drive_status(current_user=current_user, drive=drive)

    assert result["status"] == "connected"
    assert result["mode"] == "service_account"
    assert result["connected_as"] == "service_account"
    assert result["is_oauth"] is False
    assert result["files_accessible"] is True
    assert "root_folder_id" in result
    assert "quota_info" in result
    # Innocence-of-the-detector for the frontend contract (drive.api.ts reads
    # status/connected_as/files_accessible only, but keep the full shape).
    assert set(result.keys()) >= {
        "status",
        "mode",
        "connected_as",
        "is_oauth",
        "files_accessible",
        "root_folder_id",
        "quota_info",
    }


@pytest.mark.asyncio
async def test_drive_status_endpoint_reproduces_bug_with_phantom_attribute() -> None:
    """Innocence-of-the-detector: prove RealSurfaceDrive actually raises
    AttributeError when something calls the phantom method, so test #1
    passing is meaningful evidence of the fix and not a tautology.
    """
    drive = RealSurfaceDrive()

    with pytest.raises(AttributeError, match="get_connection_info"):
        drive.get_connection_info()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_drive_status_falls_back_when_not_service_account_configured() -> None:
    """mode reflects service_account_available=False without crashing."""
    drive = RealSurfaceDrive(sa_available=False)
    current_user = {"email": "team@balizero.com", "role": "admin"}

    result = await drive_status(current_user=current_user, drive=drive)

    assert result["mode"] == "not_configured"
    assert result["status"] == "connected"  # SA-configured guard happens upstream in get_drive()


@pytest.mark.asyncio
async def test_drive_status_reports_files_inaccessible_when_list_files_fails() -> None:
    """Both list_files attempts failing still returns a 200 status body,
    not a 500 (existing behavior, unrelated to this bug, must survive)."""

    class FailingDrive(RealSurfaceDrive):
        async def list_files(self, folder_id: str | None = None, page_size: int = 50) -> dict[str, Any]:
            raise RuntimeError("no access")

    drive = FailingDrive()
    current_user = {"email": "team@balizero.com", "role": "admin"}

    result = await drive_status(current_user=current_user, drive=drive)

    assert result["status"] == "connected"
    assert result["files_accessible"] is False
