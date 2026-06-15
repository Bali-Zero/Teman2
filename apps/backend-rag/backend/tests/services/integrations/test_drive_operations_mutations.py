"""Unit tests for DriveOperationsManager delete/move/copy (Drive API v3).

These methods did not exist on DriveOperationsManager before — the service exposed
delete_file/move_file/copy_file but delegated to operations methods that were absent,
so every Drive delete/move/copy raised AttributeError at runtime (the original
endpoint 500 was a missing-user_email TypeError that masked this deeper hole).

The tests mock the httpx AsyncClient and assert the correct verb + URL + payload hit
the Drive API, without any network call. Pattern mirrors the read methods already in
drive_operations.py (Bearer token via auth_manager, httpx async).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.integrations.drive.drive_operations import DriveOperationsManager

pytestmark = pytest.mark.asyncio

FILE_ID = "1AbCdEfGhIjK"
USER = "zero@balizero.com"


def _resp(json_body: dict[str, Any] | None = None, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=json_body or {})
    return r


def _manager() -> tuple[DriveOperationsManager, MagicMock]:
    auth = MagicMock()
    auth.get_access_token = AsyncMock(return_value="tok-123")
    http = MagicMock()
    http.get = AsyncMock(return_value=_resp({"parents": ["OLD_PARENT"]}))
    http.delete = AsyncMock(return_value=_resp({}, status=204))
    http.patch = AsyncMock(return_value=_resp({"id": FILE_ID, "trashed": True}))
    http.post = AsyncMock(return_value=_resp({"id": "COPY_ID", "name": "copy"}))
    # audit is required by the @drive_operation decorator (real code injects a
    # DriveAuditLogger); a MagicMock satisfies log_operation/log_error.
    audit = MagicMock()
    mgr = DriveOperationsManager(auth_manager=auth, http_client=http, audit=audit)
    return mgr, http


async def test_delete_file_trash_is_patch_trashed_true():
    mgr, http = _manager()
    out = await mgr.delete_file(USER, FILE_ID, permanent=False)
    # trash = PATCH {trashed: true}, NOT a hard DELETE
    http.patch.assert_awaited_once()
    args, kwargs = http.patch.call_args
    assert FILE_ID in args[0]
    assert kwargs["json"] == {"trashed": True}
    http.delete.assert_not_awaited()
    assert out["trashed"] is True and out["permanent"] is False


async def test_delete_file_permanent_is_http_delete():
    mgr, http = _manager()
    out = await mgr.delete_file(USER, FILE_ID, permanent=True)
    http.delete.assert_awaited_once()
    assert FILE_ID in http.delete.call_args.args[0]
    http.patch.assert_not_awaited()
    assert out["deleted"] is True and out["permanent"] is True


async def test_move_file_reparent_with_explicit_old_parent():
    mgr, http = _manager()
    await mgr.move_file(USER, FILE_ID, new_parent_id="NEW", old_parent_id="OLD")
    http.patch.assert_awaited_once()
    params = http.patch.call_args.kwargs["params"]
    assert params["addParents"] == "NEW"
    assert params["removeParents"] == "OLD"
    # explicit old_parent → no metadata lookup needed
    http.get.assert_not_awaited()


async def test_move_file_looks_up_current_parent_when_old_omitted():
    mgr, http = _manager()  # http.get returns parents=["OLD_PARENT"]
    await mgr.move_file(USER, FILE_ID, new_parent_id="NEW")
    # must GET the file's current parents first, then PATCH removing OLD_PARENT
    http.get.assert_awaited_once()
    params = http.patch.call_args.kwargs["params"]
    assert params["addParents"] == "NEW"
    assert params["removeParents"] == "OLD_PARENT"


async def test_copy_file_is_post_copy_with_name_and_parent():
    mgr, http = _manager()
    out = await mgr.copy_file(USER, FILE_ID, new_name="My Copy", parent_folder_id="DEST")
    http.post.assert_awaited_once()
    url = http.post.call_args.args[0]
    assert url.endswith(f"/files/{FILE_ID}/copy")
    body = http.post.call_args.kwargs["json"]
    assert body["name"] == "My Copy"
    assert body["parents"] == ["DEST"]
    assert out["id"] == "COPY_ID"


async def test_copy_file_bare_has_empty_body():
    mgr, http = _manager()
    await mgr.copy_file(USER, FILE_ID)
    body = http.post.call_args.kwargs["json"]
    assert body == {}  # no rename, no parent → Drive copies in place with same name


async def test_no_token_raises_permission_error():
    mgr, http = _manager()
    mgr.auth_manager.get_access_token = AsyncMock(return_value=None)
    with pytest.raises(PermissionError):
        await mgr.delete_file(USER, FILE_ID)
