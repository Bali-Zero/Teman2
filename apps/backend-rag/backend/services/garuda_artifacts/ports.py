"""Seams `GarudaArtifactService` depends on -- never a concrete class.

Same shape as `services/garuda_orders/ports.py` (`EligibilityCheckLookup`,
`PaymentProvider`): a `Protocol`, so `postgres_repository.py` /
`tigris_store.py` (production) and `fakes.py` (tests) are interchangeable
without either concrete module importing the other.
"""

from __future__ import annotations

from typing import Protocol

import asyncpg

from backend.services.garuda_artifacts.models import ArtifactRecord


class ArtifactObjectMissing(RuntimeError):
    """The object named by a `storage_key` does not exist in the store."""


class ArtifactDigestMismatch(RuntimeError):
    """The object's bytes hashed to something other than the expected digest."""


class ArtifactAlreadyExists(RuntimeError):
    """`insert` was attempted while a live artifact already exists for this
    `practice_id` -- `ux_garuda_practice_artifacts_live` (migration 312)
    refused the row. Supersession (spec SS2) is decision #7a's future work,
    not this phase's -- `putPracticeArtifact` maps this to `409` rather
    than silently replacing the live artifact."""


class ArtifactObjectStorePort(Protocol):
    """The private artifact bucket -- put, then fetch-verify.

    No `delete` member: physical deletion is the retention sweep's own role
    (spec SS6, decision #7a), not built by this phase. Supersession (spec
    SS2: "the superseded row is marked `superseded_at` and its object is
    deleted immediately") is therefore also out of this phase's scope --
    `putPracticeArtifact` refuses a second write while a live artifact
    already exists (`ArtifactAlreadyExists`, service.py) rather than
    silently deleting the first.
    """

    async def put(self, *, key: str, body: bytes, content_type: str) -> None: ...

    async def fetch_and_verify(self, *, key: str, expected_digest: str) -> bytes:
        """Fetch the object's bytes, hash them, and compare against
        `expected_digest`. Returns the bytes ONLY on a match.

        Raises `ArtifactObjectMissing` if the key does not resolve to an
        object, `ArtifactDigestMismatch` if it does but the hash disagrees.
        Never returns unverified bytes -- callers (customer/staff serve,
        PR-11's resolve step) all rely on this being the single fetch-then-
        verify primitive (spec SS5: "fetch, verify, then emit... one route
        per lane", generalised here to "one verification path per lane").
        """
        ...


class ArtifactRepositoryPort(Protocol):
    """`garuda_practice_artifacts` reads/writes, all against a caller-owned
    `asyncpg.Connection` -- this port never acquires its own connection or
    manages its own transaction, matching `staff_transitions.py::
    apply_transition`'s convention (the caller's `pool.acquire()` +
    `conn.transaction()` is the unit of atomicity, not this port).
    """

    async def insert(
        self,
        conn: asyncpg.Connection,
        *,
        artifact_id: str,
        practice_id: str,
        storage_key: str,
        artifact_digest: str,
        byte_length: int,
        content_type: str,
        produced_by: str,
        environment: str,
    ) -> ArtifactRecord: ...

    async def get_live_for_order(
        self, conn: asyncpg.Connection, *, order_id: str, result_id_ref: str
    ) -> ArtifactRecord | None:
        """Ownership-filtered, single-query read (spec SS4: enforced in the
        SAME query that loads the row, never a check after a load). `None`
        for a foreign order, a missing order, no live artifact, an expired
        one, or a superseded one -- all indistinguishable to the customer
        lane (spec SS4's error table), all 404 `ORDER_NOT_FOUND` at the
        router."""
        ...

    async def get_live_for_practice(
        self, conn: asyncpg.Connection, *, practice_id: str
    ) -> ArtifactRecord | None:
        """Staff read -- `visible_or_403` for the practice itself is the
        caller's job (same split as `get_staff_practice`); this only
        resolves the live, unexpired artifact row."""
        ...

    async def get_live_for_practice_locked(
        self, conn: asyncpg.Connection, *, practice_id: str
    ) -> ArtifactRecord | None:
        """`SELECT ... FOR UPDATE` twin of `get_live_for_practice`, for
        PR-11's resolve-and-verify (spec SS5) -- runs inside the SAME
        transaction as the CAS state UPDATE, so the row cannot be
        superseded out from under the check between resolve and write."""
        ...
