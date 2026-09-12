"""Unit tests for `TigrisArtifactObjectStore` (`tigris_store.py`).

No network, no moto (not a project dependency -- checked against
`requirements*.txt` before writing this file, only `boto3` is pinned). A
fake boto3-like client is injected via the module's own `client=` test seam
so the env-var gate, the no-ACL/no-public-bucket invariant, the
fetch-verify digest check, and the retry/backoff path are all exercised
without a real S3-compatible endpoint.

`TestFetchAndVerifyBoundedRead` covers finding F5 (Sol's O1, MAJOR): an
unbounded `.read()` of attacker-influenced bytes let a tampered object
exhaust this worker's memory before the digest check ever ran. `_BytesBody`
below records the LARGEST `amt` any `.read(amt)` call was given and the
number of bytes it actually returned, so those tests can assert the store
never asks for -- or gets handed -- more than `MAX_ARTIFACT_BYTES + 1`
bytes, even when the fake object "actually" holds far more.
"""

from __future__ import annotations

import pytest
from botocore.exceptions import ClientError

from backend.services.garuda_artifacts import tigris_store
from backend.services.garuda_artifacts.ports import (
    MAX_ARTIFACT_BYTES,
    ArtifactDigestMismatch,
    ArtifactObjectMissing,
)
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


_UNSET = object()


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
        get_object_content_length: int | None = _UNSET,
    ) -> None:
        self.put_calls: list[dict] = []
        self.get_calls: list[dict] = []
        self._put_failures = list(put_failures or [])
        self._get_object_bytes = get_object_bytes
        self._get_object_error = get_object_error
        # Defaults to the TRUE length of `get_object_bytes` -- a test that
        # wants the response to LIE (declare a small `ContentLength` while
        # the body is actually huge, or vice-versa) passes an explicit
        # value here instead.
        self._get_object_content_length = get_object_content_length
        self.last_body: _BytesBody | None = None

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        if self._put_failures:
            raise self._put_failures.pop(0)
        return {}

    def get_object(self, **kwargs):
        self.get_calls.append(kwargs)
        if self._get_object_error is not None:
            raise self._get_object_error
        data = self._get_object_bytes or b""
        content_length = (
            len(data)
            if self._get_object_content_length is _UNSET
            else self._get_object_content_length
        )
        self.last_body = _BytesBody(data)
        return {"Body": self.last_body, "ContentLength": content_length}


class _BytesBody:
    """`.read(amt)` mirrors botocore's `StreamingBody`: an `amt` truncates
    what is returned. Records the largest `amt` ever requested and how many
    bytes were actually handed back, so a test can assert the caller never
    asked for -- or received -- more than `MAX_ARTIFACT_BYTES + 1` bytes."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0
        self.max_amt_requested: int | None = None
        self.total_bytes_returned = 0

    def read(self, amt: int | None = None) -> bytes:
        self.max_amt_requested = amt if amt is not None else len(self._data)
        if amt is None:
            chunk = self._data[self._offset :]
        else:
            chunk = self._data[self._offset : self._offset + amt]
        self._offset += len(chunk)
        self.total_bytes_returned += len(chunk)
        return chunk


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
        await store.put(
            key="artifacts/TEST/prc_1/art_1", body=b"%PDF-1.4\nbody", content_type="application/pdf"
        )
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
            await store.fetch_and_verify(
                key="artifacts/TEST/prc_1/missing", expected_digest="0" * 64
            )


class TestFetchAndVerifyBoundedRead:
    """Finding F5 (Sol's O1, MAJOR): a tampered/replaced object used to be
    read into memory with an unbounded `.read()` -- the digest check that
    was supposed to protect the caller ran only AFTER the full (possibly
    multi-gigabyte) body was already buffered, so it protected trust in the
    bytes, never the worker's memory. These tests drive the cure: refuse
    on a disagreeing `ContentLength` before any read, and cap the read
    itself at `MAX_ARTIFACT_BYTES + 1` regardless of what `ContentLength`
    claims."""

    @pytest.mark.asyncio
    async def test_content_length_over_the_ceiling_is_refused_before_any_read(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_scoped_env(monkeypatch)
        fake_client = _FakeS3Client(
            get_object_bytes=b"irrelevant -- the declared size alone must refuse this",
            get_object_content_length=MAX_ARTIFACT_BYTES + 1,
        )
        store = TigrisArtifactObjectStore(client=fake_client)
        with pytest.raises(ArtifactDigestMismatch):
            await store.fetch_and_verify(key="artifacts/TEST/prc_1/art_1", expected_digest="0" * 64)
        # Refused on the DECLARED size alone -- `.read()` (bounded or not)
        # is never even called.
        assert fake_client.last_body is not None
        assert fake_client.last_body.max_amt_requested is None

    @pytest.mark.asyncio
    async def test_content_length_disagreeing_with_the_rows_expected_byte_length_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_scoped_env(monkeypatch)
        # Both well under the ceiling -- only the row/object disagreement
        # should trigger the refusal here.
        fake_client = _FakeS3Client(get_object_bytes=b"x" * 500, get_object_content_length=500)
        store = TigrisArtifactObjectStore(client=fake_client)
        with pytest.raises(ArtifactDigestMismatch):
            await store.fetch_and_verify(
                key="artifacts/TEST/prc_1/art_1",
                expected_digest="0" * 64,
                expected_byte_length=400,
            )
        assert fake_client.last_body.max_amt_requested is None

    @pytest.mark.asyncio
    async def test_agreeing_content_length_and_expected_byte_length_is_not_refused_on_size(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sanity check the size gate is not simply always-on: a body whose
        `ContentLength` matches both the ceiling and the row's expected
        length reaches the digest comparison (and fails there, on a
        deliberately wrong `expected_digest`, never on size)."""
        _set_scoped_env(monkeypatch)
        body = b"%PDF-1.4\nfine"
        fake_client = _FakeS3Client(get_object_bytes=body, get_object_content_length=len(body))
        store = TigrisArtifactObjectStore(client=fake_client)
        with pytest.raises(ArtifactDigestMismatch):
            await store.fetch_and_verify(
                key="artifacts/TEST/prc_1/art_1",
                expected_digest="0" * 64,
                expected_byte_length=len(body),
            )
        assert fake_client.last_body.max_amt_requested == MAX_ARTIFACT_BYTES + 1

    @pytest.mark.asyncio
    async def test_object_whose_true_bytes_exceed_the_ceiling_is_caught_by_the_bounded_read_even_when_content_length_lies(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The guilt case: `ContentLength` (declared 100 bytes) disagrees
        with what the object actually hands back on `.read()` -- exactly
        what a replaced/corrupted object looks like. The PRE-cure code
        called `resp["Body"].read()` with NO limit, so it would have
        buffered every one of the `MAX_ARTIFACT_BYTES + 100` bytes below
        before the digest check ever ran. The cure must never ask for, or
        receive, more than `MAX_ARTIFACT_BYTES + 1` of them."""
        _set_scoped_env(monkeypatch)
        actual_bytes = b"\x00" * (MAX_ARTIFACT_BYTES + 100)
        fake_client = _FakeS3Client(get_object_bytes=actual_bytes, get_object_content_length=100)
        store = TigrisArtifactObjectStore(client=fake_client)
        with pytest.raises(ArtifactDigestMismatch):
            await store.fetch_and_verify(key="artifacts/TEST/prc_1/art_1", expected_digest="0" * 64)
        assert fake_client.last_body.max_amt_requested == MAX_ARTIFACT_BYTES + 1
        assert fake_client.last_body.total_bytes_returned == MAX_ARTIFACT_BYTES + 1


class TestRetryBackoff:
    @pytest.mark.asyncio
    async def test_transient_error_retries_then_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_scoped_env(monkeypatch)
        fake_client = _FakeS3Client(put_failures=[_client_error("503"), _client_error("SlowDown")])
        store = TigrisArtifactObjectStore(client=fake_client)
        await store.put(
            key="artifacts/TEST/prc_1/art_1", body=b"%PDF-1.4\nbody", content_type="application/pdf"
        )
        assert len(fake_client.put_calls) == 3

    @pytest.mark.asyncio
    async def test_non_transient_error_raises_immediately_without_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_scoped_env(monkeypatch)
        fake_client = _FakeS3Client(put_failures=[_client_error("AccessDenied")])
        store = TigrisArtifactObjectStore(client=fake_client)
        with pytest.raises(ClientError):
            await store.put(
                key="artifacts/TEST/prc_1/art_1",
                body=b"%PDF-1.4\nbody",
                content_type="application/pdf",
            )
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
            await store.put(
                key="artifacts/TEST/prc_1/art_1",
                body=b"%PDF-1.4\nbody",
                content_type="application/pdf",
            )
        assert len(fake_client.put_calls) == 3
