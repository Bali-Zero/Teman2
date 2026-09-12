"""`TigrisArtifactObjectStore` -- the private artifact bucket adapter.

No network, no moto (not a project dependency -- checked against
`requirements*.txt` before writing this file, only `boto3` is pinned). A
fake boto3-like client is injected through `TigrisArtifactObjectStore
.for_tests(client=...)`, the ONE entry point that accepts a client the
class did not build; the public constructor takes none (O1 F3).

Every guarantee Sol's round O1 listed as untested has a test here, and each
test names the finding it answers. What CANNOT be tested without a bucket
is stated in `TestBucketPrivacy`: the adapter can refuse a known-public
bucket and can probe a bucket's public-access posture, but whether the
operator's bucket is private is a provisioning fact (pending #G).
"""

from __future__ import annotations

import hashlib
import logging

import pytest
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    ParamValidationError,
)

from backend.services.garuda_artifacts import tigris_store
from backend.services.garuda_artifacts.fakes import InMemoryArtifactObjectStore
from backend.services.garuda_artifacts.ports import (
    MAX_ARTIFACT_BYTES,
    ArtifactAlreadyExists,
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
_SENTINEL_KEY = "artifacts/prc_SENTINELPRACTICE/art_SENTINELARTIFACT"


def _client_error(code: str, *, status: int | None = None, op: str = "PutObject") -> ClientError:
    resp: dict = {"Error": {"Code": code, "Message": "boom"}}
    if status is not None:
        resp["ResponseMetadata"] = {"HTTPStatusCode": status}
    return ClientError(resp, op)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


_UNSET = object()


class _BytesBody:
    """`.read(amt)` mirrors botocore's `StreamingBody`: an `amt` truncates
    what is returned and a read past the end returns b"". Records the
    largest `amt` ever requested, the bytes handed back and whether
    `close()` was called."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0
        self.max_amt_requested: int | None = None
        self.total_bytes_returned = 0
        self.closed = False

    def read(self, amt: int | None = None) -> bytes:
        self.max_amt_requested = (
            amt
            if self.max_amt_requested is None or (amt or 0) > self.max_amt_requested
            else self.max_amt_requested
        )
        chunk = (
            self._data[self._offset :]
            if amt is None
            else self._data[self._offset : self._offset + amt]
        )
        self._offset += len(chunk)
        self.total_bytes_returned += len(chunk)
        return chunk

    def close(self) -> None:
        self.closed = True


class _FakeS3Client:
    """Records every call. `put_failures` / `get_failures` are queues of
    exceptions raised before eventually succeeding (or not, if a queue
    outlives the retry budget). `existing_keys` makes `put_object` with
    `IfNoneMatch="*"` answer 412 the way a conditional write does."""

    def __init__(
        self,
        *,
        put_failures: list[Exception] | None = None,
        get_failures: list[Exception] | None = None,
        get_object_bytes: bytes | None = None,
        get_object_content_length: object = _UNSET,
        existing_keys: set[str] | None = None,
        public_access_block: dict | Exception | None = None,
        policy_status: dict | Exception | None = None,
    ) -> None:
        self.put_calls: list[dict] = []
        self.get_calls: list[dict] = []
        self._put_failures = list(put_failures or [])
        self._get_failures = list(get_failures or [])
        self._get_object_bytes = get_object_bytes
        self._get_object_content_length = get_object_content_length
        self._existing_keys = set(existing_keys or ())
        self._public_access_block = public_access_block
        self._policy_status = policy_status
        self.bodies: list[_BytesBody] = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        if self._put_failures:
            raise self._put_failures.pop(0)
        if kwargs.get("IfNoneMatch") == "*" and kwargs["Key"] in self._existing_keys:
            raise _client_error("PreconditionFailed", status=412)
        self._existing_keys.add(kwargs["Key"])
        return {}

    def get_object(self, **kwargs):
        self.get_calls.append(kwargs)
        if self._get_failures:
            raise self._get_failures.pop(0)
        data = self._get_object_bytes or b""
        body = _BytesBody(data)
        self.bodies.append(body)
        resp: dict = {"Body": body}
        if self._get_object_content_length is _UNSET:
            resp["ContentLength"] = len(data)
        elif self._get_object_content_length is not None:
            resp["ContentLength"] = self._get_object_content_length
        return resp

    def get_public_access_block(self, **kwargs):
        if isinstance(self._public_access_block, Exception):
            raise self._public_access_block
        if self._public_access_block is None:
            raise _client_error("NoSuchPublicAccessBlockConfiguration", op="GetPublicAccessBlock")
        return {"PublicAccessBlockConfiguration": self._public_access_block}

    def get_bucket_policy_status(self, **kwargs):
        if isinstance(self._policy_status, Exception):
            raise self._policy_status
        if self._policy_status is None:
            raise _client_error("NoSuchBucketPolicy", op="GetBucketPolicyStatus")
        return {"PolicyStatus": self._policy_status}


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ALL_ENV:
        monkeypatch.delenv(name, raising=False)


def _store(
    client: _FakeS3Client, *, sleeps: list[float] | None = None
) -> TigrisArtifactObjectStore:
    return TigrisArtifactObjectStore.for_tests(
        client=client, sleep=(sleeps.append if sleeps is not None else (lambda _s: None))
    )


def _set_scoped_env(
    monkeypatch: pytest.MonkeyPatch, *, bucket: str = "garuda-voa-artifacts"
) -> None:
    monkeypatch.setenv(BUCKET_ENV, bucket)
    monkeypatch.setenv(ACCESS_KEY_ID_ENV, "scoped-access-key")
    monkeypatch.setenv(SECRET_ACCESS_KEY_ENV, "scoped-secret")


# --------------------------------------------------------------- env gate


class TestEnvVarGate:
    def test_missing_scoped_credentials_refuses_to_construct(self, monkeypatch, caplog) -> None:
        monkeypatch.setenv(BUCKET_ENV, "garuda-voa-artifacts")
        with caplog.at_level(logging.DEBUG), pytest.raises(GarudaArtifactsStoreUnavailable) as info:
            TigrisArtifactObjectStore()
        assert ACCESS_KEY_ID_ENV in str(info.value)
        assert SECRET_ACCESS_KEY_ENV in str(info.value)
        assert "scoped" not in caplog.text

    @pytest.mark.parametrize("absent", [BUCKET_ENV, ACCESS_KEY_ID_ENV, SECRET_ACCESS_KEY_ENV])
    def test_each_scoped_var_is_load_bearing(self, monkeypatch, absent) -> None:
        _set_scoped_env(monkeypatch)
        monkeypatch.delenv(absent)
        with pytest.raises(GarudaArtifactsStoreUnavailable) as info:
            TigrisArtifactObjectStore()
        assert absent in str(info.value)

    def test_empty_string_counts_as_absent(self, monkeypatch) -> None:
        _set_scoped_env(monkeypatch)
        monkeypatch.setenv(SECRET_ACCESS_KEY_ENV, "")
        with pytest.raises(GarudaArtifactsStoreUnavailable):
            TigrisArtifactObjectStore()

    def test_exception_message_never_carries_a_value(self, monkeypatch) -> None:
        _set_scoped_env(monkeypatch)
        monkeypatch.setenv(SECRET_ACCESS_KEY_ENV, "")
        monkeypatch.setenv(ACCESS_KEY_ID_ENV, "AKIA-SENTINEL-VALUE")
        with pytest.raises(GarudaArtifactsStoreUnavailable) as info:
            TigrisArtifactObjectStore()
        assert "AKIA-SENTINEL-VALUE" not in str(info.value)

    def test_public_constructor_has_no_client_seam(self) -> None:
        """O1 F3: the only way in with a foreign client is `for_tests`."""
        with pytest.raises(TypeError):
            TigrisArtifactObjectStore(client=_FakeS3Client())  # type: ignore[call-arg]

    def test_constructs_a_real_client_with_the_dedicated_credentials(self, monkeypatch) -> None:
        """The generic AWS_* pair is present AND different; the client must be
        built from the GARUDA_* pair, with the SDK's own retries disabled so
        this module's attempt budget is the wire-level budget (O1 F9)."""
        _set_scoped_env(monkeypatch)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "generic-public-bucket-key")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "generic-public-bucket-secret")
        captured: dict = {}

        def fake_boto3_client(service, **kwargs):
            captured.update(kwargs)
            captured["service"] = service
            return object()

        monkeypatch.setattr(tigris_store.boto3, "client", fake_boto3_client)
        TigrisArtifactObjectStore()
        assert captured["service"] == "s3"
        assert captured["aws_access_key_id"] == "scoped-access-key"
        assert captured["aws_secret_access_key"] == "scoped-secret"
        assert captured["endpoint_url"] == tigris_store.DEFAULT_ENDPOINT_URL
        assert captured["config"].retries == {"max_attempts": 1, "mode": "standard"}


# ------------------------------------------------------- endpoint + bucket


class TestEndpointAndBucketConfinement:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "http://fly.storage.tigris.dev",  # not https
            "https://s3.amazonaws.com",  # not Tigris
            "https://attacker.example/tigris.dev",  # suffix in the path, not the host
            "https://tigris.dev.attacker.example",  # suffix not terminal
            "https://",  # no host
        ],
    )
    def test_non_tigris_or_non_https_endpoint_is_refused(self, monkeypatch, endpoint) -> None:
        """O1 F2: a foreign endpoint would receive bodies and SigV4-signed
        requests carrying the dedicated key id."""
        _set_scoped_env(monkeypatch)
        monkeypatch.setenv(ENDPOINT_URL_ENV, endpoint)
        monkeypatch.setattr(
            tigris_store.boto3, "client", lambda *a, **k: pytest.fail("client built")
        )
        with pytest.raises(GarudaArtifactsStoreUnavailable) as info:
            TigrisArtifactObjectStore()
        assert ENDPOINT_URL_ENV in str(info.value)

    def test_a_tigris_regional_host_is_accepted(self, monkeypatch) -> None:
        _set_scoped_env(monkeypatch)
        monkeypatch.setenv(ENDPOINT_URL_ENV, "https://sin.storage.tigris.dev")
        captured: dict = {}
        monkeypatch.setattr(
            tigris_store.boto3, "client", lambda s, **k: captured.update(k) or object()
        )
        TigrisArtifactObjectStore()
        assert captured["endpoint_url"] == "https://sin.storage.tigris.dev"

    def test_the_known_public_bucket_is_refused_by_name(self, monkeypatch) -> None:
        """O1 F1, the part the adapter CAN enforce: `nuzantara-warroom-images`
        is public-read by its own module's admission."""
        _set_scoped_env(monkeypatch, bucket="nuzantara-warroom-images")
        monkeypatch.setattr(
            tigris_store.boto3, "client", lambda *a, **k: pytest.fail("client built")
        )
        with pytest.raises(GarudaArtifactsStoreUnavailable) as info:
            TigrisArtifactObjectStore()
        assert "PUBLIC" in str(info.value)
        with pytest.raises(GarudaArtifactsStoreUnavailable):
            TigrisArtifactObjectStore.for_tests(
                client=_FakeS3Client(), bucket="nuzantara-warroom-images"
            )


class TestBucketPrivacy:
    """O1 F1, the part the adapter can only PROBE. Whether the operator's
    bucket is private is a provisioning fact; `assert_private()` reads the
    bucket's posture and fails closed on a positive public signal."""

    @pytest.mark.asyncio
    async def test_public_policy_status_refuses(self) -> None:
        store = _store(_FakeS3Client(policy_status={"IsPublic": True}))
        with pytest.raises(GarudaArtifactsStoreUnavailable) as info:
            await store.assert_private()
        assert "PUBLIC" in str(info.value)

    @pytest.mark.asyncio
    async def test_incomplete_public_access_block_refuses(self) -> None:
        store = _store(
            _FakeS3Client(
                public_access_block={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": False,
                    "RestrictPublicBuckets": True,
                }
            )
        )
        with pytest.raises(GarudaArtifactsStoreUnavailable):
            await store.assert_private()

    @pytest.mark.asyncio
    async def test_verified_private_returns_both_probes_true(self) -> None:
        store = _store(
            _FakeS3Client(
                public_access_block=dict.fromkeys(
                    (
                        "BlockPublicAcls",
                        "IgnorePublicAcls",
                        "BlockPublicPolicy",
                        "RestrictPublicBuckets",
                    ),
                    True,
                ),
                policy_status={"IsPublic": False},
            )
        )
        assert await store.assert_private() == {"public_access_block": True, "policy_status": True}

    @pytest.mark.asyncio
    async def test_unimplemented_probes_are_reported_as_unknown_not_as_private(self) -> None:
        """A store that does not implement the call cannot be read as
        'private'; the verdict says None and the caller decides."""
        store = _store(
            _FakeS3Client(
                public_access_block=_client_error("NotImplemented", op="GetPublicAccessBlock"),
                policy_status=_client_error("MethodNotAllowed", op="GetBucketPolicyStatus"),
            )
        )
        assert await store.assert_private() == {"public_access_block": None, "policy_status": None}

    @pytest.mark.asyncio
    async def test_a_real_probe_error_is_not_swallowed(self) -> None:
        store = _store(
            _FakeS3Client(policy_status=_client_error("AccessDenied", op="GetBucketPolicyStatus"))
        )
        with pytest.raises(ClientError):
            await store.assert_private()


# -------------------------------------------------------------------- put


class TestPut:
    @pytest.mark.asyncio
    async def test_put_never_sets_an_acl_and_is_conditional(self) -> None:
        """No ACL, ever; and `IfNoneMatch="*"` so the store enforces
        write-once (O1 F5)."""
        client = _FakeS3Client()
        await _store(client).put(
            key=_SENTINEL_KEY, body=b"%PDF-1.4", content_type="application/pdf"
        )
        (call,) = client.put_calls
        assert "ACL" not in call
        assert call["IfNoneMatch"] == "*"
        assert call["Key"] == _SENTINEL_KEY
        assert call["ContentType"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_second_put_under_a_live_key_is_refused_by_the_store(self, caplog) -> None:
        """O1 F5: put A, put B under the same key -> 412 -> ArtifactAlreadyExists,
        and the bytes under the key are still A's (the fake models the
        conditional write)."""
        client = _FakeS3Client()
        store = _store(client)
        await store.put(key=_SENTINEL_KEY, body=b"A", content_type="application/pdf")
        with caplog.at_level(logging.ERROR), pytest.raises(ArtifactAlreadyExists):
            await store.put(key=_SENTINEL_KEY, body=b"B", content_type="application/pdf")
        assert len(client.put_calls) == 2
        assert "SENTINELPRACTICE" not in caplog.text

    @pytest.mark.asyncio
    async def test_oversized_body_is_refused_before_any_upload_call(self) -> None:
        """O1 F12: the ceiling binds on the way in."""
        client = _FakeS3Client()
        with pytest.raises(ValueError, match="MAX_ARTIFACT_BYTES"):
            await _store(client).put(
                key=_SENTINEL_KEY,
                body=b"x" * (MAX_ARTIFACT_BYTES + 1),
                content_type="application/pdf",
            )
        assert client.put_calls == []

    @pytest.mark.asyncio
    async def test_exactly_the_ceiling_is_accepted(self) -> None:
        client = _FakeS3Client()
        await _store(client).put(
            key=_SENTINEL_KEY, body=b"x" * MAX_ARTIFACT_BYTES, content_type="application/pdf"
        )
        assert len(client.put_calls) == 1


# ------------------------------------------------------------------ retry


class TestRetry:
    @pytest.mark.asyncio
    async def test_transient_put_failure_retries_with_backoff_then_succeeds(self) -> None:
        sleeps: list[float] = []
        client = _FakeS3Client(put_failures=[_client_error("SlowDown"), _client_error("503")])
        await _store(client, sleeps=sleeps).put(
            key=_SENTINEL_KEY, body=b"x", content_type="application/pdf"
        )
        assert len(client.put_calls) == 3
        assert sleeps == [2.0, 4.0]

    @pytest.mark.asyncio
    async def test_retry_budget_is_three_calls_total(self) -> None:
        sleeps: list[float] = []
        client = _FakeS3Client(put_failures=[_client_error("503")] * 5)
        with pytest.raises(ClientError):
            await _store(client, sleeps=sleeps).put(
                key=_SENTINEL_KEY, body=b"x", content_type="application/pdf"
            )
        assert len(client.put_calls) == 3
        assert sleeps == [2.0, 4.0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc",
        [
            _client_error("AccessDenied"),
            _client_error("NoSuchBucket"),
            ParamValidationError(report="bad param"),
            NoCredentialsError(),
        ],
    )
    async def test_permanent_failures_are_not_retried(self, exc) -> None:
        """O1 F9: botocore's own permanent errors used to retry as
        'transient' because every BotoCoreError did."""
        sleeps: list[float] = []
        client = _FakeS3Client(put_failures=[exc])
        with pytest.raises(type(exc)):
            await _store(client, sleeps=sleeps).put(
                key=_SENTINEL_KEY, body=b"x", content_type="application/pdf"
            )
        assert len(client.put_calls) == 1
        assert sleeps == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc",
        [
            _client_error("InternalError"),
            _client_error("Whatever", status=500),
            EndpointConnectionError(endpoint_url="https://fly.storage.tigris.dev"),
        ],
    )
    async def test_wire_level_transients_are_retried(self, exc) -> None:
        sleeps: list[float] = []
        client = _FakeS3Client(put_failures=[exc])
        await _store(client, sleeps=sleeps).put(
            key=_SENTINEL_KEY, body=b"x", content_type="application/pdf"
        )
        assert len(client.put_calls) == 2
        assert sleeps == [2.0]

    @pytest.mark.asyncio
    async def test_get_retries_a_transient_and_restarts_the_whole_read(self) -> None:
        """O1 F8: GET had no retry loop. First GET 503, second succeeds; the
        body is read once from the successful response."""
        data = b"%PDF-1.4 ok"
        sleeps: list[float] = []
        client = _FakeS3Client(
            get_failures=[_client_error("503", op="GetObject")], get_object_bytes=data
        )
        got = await _store(client, sleeps=sleeps).fetch_and_verify(
            key=_SENTINEL_KEY, expected_digest=_digest(data)
        )
        assert got == data
        assert len(client.get_calls) == 2
        assert sleeps == [2.0]
        assert len(client.bodies) == 1


# ----------------------------------------------------------- fetch/verify


class TestFetchAndVerify:
    @pytest.mark.asyncio
    async def test_matching_digest_returns_the_bytes(self) -> None:
        data = b"%PDF-1.4 genuine"
        client = _FakeS3Client(get_object_bytes=data)
        assert (
            await _store(client).fetch_and_verify(key=_SENTINEL_KEY, expected_digest=_digest(data))
            == data
        )

    @pytest.mark.asyncio
    async def test_digest_mismatch_refuses_and_returns_nothing(self, caplog) -> None:
        client = _FakeS3Client(get_object_bytes=b"tampered bytes")
        with caplog.at_level(logging.ERROR), pytest.raises(ArtifactDigestMismatch):
            await _store(client).fetch_and_verify(
                key=_SENTINEL_KEY, expected_digest=_digest(b"original")
            )
        assert "digest_mismatch" in caplog.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize("code", ["NoSuchKey", "404"])
    async def test_missing_object_maps_to_artifact_object_missing(self, code) -> None:
        client = _FakeS3Client(get_failures=[_client_error(code, op="GetObject")])
        with pytest.raises(ArtifactObjectMissing):
            await _store(client).fetch_and_verify(key=_SENTINEL_KEY, expected_digest="0" * 64)
        assert len(client.get_calls) == 1

    @pytest.mark.asyncio
    async def test_body_is_closed_on_success_and_on_every_refusal(self) -> None:
        """O1 F7."""
        data = b"ok"
        client = _FakeS3Client(get_object_bytes=data)
        await _store(client).fetch_and_verify(key=_SENTINEL_KEY, expected_digest=_digest(data))
        assert client.bodies[-1].closed
        client = _FakeS3Client(
            get_object_bytes=b"x" * 10, get_object_content_length=MAX_ARTIFACT_BYTES + 1
        )
        with pytest.raises(ArtifactDigestMismatch):
            await _store(client).fetch_and_verify(key=_SENTINEL_KEY, expected_digest="0" * 64)
        assert client.bodies[-1].closed
        assert client.bodies[-1].total_bytes_returned == 0


class TestKeyRedaction:
    """O1 F4: storage keys are not emitted in logs or exception messages."""

    @pytest.mark.asyncio
    async def test_no_refusal_path_leaks_the_key(self, caplog) -> None:
        cases = [
            _FakeS3Client(get_object_bytes=b"tampered"),
            _FakeS3Client(get_failures=[_client_error("NoSuchKey", op="GetObject")]),
            _FakeS3Client(get_object_bytes=b"x", get_object_content_length=MAX_ARTIFACT_BYTES + 1),
            _FakeS3Client(
                get_object_bytes=b"x" * (MAX_ARTIFACT_BYTES + 1), get_object_content_length=None
            ),
            _FakeS3Client(existing_keys={_SENTINEL_KEY}),
        ]
        with caplog.at_level(logging.DEBUG):
            for client in cases[:4]:
                with pytest.raises((ArtifactDigestMismatch, ArtifactObjectMissing)) as info:
                    await _store(client).fetch_and_verify(
                        key=_SENTINEL_KEY, expected_digest=_digest(b"original")
                    )
                assert "SENTINEL" not in str(info.value)
                assert "SENTINEL" not in repr(info.value.args)
            with pytest.raises(ArtifactAlreadyExists) as info:
                await _store(cases[4]).put(
                    key=_SENTINEL_KEY, body=b"x", content_type="application/pdf"
                )
            assert "SENTINEL" not in str(info.value)
        assert "SENTINEL" not in caplog.text
        assert caplog.records, "the refusals must still be logged, just without the key"


class TestFetchAndVerifyBoundedRead:
    """O1 F6 and the original F4/F5: no path reads unbounded, and the body
    must be EXACTLY what was declared and expected."""

    @pytest.mark.asyncio
    async def test_declared_size_over_ceiling_is_refused_before_any_read(self, caplog) -> None:
        client = _FakeS3Client(
            get_object_bytes=b"x" * 100, get_object_content_length=MAX_ARTIFACT_BYTES + 1
        )
        with caplog.at_level(logging.ERROR), pytest.raises(ArtifactDigestMismatch):
            await _store(client).fetch_and_verify(
                key=_SENTINEL_KEY, expected_digest=_digest(b"x" * 100)
            )
        assert client.bodies[-1].total_bytes_returned == 0
        assert "declared_size_refused" in caplog.text

    @pytest.mark.asyncio
    async def test_declared_size_disagreeing_with_row_is_refused_before_any_read(self) -> None:
        data = b"x" * 500
        client = _FakeS3Client(get_object_bytes=data, get_object_content_length=500)
        with pytest.raises(ArtifactDigestMismatch):
            await _store(client).fetch_and_verify(
                key=_SENTINEL_KEY, expected_digest=_digest(data), expected_byte_length=400
            )
        assert client.bodies[-1].total_bytes_returned == 0

    @pytest.mark.asyncio
    async def test_read_is_bounded_at_ceiling_plus_one_when_the_header_lies_small(self) -> None:
        huge = b"x" * (MAX_ARTIFACT_BYTES + 5000)
        client = _FakeS3Client(get_object_bytes=huge, get_object_content_length=100)
        with pytest.raises(ArtifactDigestMismatch):
            await _store(client).fetch_and_verify(key=_SENTINEL_KEY, expected_digest=_digest(huge))
        body = client.bodies[-1]
        assert body.max_amt_requested == MAX_ARTIFACT_BYTES + 1
        assert body.total_bytes_returned <= MAX_ARTIFACT_BYTES + 1

    @pytest.mark.asyncio
    async def test_missing_or_non_integer_content_length_still_bounds_and_proves_eof(self) -> None:
        data = b"%PDF-1.4 fine"
        for declared in (None, "13", 13.0):
            client = _FakeS3Client(get_object_bytes=data, get_object_content_length=declared)
            assert (
                await _store(client).fetch_and_verify(
                    key=_SENTINEL_KEY, expected_digest=_digest(data)
                )
                == data
            )
            assert client.bodies[-1].max_amt_requested == MAX_ARTIFACT_BYTES + 1
        client = _FakeS3Client(
            get_object_bytes=b"x" * (MAX_ARTIFACT_BYTES + 1), get_object_content_length=None
        )
        with pytest.raises(ArtifactDigestMismatch):
            await _store(client).fetch_and_verify(key=_SENTINEL_KEY, expected_digest="0" * 64)

    @pytest.mark.asyncio
    async def test_body_longer_than_declared_but_under_ceiling_is_refused_even_with_matching_digest(
        self,
    ) -> None:
        """O1 F6, verbatim: declare 100, return 101, digest of the 101 -> refuse."""
        actual = b"y" * 101
        client = _FakeS3Client(get_object_bytes=actual, get_object_content_length=100)
        with pytest.raises(ArtifactDigestMismatch):
            await _store(client).fetch_and_verify(
                key=_SENTINEL_KEY, expected_digest=_digest(actual), expected_byte_length=100
            )

    @pytest.mark.asyncio
    async def test_body_shorter_than_declared_is_refused_even_with_matching_digest(self) -> None:
        actual = b"y" * 99
        client = _FakeS3Client(get_object_bytes=actual, get_object_content_length=100)
        with pytest.raises(ArtifactDigestMismatch):
            await _store(client).fetch_and_verify(
                key=_SENTINEL_KEY, expected_digest=_digest(actual)
            )

    @pytest.mark.asyncio
    async def test_exactly_the_ceiling_is_served(self) -> None:
        data = b"z" * MAX_ARTIFACT_BYTES
        client = _FakeS3Client(get_object_bytes=data)
        assert (
            await _store(client).fetch_and_verify(
                key=_SENTINEL_KEY,
                expected_digest=_digest(data),
                expected_byte_length=MAX_ARTIFACT_BYTES,
            )
            == data
        )

    @pytest.mark.asyncio
    async def test_one_over_the_ceiling_is_refused_without_a_digest_pass(self) -> None:
        data = b"z" * (MAX_ARTIFACT_BYTES + 1)
        client = _FakeS3Client(get_object_bytes=data, get_object_content_length=None)
        with pytest.raises(ArtifactDigestMismatch):
            await _store(client).fetch_and_verify(key=_SENTINEL_KEY, expected_digest=_digest(data))


# -------------------------------------------------------------- the fake


class TestFakeParity:
    """O1 F10: the in-memory double refuses what the adapter refuses, in the
    adapter's order, so a service test against the fake proves something."""

    @pytest.mark.asyncio
    async def test_fake_put_refuses_over_ceiling_and_second_write(self) -> None:
        fake = InMemoryArtifactObjectStore()
        with pytest.raises(ValueError, match="MAX_ARTIFACT_BYTES"):
            await fake.put(
                key="k", body=b"x" * (MAX_ARTIFACT_BYTES + 1), content_type="application/pdf"
            )
        await fake.put(key="k", body=b"A", content_type="application/pdf")
        with pytest.raises(ArtifactAlreadyExists):
            await fake.put(key="k", body=b"B", content_type="application/pdf")
        assert await fake.fetch_and_verify(key="k", expected_digest=_digest(b"A")) == b"A"

    @pytest.mark.asyncio
    async def test_fake_fetch_checks_size_before_digest_and_ceiling_without_expected_length(
        self,
    ) -> None:
        fake = InMemoryArtifactObjectStore()
        big = b"x" * (MAX_ARTIFACT_BYTES + 1)
        fake.corrupt("k", replacement=big)  # bypasses the write-once rule, as tampering would
        with pytest.raises(ArtifactDigestMismatch):
            await fake.fetch_and_verify(key="k", expected_digest=_digest(big))
        fake.corrupt("k", replacement=b"x" * 10)
        with pytest.raises(ArtifactDigestMismatch):
            await fake.fetch_and_verify(
                key="k", expected_digest=_digest(b"x" * 10), expected_byte_length=9
            )
        fake.delete_for_test("k")
        with pytest.raises(ArtifactObjectMissing):
            await fake.fetch_and_verify(key="k", expected_digest="0" * 64)

    def test_the_test_only_seam_is_not_used_outside_tests(self) -> None:
        """O1 F3, the check the docstring promises:
        `TigrisArtifactObjectStore.for_tests(` appears nowhere under
        `backend/` except the tests tree (other modules have their own,
        unrelated `for_tests` seams -- the qualified name is the check)."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[3]
        hits = [
            p
            for p in root.rglob("*.py")
            if "tests" not in p.parts
            and "TigrisArtifactObjectStore.for_tests(" in p.read_text(encoding="utf-8", errors="ignore")
        ]
        assert hits == [], hits
