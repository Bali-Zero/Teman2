"""The private GARUDA VOA artifact bucket -- `garuda-voa-artifacts`.

Separate, on purpose, from `nuzantara-warroom-images`
(`services/canva_renderer_v2/_tigris.py`): that bucket's own module
docstring says its prefix is public-read and its purpose is minting public
HTTPS URLs -- reaching for it here would publish a passport-bearing
document to the open internet (spec SS3, fact 13's "trap in plain sight").

FAIL-CLOSED, OWN CREDENTIALS. This store reads exactly four env vars of its
own and NEVER falls back to `boto3`'s default credential chain, which on
this codebase's existing Tigris client (`_tigris.py::get_s3_client`) means
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` -- the credentials that reach
the PUBLIC bucket. Passing `aws_access_key_id=None` to `boto3.client(...)`
does not raise; it silently activates that same default chain. So presence
is checked FIRST, with `bool(os.environ.get(...))` (`${VAR:+SET}`
semantics -- never logging or printing the value), and the client is
constructed only once both scoped credentials are confirmed present.

Bucket, and the scoped credential pair, are `operator[secret]` -- this
module does not provision them (spec SS3). Absent, it raises
`GarudaArtifactsStoreUnavailable`; callers (service.py) map that to `503
SERVICE_UNAVAILABLE`, never a crash.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from backend.services.garuda_artifacts.ports import (
    MAX_ARTIFACT_BYTES,
    ArtifactDigestMismatch,
    ArtifactObjectMissing,
)

logger = logging.getLogger(__name__)

BUCKET_ENV = "GARUDA_ARTIFACTS_BUCKET"
ACCESS_KEY_ID_ENV = "GARUDA_ARTIFACTS_ACCESS_KEY_ID"
SECRET_ACCESS_KEY_ENV = "GARUDA_ARTIFACTS_SECRET_ACCESS_KEY"
ENDPOINT_URL_ENV = "GARUDA_ARTIFACTS_ENDPOINT_URL"
DEFAULT_ENDPOINT_URL = "https://fly.storage.tigris.dev"

_MAX_RETRIES = 3
_BACKOFF_BASE_S = 2.0
_TRANSIENT_ERROR_CODES = {"503", "502", "504", "RequestTimeout", "SlowDown", "Throttling"}


class GarudaArtifactsStoreUnavailable(RuntimeError):
    """One or more of this store's OWN env vars is absent. Never a fallback
    to the public bucket's credentials -- the caller must 503, not retry
    with a different credential source."""


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        return code in _TRANSIENT_ERROR_CODES
    return isinstance(exc, BotoCoreError)


class TigrisArtifactObjectStore:
    """Implements `ArtifactObjectStorePort` (structurally)."""

    def __init__(self, *, client: Any | None = None) -> None:
        """`client` is a test-only seam (a fake boto3-like S3 client) --
        production wiring never passes it, so `service_initializer.py`
        still gets the real `boto3.client(...)` built below. The env-var
        presence check runs regardless of `client`, so an injected client
        can never mask a missing credential."""
        bucket = os.environ.get(BUCKET_ENV)
        access_key_id = os.environ.get(ACCESS_KEY_ID_ENV)
        secret_access_key = os.environ.get(SECRET_ACCESS_KEY_ENV)
        # Presence-only checks (`${VAR:+SET}` semantics) -- values are never
        # logged, and the missing-vars message below names ONLY the env var,
        # never a value.
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
        self._bucket = bucket
        self._client = (
            client
            if client is not None
            else boto3.client(
                "s3",
                endpoint_url=os.environ.get(ENDPOINT_URL_ENV, DEFAULT_ENDPOINT_URL),
                region_name="auto",
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
            )
        )

    def _put_sync(self, *, key: str, body: bytes, content_type: str) -> None:
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                # No ACL kwarg -- the bucket is private by construction
                # (spec SS3); passing `ACL="public-read"` here would be
                # exactly the mistake this module exists to avoid.
                self._client.put_object(
                    Bucket=self._bucket, Key=key, Body=body, ContentType=content_type
                )
                return
            except (ClientError, BotoCoreError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES and _is_transient(exc):
                    time.sleep(_BACKOFF_BASE_S * attempt)
                    continue
                raise
        if last_exc is not None:  # pragma: no cover - defensive
            raise last_exc

    async def put(self, *, key: str, body: bytes, content_type: str) -> None:
        await asyncio.to_thread(self._put_sync, key=key, body=body, content_type=content_type)

    def _get_bytes_sync(self, *, key: str, expected_byte_length: int | None) -> bytes:
        try:
            resp: dict[str, Any] = self._client.get_object(Bucket=self._bucket, Key=key)
            # F5 cure (Sol's O1, MAJOR): a row whose private object has been
            # replaced with a multi-gigabyte value used to reach `.read()`
            # unbounded, and the digest check below -- the ONLY thing that
            # was supposed to catch a tampered object -- ran too late to
            # protect this worker's memory; it only ever protected the
            # caller's trust in the bytes it had ALREADY fully buffered.
            # `ContentLength` is metadata the GetObject response carries
            # before a single body byte is read, so refuse HERE, before
            # `.read()`, when it already disagrees with the row's own
            # expectation or this store's ceiling.
            content_length = resp.get("ContentLength")
            if content_length is not None and (
                content_length > MAX_ARTIFACT_BYTES
                or (expected_byte_length is not None and content_length != expected_byte_length)
            ):
                logger.error(
                    "garuda_artifacts.declared_size_refused",
                    extra={"storage_key": key, "content_length": content_length},
                )
                raise ArtifactDigestMismatch(key)
            # Bounded read even so: `ContentLength` is metadata the object
            # (or a misbehaving/older store) could lie about or omit. Reading
            # at most `ceiling + 1` bytes means a lying object is still
            # caught by the length check right below, and this worker's
            # memory never grows past that bound regardless of what the
            # object claims or how large it actually is.
            body = resp["Body"].read(MAX_ARTIFACT_BYTES + 1)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                raise ArtifactObjectMissing(key) from exc
            raise
        if len(body) > MAX_ARTIFACT_BYTES:
            logger.error(
                "garuda_artifacts.object_exceeds_ceiling",
                extra={"storage_key": key},
            )
            raise ArtifactDigestMismatch(key)
        return body

    async def fetch_and_verify(
        self, *, key: str, expected_digest: str, expected_byte_length: int | None = None
    ) -> bytes:
        """`expected_byte_length` is an OPTIONAL cross-check against the
        row's own `byte_length` column (finding F5) -- `None` for any
        caller that does not pass it (today, every caller in `service.py`,
        which this module must not edit in this window) still gets the
        ceiling-only refusal above; a caller that DOES pass it gets the
        stronger row-agreement check too. Either way this method never
        reads more than `MAX_ARTIFACT_BYTES + 1` bytes."""
        body = await asyncio.to_thread(
            self._get_bytes_sync, key=key, expected_byte_length=expected_byte_length
        )
        actual = hashlib.sha256(body).hexdigest()
        if actual != expected_digest:
            logger.error(
                "garuda_artifacts.digest_mismatch",
                extra={"storage_key": key},
            )
            raise ArtifactDigestMismatch(key)
        return body
