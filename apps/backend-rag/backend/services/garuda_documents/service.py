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
from backend.services.garuda_documents.ports import DocumentStorePort

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
    ) -> DocumentOutcome:
        # Stateless request-shape checks first: deterministic on the payload alone, so
        # replaying them is always safe and they never need idempotency tracking.
        byte_validation.validate_media_type(declared_media_type)
        byte_validation.validate_size(raw_bytes)

        payload_hash = _payload_hash(raw_bytes, document_kind)
        existing = await self._store.get_existing(idempotency_key, payload_hash)
        if existing is not None:
            return existing

        outcome = await self._process_new_upload(raw_bytes, document_kind)

        # `commit` is a compare-and-set, not a blind write (ports.py docstring): OCR ran
        # under an `await`, so a concurrent request with the same key can have committed
        # its own outcome in the meantime. Whoever's commit actually wins is the one
        # outcome of record — the loser discards its own result and adopts the winner's,
        # so two racing requests can never disagree or double-fire the work-item hook.
        won = await self._store.commit(idempotency_key, payload_hash, outcome)
        if not won:
            winning_outcome = await self._store.get_existing(idempotency_key, payload_hash)
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
