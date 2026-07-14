"""Regression: client avatars go to Tigris storage, never inline base64.

Follows #2206 (which stopped SERVING base64 in the list). This closes the
WRITE path: ClientUpdate rejects data: URIs, and POST /clients/{id}/avatar
uploads bytes to Tigris and stores a public URL.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from backend.app.setup.route_walk import iter_leaf_routes


class TestClientUpdateRejectsDataUri:
    def test_data_uri_rejected(self):
        from backend.app.routers.crm_clients import ClientUpdate

        with pytest.raises(ValueError):
            ClientUpdate(avatar_url="data:image/png;base64,AAAABBBB")

    def test_storage_url_accepted(self):
        from backend.app.routers.crm_clients import ClientUpdate

        u = ClientUpdate(
            avatar_url="https://nuzantara-warroom-images.fly.storage.tigris.dev/client-avatar/1/ab12cd34.jpg"
        )
        assert u.avatar_url.startswith("https://")

    def test_none_accepted(self):
        from backend.app.routers.crm_clients import ClientUpdate

        assert ClientUpdate(avatar_url=None).avatar_url is None


class TestUploadRouteRegistered:
    def test_post_avatar_registered(self):
        from backend.app.routers import crm_clients

        found = False
        for r in iter_leaf_routes(crm_clients.router):
            if getattr(r, "path", None) == "/api/crm/clients/{client_id}/avatar" and "POST" in (
                getattr(r, "methods", set()) or set()
            ):
                found = True
        assert found


class TestUploadEndpoint:
    @staticmethod
    def _pool():
        conn = MagicMock()
        conn.execute = AsyncMock(return_value=None)

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return None

        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_Ctx())
        return pool, conn

    @pytest.fixture(autouse=True)
    def _patch(self, monkeypatch):
        import backend.app.routers.crm_clients as mod

        monkeypatch.setattr(mod, "verify_client_access", AsyncMock(return_value=None))

        async def _noop_invalidate(*a, **k):
            return None

        monkeypatch.setattr(mod, "invalidate_cache", _noop_invalidate)

        # Patch the tigris client used inside the handler.
        import backend.services.canva_renderer_v2._tigris as tg

        fake_s3 = MagicMock()
        fake_s3.put_object = MagicMock(return_value={})
        monkeypatch.setattr(tg, "get_s3_client", lambda: fake_s3)
        monkeypatch.setattr(tg, "BUCKET", "test-bucket")
        monkeypatch.setattr(tg, "PUBLIC_HOST", "test-bucket.fly.storage.tigris.dev")
        self._fake_s3 = fake_s3

    @staticmethod
    def _upload(content: bytes, content_type: str) -> UploadFile:
        import io

        uf = UploadFile(filename="a.jpg", file=io.BytesIO(content))
        # UploadFile.content_type is derived from headers; set directly for the test.
        uf.__dict__["_content_type"] = content_type
        # Starlette exposes content_type via headers; patch the property source.
        object.__setattr__(uf, "headers", {"content-type": content_type})
        return uf

    @pytest.mark.asyncio
    async def test_jpeg_upload_stores_public_url(self):
        from backend.app.routers.crm_clients import upload_client_avatar

        pool, conn = self._pool()
        uf = self._upload(b"\xff\xd8\xff\xe0jpegbytes", "image/jpeg")

        result = await upload_client_avatar(
            client_id=7, file=uf, db_pool=pool, current_user={"email": "z@balizero.com"}
        )
        assert result["success"] is True
        assert result["avatar_url"].startswith("https://test-bucket.fly.storage.tigris.dev/client-avatar/7/")
        assert result["avatar_url"].endswith(".jpg")
        # DB updated with the URL, not bytes
        args = conn.execute.await_args.args
        assert args[1].startswith("https://")
        assert args[2] == 7
        # object stored public-read
        kwargs = self._fake_s3.put_object.call_args.kwargs
        assert kwargs["ACL"] == "public-read"

    @pytest.mark.asyncio
    async def test_unsupported_type_rejected(self):
        from backend.app.routers.crm_clients import upload_client_avatar

        pool, _ = self._pool()
        uf = self._upload(b"GIF89a", "image/gif")
        with pytest.raises(HTTPException) as exc:
            await upload_client_avatar(
                client_id=7, file=uf, db_pool=pool, current_user={"email": "z@balizero.com"}
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_empty_file_rejected(self):
        from backend.app.routers.crm_clients import upload_client_avatar

        pool, _ = self._pool()
        uf = self._upload(b"", "image/png")
        with pytest.raises(HTTPException) as exc:
            await upload_client_avatar(
                client_id=7, file=uf, db_pool=pool, current_user={"email": "z@balizero.com"}
            )
        assert exc.value.status_code == 400
