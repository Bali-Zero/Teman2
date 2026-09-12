"""Orchestrates one document upload: validate → (idempotent) OCR → classify → outcome.

This is the storage-agnostic core L2's router wires into the HTTP surface once it exists,
and L1's retention-covered store replaces `InMemoryDocumentStore` with once it merges (see
`ports.py`). Nothing here knows about FastAPI, Postgres, or the flag.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol
from uuid import uuid4

from backend.services.garuda_documents import byte_validation
from backend.services.garuda_documents.confidence import (
    all_confident,
    classify_fields,
    to_review_fields,
    to_uncertain_fields,
)
from backend.services.garuda_documents.models import (
    DocumentKind,
    DocumentOutcome,
    LowConfidenceOutcome,
    ProcessingOutcome,
    ReadyOutcome,
    UnreadableOutcome,
)
from backend.services.garuda_documents.ocr_client import extract_passport_biodata_dual_pass
from backend.services.garuda_documents.ports import DocumentStorePort, ReadyOutcomeValueNotPersisted

logger = logging.getLogger(__name__)

# WorkItemHook fires at most once per (idempotency_key, payload_hash) — exactly when a new
# outcome is first committed, never on a replay. It is intentionally opaque to this module:
# L7 (control tower) owns what a "work item" actually is; this lane only guarantees the
# at-most-once call.
WorkItemHook = Callable[[str, DocumentOutcome], Awaitable[None]]


class DocumentProcessingUnavailableError(Exception):
    """Raised when the local OCR pipeline cannot be reached. Maps to 503
    DOCUMENT_PROCESSING_UNAVAILABLE. Never persisted as an outcome — no row, no work item.
    """


class _ClockPort(Protocol):
    def new_document_id(self) -> str: ...


class DefaultClock:
    def new_document_id(self) -> str:
        return uuid4().hex


def _payload_hash(raw_bytes: bytes, document_kind: DocumentKind) -> str:
    digest = hashlib.sha256()
    digest.update(document_kind.value.encode("utf-8"))
    digest.update(raw_bytes)
    return digest.hexdigest()


def _reconcile_lost_race_ready_replay(
    local_outcome: DocumentOutcome, exc: ReadyOutcomeValueNotPersisted
) -> DocumentOutcome:
    """Recover a `commit()` race-loser's own `ReadyOutcome` instead of propagating
    `ReadyOutcomeValueNotPersisted` — WITHOUT fabricating or persisting anything new.

    This caller ran its own OCR pass on the exact same bytes (`commit`'s payload-hash
    check already guarantees identical input) and, if that pass also concluded
    READY_FOR_REVIEW, already holds a `ReadyOutcome` with REAL values in `local_outcome`
    — its own honest OCR result for the document IT uploaded, not someone else's data.
    Returning it, re-tagged with the WINNER's `document_id` (`exc.document_id` — the one
    actually persisted), preserves the "two racers never disagree" invariant `commit()`'s
    docstring promises: they now agree on `document_id`, which is the one field a lost
    race could otherwise return inconsistently (each `_process_new_upload` call mints its
    own via `uuid4().hex`).

    Structural agreement is checked, not assumed: `exc.persisted_fields` is exactly what
    WAS committed (field names + confirmation flags, the only part the store persists for
    a ReadyOutcome). If `local_outcome` is not itself a matching ReadyOutcome — a
    different processing_state, or the same state but different field
    names/confirmation flags (OCR non-determinism genuinely disagreeing, however rare) —
    there is nothing honest left to return, and this re-raises `exc` rather than guess.
    Compared as a set: persisted rows arrive `ORDER BY field_path` (postgres_store.py),
    while `local_outcome.review_fields`' order comes from `confidence.py`'s enum
    iteration order — a real match must not be rejected over ordering alone.
    """
    if not isinstance(local_outcome, ReadyOutcome):
        raise exc
    local_structure = frozenset(
        (review_field.field_path, review_field.confirmation_required) for review_field in local_outcome.review_fields
    )
    if local_structure != frozenset(exc.persisted_fields):
        raise exc
    return ReadyOutcome(document_id=exc.document_id, review_fields=local_outcome.review_fields)


class DocumentIntakeService:
    def __init__(
        self,
        store: DocumentStorePort,
        clock: _ClockPort | None = None,
        work_item_hook: WorkItemHook | None = None,
    ) -> None:
        self._store = store
        self._clock = clock or DefaultClock()
        self._work_item_hook = work_item_hook

    async def submit_document(
        self,
        *,
        raw_bytes: bytes,
        declared_media_type: str,
        document_kind: DocumentKind,
        idempotency_key: str,
        actor_id: str,
    ) -> DocumentOutcome:
        # Stateless request-shape checks first: deterministic on the payload alone, so
        # replaying them is always safe and they never need idempotency tracking.
        byte_validation.validate_media_type(declared_media_type)
        byte_validation.validate_size(raw_bytes)

        payload_hash = _payload_hash(raw_bytes, document_kind)
        existing = await self._store.get_existing(idempotency_key, payload_hash, actor_id=actor_id)
        if existing is not None:
            return existing

        outcome = await self._process_new_upload(raw_bytes, document_kind)

        # `commit` is a compare-and-set, not a blind write (ports.py docstring): OCR ran
        # under an `await`, so a concurrent request with the same key can have committed
        # its own outcome in the meantime. Whoever's commit actually wins is the one
        # outcome of record — the loser discards its own result and adopts the winner's,
        # so two racing requests can never disagree or double-fire the work-item hook.
        won = await self._store.commit(idempotency_key, payload_hash, outcome, actor_id=actor_id)
        if not won:
            try:
                winning_outcome = await self._store.get_existing(idempotency_key, payload_hash, actor_id=actor_id)
            except ReadyOutcomeValueNotPersisted as exc:
                # The winner committed a ReadyOutcome and the store cannot rehydrate its
                # ReviewField.value (PII boundary — postgres_store.py module docstring).
                # Unlike an ORDINARY sequential replay (top of this method, above — no
                # OCR ran on THIS call, nothing to reconcile against, so that path is
                # left to raise), this caller LOST the commit race after running its own
                # OCR pass on the identical bytes: `outcome` above already holds a full
                # ReadyOutcome with real values. See `_reconcile_lost_race_ready_replay`
                # for why re-tagging it with the winner's document_id is safe rather than
                # a fabrication, and when it still has to give up and re-raise.
                winning_outcome = _reconcile_lost_race_ready_replay(outcome, exc)
            assert winning_outcome is not None  # commit() just told us a record exists
            return winning_outcome

        if self._work_item_hook is not None and not isinstance(outcome, ReadyOutcome):
            try:
                await self._work_item_hook(idempotency_key, outcome)
            except Exception:
                # The outcome is already correctly committed and is what the customer
                # sees either way — a downstream notification failure must not turn a
                # successful upload into a 500. Logged so it is not silently lost; full
                # exactly-once delivery (outbox/retry) is L7's control-tower territory,
                # not this lane's.
                logger.exception("garuda_documents: work_item_hook failed for %s", idempotency_key)
        return outcome

    async def _process_new_upload(self, raw_bytes: bytes, document_kind: DocumentKind) -> DocumentOutcome:
        document_id = self._clock.new_document_id()

        if not byte_validation.is_readable_image(raw_bytes):
            return UnreadableOutcome(document_id=document_id)

        image_base64 = base64.b64encode(raw_bytes).decode("ascii")
        passes = await extract_passport_biodata_dual_pass(image_base64)
        if passes is None:
            logger.warning("garuda_documents: local OCR pipeline unavailable, no outcome persisted")
            raise DocumentProcessingUnavailableError()

        pass_a, pass_b = passes
        verdicts = classify_fields(pass_a, pass_b)

        if all_confident(verdicts):
            return ReadyOutcome(document_id=document_id, review_fields=tuple(to_review_fields(verdicts)))

        uncertain = to_uncertain_fields(verdicts)
        if uncertain:
            return LowConfidenceOutcome(document_id=document_id, uncertain_fields=tuple(uncertain))
        # Defensive: classify_fields always returns one verdict per PassportReviewFieldName,
        # so this is unreachable in practice (all_confident False implies >=1 uncertain).
        return ProcessingOutcome(document_id=document_id)
