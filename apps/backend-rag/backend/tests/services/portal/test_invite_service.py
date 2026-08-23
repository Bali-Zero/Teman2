from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.portal.invite_service import InviteService
from backend.services.portal.portal_profile_service import PLACEHOLDER_PIN_HASH

# A pin_hash that is NOT the placeholder: a client who really completed
# registration once. The distinction between this and PLACEHOLDER_PIN_HASH is
# the whole point of the guard below.
REAL_PIN_HASH = "$2b$12$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123"


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


# ---------------------------------------------------------------------------
# P0 account-takeover fix (2026-08-23, SPEC-p0-invite.md "PR A").
#
# A2: complete_registration must never let an invitation function as a
#     password reset on an ALREADY-ACTIVE portal account. Re-onboarding an
#     INACTIVE account (the legitimate re-invite flow) stays allowed.
# A4: an archived client (clients.deleted_at IS NOT NULL) can't be
#     (re-)invited, and an invitation JOIN can't resolve to an archived
#     client's row. FakeConnection doesn't enforce SQL semantics — it
#     returns whatever is queued regardless of query text — so these tests
#     assert on the captured query text itself; a behavioral-only test
#     (e.g. "returns None -> raises") wouldn't discriminate the fix, since
#     the pre-fix query also raises on a genuinely-missing client. Removing
#     "AND deleted_at IS NULL" (or "AND c.deleted_at IS NULL" on the JOIN)
#     makes these fail while leaving every other test in this file green.
# ---------------------------------------------------------------------------


class _NoopTransaction:
    """No-op async context manager standing in for asyncpg's real transaction."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeConnectionWithTransaction(FakeConnection):
    """FakeConnection + a working `.transaction()` for complete_registration,
    which runs its body inside `async with conn.transaction():`."""

    def transaction(self) -> _NoopTransaction:
        return _NoopTransaction()


@pytest.mark.asyncio
async def test_create_invitation_excludes_archived_clients_by_query() -> None:
    conn = FakeConnection(fetchrow_results=[None])
    service = InviteService(FakePool(conn))

    with pytest.raises(ValueError, match="Client with ID 501 not found"):
        await service.create_invitation(
            client_id=501,
            email="archived@example.com",
            created_by="team@example.com",
        )

    query, args = conn.fetchrow_calls[0]
    assert "deleted_at IS NULL" in query
    assert args == (501,)


@pytest.mark.asyncio
async def test_resend_invitation_excludes_archived_clients_by_query() -> None:
    conn = FakeConnection(fetchrow_results=[None])
    service = InviteService(FakePool(conn))

    with pytest.raises(ValueError, match="Client not found or has no email"):
        await service.resend_invitation(client_id=501, created_by="team@example.com")

    query, args = conn.fetchrow_calls[0]
    assert "deleted_at IS NULL" in query
    assert args == (501,)


@pytest.mark.asyncio
async def test_complete_registration_join_excludes_archived_clients_by_query() -> None:
    """A4 — the invitation JOIN must not resolve to an archived client's row
    (invite created before the client was archived; token still exists but
    must no longer function)."""
    conn = FakeConnectionWithTransaction(fetchrow_results=[None])
    service = InviteService(FakePool(conn))

    with pytest.raises(ValueError, match="Invalid invitation token"):
        await service.complete_registration(token="tok-archived", pin="1234")

    query, args = conn.fetchrow_calls[0]
    assert "c.deleted_at IS NULL" in query
    assert args == ("tok-archived",)


@pytest.mark.asyncio
async def test_complete_registration_rejects_active_existing_account() -> None:
    """A2 GUILT — consuming an invitation must never reset the PIN of an
    ACTIVE account. This is the exact chain step (#3 in SPEC-p0-invite.md)
    that turned a leaked invite link into a full account takeover."""
    now = datetime.now(timezone.utc)
    conn = FakeConnectionWithTransaction(
        fetchrow_results=[
            {
                "id": 9,
                "client_id": 7,
                "email": "victim@example.com",
                "expires_at": now + timedelta(hours=1),
                "used_at": None,
                "client_name": "Client Name",
            },
            {"id": 55, "active": True, "pin_hash": REAL_PIN_HASH},
        ]
    )
    service = InviteService(FakePool(conn))

    with pytest.raises(ValueError, match="already has an active portal account"):
        await service.complete_registration(token="tok", pin="1234")

    # The guard must trip BEFORE any mutation — no UPDATE/INSERT at all.
    assert conn.execute_calls == []


@pytest.mark.asyncio
async def test_complete_registration_reactivates_inactive_existing_account() -> None:
    """A2 INNOCENCE — re-onboarding an INACTIVE account (the legitimate
    re-invite flow) must keep working. Same fixture shape as the GUILT test
    above except `active: False` — this is what makes the guilt test a real
    discriminator rather than "any existing_user rejects"."""
    now = datetime.now(timezone.utc)
    conn = FakeConnectionWithTransaction(
        fetchrow_results=[
            {
                "id": 9,
                "client_id": 7,
                "email": "client@example.com",
                "expires_at": now + timedelta(hours=1),
                "used_at": None,
                "client_name": "Client Name",
            },
            {"id": 55, "active": False, "pin_hash": REAL_PIN_HASH},
        ]
    )
    service = InviteService(FakePool(conn))

    with patch(
        "backend.services.common.cache._invalidate_cache",
        new=AsyncMock(return_value=1),
    ):
        result = await service.complete_registration(token="tok", pin="1234")

    assert result == {
        "success": True,
        "user_id": 55,
        "client_id": 7,
        "email": "client@example.com",
        "name": "Client Name",
    }
    # 3 mutations: reactivate the team_member row, mark the invitation used,
    # seed default client_preferences.
    assert len(conn.execute_calls) == 3
    update_query, update_args = conn.execute_calls[0]
    assert "SET pin_hash = $1, active = true, portal_access = true" in update_query
    assert update_args[1] == 55


@pytest.mark.asyncio
async def test_complete_registration_allows_placeholder_active_account() -> None:
    """A2 REGRESSION — the ordinary first-time registration must succeed.

    `create_client` calls `ensure_portal_profile` (crm_clients.py:736), which
    provisions EVERY CRM client into `team_members` as `active=true` carrying
    PLACEHOLDER_PIN_HASH. An earlier revision of this guard refused on the
    `active` flag alone, which would have rejected essentially every real
    client's first invite completion while still letting a takeover through on
    any inactive row — a self-DoS of the flow the guard exists to protect.

    Found by an adversarial review of the patch, not by the patch's own tests:
    the two tests above BOTH pass under the broken guard, because neither
    fixture carried a placeholder PIN. That is the gap this test closes."""
    now = datetime.now(timezone.utc)
    conn = FakeConnectionWithTransaction(
        fetchrow_results=[
            {
                "id": 9,
                "client_id": 7,
                "email": "client@example.com",
                "expires_at": now + timedelta(hours=1),
                "used_at": None,
                "client_name": "Client Name",
            },
            # active=True AND never registered — the provisioned-but-unused row.
            {"id": 55, "active": True, "pin_hash": PLACEHOLDER_PIN_HASH},
        ]
    )
    service = InviteService(FakePool(conn))

    with patch(
        "backend.services.common.cache._invalidate_cache",
        new=AsyncMock(return_value=1),
    ):
        result = await service.complete_registration(token="tok", pin="1234")

    assert result["success"] is True
    assert result["user_id"] == 55
    # The real PIN is written over the placeholder — this IS onboarding.
    update_query, update_args = conn.execute_calls[0]
    assert "SET pin_hash = $1, active = true, portal_access = true" in update_query
    assert update_args[1] == 55


@pytest.mark.asyncio
async def test_existing_account_lookup_is_deterministic_without_role_filter() -> None:
    """`team_members` mixes staff and client-portal logins in one table, so a
    stray row sharing `linked_client_id` could decide whether a client may
    register. The fix is ORDERING, not filtering: `email` is UNIQUE NOT NULL
    (portal_qa_schema.sql:62), so a role filter that hides the existing row
    sends the flow into INSERT and straight into a unique violation."""
    now = datetime.now(timezone.utc)
    conn = FakeConnectionWithTransaction(
        fetchrow_results=[
            {
                "id": 9,
                "client_id": 7,
                "email": "client@example.com",
                "expires_at": now + timedelta(hours=1),
                "used_at": None,
                "client_name": "Client Name",
            },
            None,
            {"id": 77},
        ]
    )
    service = InviteService(FakePool(conn))

    with patch(
        "backend.services.common.cache._invalidate_cache",
        new=AsyncMock(return_value=1),
    ):
        await service.complete_registration(token="tok", pin="1234")

    lookup_query = conn.fetchrow_calls[1][0]
    assert "FROM team_members" in lookup_query
    assert "pin_hash" in lookup_query
    # The lookup must NOT filter by role. `linked_client_id` is what makes a row
    # the client's portal login; filtering on role would miss a row carrying a
    # different one, fall through to the INSERT branch, and hit
    # `team_members.email UNIQUE` — a 500 on a path that works today.
    assert "role = 'client'" not in lookup_query.replace("(role = 'client') DESC", "")
    # ...but it must be deterministic: a client row wins when several share the link.
    assert "ORDER BY (role = 'client') DESC" in lookup_query


@pytest.mark.asyncio
async def test_validate_token_excludes_archived_clients() -> None:
    """A4 completeness — `validate_token` is the PUBLIC read half of the same
    invariant the minting paths enforce. Leaving it unfiltered let an archived
    client's outstanding token still resolve, disclosing full_name/email/
    client_id to whoever held the link before failing confusingly at complete."""
    conn = FakeConnection(fetchrow_results=[None])
    service = InviteService(FakePool(conn))

    assert await service.validate_token("tok-archived") is None

    query, args = conn.fetchrow_calls[0]
    assert "JOIN clients c ON c.id = i.client_id AND c.deleted_at IS NULL" in query
    assert args == ("tok-archived",)
