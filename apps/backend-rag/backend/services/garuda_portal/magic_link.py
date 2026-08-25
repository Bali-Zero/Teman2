"""GARUDA VOA — magic-link authentication seam (L4, contract-frozen).

Mirrors the L2 precedent in `garuda_flow/public_api.py`: this module declares
the persistence PORT the router (`app/routers/garuda_portal_auth.py`) depends
on and does not implement it itself. A magic-link row is customer data bound
to an email address AND a result_id — it needs the same retention-policy
binding L1 lands for `garuda_voa_checks` (LANES.md prerequisite chain: "L1 is
first by construction... a lane that writes a row before L1 merges has built
a table nobody may legally keep") before any row may legally exist.
`UnconfiguredMagicLinkStore` therefore fails closed with
`PersistencePolicyUnavailable` — the SAME shape L2 ships for the identical
reason, not a stub to silence. A future adapter is wired in by overriding the
`get_garuda_magic_link_store` dependency in the router — no router or
contract change needed.

DECISIONS.md Q1 (binding, not this lane's to re-decide):
- Lifetime 15 minutes from issue (`MAGIC_LINK_TTL_MINUTES`), matching
  `contracts/openapi.yaml:x-magic-link.ttl_minutes` verbatim.
- Single-use: the token is consumed on first successful exchange and cannot
  authenticate twice.
- A consumed token and an expired token return the IDENTICAL response. This
  module enforces that at the type level: `ExchangeOutcome` carries a single
  `authorized: bool` and never a reason — there is structurally no field a
  caller could leak an "expired vs consumed" distinction through.
- The magic-link TTL is a SEPARATE number from the account-session lifetime
  it establishes on success; this seam only ever mints/consumes the link,
  never decides how long the resulting session lives (a store adapter's
  business, once L1's persistence primitive exists for this domain).

Nothing in this module performs I/O, token generation, or hashing — all of
that is the store adapter's job, exactly like `CheckStore` never mints a
`result_id` here either. This file is the seam, never a place to grow ad-hoc
SQL or `secrets.token_urlsafe` calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

#: `contracts/openapi.yaml` `x-magic-link.ttl_minutes` — DECISIONS.md Q1.
MAGIC_LINK_TTL_MINUTES = 15

__all__ = [
    "MAGIC_LINK_TTL_MINUTES",
    "ExchangeOutcome",
    "IdempotencyConflict",
    "IssueOutcome",
    "MagicLinkStore",
    "PersistencePolicyUnavailable",
    "UnconfiguredMagicLinkStore",
]


class PersistencePolicyUnavailable(RuntimeError):
    """No retention policy authority exists to legally hold a magic-link row.

    Maps 1:1 to the contract's ``PERSISTENCE_POLICY_UNAVAILABLE`` (503) — the
    same fail-closed authority `garuda_flow.public_api` raises, for the same
    reason: no policy row is seeded for this table yet.
    """


class IdempotencyConflict(RuntimeError):
    """The same scoped Idempotency-Key is already bound to a different
    canonical payload. Maps to the contract's ``IDEMPOTENCY_CONFLICT`` (409).
    """


@dataclass(frozen=True, slots=True)
class IssueOutcome:
    """What `MagicLinkStore.issue` hands back.

    Deliberately silent on whether an email was actually queued — the
    router's 202 response body never reflects this and MUST NOT branch on it
    for anything visible to the caller; the contract requires the exact same
    202 whether the result exists, is owned by this session, or neither
    (that is the enumeration oracle the whole endpoint exists to deny).
    `idempotency_replayed` only drives the `Idempotency-Replayed` response
    header, which is documented and non-enumerating by construction.
    """

    idempotency_replayed: bool


@dataclass(frozen=True, slots=True)
class ExchangeOutcome:
    """What `MagicLinkStore.exchange` hands back.

    `authorized=False` covers an unknown, an expired, AND an already-consumed
    token in exactly the same shape — DECISIONS.md Q1 requires a consumed and
    an expired token to be indistinguishable to the caller, so this type has
    no reason field a router could accidentally serialize.

    `security_counter` names the ONE coarse counter this exchange should
    increment for internal observability (`magic_link_expired` /
    `magic_link_replay` / `magic_link_invalid` / `magic_link_authorized`) —
    telemetry only, never serialized to the wire and never derived FROM the
    wire response.
    """

    authorized: bool
    security_counter: str
    result_id: str | None = None  # ACCEPT only
    account_session_secret: str | None = None  # ACCEPT only, new session only
    idempotency_replayed: bool = False


@runtime_checkable
class MagicLinkStore(Protocol):
    """Persistence port L4 depends on and does not implement (see module
    docstring). A real adapter binds a magic-link table to the SAME
    retention-policy machinery L1 builds for `garuda_voa_checks`.

    SERVER-SIDE HASHING IS PART OF THIS CONTRACT, NOT AN IMPLEMENTATION
    DETAIL LEFT TO TASTE (CodeQL `py/clear-text-storage-sensitive-data`,
    2026-08-25, refuter-confirmed REAL_DEFECT on the router's cookie sink —
    `UnconfiguredMagicLinkStore` fails closed today so the sink is currently
    unreachable, but this port exists precisely so a future adapter makes it
    reachable, and it must not do so with a plaintext bearer at rest):

    - `issue`'s `result_session_secret` and `exchange`'s `token` are
      high-entropy bearers the BROWSER holds and presents back — the adapter
      must persist and match on a hash of each, never the raw value, and
      hash the presented value before every lookup. Same posture for the
      `account_session_secret` an adapter mints inside `ExchangeOutcome`:
      the router puts it straight into a cookie the browser must hold in
      the clear, but nothing server-side may hold a stored value equal to
      it — persist a hash (or a keyed digest) and verify by hashing what
      the client presents on each request.
    - This is the EXACT convention already shipped for the sibling client-
      portal login: `backend/services/portal/magic_link_service.py` mints a
      32-byte urlsafe token, stores `hashlib.sha256(raw_token).hexdigest()`
      (`_hash_token`, module docstring point 2: "store ONLY its sha256
      hash"), and never writes the raw token to any table. A `MagicLinkStore`
      adapter for this port must follow the same shape rather than inventing
      a second convention.
    """

    async def issue(
        self,
        *,
        idempotency_key: str,
        result_id: str,
        email: str,
        result_session_secret: str,
    ) -> IssueOutcome: ...

    async def exchange(
        self,
        *,
        idempotency_key: str,
        token: str,
    ) -> ExchangeOutcome: ...


class UnconfiguredMagicLinkStore:
    """The only `MagicLinkStore` this lane ships — fails closed on every call.

    See the module docstring: this is correct fail-closed behaviour, not a
    placeholder to silence. Every method raises `PersistencePolicyUnavailable`.
    """

    async def issue(
        self,
        *,
        idempotency_key: str,
        result_id: str,
        email: str,
        result_session_secret: str,
    ) -> IssueOutcome:
        raise PersistencePolicyUnavailable("no garuda magic-link store configured")

    async def exchange(
        self,
        *,
        idempotency_key: str,
        token: str,
    ) -> ExchangeOutcome:
        raise PersistencePolicyUnavailable("no garuda magic-link store configured")
