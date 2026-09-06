"""Real ``DocumentStorePort`` over ``garuda_documents`` (migration 304).

Mirrors ``backend.services.garuda_flow.check_store.PostgresCheckStore``'s idiom
deliberately, per the mandate that built this file: ``async with self._pool.acquire()
as conn, conn.transaction():`` then ``SELECT ... FOR UPDATE`` on the idempotency row,
branch on a payload-hash mismatch (``IdempotencyConflictError``), otherwise a plain
``INSERT`` -- never ``INSERT ... ON CONFLICT``. Unlike ``check_store.py``, idempotency
tracking and the outcome row are the SAME table here (``garuda_documents``): this port's
contract (``ports.py``) has no separate "idempotency reservation, then complete later"
phase the way L3's checkout does (no external I/O happens between reserving a key and
committing an outcome -- OCR already ran, in ``service.py``, before ``commit()`` is ever
called), so a second table would only duplicate the row this one already holds.

THE PII BOUNDARY -- WHY ``garuda_document_review_fields`` HAS NO VALUE COLUMN, AND THE
ONE GAP THAT FOLLOWS FROM IT (flagged to the orchestrator, not resolved here; see
``ReadyOutcomeValueNotPersisted`` below).

``models.ReviewField`` (populated only on a ``ReadyOutcome``) carries the actual OCR'd
passport field VALUE -- full name, passport number, nationality, expiry date. That value
IS the personal data ``redaction.py`` exists to keep off any wire this lane does not
strictly need, and CLAUDE.md's PII boundary is explicit: no output, memory, log, or
persisted artifact may carry client PII in cleartext. Storing it in Postgres -- even
"just" in a retention-covered table -- would be exactly that. The mandate that built this
migration was explicit that inventing an encryption scheme to route around this is out of
scope; the honest answer, when faithful rehydration of one outcome kind genuinely requires
the extracted values, is to say so rather than store passport data.

So this store persists only the STRUCTURE of every ``DocumentOutcome``: ``document_id``,
``processing_state``, and -- for the two outcome kinds that carry review fields -- the
field NAMES plus their ``confirmation_required`` flags. For ``LowConfidenceOutcome`` this
is completely faithful: ``UncertainReviewField`` itself carries no value, so nothing is
lost. For ``ReadyOutcome`` it is NOT faithful -- ``ReviewField.value`` has no column to
round-trip through, and ``get_existing()`` raises ``ReadyOutcomeValueNotPersisted`` rather
than fabricate a placeholder that would look like real data to a caller.

This gap is narrower than it may sound. ``service.py::submit_document`` only ever calls
``get_existing()`` BEFORE running OCR, to detect a replay; when it commits a FRESH
outcome, it returns the in-memory object it just built directly -- never through this
store. So a first-time submission of a document that turns out READY_FOR_REVIEW is
completely unaffected: the customer sees the real extracted values immediately, and they
never touch this table. The gap is exactly one path: an exact idempotent REPLAY (same
Idempotency-Key AND the same payload, submitted again) of an ALREADY-READY document.
``ports.py``'s idempotency contract ("an exact scoped key plus the same canonical payload
replays the original outcome with no repeated side effect") and the PII boundary are in
genuine tension there, and this file does not resolve it -- see
``ReadyOutcomeValueNotPersisted`` for the candidates a product decision would choose
between.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

import asyncpg

from backend.services.garuda_documents.models import (
    DocumentOutcome,
    LowConfidenceOutcome,
    PassportReviewFieldName,
    ProcessingOutcome,
    ReadyOutcome,
    UncertainReviewField,
    UnreadableOutcome,
)
from backend.services.garuda_documents.ports import (
    IdempotencyConflictError,
    ReadyOutcomeValueNotPersisted,
)
from backend.services.garuda_flow.public_api import PersistencePolicyUnavailable

logger = logging.getLogger(__name__)

__all__ = ["PostgresDocumentStore", "ReadyOutcomeValueNotPersisted"]

# Storage-layer-only fourth member alongside `models.ProcessingState` -- see the
# `processing_state` column comment in migration 304 for why `UnreadableOutcome` needs
# one: it is deliberately domain-internal (models.py docstring) and carries no
# `processing_state` field of its own to reuse.
_STATE_PROCESSING = "PROCESSING"
_STATE_LOW_CONFIDENCE = "LOW_CONFIDENCE"
_STATE_READY_FOR_REVIEW = "READY_FOR_REVIEW"
_STATE_UNREADABLE = "UNREADABLE"

# ``ReadyOutcomeValueNotPersisted`` itself now lives in ``ports.py`` (re-exported here for
# every existing importer) -- THE GAP it documents is unchanged (this store never
# persists ``ReviewField.value``, the actual OCR'd passport field content, because the
# PII boundary forbids storing extracted identity-document field VALUES in cleartext, and
# inventing an encryption scheme to route around that is explicitly out of scope for this
# file). What moved: it now carries the persisted STRUCTURE (field names +
# ``confirmation_required`` flags, never a value) alongside ``document_id``, so a
# storage-agnostic caller holding its OWN independently-derived ``ReadyOutcome`` for the
# identical bytes (``service.py``'s commit-race loser) can verify agreement and recover
# without the store ever handing back -- or fabricating -- a value. See ``service.py``'s
# ``_reconcile_lost_race_ready_replay`` for the one caller that does this; an ordinary
# sequential replay (no independent outcome to reconcile against) still lets this
# propagate, which is the "genuinely unpersisted" case ``ReadyOutcomeValueNotPersisted``'s
# own docstring discusses.

# The single operation this store's `key_sha256` namespace belongs to. A store-level
# constant, not a caller-supplied parameter: this table backs exactly one endpoint
# (`uploadIntakeDocument`), so there is no second value it could ever take today. Folded
# into the hash anyway per the contract's `IdempotencyKey` scoping ("actor and
# operation") and so a FUTURE second operation sharing this table would not silently
# collide with this one's key space.
_OPERATION_UPLOAD_INTAKE_DOCUMENT = "upload_intake_document"


def _scoped_key_sha256(*, actor_id: str, operation: str, environment: str, idempotency_key: str) -> bytes:
    """Canonical, unambiguous hash of (actor, operation, environment, idempotency_key).

    NOT a bare `sha256(idempotency_key)` -- the contract's `IdempotencyKey` parameter
    (openapi.yaml) is explicit: "Scoped to actor and operation." A bare hash of the
    client-supplied key string means two different actors who happen to reuse the same
    literal key collide on the SAME `key_sha256` PRIMARY KEY row -- one actor's
    `get_existing` could read (or `commit` could clobber) another actor's document
    outcome. `environment` is included for the same reason: without it, the identical
    key submitted under TEST and PRODUCTION would also collide on this table's single
    `key_sha256` primary key.

    Length-prefixed, never separator-joined: `"|".join((actor_id, operation, ...))` would
    let `("ab", "c")` and `("a", "bc")` hash identically -- exactly the ambiguity this
    scoping fix exists to close, just moved one layer down. Each component is prefixed
    with its own big-endian uint32 byte length, so no component's content can ever be
    reinterpreted as a length prefix or as another component's boundary.
    """
    buf = bytearray()
    for part in (actor_id, operation, environment, idempotency_key):
        encoded = part.encode("utf-8")
        buf += len(encoded).to_bytes(4, "big")
        buf += encoded
    return hashlib.sha256(bytes(buf)).digest()


def _payload_sha256_bytes(payload_hash: str) -> bytes:
    """``payload_hash`` arrives as ``service.py::_payload_hash``'s hex digest string --
    convert once here so every SQL parameter is the raw 32 bytes migration 304's CHECK
    constraints require, never a hex string doing a second, wasteful trip through text.
    """
    return bytes.fromhex(payload_hash)


def _decompose(outcome: DocumentOutcome) -> tuple[str, list[tuple[PassportReviewFieldName, bool]]]:
    """Outcome -> (processing_state column value, review-field rows to insert).

    The VALUE half of a `ReadyOutcome`'s `review_fields` is intentionally dropped here --
    see the module docstring. `LowConfidenceOutcome.uncertain_fields` has no value to
    drop in the first place.
    """
    if isinstance(outcome, ReadyOutcome):
        return _STATE_READY_FOR_REVIEW, [(rf.field_path, rf.confirmation_required) for rf in outcome.review_fields]
    if isinstance(outcome, ProcessingOutcome):
        return _STATE_PROCESSING, []
    if isinstance(outcome, LowConfidenceOutcome):
        return _STATE_LOW_CONFIDENCE, [(f.field_path, f.confirmation_required) for f in outcome.uncertain_fields]
    if isinstance(outcome, UnreadableOutcome):
        return _STATE_UNREADABLE, []
    raise TypeError(f"unrecognized DocumentOutcome variant: {outcome!r}")  # pragma: no cover - exhaustive union


def _rehydrate(
    document_id: str,
    processing_state: str,
    field_rows: list[asyncpg.Record],
) -> DocumentOutcome:
    if processing_state == _STATE_PROCESSING:
        return ProcessingOutcome(document_id=document_id)
    if processing_state == _STATE_UNREADABLE:
        return UnreadableOutcome(document_id=document_id)
    if processing_state == _STATE_LOW_CONFIDENCE:
        return LowConfidenceOutcome(
            document_id=document_id,
            uncertain_fields=tuple(
                UncertainReviewField(
                    field_path=PassportReviewFieldName(row["field_path"]),
                    confirmation_required=row["confirmation_required"],
                )
                for row in field_rows
            ),
        )
    if processing_state == _STATE_READY_FOR_REVIEW:
        logger.warning(
            "garuda_documents: replay of a READY_FOR_REVIEW document (id=%s) requested -- "
            "the extracted field values were never persisted (PII boundary); raising "
            "ReadyOutcomeValueNotPersisted rather than fabricating a placeholder",
            document_id,
        )
        persisted_fields = tuple(
            (PassportReviewFieldName(row["field_path"]), row["confirmation_required"]) for row in field_rows
        )
        raise ReadyOutcomeValueNotPersisted(document_id, persisted_fields)
    raise ValueError(f"unrecognized processing_state column value: {processing_state!r}")  # pragma: no cover


class PostgresDocumentStore:
    """Real ``DocumentStorePort`` (see ``ports.py``) over ``garuda_documents``."""

    def __init__(self, pool: asyncpg.Pool, *, environment: str) -> None:
        self._pool = pool
        self._environment = environment

    async def get_existing(
        self, idempotency_key: str, payload_hash: str, *, actor_id: str
    ) -> DocumentOutcome | None:
        key_hash = _scoped_key_sha256(
            actor_id=actor_id,
            operation=_OPERATION_UPLOAD_INTAKE_DOCUMENT,
            environment=self._environment,
            idempotency_key=idempotency_key,
        )
        payload_hash_bytes = _payload_sha256_bytes(payload_hash)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT document_id, canonical_payload_sha256, processing_state
                  FROM public.garuda_documents
                 WHERE key_sha256 = $1
                """,
                key_hash,
            )
            if row is None:
                return None
            if bytes(row["canonical_payload_sha256"]) != payload_hash_bytes:
                raise IdempotencyConflictError(idempotency_key)
            field_rows = await conn.fetch(
                """
                SELECT field_path, confirmation_required
                  FROM public.garuda_document_review_fields
                 WHERE document_id = $1
                 ORDER BY field_path
                """,
                row["document_id"],
            )
        return _rehydrate(row["document_id"], row["processing_state"], field_rows)

    async def commit(
        self, idempotency_key: str, payload_hash: str, outcome: DocumentOutcome, *, actor_id: str
    ) -> bool:
        key_hash = _scoped_key_sha256(
            actor_id=actor_id,
            operation=_OPERATION_UPLOAD_INTAKE_DOCUMENT,
            environment=self._environment,
            idempotency_key=idempotency_key,
        )
        payload_hash_bytes = _payload_sha256_bytes(payload_hash)
        processing_state, fields = _decompose(outcome)

        # Sentinel used only to unwind out of the transaction block below on a lost
        # race -- never surfaced to the caller. Raised (not merely returned) so the
        # `async with conn.transaction()` context manager sees a real exception and
        # issues an explicit ROLLBACK on its way out, rather than relying on Postgres'
        # implicit-rollback-on-COMMIT-of-an-aborted-transaction behaviour, which is
        # correct but a strictly harder property to read from this call site.
        class _LostRace(Exception):
            pass

        try:
            async with self._pool.acquire() as conn, conn.transaction():
                existing = await conn.fetchrow(
                    """
                    SELECT canonical_payload_sha256
                      FROM public.garuda_documents
                     WHERE key_sha256 = $1
                     FOR UPDATE
                    """,
                    key_hash,
                )
                if existing is not None:
                    if bytes(existing["canonical_payload_sha256"]) != payload_hash_bytes:
                        raise IdempotencyConflictError(idempotency_key)
                    # Already committed by a previous call -- this call is not the
                    # winner. `service.py` re-reads via `get_existing` for the outcome.
                    raise _LostRace()

                # `SELECT ... FOR UPDATE` above only locks a row that already exists --
                # for a genuinely NEW key, there is nothing to lock, and two concurrent
                # callers can both reach here. `key_sha256`'s PRIMARY KEY is the real
                # atomicity boundary: the loser's INSERT below raises
                # `UniqueViolationError`, caught and turned into `_LostRace` the same
                # way, never a raw asyncpg exception escaping this method's `bool`
                # contract.
                now = datetime.now(UTC)
                if not await conn.fetchval(
                    "SELECT public.active_garuda_document_policy_available($1, $2)",
                    self._environment,
                    now,
                ):
                    raise PersistencePolicyUnavailable("no active GARUDA_DOCUMENT retention policy")

                try:
                    await conn.execute(
                        """
                        INSERT INTO public.garuda_documents
                            (key_sha256, canonical_payload_sha256, document_id, environment, processing_state)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        key_hash,
                        payload_hash_bytes,
                        outcome.document_id,
                        self._environment,
                        processing_state,
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise _LostRace() from exc

                for field_path, confirmation_required in fields:
                    await conn.execute(
                        """
                        INSERT INTO public.garuda_document_review_fields
                            (document_id, field_path, confirmation_required)
                        VALUES ($1, $2, $3)
                        """,
                        outcome.document_id,
                        field_path.value,
                        confirmation_required,
                    )
        except _LostRace:
            return False
        return True
