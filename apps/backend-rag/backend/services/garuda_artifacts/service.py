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
        be a worse defect than an orphan object in the bucket."""

        if not body.startswith(_PDF_MAGIC):
            raise InvalidArtifactContent("uploaded body is not a PDF")
        if len(body) > MAX_ARTIFACT_BYTES:
            raise ArtifactTooLarge(len(body))

        artifact_digest = hashlib.sha256(body).hexdigest()
        artifact_id = journal.new_opaque_id("art")
        storage_key = f"artifacts/{self._environment}/{practice_id}/{artifact_id}"

        await self._object_store.put(key=storage_key, body=body, content_type=_CONTENT_TYPE)
        try:
            return await self._repository.insert(
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
        except ArtifactAlreadyExists:
            # Best-effort: this phase has no delete member on the object
            # store port (see that port's docstring) -- an orphan object
            # under a key no row will ever reference is the accepted cost
            # of refusing supersession here rather than silently replacing
            # a live artifact. Nothing to clean up with THIS port; the
            # retention sweep never needs to (no row exists to age it out).
            raise
        except Exception:
            # Any OTHER row-insert failure (constraint violation unrelated
            # to `ux_garuda_practice_artifacts_live`, connection drop,
            # etc.) leaves the SAME orphan object behind -- the object was
            # already written above, object-then-row (spec SS3), and this
            # port has no delete member (see `ArtifactObjectStorePort`'s
            # docstring). Only `practice_id`/`artifact_id` are logged --
            # never the body, never an email, never a credential.
            logger.warning(
                "garuda_artifacts.orphan_object_on_insert_failure",
                extra={
                    "practice_id": sanitize_for_log(practice_id),
                    "artifact_id": sanitize_for_log(artifact_id),
                },
            )
            raise

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

        record = await self._repository.get_live_for_order(
            conn, order_id=order_id, result_id_ref=result_id_ref
        )
        if record is None:
            raise LookupError(order_id)
        body = await self._object_store.fetch_and_verify(
            key=record.storage_key, expected_digest=record.artifact_digest
        )
        return record, body

    async def get_staff_practice_artifact(
        self, conn: asyncpg.Connection, *, practice_id: str
    ) -> tuple[ArtifactRecord, bytes]:
        """Staff read (`getStaffPracticeArtifact`). `visible_or_403` for the
        practice is the router's job, run before this is ever called (same
        split `get_staff_practice` uses)."""

        record = await self._repository.get_live_for_practice(conn, practice_id=practice_id)
        if record is None:
            raise LookupError(practice_id)
        body = await self._object_store.fetch_and_verify(
            key=record.storage_key, expected_digest=record.artifact_digest
        )
        return record, body

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
            raise ArtifactDeliveryRejected(
                f"no live artifact matches the submitted pair for practice {practice_id}"
            )
        try:
            await self._object_store.fetch_and_verify(
                key=record.storage_key, expected_digest=record.artifact_digest
            )
        except (ArtifactObjectMissing, ArtifactDigestMismatch) as exc:
            raise ArtifactDeliveryRejected(
                f"live artifact row for {practice_id} does not resolve to verified bytes"
            ) from exc
        return record
