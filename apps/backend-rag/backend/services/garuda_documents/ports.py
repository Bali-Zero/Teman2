"""Storage port for document intake idempotency.

Migration 304 (`garuda_documents`, `garuda_document_review_fields`, retention bound by
`bind_garuda_document_retention_policy`) is applied in production, and
`postgres_store.PostgresDocumentStore` is the real implementation of this Protocol.
`DocumentStorePort` remains the seam: `service.py` is written entirely against it, and the
in-memory store below is what the service tests use. The exceptions live here, beside the
Protocol, so a storage-agnostic caller catches them without importing a concrete store.

`InMemoryDocumentStore` is a reference implementation for THIS lane's own tests only —
it is not retention-aware and must never be wired into a running service.
"""

from __future__ import annotations

from typing import Protocol

from backend.services.garuda_documents.models import DocumentOutcome, PassportReviewFieldName


class DocumentStorePort(Protocol):
    """Idempotency-key-scoped storage for one intake document's outcome.

    Mirrors the contract's Idempotency-Key semantics (openapi.yaml top-level description
    AND the `IdempotencyKey` parameter description: "Scoped to actor and operation"): an
    exact scoped key plus the same canonical payload replays the original outcome with no
    repeated side effect -- with ONE qualification a PII-honouring store cannot avoid: a
    replayed `ReadyOutcome` cannot carry its field VALUES and surfaces as
    `ReadyOutcomeValueNotPersisted` instead (limit L5); a different payload under the same key is an
    IDEMPOTENCY_CONFLICT, which this port signals by raising `IdempotencyConflictError` —
    `service.py` never has to special-case a store implementation's own exceptions.

    `actor_id` is required on every call, never defaulted: a bare `idempotency_key` is a
    client-chosen string with no uniqueness guarantee ACROSS actors, so a store that keyed
    only on it would let two different actors who happen to reuse the same literal key
    collide — one actor's `commit` becoming readable (or un-replayable-around) by another.
    Implementations must fold `actor_id` into whatever they use as the storage key, not
    merely accept and ignore it.
    """

    async def get_existing(
        self, idempotency_key: str, payload_hash: str, *, actor_id: str
    ) -> DocumentOutcome | None:
        """Returns the previously committed outcome for an exact key+payload replay by
        THIS SAME actor, or None if this is a first-time submission for this
        (actor, key) pair. Raises `IdempotencyConflictError` if the key is already bound
        (for this actor) to a DIFFERENT payload hash. A different actor reusing the same
        `idempotency_key` string is a distinct binding, not a replay and not a conflict.

        REPLAY ORDER, stated here so no consumer infers the stronger promise: a replayed
        `LowConfidenceOutcome` returns its `uncertain_fields` in the CANONICAL order --
        `PassportReviewFieldName`'s declaration order -- and NOT in the order the original
        `commit` received. For every outcome `confidence.py` builds today the two coincide,
        because it assembles the tuple by iterating that same enum; for a tuple assembled
        in any other order they do not, and what comes back is the canonical one. A
        consumer that needs the order it sent needs the store to persist an ordinal, which
        is a column, which is a migration and therefore a different concern. This is
        declared limit L1 in the PR's brief (`limits:` block) and nowhere else; a docstring
        that says more or less than L1 is wrong.

        Raises `IdempotencyKeyVanished` only from `commit()`'s post-collision re-read (see
        that method); `get_existing` itself never raises it.
        """
        ...

    async def commit(
        self, idempotency_key: str, payload_hash: str, outcome: DocumentOutcome, *, actor_id: str
    ) -> bool:
        """Atomically persists `outcome` iff no outcome is yet committed for this
        (actor, key) pair —
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


class ReadyOutcomeValueNotPersisted(Exception):
    """Raised by `get_existing()` when a replayed key resolves to a committed `ReadyOutcome`
    whose store cannot rehydrate `ReviewField.value` — the PII boundary forbids persisting
    an extracted passport field's actual VALUE in cleartext (see `postgres_store.py`'s
    module docstring for the full argument), so a store that honours that boundary has
    nothing to rehydrate the value FROM.

    Lives here, on the Protocol's own module, rather than on any one concrete store — a
    storage-agnostic caller (`service.py`) needs to be able to catch this without
    importing a specific implementation, the same reason `IdempotencyConflictError` lives
    here instead of on each store that raises it.

    Carries enough of the persisted STRUCTURE (`document_id`, `persisted_fields` — field
    names and confirmation flags only, never a value) that a caller holding its own
    independently-derived `ReadyOutcome` for the identical bytes (e.g. the loser of a
    `commit()` race, which ran its own OCR pass before losing) can verify that outcome's
    shape agrees with what was actually committed and re-tag it with the authoritative
    `document_id`, without the store ever having to hand back — or fabricate — a value.
    A caller with no such independent outcome (an ordinary sequential replay, OCR never
    ran on this call) has nothing to reconcile against and must let this propagate; the
    caller that CAN reconcile does not exist yet and arrives in its own PR.
    """

    def __init__(
        self,
        document_id: str,
        persisted_fields: tuple[tuple[PassportReviewFieldName, bool], ...],
    ) -> None:
        super().__init__(document_id)
        self.document_id = document_id
        self.persisted_fields = persisted_fields


class DuplicateReviewFieldPath(ValueError):
    """Raised by `commit()` BEFORE any SQL when an outcome names the same
    `PassportReviewFieldName` twice. The model does not forbid it; migration 304's
    `garuda_document_review_fields` has PRIMARY KEY (document_id, field_path) and would
    refuse the second row with a raw `asyncpg.UniqueViolationError` outside `commit()`'s
    contract (SPEC v2 P6: no raw asyncpg exception escapes). Typed here so the caller's
    bug is named as its bug and nothing is written."""

    def __init__(self, document_id: str, field_path: str) -> None:
        super().__init__(f"{document_id}: review field {field_path!r} named twice")
        self.document_id = document_id
        self.field_path = field_path


class IdempotencyKeyVanished(Exception):
    """Raised by `commit()` when its INSERT lost to a concurrent writer on the key's PRIMARY
    KEY and the re-read that follows finds NO row holding that key.

    The loser's transaction died on the collision, so it re-reads on a fresh connection.
    Migration 304's `guard_garuda_document_mutation` forbids DELETE only while
    `clock_timestamp() < retention_until`, so a row legitimately leaves after its retention
    expires; a caller whose single `commit()` straddles that window can find the key bound
    to nothing. That is outcome 3 of the loser's state machine (SPEC v2 §2): not corruption,
    not "impossible", and not a lost race either -- "you lost to X" is false when X is gone.

    Typed and on this module for the same reason `IdempotencyConflictError` is: a
    storage-agnostic caller must catch it without importing a concrete store. No retry is
    attempted -- re-running `commit()` re-enters a loop an adversarial re-occupier controls.
    What the HTTP layer answers is PR3's (limit L2 in the brief); until then it propagates.
    """

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(idempotency_key)
        self.idempotency_key = idempotency_key


class InMemoryDocumentStore:
    """Test-only reference implementation. NOT retention-aware — never use outside this
    lane's own unit tests.

    `commit` is compare-and-set even here (a single `dict.setdefault` call, atomic with
    respect to other coroutines because it contains no `await`) so this reference
    implementation actually exercises the race-safety contract `DocumentStorePort.commit`
    documents, rather than silently passing tests that a real concurrent store would fail.
    """

    def __init__(self) -> None:
        # Keyed by (actor_id, idempotency_key) -- NOT idempotency_key alone -- so this
        # reference implementation actually exercises the actor-scoping contract
        # `DocumentStorePort` documents, rather than silently passing tests that a real
        # cross-actor collision would fail.
        self._by_key: dict[tuple[str, str], tuple[str, DocumentOutcome]] = {}

    async def get_existing(
        self, idempotency_key: str, payload_hash: str, *, actor_id: str
    ) -> DocumentOutcome | None:
        existing = self._by_key.get((actor_id, idempotency_key))
        if existing is None:
            return None
        existing_hash, outcome = existing
        if existing_hash != payload_hash:
            raise IdempotencyConflictError(idempotency_key)
        return outcome

    async def commit(
        self, idempotency_key: str, payload_hash: str, outcome: DocumentOutcome, *, actor_id: str
    ) -> bool:
        # The winner is decided by the identity of the CANDIDATE ENTRY this call built,
        # not of `outcome`. Comparing `winning[1] is outcome` looks equivalent and is not:
        # two calls that happen to carry the SAME outcome instance would both be told they
        # won, and both would fire the at-most-once side effect `commit`'s contract says
        # exactly one caller may fire. A fresh tuple per call has no such collision.
        candidate = (payload_hash, outcome)
        winning = self._by_key.setdefault((actor_id, idempotency_key), candidate)
        if winning[0] != payload_hash:
            raise IdempotencyConflictError(idempotency_key)
        return winning is candidate
