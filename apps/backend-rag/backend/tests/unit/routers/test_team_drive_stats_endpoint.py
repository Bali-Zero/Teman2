"""Regression test for GET /api/drive/stats — the route the `get_drive_storage_stats`
MCP tool has called since inception (`apps/nuzantara-mcp/nuzantara_mcp/tools/drive.py`),
which never existed on the backend (lever #5 residual, 2026-07-19 KB audit). Every
call 404'd; `error_monitoring.py` suppresses all `/api/drive/` 404s as "Deleted Drive
folders", so it fired silently with zero alerting.

Pattern mirrors test_team_drive_status_endpoint.py: drive the real router handler
directly with a fake drive object matching TeamDriveService's real public surface,
so a regression that removes/breaks the delegation fails loudly.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.routers.team_drive import drive_stats


class RealSurfaceDrive:
    """Stand-in for TeamDriveService — has get_storage_stats, mirroring the real
    facade delegation added alongside this fix."""

    def __init__(self, stats: dict[str, Any]) -> None:
        self._stats = stats
        self.calls: list[dict[str, Any]] = []

    async def get_storage_stats(self, user_email: str) -> dict[str, Any]:
        self.calls.append({"user_email": user_email})
        return self._stats


STATS_PAYLOAD = {
    "storage_used_bytes": 1048576000,
    "storage_limit_bytes": 32985348833280,
    "files_count": 42,
    "folders_count": 7,
    "storage_by_type": {"application/pdf": 900000, "image/jpeg": 148576000},
    "largest_files": [{"id": "f1", "name": "big.pdf", "size": 900000}],
    "scanned_pages": 3,
    "truncated": False,
}


@pytest.mark.asyncio
async def test_drive_stats_endpoint_returns_full_contract():
    """Guilt: the route must exist and delegate to drive.get_storage_stats,
    returning the full stats contract the MCP tool's docstring promises."""
    drive = RealSurfaceDrive(STATS_PAYLOAD)
    current_user = {"email": "team@balizero.com", "role": "admin"}

    result = await drive_stats(current_user=current_user, drive=drive)

    assert result == STATS_PAYLOAD
    assert drive.calls == [{"user_email": "system"}]


@pytest.mark.asyncio
async def test_drive_stats_endpoint_surfaces_truncation_flag_honestly():
    """Innocence-of-the-detector: a truncated result is passed through as-is,
    never silently normalized away at the router layer."""
    truncated_payload = {**STATS_PAYLOAD, "truncated": True, "scanned_pages": 20}
    drive = RealSurfaceDrive(truncated_payload)
    current_user = {"email": "team@balizero.com", "role": "admin"}

    result = await drive_stats(current_user=current_user, drive=drive)

    assert result["truncated"] is True
    assert result["scanned_pages"] == 20
