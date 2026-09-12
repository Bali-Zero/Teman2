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
)


class InMemoryArtifactObjectStore:
    """Dict-backed `ArtifactObjectStorePort`, modelling the REAL adapter's
    checks in the REAL adapter's order (O1 F10 -- a fake more permissive
    than the adapter proves nothing): put refuses a body over the ceiling
    and refuses a key that already exists (write-once); fetch compares the
    stored length against the ceiling and against the row's expected length
    BEFORE the digest, then the digest. `corrupt(key)` lets a test simulate
    a stored object whose bytes no longer hash to its row's digest."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    async def put(self, *, key: str, body: bytes, content_type: str) -> None:
        del content_type  # not modeled -- this fake stores bytes only
        if len(body) > MAX_ARTIFACT_BYTES:
            raise ValueError(
                f"artifact body of {len(body)} bytes exceeds MAX_ARTIFACT_BYTES={MAX_ARTIFACT_BYTES}"
            )
        if key in self._objects:
            raise ArtifactAlreadyExists(key)
        self._objects[key] = body

    async def fetch_and_verify(
        self, *, key: str, expected_digest: str, expected_byte_length: int | None = None
    ) -> bytes:
        if key not in self._objects:
            raise ArtifactObjectMissing(key)
        body = self._objects[key]
        if len(body) > MAX_ARTIFACT_BYTES:
            raise ArtifactDigestMismatch(key)
        if expected_byte_length is not None and len(body) != expected_byte_length:
            raise ArtifactDigestMismatch(key)
        if hashlib.sha256(body).hexdigest() != expected_digest:
            raise ArtifactDigestMismatch(key)
        return body

    def corrupt(self, key: str, *, replacement: bytes = b"%PDF-1.4\ntampered") -> None:
        """Test hook: overwrite stored bytes without updating any digest,
        so a subsequent `fetch_and_verify` raises `ArtifactDigestMismatch`.
        Bypasses the write-once rule on purpose -- it models tampering."""
        self._objects[key] = replacement

    def delete_for_test(self, key: str) -> None:
        """Test hook: simulate an object that vanished from the bucket
        (bypassing the port, which has no delete member -- see that port's
        docstring and decision #7a)."""
        self._objects.pop(key, None)
