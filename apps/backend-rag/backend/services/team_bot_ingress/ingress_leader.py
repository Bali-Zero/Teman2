"""The leader-epoch CAS state machine (F9, superscar family #10 antidote).

Pure logic, zero I/O — Golden Rule #7 (data/logic separation). This is the
thing MANDATE.md's owning orchestrator asked to see "settled" before any
drill gets built on top of it: get this wrong and every downstream test
would faithfully prove the wrong design.

Why a CAS state machine and not a lockfile or a heuristic: superscar
family #10 ("active-active split-brain") names the antidote explicitly —
"Single-Source-of-Truth nel DB (`expected_status`/`assigned_node`) plus
graceful exit when `node != hostname`". This module IS that SSOT's
in-process contract. It is deliberately storage-agnostic
(``IngressLeaderStore`` is a ``Protocol``): ``ingress_state_repo.py``
backs it with Postgres so the SAME record the CRM mutation endpoints
already run next to can check it in-process (F7: "Backend routes
independently enforce ... the local authorizer is early-deny only" — the
local check on Mini/Pro is early-deny only; THIS is where real
enforcement lives), and ``InMemoryIngressLeaderStore`` below backs the
same contract for the drill suite with an ``asyncio.Lock`` standing in
for a DB transaction's atomicity.

Three operations, three failure shapes — deliberately NOT collapsed into
one "check permission" call, because the three callers need to fail
differently:

- ``try_promote`` — only ``team-bot-failoverd`` calls this, and only to
  hand leadership to ITS OWN node. There is no code path anywhere in this
  package that promotes a node back on its own initiative — F9's "no
  automatic failback" is enforced by that omission, not by a flag.
- ``renew`` — the ACTIVE node's heartbeat; extends the lease without
  bumping the epoch. A node that is no longer active, or believes a
  stale epoch, is rejected exactly like a mutation attempt would be.
- ``authorize`` — what a CRM mutation endpoint (or the ingress webhook
  itself) calls before acting on a principal ticket that carries a
  ``(node_id, epoch)`` pair. Three distinct rejection reasons map to two
  HTTP statuses via ``outcome_to_http_status`` — see its docstring for
  why LEASE_EXPIRED is NOT a third status code.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol


class PromoteOutcome(StrEnum):
    PROMOTED = "promoted"
    CONFLICT_STALE_EPOCH = "conflict_stale_epoch"


class RenewOutcome(StrEnum):
    RENEWED = "renewed"
    REJECTED_STALE_EPOCH = "rejected_stale_epoch"
    REJECTED_WRONG_NODE = "rejected_wrong_node"


class AuthorizeOutcome(StrEnum):
    AUTHORIZED = "authorized"
    REJECTED_STALE_EPOCH = "rejected_stale_epoch"
    REJECTED_WRONG_NODE = "rejected_wrong_node"
    REJECTED_LEASE_EXPIRED = "rejected_lease_expired"


# Every rejection is a 409 EXCEPT "the ticket names a node that has never
# held (or no longer holds) the seat at all" — that one distinguishes
# itself as 403. LEASE_EXPIRED is deliberately mapped to 409, not a third
# status: from the caller's point of view an expired lease and a stale
# epoch are the SAME instruction ("re-read the current leader and retry
# with a fresh ticket, you may still be right about who holds it") — a
# distinct code here would tempt a caller to write a THIRD retry branch
# for a case that needs the identical handling as the first.
_AUTHORIZE_HTTP_STATUS: dict[AuthorizeOutcome, int] = {
    AuthorizeOutcome.AUTHORIZED: 200,
    AuthorizeOutcome.REJECTED_STALE_EPOCH: 409,
    AuthorizeOutcome.REJECTED_LEASE_EXPIRED: 409,
    AuthorizeOutcome.REJECTED_WRONG_NODE: 403,
}


def outcome_to_http_status(outcome: AuthorizeOutcome) -> int:
    """Map an :class:`AuthorizeOutcome` to the status code a mutation
    endpoint should return. Exhaustive by construction — a new
    ``AuthorizeOutcome`` member with no entry here raises ``KeyError``
    at first use rather than silently falling through to 200.
    """

    return _AUTHORIZE_HTTP_STATUS[outcome]


@dataclass(frozen=True, slots=True)
class IngressLeaderState:
    """One row of the control record F9 §4.2 names verbatim:
    ``active_node_id`` / ``leader_epoch`` / ``lease_expires_at`` /
    ``callback_uri_sha256`` / ``changed_at``. Non-PII by construction —
    every field is an infrastructure identifier, never a phone number or
    message content.
    """

    record_id: str
    active_node_id: str
    leader_epoch: int
    lease_expires_at: datetime
    callback_uri_sha256: str
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class PromoteResult:
    outcome: PromoteOutcome
    state: IngressLeaderState
    """Current state AFTER the call either way — on CONFLICT this is the
    state the caller's ``expected_epoch`` was stale against, handed back
    so ``failoverd`` can log what it actually lost to without a second
    read.
    """


@dataclass(frozen=True, slots=True)
class RenewResult:
    outcome: RenewOutcome
    state: IngressLeaderState


@dataclass(frozen=True, slots=True)
class AuthorizeResult:
    outcome: AuthorizeOutcome
    state: IngressLeaderState

    @property
    def http_status(self) -> int:
        return outcome_to_http_status(self.outcome)


class IngressLeaderStore(Protocol):
    """Storage-agnostic contract. ``ingress_state_repo.py`` implements
    this against Postgres; :class:`InMemoryIngressLeaderStore` below
    implements the identical contract for tests — same rules, same
    outcomes, no DB required to prove the state machine correct.
    """

    async def read(self) -> IngressLeaderState: ...

    async def try_promote(
        self,
        *,
        expected_epoch: int,
        new_node_id: str,
        lease_seconds: float,
        new_callback_sha256: str,
        now: datetime,
    ) -> PromoteResult: ...

    async def renew(
        self,
        *,
        node_id: str,
        epoch: int,
        lease_seconds: float,
        now: datetime,
    ) -> RenewResult: ...

    async def authorize(
        self,
        *,
        node_id: str,
        epoch: int,
        now: datetime,
    ) -> AuthorizeResult: ...


class InMemoryIngressLeaderStore:
    """Reference implementation of :class:`IngressLeaderStore`, backed by
    a single in-process ``IngressLeaderState`` guarded by an
    ``asyncio.Lock``.

    The lock is what makes a genuinely CONCURRENT ``try_promote`` race
    (``asyncio.gather(*[store.try_promote(...) for _ in range(N)])``)
    resolve to exactly one winner — the same guarantee Postgres's
    ``UPDATE ... WHERE leader_epoch = $expected`` gives via row-level
    locking, reproduced here without a database so the split-brain drill
    can prove it deterministically and fast.

    Every method opens with ``await asyncio.sleep(0)`` — a deliberate,
    minimal yield to the event loop BEFORE touching any state. A real
    Postgres-backed store (``ingress_state_repo.py``) always yields at
    this point too, because ``pool.acquire()``/``fetchrow()`` is a real
    network round-trip; without the same yield here, two callers racing
    via ``asyncio.gather`` on THIS in-memory store would never actually
    interleave (single-threaded asyncio runs a coroutine with no internal
    await point start-to-finish before ever handing control back), so a
    "concurrent" drill against it would silently degrade into two
    sequential calls — proving nothing about the CAS guarantee it exists
    to demonstrate. Caught by
    ``test_staging_drill.py::test_split_brain_attempted_and_refused``
    failing (both contenders "won", at epoch 2 and 3) before this yield
    was added — kept as a comment here so the fix does not silently
    regress if this class is edited again.
    """

    def __init__(self, initial: IngressLeaderState) -> None:
        self._state = initial
        self._lock = asyncio.Lock()

    async def read(self) -> IngressLeaderState:
        await asyncio.sleep(0)
        return self._state

    async def try_promote(
        self,
        *,
        expected_epoch: int,
        new_node_id: str,
        lease_seconds: float,
        new_callback_sha256: str,
        now: datetime,
    ) -> PromoteResult:
        await asyncio.sleep(0)
        async with self._lock:
            current = self._state
            if current.leader_epoch != expected_epoch:
                return PromoteResult(
                    outcome=PromoteOutcome.CONFLICT_STALE_EPOCH, state=current
                )
            promoted = IngressLeaderState(
                record_id=current.record_id,
                active_node_id=new_node_id,
                leader_epoch=current.leader_epoch + 1,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                callback_uri_sha256=new_callback_sha256,
                changed_at=now,
            )
            self._state = promoted
            return PromoteResult(outcome=PromoteOutcome.PROMOTED, state=promoted)

    async def renew(
        self,
        *,
        node_id: str,
        epoch: int,
        lease_seconds: float,
        now: datetime,
    ) -> RenewResult:
        await asyncio.sleep(0)
        async with self._lock:
            current = self._state
            if current.leader_epoch != epoch:
                return RenewResult(outcome=RenewOutcome.REJECTED_STALE_EPOCH, state=current)
            if current.active_node_id != node_id:
                return RenewResult(outcome=RenewOutcome.REJECTED_WRONG_NODE, state=current)
            renewed = replace(
                current,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                changed_at=now,
            )
            self._state = renewed
            return RenewResult(outcome=RenewOutcome.RENEWED, state=renewed)

    async def authorize(
        self,
        *,
        node_id: str,
        epoch: int,
        now: datetime,
    ) -> AuthorizeResult:
        # No lock needed: a plain read-and-compare against whatever state
        # is current at the moment of the call is exactly the semantic a
        # mutation endpoint wants (an authorize() call that raced a
        # promote() and lost is supposed to see the NEW state and reject
        # — that is the stale-epoch-during-in-flight-action case, not a
        # bug to guard against).
        return evaluate_authorize(self._state, node_id=node_id, epoch=epoch, now=now)


def evaluate_authorize(
    current: IngressLeaderState, *, node_id: str, epoch: int, now: datetime
) -> AuthorizeResult:
    """The read-then-compare decision ``authorize()`` makes, factored out
    as a pure function so ``ingress_state_repo.py``'s Postgres-backed
    store (a plain ``SELECT`` followed by this same comparison — no CAS
    needed for a read) can call the IDENTICAL rule
    :class:`InMemoryIngressLeaderStore` uses, rather than maintaining a
    second copy of three if-branches that could silently drift apart from
    the one the drill suite actually tests against.

    See ``docs/plans/2026-08-25-due-bot-live/ops/F6-F9-PENDING-ACTION-EPOCH-GAP.md``
    for an open cross-lane question about a caller (B3's
    ``SqlitePendingActionStore``) that does not yet call this function at all.
    """

    if current.leader_epoch != epoch:
        return AuthorizeResult(outcome=AuthorizeOutcome.REJECTED_STALE_EPOCH, state=current)
    if current.active_node_id != node_id:
        return AuthorizeResult(outcome=AuthorizeOutcome.REJECTED_WRONG_NODE, state=current)
    if now > current.lease_expires_at:
        return AuthorizeResult(outcome=AuthorizeOutcome.REJECTED_LEASE_EXPIRED, state=current)
    return AuthorizeResult(outcome=AuthorizeOutcome.AUTHORIZED, state=current)


DEFAULT_RECORD_ID = "team_wa_default"
"""Single-tenant control record id — there is exactly one team-bot ingress
to arbitrate today. A second WABA would get a second ``record_id``, never
a second table."""
