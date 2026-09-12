"""`DocumentStorePort`'s actor scoping — at the port, through the service, and
through the router's observing wrapper.

`ports.py` makes `actor_id` a required, non-defaulted keyword on both port methods
because an `Idempotency-Key` is a CLIENT-chosen string: nothing stops two different
customers from picking the same literal value. A store that keyed on that string alone
would let one customer's `get_existing` read the other's committed outcome, or let one
customer's `commit` be reported as a lost race against the other's.

`InMemoryDocumentStore` is the only implementation this lane can exercise without a
database, and it is what every service-level test in this directory runs against — so if
IT silently ignored `actor_id`, the whole suite would keep passing while the contract went
unenforced. These tests pin the scoping on that implementation directly.

Guilt, measured rather than asserted. Each mutation below was run against this file:

  - `InMemoryDocumentStore` reverted to a single-string key (its shape before actor
    scoping) -> 2 failed, 3 passed. The three that stay green are the replay, conflict
    and required-keyword checks; they are not isolation proofs and are not meant to be.
  - the store keyed on `actor_id` ALONE, ignoring the idempotency key ->
    `test_one_actors_two_distinct_keys_stay_independent` red. Without that test the
    mutant passed all five of the original checks.
  - every `actor_id=` forward in `service.py` and the router replaced by one constant
    -> `test_service_does_not_replay_one_actors_outcome_to_another` red. Without it the
    whole suite stayed green while the actor never actually reached the store.
  - `_ReplayTrackingStore` substituting its own actor -> `test_replay_tracking_wrapper_
    forwards_the_actor_it_was_given` red.

The `same_actor_*` tests are the innocence half — scoping must not break a genuine replay.
"""

from __future__ import annotations

import pytest

from backend.app.routers import garuda_documents_router
from backend.services.garuda_documents.models import DocumentKind, UnreadableOutcome
from backend.services.garuda_documents.ports import InMemoryDocumentStore
from backend.services.garuda_documents.service import DocumentIntakeService

pytestmark = pytest.mark.asyncio

_SHARED_KEY = "a-key-both-customers-happened-to-pick"
_PAYLOAD_A = "aa" * 32
_PAYLOAD_B = "bb" * 32


@pytest.fixture
def store() -> InMemoryDocumentStore:
    return InMemoryDocumentStore()


async def test_two_actors_sharing_a_literal_key_do_not_collide(store: InMemoryDocumentStore):
    """Both actors must WIN their own commit under the same literal key."""
    assert await store.commit(_SHARED_KEY, _PAYLOAD_A, UnreadableOutcome(document_id="doc-a"), actor_id="actor-a")
    assert await store.commit(_SHARED_KEY, _PAYLOAD_B, UnreadableOutcome(document_id="doc-b"), actor_id="actor-b")


async def test_a_second_actor_cannot_read_the_first_actors_outcome(store: InMemoryDocumentStore):
    """A key/payload pair bound by one actor is simply ABSENT for another — not a
    replay (that would leak the first actor's document_id) and not an
    IdempotencyConflictError (that would confirm the key exists, an enumeration
    oracle across customers). `None` is the only honest answer.
    """
    await store.commit(_SHARED_KEY, _PAYLOAD_A, UnreadableOutcome(document_id="doc-a"), actor_id="actor-a")

    assert await store.get_existing(_SHARED_KEY, _PAYLOAD_A, actor_id="actor-b") is None
    assert await store.get_existing(_SHARED_KEY, _PAYLOAD_B, actor_id="actor-b") is None


async def test_same_actor_same_key_same_payload_still_replays(store: InMemoryDocumentStore):
    committed = UnreadableOutcome(document_id="doc-a")
    await store.commit(_SHARED_KEY, _PAYLOAD_A, committed, actor_id="actor-a")

    replayed = await store.get_existing(_SHARED_KEY, _PAYLOAD_A, actor_id="actor-a")

    assert replayed == committed


async def test_same_actor_same_key_different_payload_still_conflicts(store: InMemoryDocumentStore):
    from backend.services.garuda_documents.ports import IdempotencyConflictError

    await store.commit(_SHARED_KEY, _PAYLOAD_A, UnreadableOutcome(document_id="doc-a"), actor_id="actor-a")

    with pytest.raises(IdempotencyConflictError):
        await store.get_existing(_SHARED_KEY, _PAYLOAD_B, actor_id="actor-a")
    with pytest.raises(IdempotencyConflictError):
        await store.commit(_SHARED_KEY, _PAYLOAD_B, UnreadableOutcome(document_id="doc-z"), actor_id="actor-a")


async def test_actor_id_is_required_not_defaulted():
    """A store that accepted a missing `actor_id` would let a stale call site keep
    compiling while silently dropping the scoping — the failure mode this keyword
    exists to make loud.
    """
    store = InMemoryDocumentStore()
    with pytest.raises(TypeError):
        await store.get_existing(_SHARED_KEY, _PAYLOAD_A)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        await store.commit(_SHARED_KEY, _PAYLOAD_A, UnreadableOutcome(document_id="doc-a"))  # type: ignore[call-arg]


async def test_one_actors_two_distinct_keys_stay_independent(store: InMemoryDocumentStore):
    """Scoping must add the actor to the key, never REPLACE it.

    A store indexed on `actor_id` alone satisfies every cross-actor assertion above and is
    still badly wrong: one customer's second, unrelated upload would come back as an
    IdempotencyConflictError against their first. This is the test that separates the two.
    """
    first = UnreadableOutcome(document_id="doc-first")
    second = UnreadableOutcome(document_id="doc-second")

    assert await store.commit("key-one-0000000000000", _PAYLOAD_A, first, actor_id="actor-a")
    assert await store.commit("key-two-0000000000000", _PAYLOAD_B, second, actor_id="actor-a")

    assert await store.get_existing("key-one-0000000000000", _PAYLOAD_A, actor_id="actor-a") == first
    assert await store.get_existing("key-two-0000000000000", _PAYLOAD_B, actor_id="actor-a") == second


async def test_committing_the_same_outcome_instance_twice_yields_one_winner(store: InMemoryDocumentStore):
    """`commit` returning True is the caller's permission to fire an at-most-once side
    effect (the staff work-item hook). Exactly one caller may receive it. Deciding the
    winner by `outcome` identity rather than by the entry this call built hands BOTH
    callers that permission whenever they happen to share one outcome instance.
    """
    shared = UnreadableOutcome(document_id="doc-shared")

    assert await store.commit(_SHARED_KEY, _PAYLOAD_A, shared, actor_id="actor-a") is True
    assert await store.commit(_SHARED_KEY, _PAYLOAD_A, shared, actor_id="actor-a") is False


async def test_service_does_not_replay_one_actors_outcome_to_another(monkeypatch):
    """The port-level tests above call the store DIRECTLY, so they stay green even if
    `service.py` forwards a constant instead of the caller's actor. This one goes through
    `submit_document`, which is the only path production uses.

    Deliberately uses bytes that fail `byte_validation` (an UnreadableOutcome), so no OCR
    runs and no synthetic image is needed — the property under test is the key, not the
    pipeline.
    """
    store = InMemoryDocumentStore()
    service = DocumentIntakeService(store=store)
    submission = {
        "raw_bytes": b"not-an-image-at-all",
        "declared_media_type": "image/png",
        "document_kind": DocumentKind.PASSPORT_BIODATA,
        "idempotency_key": _SHARED_KEY,
    }

    first = await service.submit_document(**submission, actor_id="actor-a")
    second = await service.submit_document(**submission, actor_id="actor-b")

    assert first is not second
    assert first.document_id != second.document_id


async def test_replay_tracking_wrapper_forwards_the_actor_it_was_given():
    """`_ReplayTrackingStore` exists to observe replays, not to make a second scoping
    decision. A wrapper that substituted or dropped the actor would silently undo the
    scoping for every request that goes through the router — which is all of them.
    """
    seen: list[str] = []

    class _RecordingStore:
        async def get_existing(self, idempotency_key, payload_hash, *, actor_id):
            seen.append(actor_id)
            return None

        async def commit(self, idempotency_key, payload_hash, outcome, *, actor_id):
            seen.append(actor_id)
            return True

    wrapper = garuda_documents_router._ReplayTrackingStore(_RecordingStore())
    await wrapper.get_existing(_SHARED_KEY, _PAYLOAD_A, actor_id="actor-from-session")
    await wrapper.commit(_SHARED_KEY, _PAYLOAD_A, UnreadableOutcome(document_id="doc-a"), actor_id="actor-from-session")

    assert seen == ["actor-from-session", "actor-from-session"]
