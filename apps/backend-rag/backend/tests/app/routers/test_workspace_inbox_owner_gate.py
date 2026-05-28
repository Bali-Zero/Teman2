"""Owner-only gate for the workspace inbox router (2026-05-28).

The inbox is private to Zero. Every other user — including the other CRM
admins (asya@, antonellosiano@) and all team members — must receive 403 on
both /api/workspace/inbox and /api/workspace/inbox/stats.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app.deps.auth import get_current_user
from backend.app.deps.database import get_database_pool
from backend.app.routers.workspace_inbox import INBOX_OWNER_EMAILS, router


class _AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return None


def make_app(user_email: str, role: str = "admin") -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def fake_user():
        return {"email": user_email, "role": role}

    async def fake_pool():
        pool = MagicMock()
        conn = MagicMock()

        async def fetch(*args, **kwargs):
            return []

        conn.fetch = MagicMock(side_effect=fetch)
        pool.acquire = MagicMock(return_value=_AsyncContext(conn))
        return pool

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_database_pool] = fake_pool
    return app


def test_owner_allowlist_is_zero_only():
    # Guard against a future edit widening the inbox allowlist.
    assert INBOX_OWNER_EMAILS == frozenset({"zero@balizero.com"})


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/workspace/inbox", "/api/workspace/inbox/stats"])
@pytest.mark.parametrize(
    "email,role",
    [
        ("asya@balizero.com", "admin"),  # other CRM admin — still denied
        ("antonellosiano@balizero.com", "admin"),  # owner alias — denied for inbox
        ("adit@balizero.com", "member"),  # team member — denied
        ("subhi@balizero.com", "member"),  # team member — denied
        ("", "admin"),  # missing email — denied
        ("notzero@balizero.com", "admin"),  # lookalike — denied
    ],
)
async def test_non_owner_denied(path: str, email: str, role: str):
    app = make_app(email, role)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(path)
    assert r.status_code == 403, f"{email} should be denied on {path}, got {r.status_code}"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/workspace/inbox", "/api/workspace/inbox/stats"])
@pytest.mark.parametrize("email", ["zero@balizero.com", "ZERO@BALIZERO.COM"])
async def test_owner_allowed(path: str, email: str):
    # Email is lower-cased before the allowlist check, so case variants pass.
    app = make_app(email)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(path)
    assert r.status_code == 200, f"owner denied on {path}: {r.status_code} {r.text}"
