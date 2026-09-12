"""The private GARUDA VOA artifact bucket -- `garuda-voa-artifacts`.

Separate, on purpose, from `nuzantara-warroom-images`
(`services/canva_renderer_v2/_tigris.py`): that bucket's own module
docstring says its prefix is public-read and its purpose is minting public
HTTPS URLs -- reaching for it here would publish a passport-bearing
document to the open internet (spec SS3, fact 13's "trap in plain sight").
This module refuses that bucket by name, and refuses any endpoint that is
not Tigris over HTTPS: a misconfigured endpoint would receive artifact
bodies AND SigV4-signed requests carrying the dedicated key id (O1 F2).

FAIL-CLOSED, OWN CREDENTIALS. This store reads exactly four env vars of its
own and NEVER falls back to `boto3`'s default credential chain, which on
this codebase's existing Tigris client (`_tigris.py::get_s3_client`) means
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` -- the credentials that reach
the PUBLIC bucket. Passing `aws_access_key_id=None` to `boto3.client(...)`
does not raise; it silently activates that same default chain. So presence
is checked FIRST, with `bool(os.environ.get(...))` (`${VAR:+SET}`
semantics -- never logging or printing the value), and the client is
constructed only once both scoped credentials are confirmed present. The
public constructor takes NO client: the only way to hand this class a
client it did not build is `for_tests`, which says so in its name and skips
the env gate, so production wiring cannot reach it by accident (O1 F3).

WHAT THIS MODULE CANNOT DO, stated rather than implied (O1 F1): omitting an
ACL does not make a bucket private when the bucket's own policy grants
public reads. Privacy is a property of the bucket the operator provisions
(spec SS3, pending #G), not of this adapter. What the adapter can do is
refuse the one public bucket this codebase knows by name, and offer
`assert_private()` -- a read-only probe of the bucket's public-access block
and policy status -- for the wiring to call at startup and fail closed on
`IsPublic`. Where the S3 API behind Tigris does not implement those calls,
the probe says so in its return value instead of pretending.

Bucket, and the scoped credential pair, are `operator[secret]` -- this
module does not provision them (spec SS3). Absent, it raises
`GarudaArtifactsStoreUnavailable`; a future caller maps that to `503
SERVICE_UNAVAILABLE`, never a crash. No caller exists in this PR.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.parse import urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    IncompleteReadError,
    ReadTimeoutError,
    ResponseStreamingError,
)

from backend.services.garuda_artifacts.ports import (
    MAX_ARTIFACT_BYTES,
    ArtifactAlreadyExists,
    ArtifactDigestMismatch,
    ArtifactObjectMissing,
)

logger = logging.getLogger(__name__)

BUCKET_ENV = "GARUDA_ARTIFACTS_BUCKET"
ACCESS_KEY_ID_ENV = "GARUDA_ARTIFACTS_ACCESS_KEY_ID"
SECRET_ACCESS_KEY_ENV = "GARUDA_ARTIFACTS_SECRET_ACCESS_KEY"
ENDPOINT_URL_ENV = "GARUDA_ARTIFACTS_ENDPOINT_URL"
DEFAULT_ENDPOINT_URL = "https://fly.storage.tigris.dev"

#: The only endpoint hosts this store will sign requests for (O1 F2). An
#: override exists for a Tigris regional host, never for "any S3".
_ALLOWED_ENDPOINT_HOST_SUFFIXES = (".tigris.dev",)
#: The bucket this codebase already publishes from. Refused by name so that
#: no env-var mixup can route a passport-bearing PDF to a public prefix.
_FORBIDDEN_BUCKETS = frozenset({"nuzantara-warroom-images"})

_MAX_ATTEMPTS = 3
_BACKOFF_BASE_S = 2.0
#: Transient on the wire: retried, with backoff, up to `_MAX_ATTEMPTS` total
#: calls. Everything else -- including botocore's own permanent errors such
#: as `ParamValidationError` and `NoCredentialsError` -- is raised on the
#: first occurrence (O1 F9).
_TRANSIENT_ERROR_CODES = frozenset(
    {
        "500",
        "502",
        "503",
        "504",
        "InternalError",
        "RequestTimeout",
        "ServiceUnavailable",
        "SlowDown",
        "Throttling",
        "ThrottlingException",
    }
)
_TRANSIENT_BOTOCORE_TYPES = (
    EndpointConnectionError,
    ConnectionClosedError,
    ReadTimeoutError,
    ConnectTimeoutError,
)
#: Never retried, whatever HTTP status accompanies them (O2 F9): a 5xx that
#: carries one of these codes is a contradiction, and the permanent code wins
#: because retrying a side-effecting call on a permanent condition duplicates
#: it for nothing.
_PERMANENT_ERROR_CODES = frozenset(
    {
        "AccessDenied",
        "InvalidAccessKeyId",
        "SignatureDoesNotMatch",
        "NoSuchBucket",
        "NoSuchKey",
        "PreconditionFailed",
        "InvalidArgument",
        "InvalidRequest",
        "MalformedXML",
        "EntityTooLarge",
        "MethodNotAllowed",
        "NotImplemented",
    }
)

_T = TypeVar("_T")


class GarudaArtifactsStoreUnavailable(RuntimeError):
    """This store cannot be constructed safely: an env var of its own is
    absent, the endpoint is not Tigris over HTTPS, or the bucket is the one
    public bucket this codebase knows. Never a fallback to the public
    bucket's credentials -- the caller must 503, not retry with a different
    credential source."""


def _key_ref(key: str) -> str:
    """What logs and exception messages carry instead of the storage key
    (O1 F4): a short digest, enough to correlate one refusal with one
    object across a log and a row, not enough to reconstruct the key."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        error = exc.response.get("Error", {})
        code = str(error.get("Code", ""))
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in _PERMANENT_ERROR_CODES:
            return False
        return code in _TRANSIENT_ERROR_CODES or status in (500, 502, 503, 504)
    return isinstance(exc, _TRANSIENT_BOTOCORE_TYPES)


def _validate_endpoint(url: str) -> str:
    """https, an ASCII host ending in a Tigris suffix, and NOTHING else in the
    URL (O2 F2): no userinfo, no port, no path, no query, no fragment. An
    endpoint is a scheme and a host; anything more is a place for a
    confusion to hide."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    extras = (
        parts.username,
        parts.password,
        parts.port,
        parts.path.strip("/") or None,
        parts.query or None,
        parts.fragment or None,
    )
    if (
        parts.scheme != "https"
        or not host.isascii()
        or not host.endswith(_ALLOWED_ENDPOINT_HOST_SUFFIXES)
        or any(extra is not None for extra in extras)
    ):
        raise GarudaArtifactsStoreUnavailable(
            f"garuda artifacts store: {ENDPOINT_URL_ENV} must be an https Tigris endpoint "
            f"(host ending in {', '.join(_ALLOWED_ENDPOINT_HOST_SUFFIXES)}); refusing to sign "
            "requests for any other host"
        )
    return url


def _validate_bucket(bucket: str) -> str:
    if bucket in _FORBIDDEN_BUCKETS:
        raise GarudaArtifactsStoreUnavailable(
            f"garuda artifacts store: {BUCKET_ENV} names the PUBLIC bucket this codebase "
            "publishes from; refusing"
        )
    return bucket


class TigrisArtifactObjectStore:
    """Implements `ArtifactObjectStorePort` (structurally)."""

    def __init__(self) -> None:
        bucket = os.environ.get(BUCKET_ENV)
        access_key_id = os.environ.get(ACCESS_KEY_ID_ENV)
        secret_access_key = os.environ.get(SECRET_ACCESS_KEY_ENV)
        # Presence only -- `bool(value)`; the values themselves are never
        # formatted into any message.
        missing = [
            name
            for name, value in (
                (BUCKET_ENV, bucket),
                (ACCESS_KEY_ID_ENV, access_key_id),
                (SECRET_ACCESS_KEY_ENV, secret_access_key),
            )
            if not value
        ]
        if missing:
            raise GarudaArtifactsStoreUnavailable(
                f"garuda artifacts store: missing env var(s) {', '.join(missing)} -- "
                "refusing to fall back to the public bucket's credentials"
            )
        assert bucket is not None
        self._bucket = _validate_bucket(bucket)
        endpoint_url = _validate_endpoint(os.environ.get(ENDPOINT_URL_ENV, DEFAULT_ENDPOINT_URL))
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name="auto",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            # This module owns the retry budget (`_MAX_ATTEMPTS` calls, its
            # own backoff); the SDK must not multiply it underneath (O1 F9).
            # `total_max_attempts` INCLUDES the initial request (botocore's own
            # docstring): 1 means no SDK retry at all. `max_attempts` would have
            # meant one RETRY on top of the request -- O2 F9 caught the difference.
            config=Config(retries={"total_max_attempts": 1, "mode": "standard"}),
        )
        self._sleep: Callable[[float], None] = time.sleep

    @classmethod
    def for_tests(
        cls,
        *,
        client: Any,
        bucket: str = "garuda-voa-artifacts-test",
        sleep: Callable[[float], None] | None = None,
    ) -> TigrisArtifactObjectStore:
        """The ONLY entry point that accepts a client this class did not
        build, and it skips the env gate on purpose: it is for a fake
        boto3-shaped client in a test. Its name is the boundary (O1 F3) --
        production wiring calls the constructor, and a grep for
        `for_tests(` outside `backend/tests/` is the check."""
        self = cls.__new__(cls)
        self._bucket = _validate_bucket(bucket)
        self._client = client
        self._sleep = sleep if sleep is not None else time.sleep
        return self

    # ------------------------------------------------------------------ retry

    def _with_retries(self, call: Callable[[], _T]) -> _T:
        """Up to `_MAX_ATTEMPTS` calls, backoff between them, ONLY on wire
        errors classified transient; the first permanent error is raised as
        is. A retried fetch restarts the whole GetObject -- never resumes a
        partial read (O1 F8)."""
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                return call()
            except (ClientError, BotoCoreError) as exc:
                if attempt < _MAX_ATTEMPTS and _is_transient(exc):
                    self._sleep(_BACKOFF_BASE_S * attempt)
                    continue
                raise
        raise AssertionError("unreachable: the loop returns or raises")  # pragma: no cover

    # ------------------------------------------------------------------- put

    def _head_etag_sync(self, *, key: str) -> str | None:
        """The stored object's ETag, or None when no object exists under the
        key. Used twice: before a put, to refuse a live key even on a store
        that ignores `IfNoneMatch` (O2 F5); and after a 412 on a RETRIED put,
        to tell our own committed-but-500'd write from someone else's (O2 N1)."""
        try:
            return (
                str(self._client.head_object(Bucket=self._bucket, Key=key).get("ETag", "")).strip(
                    '"'
                )
                or None
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in ("NoSuchKey", "404", "NotFound"):
                return None
            raise

    def _put_sync(self, *, key: str, body: bytes, content_type: str) -> None:
        ref = _key_ref(key)
        own_etag = hashlib.md5(body, usedforsecurity=False).hexdigest()
        # Layer one of write-once: a HEAD before the PUT. A store that honours
        # `IfNoneMatch` makes this redundant; a store that silently ignores it
        # (O2 F5) would otherwise overwrite undetected. TOCTOU between HEAD and
        # PUT is closed by layer two on a compliant store and is the declared
        # residual on a non-compliant one.
        if self._with_retries(lambda: self._head_etag_sync(key=key)) is not None:
            logger.error("garuda_artifacts.put_refused_key_exists", extra={"key_ref": ref})
            raise ArtifactAlreadyExists(ref)
        attempt = 0

        def _once() -> None:
            nonlocal attempt
            attempt += 1
            try:
                # No ACL kwarg -- see the module docstring for what that does
                # and does not buy. `IfNoneMatch="*"` is the write-once rule
                # (spec SS2, O1 F5): the object is created only if no object
                # exists under this key; a second put of any bytes under a
                # live key is refused by the store, not by convention.
                self._client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=body,
                    ContentType=content_type,
                    IfNoneMatch="*",
                )
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if code == "PreconditionFailed" or status == 412:
                    # O2 N1: on a RETRY, a 412 may be our own first attempt
                    # having committed before surfacing a 5xx. Only an ETag
                    # equal to this body's MD5 is ours; anything else is a
                    # real collision.
                    if attempt > 1 and self._head_etag_sync(key=key) == own_etag:
                        logger.info(
                            "garuda_artifacts.put_committed_on_earlier_attempt",
                            extra={"key_ref": ref},
                        )
                        return
                    logger.error("garuda_artifacts.put_refused_key_exists", extra={"key_ref": ref})
                    raise ArtifactAlreadyExists(ref) from exc
                raise

        self._with_retries(_once)

    async def put(self, *, key: str, body: bytes, content_type: str) -> None:
        if len(body) > MAX_ARTIFACT_BYTES:
            # The ceiling binds on the way IN as well (O1 F12): nothing above
            # it is ever uploaded, so nothing above it can be fetched.
            logger.error(
                "garuda_artifacts.put_refused_over_ceiling",
                extra={"key_ref": _key_ref(key), "byte_length": len(body)},
            )
            raise ValueError(
                f"artifact body of {len(body)} bytes exceeds MAX_ARTIFACT_BYTES={MAX_ARTIFACT_BYTES}"
            )
        await asyncio.to_thread(self._put_sync, key=key, body=body, content_type=content_type)

    # ----------------------------------------------------------------- fetch

    def _get_bytes_sync(self, *, key: str, expected_byte_length: int | None) -> bytes:
        ref = _key_ref(key)

        def _once() -> bytes:
            try:
                resp = self._client.get_object(Bucket=self._bucket, Key=key)
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code in ("NoSuchKey", "404"):
                    raise ArtifactObjectMissing(ref) from exc
                raise
            stream = resp["Body"]
            try:
                # `ContentLength` is metadata the GetObject response carries
                # before a single body byte is read, so refuse HERE, before
                # `.read()`, when it already disagrees with the row's own
                # expectation or this store's ceiling. A missing or
                # non-integer length is not trusted: the bounded read below
                # and the EOF check after it are what then bind.
                raw_length = resp.get("ContentLength")
                content_length = raw_length if isinstance(raw_length, int) else None
                if content_length is not None and (
                    content_length > MAX_ARTIFACT_BYTES
                    or (expected_byte_length is not None and content_length != expected_byte_length)
                ):
                    logger.error(
                        "garuda_artifacts.declared_size_refused",
                        extra={"key_ref": ref, "content_length": content_length},
                    )
                    raise ArtifactDigestMismatch(ref)
                # Bounded read even so: metadata the object (or a misbehaving
                # store) could lie about or omit. At most `ceiling + 1` bytes
                # ever sit in this worker's memory, whatever the object claims.
                # Accumulate until the bound is reached or the stream ends: a
                # single `read(amt)` may legally return fewer than `amt` bytes
                # without being at EOF (O2 F6). botocore verifies the declared
                # length itself when a read returns empty, raising
                # IncompleteReadError on a truncated body -- mapped below to the
                # same refusal as every other length disagreement.
                chunks: list[bytes] = []
                remaining = MAX_ARTIFACT_BYTES + 1
                try:
                    while remaining > 0:
                        chunk = stream.read(remaining)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        remaining -= len(chunk)
                    body = b"".join(chunks)
                    if len(body) <= MAX_ARTIFACT_BYTES and stream.read(1):
                        logger.error(
                            "garuda_artifacts.body_longer_than_read", extra={"key_ref": ref}
                        )
                        raise ArtifactDigestMismatch(ref)
                except (IncompleteReadError, ResponseStreamingError) as exc:
                    logger.error(
                        "garuda_artifacts.body_truncated_on_the_wire", extra={"key_ref": ref}
                    )
                    raise ArtifactDigestMismatch(ref) from exc
                if len(body) > MAX_ARTIFACT_BYTES:
                    logger.error("garuda_artifacts.object_exceeds_ceiling", extra={"key_ref": ref})
                    raise ArtifactDigestMismatch(ref)
                # The body must be EXACTLY what was declared and expected (O1
                # F6): shorter than declared is a truncated object, longer
                # than declared is a lying header, and either one must never
                # reach the digest check -- a digest computed over the wrong
                # length can still match an attacker's chosen bytes. One more
                # bounded read proves EOF, because a single `read(amt)` on a
                # streaming body does not.
                if content_length is not None and len(body) != content_length:
                    logger.error(
                        "garuda_artifacts.body_length_disagrees_with_declared",
                        extra={"key_ref": ref, "content_length": content_length, "read": len(body)},
                    )
                    raise ArtifactDigestMismatch(ref)
                if expected_byte_length is not None and len(body) != expected_byte_length:
                    logger.error(
                        "garuda_artifacts.body_length_disagrees_with_row",
                        extra={"key_ref": ref, "expected": expected_byte_length, "read": len(body)},
                    )
                    raise ArtifactDigestMismatch(ref)
                return body
            finally:
                # Drain-or-close on every path, including refusals that never
                # read (O1 F7): an undrained streaming body pins a pooled
                # connection.
                close = getattr(stream, "close", None)
                if callable(close):
                    close()

        return self._with_retries(_once)

    async def fetch_and_verify(
        self, *, key: str, expected_digest: str, expected_byte_length: int | None = None
    ) -> bytes:
        """Fetch, bound, cross-check, hash -- and return bytes ONLY when every
        check passed. `expected_byte_length` is the row's recorded length;
        `None` (no caller exists in this PR) still gets the ceiling, the EOF
        proof and the declared-length agreement; a caller that passes it gets
        the row-agreement check too. Never more than `MAX_ARTIFACT_BYTES + 1`
        bytes are read, plus one byte to prove EOF."""
        body = await asyncio.to_thread(
            self._get_bytes_sync, key=key, expected_byte_length=expected_byte_length
        )
        actual = hashlib.sha256(body).hexdigest()
        if actual != expected_digest:
            logger.error("garuda_artifacts.digest_mismatch", extra={"key_ref": _key_ref(key)})
            raise ArtifactDigestMismatch(_key_ref(key))
        return body

    # ---------------------------------------------------------------- delete

    def _delete_sync(self, *, key: str) -> None:
        ref = _key_ref(key)

        def _once() -> None:
            try:
                self._client.delete_object(Bucket=self._bucket, Key=key)
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code in ("NoSuchKey", "404"):
                    # Idempotent by decision #39: the object is already not
                    # retrievable, which is the state a delete exists to reach.
                    logger.info("garuda_artifacts.delete_already_absent", extra={"key_ref": ref})
                    return
                raise
            logger.info("garuda_artifacts.deleted", extra={"key_ref": ref})

        self._with_retries(_once)

    async def delete(self, *, key: str) -> None:
        """One object, by exact key, idempotent. WHEN is the service's rule
        (S3); this adapter cannot tell a superseded key from a live one."""
        await asyncio.to_thread(self._delete_sync, key=key)

    # ---------------------------------------------------------------- probes

    def _assert_private_sync(self, *, require_verified: bool) -> dict[str, bool | None]:
        """Read-only probe of the bucket's public-access posture (O1 F1).
        Raises `GarudaArtifactsStoreUnavailable` on any positive signal that
        the bucket is public. Returns what each probe could establish:
        `True` (verified not public), `False` (public -- but then this has
        already raised), or `None` (the store does not implement that call,
        so this adapter cannot verify it and says so)."""
        verdict: dict[str, bool | None] = {"public_access_block": None, "policy_status": None}
        try:
            cfg = self._client.get_public_access_block(Bucket=self._bucket)[
                "PublicAccessBlockConfiguration"
            ]
            blocked = all(
                bool(cfg.get(k))
                for k in (
                    "BlockPublicAcls",
                    "IgnorePublicAcls",
                    "BlockPublicPolicy",
                    "RestrictPublicBuckets",
                )
            )
            verdict["public_access_block"] = blocked
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in (
                "NoSuchPublicAccessBlockConfiguration",
                "NotImplemented",
                "MethodNotAllowed",
            ):
                raise
        try:
            status = self._client.get_bucket_policy_status(Bucket=self._bucket)["PolicyStatus"]
            verdict["policy_status"] = not bool(status.get("IsPublic"))
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in ("NoSuchBucketPolicy", "NotImplemented", "MethodNotAllowed"):
                raise
        if verdict["policy_status"] is False or verdict["public_access_block"] is False:
            raise GarudaArtifactsStoreUnavailable(
                "garuda artifacts store: the configured bucket is PUBLIC "
                f"(policy_status={verdict['policy_status']}, "
                f"public_access_block={verdict['public_access_block']}); refusing to serve artifacts"
            )
        if require_verified and not any(v is True for v in verdict.values()):
            # O2 F1: two unknowns are not a private bucket. The caller that
            # knows its store cannot answer these probes says so explicitly.
            raise GarudaArtifactsStoreUnavailable(
                "garuda artifacts store: bucket privacy could not be VERIFIED (both probes "
                "unimplemented or absent); refusing by default -- pass require_verified=False "
                "only where the store is known not to implement the probes, and log that"
            )
        return verdict

    async def assert_private(self, *, require_verified: bool = True) -> dict[str, bool | None]:
        return await asyncio.to_thread(self._assert_private_sync, require_verified=require_verified)
