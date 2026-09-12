"""In-memory test doubles for `GarudaArtifactService`'s two ports.

TEST-ONLY. Never imported by `service_initializer.py` or any production
wiring -- same discipline as `garuda_orders.errors`'s
`UnconfiguredEligibilityCheckLookup` fails closed instead of this module
being reachable in prod.
"""

from __future__ import annotations

from backend.services.garuda_artifacts.ports import (
    ArtifactDigestMismatch,
    ArtifactObjectMissing,
)


class InMemoryArtifactObjectStore:
    """Dict-backed `ArtifactObjectStorePort`. `corrupt(key)` lets a test
    simulate a stored object whose bytes no longer hash to its row's
    digest, without needing a real bucket."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    async def put(self, *, key: str, body: bytes, content_type: str) -> None:
        del content_type  # not modeled -- this fake stores bytes only
        self._objects[key] = body

    async def fetch_and_verify(
        self, *, key: str, expected_digest: str, expected_byte_length: int | None = None
    ) -> bytes:
        import hashlib

        if key not in self._objects:
            raise ArtifactObjectMissing(key)
        body = self._objects[key]
        # Models the real store's size check (finding F5), in the same
        # order: the declared length is compared BEFORE the digest, so a
        # test that grows an object past its row's recorded length sees
        # the refusal the real adapter gives, not a digest mismatch that
        # only happens to fire for the same object. A fake that skipped
        # this would let a caller pass here and fail in production.
        if expected_byte_length is not None and len(body) != expected_byte_length:
            raise ArtifactDigestMismatch(key)
        if hashlib.sha256(body).hexdigest() != expected_digest:
            raise ArtifactDigestMismatch(key)
        return body

    def corrupt(self, key: str, *, replacement: bytes = b"%PDF-1.4\ntampered") -> None:
        """Test hook: overwrite stored bytes without updating any digest,
        so a subsequent `fetch_and_verify` raises `ArtifactDigestMismatch`."""
        self._objects[key] = replacement

    def delete_for_test(self, key: str) -> None:
        """Test hook: simulate an object that vanished from the bucket
        (bypassing this phase's own `ArtifactObjectStorePort`, which has no
        delete member -- see that port's docstring)."""
        self._objects.pop(key, None)
