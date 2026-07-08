from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.portal.invite_service import InviteService


class AcquireContext:
    def __init__(self, conn: "FakeConnection") -> None:
        self.conn = conn

    async def __aenter__(self) -> "FakeConnection":
        return self.conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakePool:
    def __init__(self, conn: "FakeConnection") -> None:
        self.conn = conn

    def acquire(self) -> AcquireContext:
        return AcquireContext(self.conn)


class FakeConnection:
    def __init__(
        self,
        fetchrow_results: list[dict | None] | None = None,
        fetch_results: list[dict] | None = None,
    ) -> None:
        self.fetchrow_results = list(fetchrow_results or [])
        self.fetch_results = fetch_results or []
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.execute_calls: list[tuple[str, tuple]] = []
        self.fetch_calls: list[tuple[str, tuple]] = []

    async def fetchrow(self, query: str, *args) -> dict | None:
        self.fetchrow_calls.append((query, args))
        return self.fetchrow_results.pop(0)

    async def execute(self, query: str, *args) -> str:
        self.execute_calls.append((query, args))
        return "OK"

    async def fetch(self, query: str, *args) -> list[dict]:
        self.fetch_calls.append((query, args))
        return self.fetch_results


@pytest.mark.asyncio
async def test_create_invitation_invalidates_existing_token_and_returns_invite() -> None:
    expires_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    conn = FakeConnection(
        fetchrow_results=[
            {"id": 7, "full_name": "Client Name", "email": "old@example.com"},
            {"id": 12},
            {"id": 44, "token": "token-abc", "expires_at": expires_at, "created_at": expires_at},
        ],
    )
    service = InviteService(FakePool(conn))

    with (
        patch(
            "backend.services.portal.invite_service.secrets.token_urlsafe",
            return_value="token-abc",
        ),
        patch(
            "backend.services.common.cache._invalidate_cache",
            new=AsyncMock(return_value=1),
        ) as invalidate_cache,
    ):
        result = await service.create_invitation(
            client_id=7,
            email="client@example.com",
            created_by="team@example.com",
        )

    assert result == {
        "invitation_id": 44,
        "client_id": 7,
        "client_name": "Client Name",
        "email": "client@example.com",
        "token": "token-abc",
        "expires_at": expires_at.isoformat(),
        "invite_url": "/portal/register?token=token-abc",
    }
    assert conn.execute_calls[0][1] == (12,)
    assert invalidate_cache.await_count == 2


@pytest.mark.asyncio
async def test_create_invitation_rejects_missing_client() -> None:
    service = InviteService(FakePool(FakeConnection(fetchrow_results=[None])))

    with pytest.raises(ValueError, match="Client with ID 404 not found"):
        await service.create_invitation(
            client_id=404,
            email="missing@example.com",
            created_by="team@example.com",
        )


@pytest.mark.asyncio
async def test_validate_token_returns_valid_invitation_details() -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    conn = FakeConnection(
        fetchrow_results=[
            {
                "id": 4,
                "client_id": 7,
                "email": "client@example.com",
                "expires_at": expires_at,
                "used_at": None,
                "client_name": "Client Name",
            }
        ]
    )
    service = InviteService(FakePool(conn))

    result = await service.validate_token("token")

    assert result == {
        "valid": True,
        "invitation_id": 4,
        "client_id": 7,
        "client_name": "Client Name",
        "email": "client@example.com",
    }


@pytest.mark.asyncio
async def test_validate_token_reports_used_and_expired_states() -> None:
    now = datetime.now(timezone.utc)
    service = InviteService(
        FakePool(
            FakeConnection(
                fetchrow_results=[
                    {
                        "id": 4,
                        "client_id": 7,
                        "email": "client@example.com",
                        "expires_at": now + timedelta(hours=1),
                        "used_at": now,
                        "client_name": "Client Name",
                    },
                    {
                        "id": 5,
                        "client_id": 8,
                        "email": "expired@example.com",
                        "expires_at": now - timedelta(seconds=1),
                        "used_at": None,
                        "client_name": "Expired Client",
                    },
                ]
            )
        )
    )

    assert await service.validate_token("used-token") == {
        "error": "already_used",
        "message": "This invitation has already been used",
    }
    assert await service.validate_token("expired-token") == {
        "error": "expired",
        "message": "This invitation has expired",
    }


@pytest.mark.asyncio
async def test_complete_registration_rejects_invalid_pin_before_db_access() -> None:
    conn = FakeConnection()
    service = InviteService(FakePool(conn))

    with pytest.raises(ValueError, match="PIN must be 4-6 digits"):
        await service.complete_registration(token="token", pin="12ab")

    assert conn.fetchrow_calls == []


@pytest.mark.asyncio
async def test_get_client_invitations_maps_statuses() -> None:
    now = datetime.now(timezone.utc)
    conn = FakeConnection(
        fetch_results=[
            {
                "id": 1,
                "email": "used@example.com",
                "expires_at": now + timedelta(hours=1),
                "used_at": now,
                "created_by": "team@example.com",
                "created_at": now,
            },
            {
                "id": 2,
                "email": "expired@example.com",
                "expires_at": now - timedelta(hours=1),
                "used_at": None,
                "created_by": "team@example.com",
                "created_at": now,
            },
            {
                "id": 3,
                "email": "pending@example.com",
                "expires_at": now + timedelta(hours=1),
                "used_at": None,
                "created_by": "team@example.com",
                "created_at": now,
            },
        ]
    )
    service = InviteService(FakePool(conn))

    invitations = await service.get_client_invitations(7)

    assert [invite["status"] for invite in invitations] == ["used", "expired", "pending"]
    assert conn.fetch_calls[0][1] == (7,)
