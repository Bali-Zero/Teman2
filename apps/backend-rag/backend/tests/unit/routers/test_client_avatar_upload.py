"""Regression: client avatars go to Tigris storage, never inline base64.

Follows #2206 (which stopped SERVING base64 in the list). This closes the
WRITE path: ClientUpdate rejects data: URIs, and POST /clients/{id}/avatar
uploads bytes to Tigris and stores a public URL.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, UploadFile

from backend.app.setup.route_walk import iter_leaf_routes

DATA_URI = "data:image/png;base64,AAAABBBB"
STORAGE_URL = (
    "https://nuzantara-warroom-images.fly.storage.tigris.dev/client-avatar/1/ab12cd34.jpg"
)


def _build_create(**kw):
    from backend.app.routers.crm_clients import ClientCreate

    return ClientCreate(full_name="Test Client", **kw)


def _build_update(**kw):
    from backend.app.routers.crm_clients import ClientUpdate

    return ClientUpdate(**kw)


def _build_profile_update(**kw):
    from backend.app.routers.crm_enhanced import ClientProfileUpdate

    return ClientProfileUpdate(**kw)


def _build_validator(**kw):
    from backend.services.crm.client_core import ClientValidator

    return ClientValidator(full_name="Test Client", **kw)


# Every model that can write clients.avatar_url. #2208 guarded ONLY ClientUpdate;
# the other three stayed open and kept minting the inline-base64 rows that 422'd
# every edit of those clients (19 of 1744). They share one validator now — the
# `AvatarUrl` type in crm_utils — and this matrix is what keeps them sharing it.
AVATAR_WRITE_MODELS = [
    ("ClientCreate", _build_create),
    ("ClientUpdate", _build_update),
    ("ClientProfileUpdate", _build_profile_update),
    ("ClientValidator", _build_validator),
]


class TestEveryWritePathRejectsDataUri:
    """GUILT: no write-path may accept an inline base64 avatar."""

    @pytest.mark.parametrize("name,build", AVATAR_WRITE_MODELS)
    def test_data_uri_rejected(self, name, build):
        with pytest.raises(ValueError):
            build(avatar_url=DATA_URI)

    @pytest.mark.parametrize(
        "uri",
        [
            "data:image/jpeg;base64,/9j/4AAQSkZJRg==",
            "data:image/webp;base64,UklGRg==",
            "data:text/plain,hello",
        ],
    )
    def test_data_uri_variants_rejected(self, uri):
        """The guard keys on the `data:` scheme, not on one sample mime."""
        with pytest.raises(ValueError):
            _build_create(avatar_url=uri)


class TestEveryWritePathAcceptsStorageUrl:
    """INNOCENCE: the guard must not clobber legitimate values."""

    @pytest.mark.parametrize("name,build", AVATAR_WRITE_MODELS)
    def test_storage_url_accepted(self, name, build):
        assert build(avatar_url=STORAGE_URL).avatar_url == STORAGE_URL

    @pytest.mark.parametrize("name,build", AVATAR_WRITE_MODELS)
    def test_none_accepted(self, name, build):
        assert build(avatar_url=None).avatar_url is None

    @pytest.mark.parametrize("name,build", AVATAR_WRITE_MODELS)
    def test_empty_string_accepted(self, name, build):
        """"" clears the avatar — the edit modal sends it on remove (#2494)."""
        assert build(avatar_url="").avatar_url == ""

    @pytest.mark.parametrize("name,build", AVATAR_WRITE_MODELS)
    def test_omitted_field_accepted(self, name, build):
        """A payload that never mentions avatar_url must validate untouched."""
        assert build().avatar_url is None


class TestReadPathStillServesLegacyRows:
    """The 19 legacy rows must keep rendering: guard the WRITE, never the READ.

    Putting the validator on ClientResponse would 500 every GET of a client whose
    stored avatar_url is still a data: URI — turning a cosmetic debt into an
    outage. The list endpoint nulls them and GET /{id}/avatar serves them.
    """

    def test_client_response_accepts_legacy_data_uri(self):
        from backend.app.routers.crm_clients import ClientResponse

        r = ClientResponse(
            id=1,
            uuid="u-1",
            full_name="Test Client",
            status="lead",
            client_type="individual",
            avatar_url=DATA_URI,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        assert r.avatar_url == DATA_URI


class TestSharedValidatorIsSingleSourceOfTruth:
    def test_models_use_the_shared_type(self):
        """Each write-model's avatar_url carries the shared AfterValidator.

        Pinning the wiring itself: a future model that re-declares
        `avatar_url: str | None` locally would still pass the behavioural tests
        above only by duplicating the check — this asserts they share ONE.
        """
        from backend.app.utils.crm_utils import reject_data_uri_avatar

        for name, build in AVATAR_WRITE_MODELS:
            model = build().__class__
            meta = model.model_fields["avatar_url"].metadata
            funcs = [getattr(m, "func", None) for m in meta]
            assert reject_data_uri_avatar in funcs, (
                f"{name}.avatar_url does not use the shared AvatarUrl type"
            )

    def test_validator_function_is_pure_and_direct(self):
        from backend.app.utils.crm_utils import reject_data_uri_avatar

        assert reject_data_uri_avatar(None) is None
        assert reject_data_uri_avatar("") == ""
        assert reject_data_uri_avatar(STORAGE_URL) == STORAGE_URL
        with pytest.raises(ValueError):
            reject_data_uri_avatar(DATA_URI)


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
