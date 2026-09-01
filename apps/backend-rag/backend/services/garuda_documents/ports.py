"""Storage port for document intake idempotency.

L1 (retention + archive) has not merged into `feature/garuda-voa` yet — no
garuda-scoped documents migration exists, and LANES.md is explicit that a lane must not
persist a row before L1's retention primitive covers it. `DocumentStorePort` is therefore
the seam: `service.py` is written entirely against this Protocol, and a real Postgres
implementation (owned by L1/L2, retention-covered) can be dropped in later without
touching the OCR/confidence/redaction logic this lane owns.

`InMemoryDocumentStore` is a reference implementation for THIS lane's own tests only —
it is not retention-aware and must never be wired into a running service.
"""

from __future__ import annotations

from typing import Protocol

from backend.services.garuda_documents.models import DocumentOutcome


class DocumentStorePort(Protocol):
    """Idempotency-key-scoped storage for one intake document's outcome.

    Mirrors the contract's Idempotency-Key semantics (openapi.yaml top-level description):
    an exact scoped key plus the same canonical payload replays the original outcome with
    no repeated side effect; a different payload under the same key is an
    IDEMPOTENCY_CONFLICT, which this port signals by raising `IdempotencyConflictError` —
    `service.py` never has to special-case a store implementation's own exceptions.
    """

    async def get_existing(self, idempotency_key: str, payload_hash: str) -> DocumentOutcome | None:
        """Returns the previously committed outcome for an exact key+payload replay, or
        None if this is a first-time submission for this key. Raises
        `IdempotencyConflictError` if the key is already bound to a DIFFERENT payload hash.
        """
        ...

    async def commit(self, idempotency_key: str, payload_hash: str, outcome: DocumentOutcome) -> bool:
        """Atomically persists `outcome` iff no outcome is yet committed for this key —
        a compare-and-set, not a blind write. Returns True when THIS call performed the
        commit (the caller is the one that should fire any at-most-once side effect, like
        a staff work-item notification); returns False when a concurrent call already won
        (`service.py` then re-reads via `get_existing` and uses the winner's outcome
        instead of its own).

        Two same-key requests can genuinely race here: `get_existing` returning None does
        not mean this call is exclusive owner of the key, because OCR runs as an `await`
        in between — a second coroutine can enter the same window on the same event loop,
        let alone a second process. A real store implements this as an
        `INSERT ... ON CONFLICT DO NOTHING RETURNING` (or equivalent) so the atomicity is
        the database's, not a lock this module has to hold. Still raises
        `IdempotencyConflictError` if the key is already bound to a DIFFERENT payload hash.
        """
        ...


class IdempotencyConflictError(Exception):
    """Raised by a `DocumentStorePort` when a key is replayed with a different payload."""


class InMemoryDocumentStore:
    """Test-only reference implementation. NOT retention-aware — never use outside this
    lane's own unit tests.

    `commit` is compare-and-set even here (a single `dict.setdefault` call, atomic with
    respect to other coroutines because it contains no `await`) so this reference
    implementation actually exercises the race-safety contract `DocumentStorePort.commit`
    documents, rather than silently passing tests that a real concurrent store would fail.
    """

    def __init__(self) -> None:
        self._by_key: dict[str, tuple[str, DocumentOutcome]] = {}

    async def get_existing(self, idempotency_key: str, payload_hash: str) -> DocumentOutcome | None:
        existing = self._by_key.get(idempotency_key)
        if existing is None:
            return None
        existing_hash, outcome = existing
        if existing_hash != payload_hash:
            raise IdempotencyConflictError(idempotency_key)
        return outcome

    async def commit(self, idempotency_key: str, payload_hash: str, outcome: DocumentOutcome) -> bool:
        winning = self._by_key.setdefault(idempotency_key, (payload_hash, outcome))
        if winning[0] != payload_hash:
            raise IdempotencyConflictError(idempotency_key)
        return winning[1] is outcome
