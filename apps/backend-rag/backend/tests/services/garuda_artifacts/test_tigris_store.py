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
    IncompleteReadError,
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
    key_ref,
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

    def __init__(
        self, data: bytes, *, declared: int | None = None, short_reads: bool = False
    ) -> None:
        self._data = data
        self._offset = 0
        self._declared = declared
        self._short_reads = short_reads
        self.max_amt_requested: int | None = None
        self.total_bytes_returned = 0
        self.read_calls = 0
        self.closed = False

    def read(self, amt: int | None = None) -> bytes:
        self.read_calls += 1
        # botocore: a short read is legal; on an EMPTY read with amt > 0 the
        # declared length is verified and IncompleteReadError raised.
        if self._short_reads and amt is not None and amt > 1000:
            amt = 1000  # a short read: fewer bytes than asked, not EOF
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
        if (
            (amt is None or (not chunk and amt > 0))
            and self._declared is not None
            and self._offset != self._declared
        ):
            raise IncompleteReadError(actual_bytes=self._offset, expected_bytes=self._declared)
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
        delete_failures: list[Exception] | None = None,
        get_object_bytes: bytes | None = None,
        get_object_content_length: object = _UNSET,
        existing_keys: set[str] | None = None,
        honours_if_none_match: bool = True,
        short_reads: bool = False,
        head_failures: list[Exception] | None = None,
        head_without_etag: bool = False,
        public_access_block: dict | Exception | None = None,
        policy_status: dict | Exception | None = None,
    ) -> None:
        self.put_calls: list[dict] = []
        self.get_calls: list[dict] = []
        self.delete_calls: list[dict] = []
        self._delete_failures = list(delete_failures or [])
        self._put_failures = list(put_failures or [])
        self._get_failures = list(get_failures or [])
        self._get_object_bytes = get_object_bytes
        self._get_object_content_length = get_object_content_length
        self._existing_keys = set(existing_keys or ())
        self.stored: dict[str, bytes] = dict.fromkeys(self._existing_keys, b"<pre-existing>")
        self._honours_if_none_match = honours_if_none_match
        self._short_reads = short_reads
        self._head_failures = list(head_failures or [])
        self._head_without_etag = head_without_etag
        self.head_calls: list[dict] = []
        self._public_access_block = public_access_block
        self._policy_status = policy_status
        self.bodies: list[_BytesBody] = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        if self._put_failures:
            raise self._put_failures.pop(0)
        if (
            self._honours_if_none_match
            and kwargs.get("IfNoneMatch") == "*"
            and kwargs["Key"] in self._existing_keys
        ):
            raise _client_error("PreconditionFailed", status=412)
        self._existing_keys.add(kwargs["Key"])
        self.stored[kwargs["Key"]] = bytes(kwargs["Body"])
        return {}

    def head_object(self, **kwargs):
        self.head_calls.append(kwargs)
        if self._head_failures:
            raise self._head_failures.pop(0)
        if kwargs["Key"] not in self._existing_keys:
            raise _client_error("404", status=404, op="HeadObject")
        if self._head_without_etag:
            return {}
        etag = hashlib.md5(self.stored[kwargs["Key"]], usedforsecurity=False).hexdigest()
        return {"ETag": f'"{etag}"'}

    def get_object(self, **kwargs):
        self.get_calls.append(kwargs)
        if self._get_failures:
            raise self._get_failures.pop(0)
        if self._get_object_bytes is None and kwargs["Key"] not in self._existing_keys:
            raise _client_error("NoSuchKey", op="GetObject")
        data = (
            self._get_object_bytes
            if self._get_object_bytes is not None
            else self.stored.get(kwargs["Key"], b"")
        )
        resp: dict = {}
        if self._get_object_content_length is _UNSET:
            resp["ContentLength"] = len(data)
        elif self._get_object_content_length is not None:
            resp["ContentLength"] = self._get_object_content_length
        declared = resp.get("ContentLength") if isinstance(resp.get("ContentLength"), int) else None
        body = _BytesBody(data, declared=declared, short_reads=self._short_reads)
        self.bodies.append(body)
        resp["Body"] = body
        return resp

    def delete_object(self, **kwargs):
        self.delete_calls.append(kwargs)
        if self._delete_failures:
            raise self._delete_failures.pop(0)
        if kwargs["Key"] not in self._existing_keys:
            raise _client_error("NoSuchKey", op="DeleteObject")
        self._existing_keys.discard(kwargs["Key"])
        self.stored.pop(kwargs["Key"], None)
        return {}

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
        assert captured["aws_secret_access_key"] == "scoped-secret"  # pragma: allowlist secret
        assert captured["endpoint_url"] == tigris_store.DEFAULT_ENDPOINT_URL
        # `total_max_attempts` INCLUDES the initial request (botocore's docstring);
        # `max_attempts` would have been one RETRY. What a unit test can observe
        # is the configuration handed to the SDK, not wire attempts -- stated.
        assert captured["config"].retries == {"total_max_attempts": 1, "mode": "standard"}


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
            "https://evil@fly.storage.tigris.dev",  # userinfo (O2)
            "https://fly.storage.tigris.dev:8443",  # port (O2)
            "https://fly.storage.tigris.dev/prefix",  # path (O2)
            "https://fly.storage.tigris.dev?x=1",  # query (O2)
            "https://fly.storage.tigris.dev.",  # trailing dot
            "https://flý.storage.tigris.dev",  # non-ASCII label (O2)
            "https://fly.storage.tigris.dev:notaport",  # malformed port (O3 N8)
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
    async def test_malformed_probe_answers_are_unknown_not_private(self) -> None:
        """O3 N3: PolicyStatus={} used to read as verified-private."""
        store = _store(_FakeS3Client(policy_status={}))
        with pytest.raises(GarudaArtifactsStoreUnavailable, match="VERIFIED"):
            await store.assert_private()
        store = _store(_FakeS3Client(public_access_block={"BlockPublicAcls": True}))
        with pytest.raises(GarudaArtifactsStoreUnavailable, match="VERIFIED"):
            await store.assert_private()
        assert await store.assert_private(require_verified=False) == {
            "public_access_block": None,
            "policy_status": None,
        }

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
    async def test_unimplemented_probes_fail_closed_unless_the_caller_opts_out(self) -> None:
        """O2 F1: two unknowns are not a private bucket. Refused by default;
        the caller that knows its store cannot answer says so explicitly."""
        store = _store(
            _FakeS3Client(
                public_access_block=_client_error("NotImplemented", op="GetPublicAccessBlock"),
                policy_status=_client_error("MethodNotAllowed", op="GetBucketPolicyStatus"),
            )
        )
        with pytest.raises(GarudaArtifactsStoreUnavailable, match="VERIFIED"):
            await store.assert_private()
        assert await store.assert_private(require_verified=False) == {
            "public_access_block": None,
            "policy_status": None,
        }

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
        # Layer one (HEAD) refused before layer two (IfNoneMatch) was needed.
        assert len(client.put_calls) == 1
        assert client.stored[_SENTINEL_KEY] == b"A"
        assert "SENTINELPRACTICE" not in caplog.text

    @pytest.mark.asyncio
    async def test_a_store_that_ignores_if_none_match_still_cannot_overwrite(self) -> None:
        """O2 F5: the HEAD layer catches a non-compliant store."""
        client = _FakeS3Client(honours_if_none_match=False)
        store = _store(client)
        await store.put(key=_SENTINEL_KEY, body=b"A", content_type="application/pdf")
        with pytest.raises(ArtifactAlreadyExists):
            await store.put(key=_SENTINEL_KEY, body=b"B", content_type="application/pdf")
        assert client.stored[_SENTINEL_KEY] == b"A"

    @pytest.mark.asyncio
    async def test_a_412_on_a_retry_after_our_own_commit_is_a_success(self) -> None:
        """O2 N1: first attempt commits but surfaces a 500; the retry sees 412;
        the ETag is our body's MD5, so this is our write, not a collision."""
        client = _FakeS3Client()
        original_put = client.put_object

        def put_then_500(**kwargs):
            original_put(**kwargs)
            raise _client_error("InternalError", status=500)

        client.put_object = put_then_500  # type: ignore[method-assign]
        await _store(client).put(key=_SENTINEL_KEY, body=b"A", content_type="application/pdf")
        assert client.stored[_SENTINEL_KEY] == b"A"

    @pytest.mark.asyncio
    async def test_head_200_without_etag_is_an_existing_object_not_absence(self) -> None:
        """O3 N4."""
        client = _FakeS3Client(
            existing_keys={_SENTINEL_KEY}, honours_if_none_match=False, head_without_etag=True
        )
        with pytest.raises(ArtifactAlreadyExists):
            await _store(client).put(key=_SENTINEL_KEY, body=b"B", content_type="application/pdf")
        assert client.put_calls == []

    @pytest.mark.asyncio
    async def test_a_permanent_head_failure_aborts_before_any_put(self) -> None:
        """O3: the HEAD layer is a new dependency; permanent failures surface as themselves."""
        client = _FakeS3Client(head_failures=[_client_error("AccessDenied", op="HeadObject")])
        with pytest.raises(ClientError):
            await _store(client).put(key=_SENTINEL_KEY, body=b"A", content_type="application/pdf")
        assert client.put_calls == []

    @pytest.mark.asyncio
    async def test_a_412_on_a_retry_with_an_unreadable_etag_is_a_collision(self) -> None:
        """O3 N1: an absent ETag cannot prove the write is ours -> conservative."""
        client = _FakeS3Client(head_without_etag=True)
        original_put = client.put_object

        def put_then_500(**kwargs):
            original_put(**kwargs)
            raise _client_error("InternalError", status=500)

        client.put_object = put_then_500  # type: ignore[method-assign]
        with pytest.raises(ArtifactAlreadyExists):
            await _store(client).put(key=_SENTINEL_KEY, body=b"A", content_type="application/pdf")

    @pytest.mark.asyncio
    async def test_a_412_on_a_retry_for_someone_elses_object_is_a_collision(self) -> None:
        client = _FakeS3Client()
        calls = {"n": 0}

        def put_500_then_other_wins(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                client._existing_keys.add(kwargs["Key"])
                client.stored[kwargs["Key"]] = b"SOMEONE-ELSE"
                raise _client_error("InternalError", status=500)
            raise _client_error("PreconditionFailed", status=412)

        client.put_object = put_500_then_other_wins  # type: ignore[method-assign]
        with pytest.raises(ArtifactAlreadyExists):
            await _store(client).put(key=_SENTINEL_KEY, body=b"A", content_type="application/pdf")
        assert client.stored[_SENTINEL_KEY] == b"SOMEONE-ELSE"

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
            _client_error("AccessDenied", status=500),
        ],
    )
    async def test_permanent_failures_are_not_retried(self, exc) -> None:
        """O1/O2 F9: includes a permanent Error.Code wearing a 5xx."""
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
    async def test_digest_mismatch_log_record_carries_key_ref_not_the_key(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Gate-6334 C1: mutation (d) -- `_key_ref(key)` -> `key` in the
        digest-mismatch log at the end of `fetch_and_verify` -- survived the
        S2a suite, because no test read that LOG RECORD. This one does: the
        record's `key_ref` is the digest, and the sentinel key appears in
        no field of the record and nowhere in the captured text."""
        caplog.set_level(logging.ERROR, logger="backend.services.garuda_artifacts.tigris_store")
        client = _FakeS3Client(get_object_bytes=b"tampered")
        with pytest.raises(ArtifactDigestMismatch):
            await _store(client).fetch_and_verify(
                key=_SENTINEL_KEY, expected_digest=_digest(b"original")
            )
        records = [
            r for r in caplog.records if r.getMessage() == "garuda_artifacts.digest_mismatch"
        ]
        assert len(records) == 1, "exactly one digest-mismatch record per refusal"
        assert records[0].key_ref == key_ref(_SENTINEL_KEY)  # type: ignore[attr-defined]
        assert _SENTINEL_KEY not in caplog.text
        assert all(_SENTINEL_KEY not in str(v) for v in records[0].__dict__.values())

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
            assert client.bodies[-1].total_bytes_returned == len(data)
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
        with pytest.raises(
            IncompleteReadError
        ):  # botocore's own length check, after the retry budget (O3 N6)
            await _store(client).fetch_and_verify(
                key=_SENTINEL_KEY, expected_digest=_digest(actual), expected_byte_length=100
            )

    @pytest.mark.asyncio
    async def test_body_shorter_than_declared_is_refused_even_with_matching_digest(self) -> None:
        """O2 F6: the fake body now does what botocore does -- raises
        IncompleteReadError on the EOF probe -- and the adapter maps it."""
        actual = b"y" * 99
        client = _FakeS3Client(get_object_bytes=actual, get_object_content_length=100)
        with pytest.raises(
            IncompleteReadError
        ):  # botocore's own length check, after the retry budget (O3 N6)
            await _store(client).fetch_and_verify(
                key=_SENTINEL_KEY, expected_digest=_digest(actual)
            )

    @pytest.mark.asyncio
    async def test_a_truncated_body_is_retried_then_refused(self) -> None:
        """O3 N6: a body cut short on the wire is a wire fault -- the GET
        restarts whole; only an exhausted budget is a refusal."""
        data = b"y" * 99
        sleeps: list[float] = []
        client = _FakeS3Client(get_object_bytes=data, get_object_content_length=100)
        with pytest.raises(IncompleteReadError):
            await _store(client, sleeps=sleeps).fetch_and_verify(
                key=_SENTINEL_KEY, expected_digest=_digest(data)
            )
        assert len(client.get_calls) == 3 and sleeps == [2.0, 4.0]
        assert all(b.closed for b in client.bodies)

    @pytest.mark.asyncio
    async def test_body_is_closed_on_every_refusal_path(self) -> None:
        refusals = [
            _FakeS3Client(
                get_object_bytes=b"x" * 10, get_object_content_length=MAX_ARTIFACT_BYTES + 1
            ),
            _FakeS3Client(
                get_object_bytes=b"x" * (MAX_ARTIFACT_BYTES + 1), get_object_content_length=None
            ),
            _FakeS3Client(get_object_bytes=b"y" * 101, get_object_content_length=100),
            _FakeS3Client(get_object_bytes=b"y" * 99, get_object_content_length=100),
            _FakeS3Client(get_object_bytes=b"tampered"),
        ]
        for client in refusals:
            with pytest.raises((ArtifactDigestMismatch, IncompleteReadError)):
                await _store(client).fetch_and_verify(
                    key=_SENTINEL_KEY, expected_digest=_digest(b"original")
                )
            assert all(b.closed for b in client.bodies)
        assert refusals[0].bodies[-1].total_bytes_returned == 0

    @pytest.mark.asyncio
    async def test_short_reads_are_accumulated_not_mistaken_for_eof(self) -> None:
        """O2 F6: a single read(amt) may return fewer than amt bytes."""
        data = b"q" * 3000
        client = _FakeS3Client(get_object_bytes=data, short_reads=True)
        assert (
            await _store(client).fetch_and_verify(key=_SENTINEL_KEY, expected_digest=_digest(data))
            == data
        )
        assert client.bodies[-1].read_calls > 2
        big = b"q" * (MAX_ARTIFACT_BYTES + 1)
        client = _FakeS3Client(
            get_object_bytes=big, get_object_content_length=None, short_reads=True
        )
        with pytest.raises(ArtifactDigestMismatch):
            await _store(client).fetch_and_verify(key=_SENTINEL_KEY, expected_digest=_digest(big))
        assert client.bodies[-1].total_bytes_returned <= MAX_ARTIFACT_BYTES + 1

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


# ----------------------------------------------------------------- delete


class TestDelete:
    """Decision #39: one key, idempotent, hashed in logs, wire-level retry.
    LIMIT, stated: the adapter cannot tell a superseded key from a live
    one; a consumer that reaches the port can delete anything it names.
    That rule is the service's (S3)."""

    @pytest.mark.asyncio
    async def test_delete_removes_exactly_one_key_and_nothing_else(self, caplog) -> None:
        client = _FakeS3Client(existing_keys={_SENTINEL_KEY, "artifacts/other/keep"})
        with caplog.at_level(logging.INFO):
            await _store(client).delete(key=_SENTINEL_KEY)
        (call,) = client.delete_calls
        assert call == {"Bucket": "garuda-voa-artifacts-test", "Key": _SENTINEL_KEY}
        assert "artifacts/other/keep" in client._existing_keys
        assert "SENTINEL" not in caplog.text
        assert "garuda_artifacts.deleted" in caplog.text

    @pytest.mark.asyncio
    async def test_delete_then_fetch_is_missing(self) -> None:
        client = _FakeS3Client(existing_keys={_SENTINEL_KEY})
        store = _store(client)
        await store.delete(key=_SENTINEL_KEY)
        with pytest.raises(ArtifactObjectMissing):
            await store.fetch_and_verify(key=_SENTINEL_KEY, expected_digest="0" * 64)

    @pytest.mark.asyncio
    async def test_delete_of_an_absent_key_is_a_success(self, caplog) -> None:
        client = _FakeS3Client()
        with caplog.at_level(logging.INFO):
            await _store(client).delete(key=_SENTINEL_KEY)
        assert len(client.delete_calls) == 1
        assert "delete_already_absent" in caplog.text
        assert "SENTINEL" not in caplog.text

    @pytest.mark.asyncio
    async def test_delete_retries_a_transient_and_raises_a_permanent(self) -> None:
        sleeps: list[float] = []
        client = _FakeS3Client(
            existing_keys={_SENTINEL_KEY}, delete_failures=[_client_error("503", op="DeleteObject")]
        )
        await _store(client, sleeps=sleeps).delete(key=_SENTINEL_KEY)
        assert len(client.delete_calls) == 2 and sleeps == [2.0]
        client = _FakeS3Client(
            existing_keys={_SENTINEL_KEY},
            delete_failures=[_client_error("AccessDenied", op="DeleteObject")],
        )
        with pytest.raises(ClientError):
            await _store(client).delete(key=_SENTINEL_KEY)
        assert len(client.delete_calls) == 1
        assert _SENTINEL_KEY in client._existing_keys

    @pytest.mark.asyncio
    async def test_fake_delete_is_in_parity(self) -> None:
        fake = InMemoryArtifactObjectStore()
        await fake.put(key="k", body=b"A", content_type="application/pdf")
        await fake.delete(key="k")
        await fake.delete(key="k")  # idempotent
        with pytest.raises(ArtifactObjectMissing):
            await fake.fetch_and_verify(key="k", expected_digest=_digest(b"A"))
        await fake.put(key="k", body=b"B", content_type="application/pdf")  # key is free again


# -------------------------------------------------------------- the fake


class TestFakeParity:
    """O1 F10: the in-memory double refuses what the adapter refuses, in the
    adapter's order, so a service test against the fake proves something."""

    @pytest.mark.asyncio
    async def test_fake_exceptions_carry_the_key_ref_not_the_key(self) -> None:
        """K3 (second reader): the fake's messages used to carry the raw key
        while the adapter's carry sha256(key)[:12]; a service test asserting
        on a message would have baked in a shape production never emits."""
        fake = InMemoryArtifactObjectStore()
        await fake.put(key=_SENTINEL_KEY, body=b"A", content_type="application/pdf")
        raised: list[BaseException] = []
        for coro in (
            fake.put(key=_SENTINEL_KEY, body=b"B", content_type="application/pdf"),
            fake.fetch_and_verify(key=_SENTINEL_KEY, expected_digest=_digest(b"other")),
            fake.fetch_and_verify(key="absent-" + _SENTINEL_KEY, expected_digest=_digest(b"A")),
        ):
            with pytest.raises(
                (ArtifactAlreadyExists, ArtifactDigestMismatch, ArtifactObjectMissing)
            ) as ei:
                await coro
            raised.append(ei.value)
        for exc in raised:
            assert _SENTINEL_KEY not in str(exc) and _SENTINEL_KEY not in repr(exc.args)
        assert str(raised[0]) == key_ref(_SENTINEL_KEY) == tigris_store._key_ref(_SENTINEL_KEY)

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
        unrelated `for_tests` seams -- the qualified name is the check).
        LIMIT: a textual scan of `backend/`; an alias, reflection or a caller
        outside that tree evades it. It is a tripwire, not a boundary."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[3]
        hits = [
            p
            for p in root.rglob("*.py")
            if "tests" not in p.parts
            and "TigrisArtifactObjectStore.for_tests("
            in p.read_text(encoding="utf-8", errors="ignore")
        ]
        assert hits == [], hits
