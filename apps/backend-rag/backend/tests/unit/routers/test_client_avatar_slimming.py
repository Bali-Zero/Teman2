"""Regression: the clients LIST must not inline base64 data-URI avatars.

Live 2026-07-10: GET /api/crm/clients?limit=200 returned ~7.5MB because
`avatar_url` holds base64 data:image blobs (avg ~20KB, max 518KB, 383 clients).
The list now returns `avatar_url=None` + `has_avatar=True` for data-URI avatars
(http URLs pass through), and the image is served lazily by
GET /api/crm/clients/{id}/avatar.
"""

import base64

import pytest
from fastapi import HTTPException


class TestClientResponseHasAvatar:
    def test_field_present_default_false(self):
        from backend.app.routers.crm_clients import ClientResponse

        assert "has_avatar" in ClientResponse.model_fields
        assert ClientResponse.model_fields["has_avatar"].default is False


class TestAvatarRouteRegistered:
    def test_route_registered(self):
        from backend.app.routers import crm_clients

        paths = [r.path for r in crm_clients.router.routes]
        assert "/api/crm/clients/{client_id}/avatar" in paths


class TestAvatarEndpoint:
    """Exercise the decode/redirect/404 branches directly."""

    @staticmethod
    def _pool(avatar_value):
        from unittest.mock import AsyncMock, MagicMock

        conn = MagicMock()
        conn.fetchval = AsyncMock(return_value=avatar_value)

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return None

        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_Ctx())
        return pool

    @pytest.fixture(autouse=True)
    def _patch_access(self, monkeypatch):
        # verify_client_access is imported into the router module namespace.
        from unittest.mock import AsyncMock

        import backend.app.routers.crm_clients as mod

        monkeypatch.setattr(mod, "verify_client_access", AsyncMock(return_value=None))

    @pytest.mark.asyncio
    async def test_data_uri_returns_image_bytes(self):
        from backend.app.routers.crm_clients import get_client_avatar

        payload = b"\xff\xd8\xff\xe0hello-jpeg"
        b64 = base64.b64encode(payload).decode()
        data_uri = f"data:image/png;base64,{b64}"

        resp = await get_client_avatar(
            client_id=1, db_pool=self._pool(data_uri), current_user={"email": "z@balizero.com"}
        )
        assert resp.body == payload
        assert resp.media_type == "image/png"
        assert "max-age" in resp.headers.get("cache-control", "")

    @pytest.mark.asyncio
    async def test_http_url_redirects(self):
        from backend.app.routers.crm_clients import get_client_avatar

        resp = await get_client_avatar(
            client_id=1,
            db_pool=self._pool("https://cdn.example.com/a.jpg"),
            current_user={"email": "z@balizero.com"},
        )
        assert resp.status_code == 302
        assert resp.headers["location"] == "https://cdn.example.com/a.jpg"

    @pytest.mark.asyncio
    async def test_no_avatar_is_404(self):
        from backend.app.routers.crm_clients import get_client_avatar

        with pytest.raises(HTTPException) as exc:
            await get_client_avatar(
                client_id=1, db_pool=self._pool(None), current_user={"email": "z@balizero.com"}
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_malformed_data_uri_is_422(self):
        from backend.app.routers.crm_clients import get_client_avatar

        with pytest.raises(HTTPException) as exc:
            await get_client_avatar(
                client_id=1,
                db_pool=self._pool("data:image/png;base64,!!!not-base64!!!"),
                current_user={"email": "z@balizero.com"},
            )
        assert exc.value.status_code == 422
