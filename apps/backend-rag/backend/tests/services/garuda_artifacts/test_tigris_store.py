"""Unit tests for `TigrisArtifactObjectStore` (`tigris_store.py`).

No network, no moto (not a project dependency -- checked against
`requirements*.txt` before writing this file, only `boto3` is pinned). A
fake boto3-like client is injected via the module's own `client=` test seam
so the env-var gate, the no-ACL/no-public-bucket invariant, the
fetch-verify digest check, and the retry/backoff path are all exercised
without a real S3-compatible endpoint.
"""

from __future__ import annotations

import pytest
from botocore.exceptions import ClientError

from backend.services.garuda_artifacts import tigris_store
from backend.services.garuda_artifacts.ports import ArtifactDigestMismatch, ArtifactObjectMissing
from backend.services.garuda_artifacts.tigris_store import (
    ACCESS_KEY_ID_ENV,
    BUCKET_ENV,
    ENDPOINT_URL_ENV,
    SECRET_ACCESS_KEY_ENV,
    GarudaArtifactsStoreUnavailable,
    TigrisArtifactObjectStore,
)

_ALL_ENV = (BUCKET_ENV, ACCESS_KEY_ID_ENV, SECRET_ACCESS_KEY_ENV, ENDPOINT_URL_ENV)


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "boom"}}, "PutObject")


class _FakeS3Client:
    """Records every `put_object`/`get_object` call. `put_failures` is a
    queue of exceptions to raise before eventually succeeding (or not, if
    the queue outlives `_MAX_RETRIES`); `get_object_bytes` is what a
    successful `get_object` returns."""

    def __init__(
        self,
        *,
        put_failures: list[Exception] | None = None,
        get_object_bytes: bytes | None = None,
        get_object_error: Exception | None = None,
    ) -> None:
        self.put_calls: list[dict] = []
        self.get_calls: list[dict] = []
        self._put_failures = list(put_failures or [])
        self._get_object_bytes = get_object_bytes
        self._get_object_error = get_object_error

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        if self._put_failures:
            raise self._put_failures.pop(0)
        return {}

    def get_object(self, **kwargs):
        self.get_calls.append(kwargs)
        if self._get_object_error is not None:
            raise self._get_object_error
        return {"Body": _BytesBody(self._get_object_bytes or b"")}


class _BytesBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ALL_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """The retry loop calls `time.sleep(...)` between attempts -- never
    actually sleep in a unit test."""
    monkeypatch.setattr(tigris_store.time, "sleep", lambda _seconds: None)


def _set_scoped_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(BUCKET_ENV, "garuda-voa-artifacts")
    monkeypatch.setenv(ACCESS_KEY_ID_ENV, "scoped-access-key")
    monkeypatch.setenv(SECRET_ACCESS_KEY_ENV, "scoped-secret-key")


class TestEnvVarGate:
    @pytest.mark.parametrize("missing_env", [BUCKET_ENV, ACCESS_KEY_ID_ENV, SECRET_ACCESS_KEY_ENV])
    def test_each_required_env_var_absent_raises_typed_unavailable(
        self, monkeypatch: pytest.MonkeyPatch, missing_env: str
    ) -> None:
        _set_scoped_env(monkeypatch)
        monkeypatch.delenv(missing_env, raising=False)
        with pytest.raises(GarudaArtifactsStoreUnavailable) as excinfo:
            TigrisArtifactObjectStore(client=_FakeS3Client())
        # The message names the env var, but never a value -- the other two
        # scoped credential values set by `_set_scoped_env` must not leak.
        assert missing_env in str(excinfo.value)
        assert "scoped-access-key" not in str(excinfo.value)
        assert "scoped-secret-key" not in str(excinfo.value)

    def test_public_bucket_fallback_credentials_do_not_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (the public-bucket
        client's own env vars) being set must NOT satisfy this store's own,
        differently-named vars -- no fallback, ever."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "public-bucket-key")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "public-bucket-secret")
        # This store's own vars stay absent.
        with pytest.raises(GarudaArtifactsStoreUnavailable):
            TigrisArtifactObjectStore(client=_FakeS3Client())


class TestPutNeverPublic:
    @pytest.mark.asyncio
    async def test_put_never_passes_acl_and_never_targets_the_public_bucket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_scoped_env(monkeypatch)
        fake_client = _FakeS3Client()
        store = TigrisArtifactObjectStore(client=fake_client)
        await store.put(key="artifacts/TEST/prc_1/art_1", body=b"%PDF-1.4\nbody", content_type="application/pdf")
        assert len(fake_client.put_calls) == 1
        call = fake_client.put_calls[0]
        assert "ACL" not in call
        assert call["Bucket"] == "garuda-voa-artifacts"
        assert call["Bucket"] != "nuzantara-warroom-images"


class TestFetchAndVerify:
    @pytest.mark.asyncio
    async def test_digest_mismatch_raises_typed_error_and_returns_no_bytes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_scoped_env(monkeypatch)
        fake_client = _FakeS3Client(get_object_bytes=b"tampered bytes")
        store = TigrisArtifactObjectStore(client=fake_client)
        with pytest.raises(ArtifactDigestMismatch):
            await store.fetch_and_verify(
                key="artifacts/TEST/prc_1/art_1",
                expected_digest="0" * 64,  # sha256("tampered bytes") != this
            )

    @pytest.mark.asyncio
    async def test_missing_object_raises_typed_missing_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_scoped_env(monkeypatch)
        fake_client = _FakeS3Client(get_object_error=_client_error("NoSuchKey"))
        store = TigrisArtifactObjectStore(client=fake_client)
        with pytest.raises(ArtifactObjectMissing):
            await store.fetch_and_verify(key="artifacts/TEST/prc_1/missing", expected_digest="0" * 64)


class TestRetryBackoff:
    @pytest.mark.asyncio
    async def test_transient_error_retries_then_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_scoped_env(monkeypatch)
        fake_client = _FakeS3Client(put_failures=[_client_error("503"), _client_error("SlowDown")])
        store = TigrisArtifactObjectStore(client=fake_client)
        await store.put(key="artifacts/TEST/prc_1/art_1", body=b"%PDF-1.4\nbody", content_type="application/pdf")
        assert len(fake_client.put_calls) == 3

    @pytest.mark.asyncio
    async def test_non_transient_error_raises_immediately_without_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_scoped_env(monkeypatch)
        fake_client = _FakeS3Client(put_failures=[_client_error("AccessDenied")])
        store = TigrisArtifactObjectStore(client=fake_client)
        with pytest.raises(ClientError):
            await store.put(key="artifacts/TEST/prc_1/art_1", body=b"%PDF-1.4\nbody", content_type="application/pdf")
        assert len(fake_client.put_calls) == 1

    @pytest.mark.asyncio
    async def test_transient_error_exhausting_all_retries_raises_the_last_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_scoped_env(monkeypatch)
        fake_client = _FakeS3Client(
            put_failures=[_client_error("503"), _client_error("503"), _client_error("503")]
        )
        store = TigrisArtifactObjectStore(client=fake_client)
        with pytest.raises(ClientError):
            await store.put(key="artifacts/TEST/prc_1/art_1", body=b"%PDF-1.4\nbody", content_type="application/pdf")
        assert len(fake_client.put_calls) == 3
