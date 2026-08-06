"""Tenant-isolation coverage for client-facing LKPM mutations."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.app.models.lkpm import LKPMClientSubmission, LKPMDraft
from backend.app.routers import lkpm as lkpm_router
from backend.services.compliance.lkpm_service import LKPMService

CLIENT_A_ID = 101
CLIENT_B_ID = 202
COMPANY_A_ID = 1001
COMPANY_B_ID = 2002


class _AcquireContext:
    """Minimal asyncpg acquisition context for isolated unit tests."""

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
    connection.fetchval = AsyncMock()
    connection.fetchrow = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value = _AcquireContext(connection)
    return pool, connection


def _client_user(label: str = "tenant-a") -> dict[str, str]:
    return {
        "email": f"{label}@example.test",
        "user_id": f"portal-user-{label}",
        "role": "client",
    }


def _submission(
    client_id: int,
    company_id: int | None = COMPANY_A_ID,
) -> LKPMClientSubmission:
    return LKPMClientSubmission(
        client_id=client_id,
        company_id=company_id,
        quarter="Q1",
        year=2026,
    )


def _service_without_constructor(pool: MagicMock) -> LKPMService:
    service = object.__new__(LKPMService)
    service.db_pool = pool
    return service


@pytest.mark.asyncio
async def test_submit_route_passes_only_server_resolved_client_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A forged body client_id is never used as the authenticated scope."""
    pool, _ = _pool()
    draft = LKPMDraft(id=301, client_id=CLIENT_A_ID, quarter="Q1", year=2026)
    service = SimpleNamespace(
        resolve_portal_client_id=AsyncMock(return_value=CLIENT_A_ID),
        submit_form_data_for_client=AsyncMock(return_value=draft),
        submit_form_data_for_admin=AsyncMock(),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)
    forged = _submission(CLIENT_B_ID)

    result = await lkpm_router.submit_data(
        submission=forged,
        current_user=_client_user(),
        db_pool=pool,
    )

    service.resolve_portal_client_id.assert_awaited_once_with("portal-user-tenant-a")
    service.submit_form_data_for_client.assert_awaited_once_with(
        forged,
        authenticated_client_id=CLIENT_A_ID,
    )
    service.submit_form_data_for_admin.assert_not_awaited()
    assert result["draft_id"] == 301


@pytest.mark.asyncio
async def test_submit_route_rejects_non_client_role_before_service_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool, _ = _pool()
    service = SimpleNamespace(
        resolve_portal_client_id=AsyncMock(),
        submit_form_data_for_client=AsyncMock(),
        submit_form_data_for_admin=AsyncMock(),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)

    with pytest.raises(HTTPException) as exc_info:
        await lkpm_router.submit_data(
            submission=_submission(CLIENT_A_ID),
            current_user={"email": "staff@example.test", "user_id": "staff-1", "role": "team"},
            db_pool=pool,
        )

    assert exc_info.value.status_code == 403
    service.resolve_portal_client_id.assert_not_awaited()
    service.submit_form_data_for_client.assert_not_awaited()
    service.submit_form_data_for_admin.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_route_allows_only_verified_admin_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool, _ = _pool()
    submission = _submission(CLIENT_B_ID, COMPANY_B_ID)
    draft = LKPMDraft(
        id=302,
        client_id=CLIENT_B_ID,
        company_id=COMPANY_B_ID,
        quarter="Q1",
        year=2026,
    )
    service = SimpleNamespace(
        resolve_portal_client_id=AsyncMock(),
        submit_form_data_for_client=AsyncMock(),
        submit_form_data_for_admin=AsyncMock(return_value=draft),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)

    result = await lkpm_router.submit_data(
        submission=submission,
        current_user={"email": "admin@example.test", "user_id": "admin-1", "role": "admin"},
        db_pool=pool,
    )

    service.resolve_portal_client_id.assert_not_awaited()
    service.submit_form_data_for_client.assert_not_awaited()
    service.submit_form_data_for_admin.assert_awaited_once_with(submission)
    assert result["draft_id"] == 302


@pytest.mark.asyncio
async def test_submit_service_rebinds_both_tenant_and_owned_company() -> None:
    pool, connection = _pool()
    connection.fetchval.return_value = COMPANY_A_ID
    service = _service_without_constructor(pool)
    expected = LKPMDraft(
        id=301,
        client_id=CLIENT_A_ID,
        company_id=COMPANY_A_ID,
        quarter="Q1",
        year=2026,
    )
    service.submit_form_data = AsyncMock(return_value=expected)

    result = await service.submit_form_data_for_client(
        _submission(CLIENT_B_ID, COMPANY_A_ID),
        authenticated_client_id=CLIENT_A_ID,
    )

    scoped = service.submit_form_data.await_args.args[0]
    assert scoped.client_id == CLIENT_A_ID
    assert scoped.company_id == COMPANY_A_ID
    assert result == expected
    assert connection.fetchval.await_args.args[1:] == (CLIENT_A_ID, COMPANY_A_ID)


@pytest.mark.asyncio
async def test_submit_service_rejects_company_owned_by_second_tenant() -> None:
    pool, connection = _pool()
    connection.fetchval.return_value = None
    service = _service_without_constructor(pool)
    service.submit_form_data = AsyncMock()

    with pytest.raises(LookupError, match="LKPM submission target not found"):
        await service.submit_form_data_for_client(
            _submission(CLIENT_B_ID, COMPANY_B_ID),
            authenticated_client_id=CLIENT_A_ID,
        )

    service.submit_form_data.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_admin_body_ids_fail_without_server_owned_relationship() -> None:
    pool, connection = _pool()
    connection.fetchval.return_value = None
    service = _service_without_constructor(pool)
    service.submit_form_data = AsyncMock()

    with pytest.raises(LookupError, match="LKPM submission target not found"):
        await service.submit_form_data_for_admin(
            _submission(CLIENT_A_ID, COMPANY_B_ID),
        )

    assert connection.fetchval.await_args.args[1:] == (CLIENT_A_ID, COMPANY_B_ID)
    service.submit_form_data.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_admin_uses_server_validated_client_company_relationship() -> None:
    pool, connection = _pool()
    connection.fetchval.return_value = COMPANY_B_ID
    service = _service_without_constructor(pool)
    expected = LKPMDraft(
        id=302,
        client_id=CLIENT_B_ID,
        company_id=COMPANY_B_ID,
        quarter="Q1",
        year=2026,
    )
    service.submit_form_data = AsyncMock(return_value=expected)

    result = await service.submit_form_data_for_admin(
        _submission(CLIENT_B_ID, COMPANY_B_ID),
    )

    scoped = service.submit_form_data.await_args.args[0]
    assert scoped.client_id == CLIENT_B_ID
    assert scoped.company_id == COMPANY_B_ID
    assert connection.fetchval.await_args.args[1:] == (CLIENT_B_ID, COMPANY_B_ID)
    assert result == expected


@pytest.mark.asyncio
async def test_approve_cross_tenant_and_missing_are_non_enumerating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool, _ = _pool()
    service = SimpleNamespace(
        resolve_portal_client_id=AsyncMock(return_value=CLIENT_A_ID),
        approve_draft_for_actor=AsyncMock(
            side_effect=LookupError("LKPM draft not found"),
        ),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)

    observed: list[tuple[int, str]] = []
    for draft_id in (401, 999):
        with pytest.raises(HTTPException) as exc_info:
            await lkpm_router.approve_draft(
                draft_id=draft_id,
                current_user=_client_user(),
                db_pool=pool,
            )
        observed.append((exc_info.value.status_code, str(exc_info.value.detail)))

    assert observed == [
        (404, "LKPM draft not found"),
        (404, "LKPM draft not found"),
    ]


@pytest.mark.asyncio
async def test_approve_nominal_owner_uses_authenticated_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool, _ = _pool()
    service = SimpleNamespace(
        resolve_portal_client_id=AsyncMock(return_value=CLIENT_A_ID),
        approve_draft_for_actor=AsyncMock(
            return_value={"success": True, "draft_id": 301, "status": "approved"},
        ),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)

    result = await lkpm_router.approve_draft(
        draft_id=301,
        current_user=_client_user(),
        db_pool=pool,
    )

    service.approve_draft_for_actor.assert_awaited_once_with(
        301,
        authenticated_client_id=CLIENT_A_ID,
        is_admin=False,
    )
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_approve_admin_uses_verified_admin_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool, _ = _pool()
    service = SimpleNamespace(
        resolve_portal_client_id=AsyncMock(),
        approve_draft_for_actor=AsyncMock(
            return_value={"success": True, "draft_id": 301, "status": "approved"},
        ),
    )
    monkeypatch.setattr(lkpm_router, "_get_service", lambda _pool: service)

    result = await lkpm_router.approve_draft(
        draft_id=301,
        current_user={"email": "admin@example.test", "user_id": "admin-1", "role": "admin"},
        db_pool=pool,
    )

    service.resolve_portal_client_id.assert_not_awaited()
    service.approve_draft_for_actor.assert_awaited_once_with(
        301,
        authenticated_client_id=None,
        is_admin=True,
    )
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_approve_service_atomically_rejects_other_tenant() -> None:
    pool, connection = _pool()
    connection.fetchrow.return_value = None
    service = _service_without_constructor(pool)

    with pytest.raises(LookupError, match="LKPM draft not found"):
        await service.approve_draft_for_actor(
            401,
            authenticated_client_id=CLIENT_A_ID,
            is_admin=False,
        )

    sql = connection.fetchrow.await_args.args[0]
    assert "UPDATE lkpm_reports AS r" in sql
    assert "client_company_links" in sql
    assert connection.fetchrow.await_args.args[3:] == (False, CLIENT_A_ID)


@pytest.mark.asyncio
async def test_approve_service_nominal_owner_and_admin() -> None:
    pool, connection = _pool()
    connection.fetchrow.return_value = {"id": 301}
    service = _service_without_constructor(pool)

    owner_result = await service.approve_draft_for_actor(
        301,
        authenticated_client_id=CLIENT_A_ID,
        is_admin=False,
    )
    admin_result = await service.approve_draft_for_actor(
        302,
        authenticated_client_id=None,
        is_admin=True,
    )

    assert owner_result == {"success": True, "draft_id": 301, "status": "approved"}
    assert admin_result == {"success": True, "draft_id": 302, "status": "approved"}
    assert connection.fetchrow.await_count == 2
