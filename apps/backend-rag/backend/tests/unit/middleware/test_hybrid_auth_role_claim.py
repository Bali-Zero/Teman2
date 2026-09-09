"""A JWT without a role claim must not become a colleague on its way through the middleware.

PENDING-ARMS row 88, second half: both middleware JWT paths used to substitute
``member`` for an absent ``role`` claim — and ``member`` is a role real staff hold,
so the allow-list in ``service_accounts.py`` would admit it. The gate is only as
strict as the weakest transformation upstream of it, so these tests traverse the
whole consumer chain: middleware -> ``get_current_user`` -> ``require_team_member``.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from middleware.hybrid_auth import HybridAuthMiddleware

from backend.app.deps.auth import get_current_user, require_team_member


@pytest.fixture(autouse=True)
def available_revocation_store():
    async_client = MagicMock()
    async_client.exists = AsyncMock(return_value=0)
    async_client.get = AsyncMock(return_value=None)
    manager = MagicMock()
    manager.get_async_client.return_value = async_client
    with patch("backend.core.redis_manager.RedisManager.get_instance", return_value=manager):
        yield


@pytest.fixture
def middleware() -> HybridAuthMiddleware:
    return HybridAuthMiddleware(app=MagicMock())


def _bearer_request() -> MagicMock:
    req = MagicMock(spec=Request)
    req.headers = {"Authorization": "Bearer token"}
    req.cookies = {}
    req.state = MagicMock()
    req.url.path = "/api/protected"
    req.method = "GET"
    req.client.host = "127.0.0.1"
    return req


def _through_the_gate(user_ctx: dict) -> dict:
    """What a router sees: the middleware's context, read back by the deps chain."""
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = user_ctx
    return require_team_member(get_current_user(request, None))


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["cookie", "bearer"])
async def test_a_token_without_a_role_claim_is_refused_by_the_team_gate(
    middleware: HybridAuthMiddleware, path: str
) -> None:
    """Guilt: the old default mapped an absent claim to ``member`` and passed."""
    with patch("jose.jwt.decode", return_value={"sub": "1", "email": "a@balizero.com"}):
        if path == "cookie":
            ctx = await middleware.authenticate_jwt_token("token")
        else:
            ctx = await middleware.authenticate_jwt(_bearer_request())
    assert ctx is not None
    assert ctx["role"] == ""
    with pytest.raises(HTTPException) as exc_info:
        _through_the_gate(ctx)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["cookie", "bearer"])
@pytest.mark.parametrize("role", ["member", "Tax Lead"])
async def test_an_explicit_staff_role_claim_still_passes(
    middleware: HybridAuthMiddleware, path: str, role: str
) -> None:
    """Innocence: a real ``member`` (two staff rows) keeps its access."""
    payload = {"sub": "1", "email": "a@balizero.com", "role": role}
    with patch("jose.jwt.decode", return_value=payload):
        if path == "cookie":
            ctx = await middleware.authenticate_jwt_token("token")
        else:
            ctx = await middleware.authenticate_jwt(_bearer_request())
    assert ctx is not None
    assert ctx["role"] == role
    assert _through_the_gate(ctx)["role"] == role
