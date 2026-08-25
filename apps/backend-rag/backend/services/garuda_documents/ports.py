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

    async def commit(self, idempotency_key: str, payload_hash: str, outcome: DocumentOutcome) -> None:
        """Persists the outcome exactly once per (idempotency_key, payload_hash)."""
        ...


class IdempotencyConflictError(Exception):
    """Raised by a `DocumentStorePort` when a key is replayed with a different payload."""


class InMemoryDocumentStore:
    """Test-only reference implementation. NOT retention-aware — never use outside this
    lane's own unit tests.
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

    async def commit(self, idempotency_key: str, payload_hash: str, outcome: DocumentOutcome) -> None:
        self._by_key[idempotency_key] = (payload_hash, outcome)
