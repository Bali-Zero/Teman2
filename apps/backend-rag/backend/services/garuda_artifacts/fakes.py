"""In-memory test doubles for `GarudaArtifactService`'s two ports.

TEST-ONLY. Never imported by `service_initializer.py` or any production
wiring -- same discipline as `garuda_orders.errors`'s
`UnconfiguredEligibilityCheckLookup` fails closed instead of this module
being reachable in prod.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

from backend.services.garuda_artifacts.models import ArtifactRecord
from backend.services.garuda_artifacts.ports import (
    ArtifactAlreadyExists,
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

    async def fetch_and_verify(self, *, key: str, expected_digest: str) -> bytes:
        import hashlib

        if key not in self._objects:
            raise ArtifactObjectMissing(key)
        body = self._objects[key]
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


class InMemoryArtifactRepository:
    """Dict-backed `ArtifactRepositoryPort`, for `GarudaArtifactService`
    unit tests that want to exercise `put`/`resolve` orchestration without a
    real Postgres. `conn` parameters are accepted (protocol conformance) and
    ignored -- this fake has no transaction of its own.

    Models `ux_garuda_practice_artifacts_live` (migration 312's partial
    unique index) by refusing a second live insert for the same
    `practice_id`, same as the real constraint would.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, ArtifactRecord] = {}

    async def insert(
        self,
        conn,
        *,
        artifact_id: str,
        practice_id: str,
        storage_key: str,
        artifact_digest: str,
        byte_length: int,
        content_type: str,
        produced_by: str,
        environment: str,
    ) -> ArtifactRecord:
        del conn
        if any(
            r.practice_id == practice_id and r.is_live for r in self._by_id.values()
        ):
            raise ArtifactAlreadyExists(practice_id)
        now = datetime.now(UTC)
        record = ArtifactRecord(
            artifact_id=artifact_id,
            practice_id=practice_id,
            storage_key=storage_key,
            artifact_digest=artifact_digest,
            byte_length=byte_length,
            content_type=content_type,
            produced_by=produced_by,
            environment=environment,
            created_at=now,
            retention_until=now + timedelta(days=30),
            superseded_at=None,
            superseded_by=None,
        )
        self._by_id[artifact_id] = record
        return record

    async def lock_practice_for_artifact_write(self, conn, *, practice_id: str) -> None:
        # No real concurrency to serialize in this single-coroutine fake --
        # protocol conformance only (see the Postgres implementation's own
        # docstring for the race this closes for real).
        del conn, practice_id

    async def insert_superseding(
        self,
        conn,
        *,
        old_artifact_id: str,
        artifact_id: str,
        practice_id: str,
        storage_key: str,
        artifact_digest: str,
        byte_length: int,
        content_type: str,
        produced_by: str,
        environment: str,
    ) -> ArtifactRecord:
        del conn
        old = self._by_id[old_artifact_id]
        self._by_id[old_artifact_id] = dataclasses.replace(
            old, superseded_at=datetime.now(UTC), superseded_by=artifact_id
        )
        now = datetime.now(UTC)
        record = ArtifactRecord(
            artifact_id=artifact_id,
            practice_id=practice_id,
            storage_key=storage_key,
            artifact_digest=artifact_digest,
            byte_length=byte_length,
            content_type=content_type,
            produced_by=produced_by,
            environment=environment,
            created_at=now,
            retention_until=now + timedelta(days=30),
            superseded_at=None,
            superseded_by=None,
        )
        self._by_id[artifact_id] = record
        return record

    async def get_live_for_order(self, conn, *, order_id: str, result_id_ref: str):
        del conn, order_id, result_id_ref
        raise NotImplementedError("not modeled by this fake -- unit-test resolve/put only")

    async def get_live_for_practice(self, conn, *, practice_id: str) -> ArtifactRecord | None:
        del conn
        for record in self._by_id.values():
            if record.practice_id == practice_id and record.is_live:
                return record
        return None

    async def get_live_for_practice_locked(
        self, conn, *, practice_id: str
    ) -> ArtifactRecord | None:
        return await self.get_live_for_practice(conn, practice_id=practice_id)

    async def move_practice_pointer_if_delivered(
        self, conn, *, practice_id: str, artifact_id: str, artifact_digest: str
    ) -> bool:
        # Not modeled: this fake tracks garuda_practice_artifacts only, no
        # garuda_practices state at all. Always reports "not Delivered" --
        # the Delivered-pointer-move is exercised for real against Postgres
        # in tests/services/garuda_portal/test_staff_router_put_practice_
        # artifact.py and tests/app/routers/test_garuda_voa_artifact_get.py.
        del conn, practice_id, artifact_id, artifact_digest
        return False

    def supersede_for_test(self, artifact_id: str, *, superseded_by: str = "art_test_other") -> None:
        """Test hook: mark a row superseded directly, without going through
        `insert_superseding` -- for tests that only need "this row is
        already superseded" as a precondition (e.g. `resolve_for_delivery`
        rejecting a stale id), not the full supersession side effects."""
        record = self._by_id[artifact_id]
        self._by_id[artifact_id] = dataclasses.replace(
            record, superseded_at=datetime.now(UTC), superseded_by=superseded_by
        )
