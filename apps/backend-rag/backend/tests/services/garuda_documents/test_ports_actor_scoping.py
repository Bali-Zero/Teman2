"""`DocumentStorePort`'s actor scoping, proved on the reference implementation.

`ports.py` makes `actor_id` a required, non-defaulted keyword on both port methods
because an `Idempotency-Key` is a CLIENT-chosen string: nothing stops two different
customers from picking the same literal value. A store that keyed on that string alone
would let one customer's `get_existing` read the other's committed outcome, or let one
customer's `commit` be reported as a lost race against the other's.

`InMemoryDocumentStore` is the only implementation this lane can exercise without a
database, and it is what every service-level test in this directory runs against — so if
IT silently ignored `actor_id`, the whole suite would keep passing while the contract went
unenforced. These tests pin the scoping on that implementation directly.

Guilt, not just innocence: reverting `InMemoryDocumentStore` to a single-string key (its
shape before actor scoping) turns `test_two_actors_sharing_a_literal_key_do_not_collide`
and `test_a_second_actor_cannot_read_the_first_actors_outcome` red. The two
`same_actor_*` tests are the innocence half — scoping must not break a genuine replay.
"""

from __future__ import annotations

import pytest

from backend.services.garuda_documents.models import UnreadableOutcome
from backend.services.garuda_documents.ports import InMemoryDocumentStore

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
