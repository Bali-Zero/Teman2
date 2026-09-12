"""In-memory test doubles for `GarudaArtifactService`'s two ports.

TEST-ONLY. Never imported by `service_initializer.py` or any production
wiring -- same discipline as `garuda_orders.errors`'s
`UnconfiguredEligibilityCheckLookup` fails closed instead of this module
being reachable in prod.
"""

from __future__ import annotations

import hashlib

from backend.services.garuda_artifacts.ports import (
    MAX_ARTIFACT_BYTES,
    ArtifactAlreadyExists,
    ArtifactDigestMismatch,
    ArtifactObjectMissing,
    key_ref,
)


class InMemoryArtifactObjectStore:
    """Dict-backed `ArtifactObjectStorePort`, modelling the REAL adapter's
    checks in the REAL adapter's order (O1 F10 -- a fake more permissive
    than the adapter proves nothing): put refuses a body over the ceiling
    and refuses a key that already exists (write-once); fetch compares the
    stored length against the ceiling and against the row's expected length
    BEFORE the digest, then the digest. `corrupt(key)` lets a test simulate
    a stored object whose bytes no longer hash to its row's digest. Port
    exceptions carry `key_ref(key)`, as the adapter's do (K3): a service test
    asserting on a message meets the same shape production emits, and a
    realistic key in a fixture never lands in failure output."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    async def put(self, *, key: str, body: bytes, content_type: str) -> None:
        del content_type  # not modeled -- this fake stores bytes only
        if len(body) > MAX_ARTIFACT_BYTES:
            raise ValueError(
                f"artifact body of {len(body)} bytes exceeds MAX_ARTIFACT_BYTES={MAX_ARTIFACT_BYTES}"
            )
        if key in self._objects:
            raise ArtifactAlreadyExists(key_ref(key))
        self._objects[key] = body

    async def fetch_and_verify(
        self, *, key: str, expected_digest: str, expected_byte_length: int | None = None
    ) -> bytes:
        ref = key_ref(key)
        if key not in self._objects:
            raise ArtifactObjectMissing(ref)
        body = self._objects[key]
        if len(body) > MAX_ARTIFACT_BYTES:
            raise ArtifactDigestMismatch(ref)
        if expected_byte_length is not None and len(body) != expected_byte_length:
            raise ArtifactDigestMismatch(ref)
        if hashlib.sha256(body).hexdigest() != expected_digest:
            raise ArtifactDigestMismatch(ref)
        return body

    def corrupt(self, key: str, *, replacement: bytes = b"%PDF-1.4\ntampered") -> None:
        """Test hook: overwrite stored bytes without updating any digest,
        so a subsequent `fetch_and_verify` raises `ArtifactDigestMismatch`.
        Bypasses the write-once rule on purpose -- it models tampering."""
        self._objects[key] = replacement

    async def delete(self, *, key: str) -> None:
        """Port member (decision #39): one key, idempotent -- an absent key
        is a success. The fake cannot tell a superseded key from a live one
        any more than the adapter can; that rule is the service's."""
        self._objects.pop(key, None)

    def delete_for_test(self, key: str) -> None:
        """Test hook: simulate an object that vanished from the bucket
        outside the port (a store-side loss, not a service decision)."""
        self._objects.pop(key, None)
