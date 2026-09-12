"""`GarudaArtifactService` -- put / customer-get / staff-get / resolve-for-
delivery, over the two ports in `ports.py`.

Every method takes a caller-owned `asyncpg.Connection` (never a pool): the
router or `staff_transitions.py` decides the transaction boundary, this
service never does (same discipline as `PracticeRepository` /
`apply_transition`).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable

import asyncpg

from backend.app.utils.logging_utils import sanitize_for_log
from backend.services.garuda_artifacts.models import ArtifactRecord
from backend.services.garuda_artifacts.ports import (
    ArtifactAlreadyExists,
    ArtifactDigestMismatch,
    ArtifactObjectMissing,
    ArtifactObjectStorePort,
    ArtifactRepositoryPort,
)
from backend.services.garuda_orders import journal

logger = logging.getLogger(__name__)

__all__ = [
    "MAX_ARTIFACT_BYTES",
    "ArtifactDeliveryRejected",
    "ArtifactTooLarge",
    "GarudaArtifactService",
    "InvalidArtifactContent",
]

#: Conservative ceiling for a VOA grant PDF (spec SS5: "a VOA grant is a
#: document, not a video" -- the byte ceiling is what makes fetch-verify-
#: emit's in-memory buffering safe). Well under the migration's 25 MiB
#: defense-in-depth CHECK, which exists as a second, independent limit --
#: not the one callers should rely on for UX-quality error messages.
MAX_ARTIFACT_BYTES = 10 * 1024 * 1024

_PDF_MAGIC = b"%PDF-"
_CONTENT_TYPE = "application/pdf"

#: How many times a read may re-resolve after losing the race with a
#: concurrent supersession (finding F6). Two: the first pass serves the
#: common case, the second serves the successor of a correction that landed
#: mid-fetch. A third would be a correction landing during the retry of a
#: correction -- at which point "absent" is a truer answer than any of the
#: rows involved, and the caller can simply ask again.
_READ_REVALIDATIONS = 2


class InvalidArtifactContent(ValueError):
    """The uploaded body is not a PDF (spec SS5's allowlist)."""


class ArtifactTooLarge(ValueError):
    """The uploaded body exceeds `MAX_ARTIFACT_BYTES`."""


class ArtifactDeliveryRejected(RuntimeError):
    """PR-11's resolve-and-verify (spec SS5) failed: a fabricated, stale,
    superseded, or mismatched `(artifact_id, artifact_digest)` pair, or a
    live row whose object is missing or corrupt. `staff_transitions.py`
    maps every one of these to `422 INVALID_REQUEST` before any state
    change or outbox enqueue -- the ledger row's own proof-of-armed
    (PENDING-ARMS row 1847)."""


class GarudaArtifactService:
    def __init__(
        self,
        *,
        repository: ArtifactRepositoryPort,
        object_store: ArtifactObjectStorePort,
        environment: str,
    ) -> None:
        self._repository = repository
        self._object_store = object_store
        self._environment = environment

    async def put_practice_artifact(
        self, conn: asyncpg.Connection, *, practice_id: str, body: bytes, produced_by: str
    ) -> ArtifactRecord:
        """Staff write (`putPracticeArtifact`). PDF allowlist, byte
        ceiling, server-side digest -- object THEN row (spec SS3), never
        the reverse: a row pointing at bytes that were never written would
        be a worse defect than an orphan object in the bucket.

        Always supersedes a live artifact rather than refusing the write
        (decision #13-revision, 2026-09-11: "always supersede, never 409,
        made observable") -- see `_supersede_side_effects` for what else
        happens, in the SAME transaction, when a live row already exists.
        """

        if not body.startswith(_PDF_MAGIC):
            raise InvalidArtifactContent("uploaded body is not a PDF")
        if len(body) > MAX_ARTIFACT_BYTES:
            raise ArtifactTooLarge(len(body))

        artifact_digest = hashlib.sha256(body).hexdigest()
        artifact_id = journal.new_opaque_id("art")
        storage_key = f"artifacts/{self._environment}/{practice_id}/{artifact_id}"

        await self._object_store.put(key=storage_key, body=body, content_type=_CONTENT_TYPE)

        # Advisory lock BEFORE the first read of this practice's artifacts --
        # see `lock_practice_for_artifact_write`'s own docstring for the
        # exact two-concurrent-puts race this closes.
        await self._repository.lock_practice_for_artifact_write(conn, practice_id=practice_id)
        existing = await self._repository.get_live_for_practice_locked(
            conn, practice_id=practice_id
        )

        try:
            if existing is None:
                record = await self._repository.insert(
                    conn,
                    artifact_id=artifact_id,
                    practice_id=practice_id,
                    storage_key=storage_key,
                    artifact_digest=artifact_digest,
                    byte_length=len(body),
                    content_type=_CONTENT_TYPE,
                    produced_by=produced_by,
                    environment=self._environment,
                )
            else:
                record = await self._repository.insert_superseding(
                    conn,
                    old_artifact_id=existing.artifact_id,
                    artifact_id=artifact_id,
                    practice_id=practice_id,
                    storage_key=storage_key,
                    artifact_digest=artifact_digest,
                    byte_length=len(body),
                    content_type=_CONTENT_TYPE,
                    produced_by=produced_by,
                    environment=self._environment,
                )
        except ArtifactAlreadyExists:
            # Best-effort: this phase has no delete member on the object
            # store port (see that port's docstring) -- an orphan object
            # under a key no row will ever reference is the accepted cost.
            # This is now a genuine anomaly (PK/storage_key collision), NOT
            # "a live artifact already exists" -- that case is handled
            # above by superseding instead of racing into this exception
            # (decision #13-revision).
            raise
        except Exception:
            # Any OTHER row-write failure (constraint violation, connection
            # drop, etc.) leaves the SAME orphan object behind -- the
            # object was already written above, object-then-row (spec
            # SS3), and this port has no delete member (see
            # `ArtifactObjectStorePort`'s docstring). Only
            # `practice_id`/`artifact_id` are logged -- never the body,
            # never an email, never a credential.
            logger.warning(
                "garuda_artifacts.orphan_object_on_insert_failure",
                extra={
                    "practice_id": sanitize_for_log(practice_id),
                    "artifact_id": sanitize_for_log(artifact_id),
                },
            )
            raise

        if existing is not None:
            await self._supersede_side_effects(
                conn, practice_id=practice_id, old=existing, new=record
            )
        return record

    async def _supersede_side_effects(
        self,
        conn: asyncpg.Connection,
        *,
        practice_id: str,
        old: ArtifactRecord,
        new: ArtifactRecord,
    ) -> None:
        """Everything decision #13-revision requires beyond the row swap
        itself, in the SAME transaction as the insert/update above:

        1. If the practice is already Delivered, move its
           `artifact_id`/`artifact_digest` pointer to the new pair so
           Delivered always resolves to retrievable bytes (287's CHECK --
           `(state = 'Delivered') = (artifact_id IS NOT NULL AND
           artifact_digest IS NOT NULL)` -- still holds: both columns stay
           non-NULL, only their VALUES move). `artifact_available` is
           untouched (stays TRUE). No transition happens here -- Delivered
           has no outgoing transition (STATE-MACHINE.md), so no concurrent
           `apply_transition` can be racing this UPDATE for this practice.
        2. Make it OBSERVABLE without a journal row. The Dux's ruling on
           this exact question (2026-09-12, restated after an earlier
           inbox crossing): NO `garuda_order_journal` row for supersession
           in this preparation -- `transition_id` (284_garuda_orders.sql:
           292-306) is CHECK-constrained to the SAME closed enum the
           frozen `products/garuda-voa/contracts/events.yaml` TransitionId
           admits, by explicit design, and no existing member fits a
           non-state-transition artifact-lifecycle event. Inventing a
           DB-only value breaks that invariant; editing `events.yaml` is
           out of this window's scope (`contracts/**`). The superseded ROW
           ITSELF is the persisted, ids-only, immutable record the
           Imperatore's decision actually requires (`superseded_at` +
           `superseded_by`, set once, guard-enforced, undeletable) -- a
           STRONGER guarantee than a journal line would have been. This
           structured log line is the observability surface on top of
           that row, not a substitute for it.

           DEFERRED CONTRACT ITEM (rebase-time, not DB-first): a
           `practice.artifact_superseded` journal event, its
           `events.yaml` TransitionId member, and a customer-tracker field
           land TOGETHER in the contract PR at rebase -- never DB-first,
           same discipline as every other frozen-contract boundary this
           window respects.
        """
        practice_was_delivered = await self._repository.move_practice_pointer_if_delivered(
            conn,
            practice_id=practice_id,
            artifact_id=new.artifact_id,
            artifact_digest=new.artifact_digest,
        )
        logger.info(
            "garuda_artifacts.artifact_superseded",
            extra={
                "practice_id": sanitize_for_log(practice_id),
                "superseded_artifact_id": sanitize_for_log(old.artifact_id),
                "new_artifact_id": sanitize_for_log(new.artifact_id),
                "practice_was_delivered": practice_was_delivered,
            },
        )

    async def get_order_artifact(
        self, conn: asyncpg.Connection, *, order_id: str, result_id_ref: str
    ) -> tuple[ArtifactRecord, bytes]:
        """Customer read (`getPracticeArtifact`). Returns `(record, bytes)`
        on success. Raises `LookupError` for "no such artifact" (the
        router's single 404 `ORDER_NOT_FOUND` -- spec SS4's table
        deliberately collapses every not-mine/not-ready/expired/superseded
        case into this one outcome) and propagates `ArtifactObjectMissing`
        / `ArtifactDigestMismatch` for the router's `503
        SERVICE_UNAVAILABLE` case."""

        async def resolve() -> ArtifactRecord | None:
            return await self._repository.get_live_for_order(
                conn, order_id=order_id, result_id_ref=result_id_ref
            )

        return await self._fetch_still_live(resolve, missing_key=order_id)

    async def get_staff_practice_artifact(
        self, conn: asyncpg.Connection, *, practice_id: str
    ) -> tuple[ArtifactRecord, bytes]:
        """Staff read (`getStaffPracticeArtifact`). `visible_or_403` for the
        practice is the router's job, run before this is ever called (same
        split `get_staff_practice` uses)."""

        async def resolve() -> ArtifactRecord | None:
            return await self._repository.get_live_for_practice(conn, practice_id=practice_id)

        return await self._fetch_still_live(resolve, missing_key=practice_id)

    async def _fetch_still_live(
        self,
        resolve: Callable[[], Awaitable[ArtifactRecord | None]],
        *,
        missing_key: str,
    ) -> tuple[ArtifactRecord, bytes]:
        """Resolve, fetch, then CONFIRM the row is still the live one
        before its bytes are handed back.

        Sol's O1 refutation (2026-09-11, finding F6) interleaved a read
        with a correction: the reader resolves the live row, a concurrent
        `putPracticeArtifact` supersedes it and commits, and the reader --
        already holding a key from the retired row, whose object is kept on
        purpose (decision #13-revision: superseded objects are never
        removed) -- fetches and emits the OLD grant. Nothing in the fetch
        path could notice, because the digest it verifies is the retired
        row's own and matches perfectly. The customer downloads a document
        the correction existed to replace.

        The re-resolve after the fetch closes that window: if the live row
        moved under us, the loop serves the SUCCESSOR rather than what it
        started with. A read that loses the race twice in a row stops and
        reads as absent -- `LookupError`, the router's single 404, which is
        also what spec SS4 already says a superseded artifact looks like
        from outside. No new error code, and no contract surface, for a
        case whose correct answer the contract already names.

        Not a lock, deliberately: the fetch is a network round trip to the
        object store, and `putPracticeArtifact` holds
        `pg_advisory_xact_lock` on the practice for its whole transaction.
        Making readers take that same lock would let one slow customer
        download block every correction for the same practice -- a
        liveness cost paid on the frequent path to fix a rare one.

        WHAT THIS DOES NOT CLOSE, stated rather than implied (Sol's O2 read
        this method as PARTIAL, correctly). A supersession committing
        between the confirming read and this return still leaves the caller
        holding the previous row's bytes, and no amount of re-reading
        removes that window: a non-blocking read can promise "these bytes
        were the live row at an instant inside this request", never "they
        still are as you receive them" -- even a lock held across the fetch
        would only move the window to the moment it is released. What the
        confirming read DOES buy is that bytes known to be retired are
        never emitted. The other edge of the same trade: two corrections
        landing during one read exhaust the attempts and produce a 404
        while a live row exists. That is a self-correcting answer to a
        deliberately contended read, and the same 404 the contract already
        gives for a superseded artifact -- not a claim that the practice
        has none.
        """
        for _ in range(_READ_REVALIDATIONS):
            record = await resolve()
            if record is None:
                raise LookupError(missing_key)
            # `expected_byte_length` is what turns F5's ceiling check into
            # a check against THIS row: an object whose declared size does
            # not equal the length the row recorded at write time is
            # refused before a byte is read, whatever its digest would
            # have been.
            body = await self._object_store.fetch_and_verify(
                key=record.storage_key,
                expected_digest=record.artifact_digest,
                expected_byte_length=record.byte_length,
            )
            still_live = await resolve()
            if still_live is not None and still_live.artifact_id == record.artifact_id:
                return record, body
        raise LookupError(missing_key)

    async def resolve_for_delivery(
        self, conn: asyncpg.Connection, *, practice_id: str, artifact_id: str, artifact_digest: str
    ) -> ArtifactRecord:
        """PR-11's resolve-and-verify (spec SS5, steps 1-3):

        1. resolve the live artifact row for this practice (locked, inside
           the caller's transaction),
        2. require the submitted pair to equal that row's,
        3. confirm the stored object exists and hashes to the row's digest.

        Step 4 (write the columns, `artifact_available = TRUE`) is the
        caller's (`staff_transitions.py::apply_transition`) -- this method
        only ever reads and raises; it never mutates `garuda_practices` or
        `garuda_practice_artifacts`.
        """

        record = await self._repository.get_live_for_practice_locked(
            conn, practice_id=practice_id
        )
        if (
            record is None
            or record.artifact_id != artifact_id
            or record.artifact_digest != artifact_digest
        ):
            # One message for "no such live row", "expired past retention"
            # and "the pair does not match": the staff caller learns the
            # delivery was refused, never WHICH of the three it was. The
            # retention arm is the one Sol's F3 added -- `get_live_for_
            # practice_locked` now filters it, so an expired pair arrives
            # here as `record is None`.
            raise ArtifactDeliveryRejected(
                f"no live, unexpired artifact matches the submitted pair for practice {practice_id}"
            )
        try:
            await self._object_store.fetch_and_verify(
                key=record.storage_key,
                expected_digest=record.artifact_digest,
                expected_byte_length=record.byte_length,
            )
        except (ArtifactObjectMissing, ArtifactDigestMismatch) as exc:
            raise ArtifactDeliveryRejected(
                f"live artifact row for {practice_id} does not resolve to verified bytes"
            ) from exc
        return record
