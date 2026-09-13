"""Seams `GarudaArtifactService` depends on -- never a concrete class.

Same shape as `services/garuda_orders/ports.py` (`EligibilityCheckLookup`,
`PaymentProvider`): a `Protocol`, so `postgres_repository.py` /
`tigris_store.py` (production) and `fakes.py` (tests) are interchangeable
without either concrete module importing the other.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

import asyncpg

from backend.services.garuda_artifacts.models import ArtifactRecord

#: Hard ceiling on one artifact's byte length, enforced on BOTH sides of the
#: port: `put` refuses a body above it before any upload call, and
#: `fetch_and_verify` refuses a declared ContentLength above it before reading,
#: bounds the read at ceiling + 1, and refuses a body that turns out longer
#: than declared. It lives on
#: the port and not on the service because every adapter of the port has to
#: honour it whether or not a service exists yet (S2a ships the store before
#: the service).
MAX_ARTIFACT_BYTES = 10 * 1024 * 1024


def key_ref(key: str) -> str:
    """What logs and port exceptions carry instead of the storage key (O1
    F4): a short digest, enough to correlate one refusal with one object
    across a log and a row, not enough to reconstruct the key. On the port
    so BOTH implementations emit the same shape (K3, second reader)."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


class ArtifactObjectMissing(RuntimeError):
    """The object named by a `storage_key` does not exist in the store."""


class ArtifactDigestMismatch(RuntimeError):
    """The object's bytes cannot be the row's bytes. Raised for a hash
    disagreement AND for every length refusal that precedes the hash (K3,
    second reader): a declared ContentLength above the ceiling or disagreeing
    with the row, a body longer than the ceiling, a body whose length
    disagrees with its declaration or with the row. One exception because
    the consumer's answer is the same on every branch -- refuse to serve,
    name the key ref, never the bytes -- and because a digest computed over
    the wrong length can still match an attacker's chosen bytes, so length
    is part of integrity, not a separate failure."""


class ArtifactAlreadyExists(RuntimeError):
    """Raised by EITHER side of the port when a write would land on a key or
    id that is already taken (O2 N2 -- one exception, two raisers, stated):
    the object store raises it when a put finds an object already under the
    key -- by a HEAD before the write or by the store's conditional-write
    refusal, whichever answers first (write-once, spec SS2); the repository
    raises it on the
    `artifact_id` PK or `storage_key` UNIQUE (both astronomically unlikely:
    128 random bits from `journal.new_opaque_id`). NOT raised for "a live
    artifact already exists" (decision #13-revision: always supersede, never
    409) -- the service resolves the live row itself. A consumer maps this to
    `500`, not `409`: an anomaly, not a business conflict."""


class ArtifactObjectStorePort(Protocol):
    """The private artifact bucket -- put, fetch-verify, delete.

    `delete` is here because the pinned spec says a superseded artifact's
    OBJECT is removed immediately ("a withdrawn travel document must stop
    being retrievable the moment it is withdrawn"); the ROW survives,
    append-only, as the record that bytes once existed. Decision #39
    (2026-09-12) read the earlier "leaves the object in the bucket -- on
    purpose" comment as a misreading of #13 and struck it; decision #7a
    excluded only the retention SWEEP (an executor and a scheduler, a new
    organ), not deletion on supersession. WHEN to delete is the service's
    rule, not this port's: a consumer that reaches this port can delete any
    key it names, superseded or not -- the port does not know which rows are
    live. That constraint belongs to the service that ships in S3, and is
    stated here as a limit rather than implied as a guarantee.
    """

    async def put(self, *, key: str, body: bytes, content_type: str) -> None:
        """Write the object under `key`, once. Raises `ValueError` if `body`
        is above `MAX_ARTIFACT_BYTES` (before any upload call -- a caller's
        bug, not a store condition, hence not a port exception) and
        `ArtifactAlreadyExists` if the key is taken. Transient wire errors
        are retried by the adapter; a permanent store error (denied, no such
        bucket, malformed request) is raised as the SDK raises it -- the
        port does not launder it into a port exception, because a consumer
        that maps "the store is broken" to "the artifact is missing" would
        lie to the customer. The fake has no wire and raises neither."""
        ...

    async def fetch_and_verify(
        self, *, key: str, expected_digest: str, expected_byte_length: int | None = None
    ) -> bytes:
        """Fetch the object's bytes, hash them, and compare against
        `expected_digest`. Returns the bytes ONLY on a match.

        `expected_byte_length` is the row's recorded length, and it is a
        BEFORE-the-read check (finding F5): an implementation that can
        learn the object's declared size without transferring it must
        refuse a disagreement, and must in any case never read more than
        the ceiling plus one byte. Optional because it narrows rather than
        replaces the digest check -- an implementation that cannot see a
        declared size still satisfies this port by bounding its read.

        Raises `ArtifactObjectMissing` if the key does not resolve to an
        object, `ArtifactDigestMismatch` if it does but its length or hash
        disagrees (see that exception's docstring for the full list). Two
        more escape the port on the ADAPTER only, stated so a consumer does
        not learn the vocabulary from a stack trace (K3): botocore's
        `IncompleteReadError` when the wire cut the body short on every
        attempt of the retry budget (a wire fault, retried whole, not a
        refusal), and a permanent `ClientError` from the store (denied,
        missing bucket) -- the fake has no wire and raises neither.
        Never returns unverified bytes -- callers (customer/staff serve,
        PR-11's resolve step) all rely on this being the single fetch-then-
        verify primitive (spec SS5: "fetch, verify, then emit... one route
        per lane", generalised here to "one verification path per lane").
        """

    async def delete(self, *, key: str) -> None:
        """Remove ONE object by its exact key. Idempotent: a key that does
        not resolve to an object is a success, not an error -- the desired
        state (nothing retrievable under this key) already holds. Never a
        prefix, never a batch: one call, one key. Transient wire errors are
        retried by the adapter, as for `put` and `fetch_and_verify`; a
        permanent store error is raised as the SDK raises it."""
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
        superseded out from under the check between resolve and write.
        Also `putPracticeArtifact`'s own first read (decision #13-revision):
        locates the row it is about to supersede, if any."""
        ...

    async def lock_practice_for_artifact_write(
        self, conn: asyncpg.Connection, *, practice_id: str
    ) -> None:
        """Advisory xact-lock keyed on `practice_id`, taken before the FIRST
        read of this practice's artifacts in `putPracticeArtifact` (decision
        #13-revision) -- serializes two concurrent puts for the SAME
        practice so the second one's `get_live_for_practice_locked` always
        sees the first one's fully-committed result, never a stale re-check
        of the row the first one just superseded. See the Postgres
        implementation's own docstring for the exact race this closes."""
        ...

    async def insert_superseding(
        self,
        conn: asyncpg.Connection,
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
        """Mark `old_artifact_id` superseded by the new row and insert that
        new row, in the one order that never transiently violates
        `ux_garuda_practice_artifacts_live` (decision #13-revision).
        Caller must already hold `old_artifact_id`'s row lock (via
        `get_live_for_practice_locked`) and the practice's advisory lock
        (via `lock_practice_for_artifact_write`)."""
        ...

    async def move_practice_pointer_if_delivered(
        self, conn: asyncpg.Connection, *, practice_id: str, artifact_id: str, artifact_digest: str
    ) -> bool:
        """If `practice_id`'s `garuda_practices` row is already Delivered
        (287's CHECK: `(state = 'Delivered') = (artifact_id IS NOT NULL
        AND artifact_digest IS NOT NULL)`), move its pointer to this new
        `(artifact_id, artifact_digest)` pair so Delivered always resolves
        to retrievable bytes (decision #13-revision) -- a no-op otherwise.
        `artifact_available` is untouched; no transition happens (Delivered
        has no outgoing transition, so nothing else can be racing this
        practice's row). Returns whether the practice WAS Delivered (i.e.
        whether the pointer actually moved) -- the caller's `practice_was_
        delivered` structured-log field."""
        ...
