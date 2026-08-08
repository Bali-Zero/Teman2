"""Client-safe contract and tenant boundary for LKPM receipt downloads."""

from __future__ import annotations

import json
import logging
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Request

from backend.app.routers import lkpm as lkpm_router
from backend.app.routers import portal as portal_router
from backend.services.compliance import lkpm_service as service_module
from backend.services.compliance.lkpm_service import LKPMService
from backend.services.integrations import google_drive_service


class _AcquireContext:
    def __init__(self, connection: MagicMock) -> None:
        self.connection = connection

    async def __aenter__(self) -> MagicMock:
        return self.connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        return None


def _pool() -> tuple[MagicMock, MagicMock]:
    connection = MagicMock()
    connection.fetchrow = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value = _AcquireContext(connection)
    return pool, connection


def _request(path: str = "/api/v1/lkpm/receipts/me") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
        }
    )


def _client_user() -> dict[str, object]:
    return {
        "user_id": "synthetic-portal-user-101",
        "email": "portal-client@example.test",
        "role": "client",
    }


def _tax_user() -> dict[str, object]:
    return {
        "user_id": "synthetic-tax-user",
        "email": "Veronika.Tax@balizero.com",
        "role": "team",
    }


@pytest.mark.asyncio
async def test_portal_receipt_response_replaces_drive_metadata_with_proxy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_file_id = "raw-drive-file-id-0A1b2C3d4E5f6G7h8I"
    raw_drive_url = f"https://drive.google.com/file/d/{raw_file_id}/view"
    service = SimpleNamespace(
        get_receipts_for_portal_client=AsyncMock(
            return_value=[
                {
                    "id": 81,
                    "lkpm_report_id": 42,
                    "nomor_laporan": "LKPM-2026-Q1",
                    "file_drive_id": raw_file_id,
                    "file_drive_url": raw_drive_url,
                    "file_name": "receipt.pdf",
                    "source_trace": {"provider": "drive"},
                }
            ]
        )
    )
    pool = MagicMock()
    monkeypatch.setattr(
        portal_router,
        "get_current_client",
        AsyncMock(return_value={"client_id": 101}),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)

    response = await lkpm_router.get_my_receipts(request=_request(), db_pool=pool)

    assert response == {
        "success": True,
        "client_id": 101,
        "count": 1,
        "items": [
            {
                "id": 81,
                "lkpm_report_id": 42,
                "nomor_laporan": "LKPM-2026-Q1",
                "file_name": "receipt.pdf",
                "download_url": "/api/v1/lkpm/receipts/81/download",
            }
        ],
    }
    serialized = json.dumps(response)
    assert raw_file_id not in serialized
    assert raw_drive_url not in serialized
    assert "source_trace" not in serialized


def test_portal_receipt_without_backing_file_has_no_download_path() -> None:
    response = lkpm_router._client_safe_receipt(
        {
            "id": 82,
            "lkpm_report_id": 43,
            "file_drive_id": None,
            "file_drive_url": None,
        }
    )

    assert response["download_url"] is None
    assert "file_drive_id" not in response
    assert "file_drive_url" not in response


@pytest.mark.asyncio
async def test_portal_download_returns_bytes_with_private_cache_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SimpleNamespace(
        download_receipt_for_portal_client=AsyncMock(
            return_value={
                "content": b"synthetic-pdf",
                "file_name": "LKPM receipt.pdf",
                "mime_type": "application/pdf",
            }
        )
    )
    pool = MagicMock()
    monkeypatch.setattr(
        portal_router,
        "get_current_client",
        AsyncMock(return_value={"client_id": 101}),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)

    response = await lkpm_router.download_my_receipt(
        receipt_id=81,
        request=_request("/api/v1/lkpm/receipts/81/download"),
        db_pool=pool,
    )

    service.download_receipt_for_portal_client.assert_awaited_once_with(101, 81)
    assert response.body == b"synthetic-pdf"
    assert response.media_type == "application/pdf"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''LKPM%20receipt.pdf"
    )


@pytest.mark.asyncio
async def test_portal_download_cross_tenant_and_missing_are_non_enumerating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SimpleNamespace(download_receipt_for_portal_client=AsyncMock(return_value=None))
    pool = MagicMock()
    monkeypatch.setattr(
        portal_router,
        "get_current_client",
        AsyncMock(return_value={"client_id": 101}),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)

    with pytest.raises(HTTPException) as exc_info:
        await lkpm_router.download_my_receipt(
            receipt_id=999,
            request=_request("/api/v1/lkpm/receipts/999/download"),
            db_pool=pool,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Receipt not found or not downloadable"


@pytest.mark.asyncio
async def test_portal_download_redacts_internal_failure_and_identifiers(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    marker = "SYNTHETIC_RECEIPT_DOWNLOAD_INTERNAL_MARKER"
    client_id = 987654321
    receipt_id = 876543219
    service = SimpleNamespace(
        download_receipt_for_portal_client=AsyncMock(
            side_effect=RuntimeError(marker),
        )
    )
    pool = MagicMock()
    monkeypatch.setattr(
        portal_router,
        "get_current_client",
        AsyncMock(return_value={"client_id": client_id}),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(HTTPException) as exc_info:
            await lkpm_router.download_my_receipt(
                receipt_id=receipt_id,
                request=_request(f"/api/v1/lkpm/receipts/{receipt_id}/download"),
                db_pool=pool,
            )

    assert exc_info.value.status_code == 500
    detail = str(exc_info.value.detail)
    match = re.fullmatch(
        r"LKPM receipt download temporarily unavailable\. Reference: ([0-9a-f]{32})",
        detail,
    )
    assert match is not None
    assert marker not in detail
    assert str(client_id) not in detail
    assert str(receipt_id) not in detail
    assert marker not in caplog.text
    assert str(client_id) not in caplog.text
    assert str(receipt_id) not in caplog.text
    assert f"error_ref={match.group(1)}" in caplog.text
    assert "error_type=RuntimeError" in caplog.text


@pytest.mark.asyncio
async def test_service_download_query_is_tenant_bound() -> None:
    pool, connection = _pool()
    connection.fetchrow.return_value = None
    service = object.__new__(LKPMService)
    service.db_pool = pool

    result = await service.download_receipt_for_portal_client(101, 81)

    assert result is None
    sql = connection.fetchrow.await_args.args[0]
    assert "client_company_links" in sql
    assert "ccl.status = 'active'" in sql
    assert connection.fetchrow.await_args.args[1:] == (81, 101)


class _FakeDriveService:
    SYSTEM_USER_ID = "SYSTEM"

    def __init__(self, pool: MagicMock) -> None:
        self.pool = pool

    async def get_valid_token(self, user_id: str) -> str:
        assert user_id == self.SYSTEM_USER_ID
        return "synthetic-access-token"


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        payload: dict[str, str] | None = None,
        content: bytes = b"",
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content

    def json(self) -> dict[str, str]:
        return self._payload


class _FakeHTTPClient:
    calls: list[dict[str, object]] = []

    def __init__(self, *, timeout: float) -> None:
        assert timeout == 30.0

    async def __aenter__(self) -> _FakeHTTPClient:
        self.calls.clear()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> None:
        return None

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> _FakeResponse:
        self.calls.append({"url": url, "params": params, "headers": headers})
        if params == {"fields": "mimeType,name,size"}:
            return _FakeResponse(
                200,
                payload={"mimeType": "application/pdf", "name": "receipt.pdf"},
            )
        return _FakeResponse(200, content=b"synthetic-pdf")


@pytest.mark.asyncio
async def test_service_proxy_fetches_tenant_owned_drive_file_server_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_file_id = "drive-file-0A1b2C3d4E5f6G7h8I"
    pool, connection = _pool()
    connection.fetchrow.return_value = {
        "file_drive_id": raw_file_id,
        "file_drive_url": None,
        "file_name": "fallback.pdf",
    }
    service = object.__new__(LKPMService)
    service.db_pool = pool
    monkeypatch.setattr(google_drive_service, "GoogleDriveService", _FakeDriveService)
    monkeypatch.setattr(service_module.httpx, "AsyncClient", _FakeHTTPClient)

    result = await service.download_receipt_for_portal_client(101, 81)

    assert result == {
        "content": b"synthetic-pdf",
        "file_name": "receipt.pdf",
        "mime_type": "application/pdf",
    }
    assert len(_FakeHTTPClient.calls) == 2
    assert all(raw_file_id in str(call["url"]) for call in _FakeHTTPClient.calls)
    assert all(
        call["headers"] == {"Authorization": "Bearer synthetic-access-token"}
        for call in _FakeHTTPClient.calls
    )


@pytest.mark.parametrize(
    ("stored_value", "expected"),
    [
        ("https://drive.google.com/file/d/file_123/view", "file_123"),
        ("https://drive.google.com/open?id=file_456", "file_456"),
        ("https://docs.google.com/document/d/file_789/edit", "file_789"),
        ("https://example.test/file/d/not-drive/view", None),
        (None, None),
    ],
)
def test_drive_file_id_fallback_accepts_only_google_drive_boundaries(
    stored_value: str | None,
    expected: str | None,
) -> None:
    assert LKPMService._extract_drive_file_id(stored_value) == expected


@pytest.mark.parametrize(
    "operation",
    [
        "save_client_config",
        "sync_jurnal",
        "validate_draft",
        "get_ready_pack",
        "mark_submitted",
        "upload_receipt",
        "get_receipts_by_client",
        "get_receipts_for_report",
        "get_batch",
        "get_alerts",
        "get_history",
        "generate_ready_pack_pdf",
    ],
)
@pytest.mark.asyncio
async def test_portal_client_cannot_enter_workspace_lkpm_endpoints_before_lookup(
    operation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_factory = MagicMock(side_effect=AssertionError("service lookup must not run"))
    monkeypatch.setattr(lkpm_router, "_get_service", service_factory)
    user = _client_user()
    pool = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        if operation == "save_client_config":
            await lkpm_router.save_client_config(
                config=MagicMock(),
                current_user=user,
                db_pool=pool,
            )
        elif operation == "sync_jurnal":
            await lkpm_router.sync_jurnal(
                client_id=202,
                quarter="Q1",
                year=2026,
                current_user=user,
                db_pool=pool,
            )
        elif operation == "validate_draft":
            await lkpm_router.validate_draft(
                draft_id=902,
                current_user=user,
                db_pool=pool,
            )
        elif operation == "get_ready_pack":
            await lkpm_router.get_ready_pack(
                draft_id=902,
                current_user=user,
                db_pool=pool,
            )
        elif operation == "mark_submitted":
            await lkpm_router.mark_submitted(
                draft_id=902,
                submitted_by="forged@example.test",
                current_user=user,
                db_pool=pool,
            )
        elif operation == "upload_receipt":
            await lkpm_router.upload_receipt(
                draft_id=902,
                receipt_number="SYNTHETIC-RECEIPT",
                receipt_file_url=None,
                current_user=user,
                db_pool=pool,
            )
        elif operation == "get_receipts_by_client":
            await lkpm_router.get_receipts_by_client(
                client_id=202,
                current_user=user,
                db_pool=pool,
            )
        elif operation == "get_receipts_for_report":
            await lkpm_router.get_receipts_for_report(
                lkpm_report_id=902,
                current_user=user,
                db_pool=pool,
            )
        elif operation == "get_batch":
            await lkpm_router.get_batch(
                quarter="Q1",
                year=2026,
                current_user=user,
                db_pool=pool,
            )
        elif operation == "get_alerts":
            await lkpm_router.get_alerts(current_user=user, db_pool=pool)
        elif operation == "get_history":
            await lkpm_router.get_history(
                client_id=202,
                current_user=user,
                db_pool=pool,
            )
        elif operation == "generate_ready_pack_pdf":
            await lkpm_router.generate_ready_pack_pdf(
                client_id=202,
                body=lkpm_router.ReadyPackBody(period="Q1 2026", dry_run=True),
                current_user=user,
                db_pool=pool,
            )
        else:  # pragma: no cover - parametrization is the closed operation set
            raise AssertionError(f"Unknown operation: {operation}")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "LKPM target not found"
    service_factory.assert_not_called()


@pytest.mark.asyncio
async def test_portal_draft_scope_comes_from_principal_and_is_non_enumerating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft = MagicMock()
    draft.model_dump.return_value = {"id": 501, "client_id": 101}
    service = SimpleNamespace(
        resolve_portal_client_id=AsyncMock(return_value=101),
        get_draft=AsyncMock(return_value=draft),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)
    user = _client_user()
    pool = MagicMock()

    with pytest.raises(HTTPException) as cross_tenant:
        await lkpm_router.get_draft(
            client_id=202,
            quarter="Q1",
            request=_request("/api/v1/lkpm/draft/202/Q1"),
            year=2026,
            current_user=user,
            db_pool=pool,
        )

    assert cross_tenant.value.status_code == 404
    assert cross_tenant.value.detail == "Draft not found"
    service.get_draft.assert_not_awaited()

    response = await lkpm_router.get_draft(
        client_id=0,
        quarter="Q1",
        request=_request("/api/v1/lkpm/draft/0/Q1"),
        year=2026,
        current_user=user,
        db_pool=pool,
    )

    assert response == {"success": True, "draft": {"id": 501, "client_id": 101}}
    assert service.resolve_portal_client_id.await_count == 2
    service.get_draft.assert_awaited_once_with(101, "Q1", 2026)


@pytest.mark.asyncio
async def test_missing_portal_link_and_missing_draft_share_the_same_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SimpleNamespace(
        resolve_portal_client_id=AsyncMock(return_value=None),
        get_draft=AsyncMock(),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)

    with pytest.raises(HTTPException) as exc_info:
        await lkpm_router.get_draft(
            client_id=0,
            quarter="Q1",
            request=_request("/api/v1/lkpm/draft/0/Q1"),
            year=2026,
            current_user=_client_user(),
            db_pool=MagicMock(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Draft not found"
    service.get_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_submitted_uses_authenticated_actor_not_query_attribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SimpleNamespace(
        mark_submitted=AsyncMock(
            return_value={"success": True, "draft_id": 902, "status": "submitted"}
        )
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)

    response = await lkpm_router.mark_submitted(
        draft_id=902,
        submitted_by="forged@example.test",
        current_user=_tax_user(),
        db_pool=MagicMock(),
    )

    assert response["success"] is True
    service.mark_submitted.assert_awaited_once_with(902, "veronika.tax@balizero.com")


@pytest.mark.parametrize("mutation", ["mark_submitted", "upload_receipt"])
@pytest.mark.asyncio
async def test_service_mutations_are_atomic_and_missing_targets_are_not_successful(
    mutation: str,
) -> None:
    pool, connection = _pool()
    connection.fetchrow.return_value = None
    service = object.__new__(LKPMService)
    service.db_pool = pool

    with pytest.raises(LookupError, match="LKPM draft not found"):
        if mutation == "mark_submitted":
            await service.mark_submitted(902, "veronika.tax@balizero.com")
        else:
            await service.upload_receipt(902, "SYNTHETIC-RECEIPT", None)

    sql = connection.fetchrow.await_args.args[0]
    assert "UPDATE lkpm_reports" in sql
    assert "RETURNING id" in sql
