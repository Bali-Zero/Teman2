"""GARUDA VOA — the public-eligibility-check orchestration seam (L2, contract-frozen).

This module is the ONLY place `app/routers/garuda_voa_public.py` reaches into the
pure engine (`intake.py` / `pricing.py` / `civil_clock.py`) to build a wire-safe
verdict, and the ONLY place that declares the persistence PORT the router depends
on. It deliberately does not implement persistence itself.

Why the port is unimplemented here (LANES.md prerequisite chain, D1/D2
`products/garuda-voa/ARCHITECTURE.md`): `garuda_voa_checks` is about to gain a
retention-policy binding trigger owned by lane L1, and "fail-closed by
construction: no policy row is seeded" means an INSERT against that table has
no legal home until L1's migration lands and Zero signs a policy row. Building
a working adapter here — even a "temporary" one — would either (a) write rows
with no retention binding, reproducing exactly the defect D2 exists to close,
or (b) require this lane to invent its own migration, which LANES.md reserves
to L1 alone. `UnconfiguredCheckStore` is therefore not a stub to delete later;
it is the CORRECT fail-closed behaviour for as long as no policy exists, and
the contract already has a code for it: `PERSISTENCE_POLICY_UNAVAILABLE` (503).
A future adapter is wired in by replacing the `get_garuda_check_store`
dependency in the router — no router or contract change needed.

Nothing in this module performs I/O. `today` is always caller-supplied (see
`civil_clock.garuda_today()` at the router boundary) — never `date.today()`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol, runtime_checkable

from backend.services.garuda_flow.eligibility import DeclineCode
from backend.services.garuda_flow.intake import (
    CaseType,
    Purpose,
    VoaIntakeRequest,
    build_verdict,
)
from backend.services.garuda_flow.pricing import price_for_case

logger = logging.getLogger(__name__)

__all__ = [
    "CheckStore",
    "EligibilityCheckOutcome",
    "IdempotencyConflict",
    "PersistencePolicyUnavailable",
    "PriceUnresolvable",
    "StoredCheck",
    "UnconfiguredCheckStore",
    "evaluate_public_check",
]


class PersistencePolicyUnavailable(RuntimeError):
    """No retention policy authority exists to legally hold a new row.

    Maps 1:1 to the contract's ``PERSISTENCE_POLICY_UNAVAILABLE`` (503) — a
    fail-closed authority, never a bare error.
    """


class PriceUnresolvable(RuntimeError):
    """`pricing.price_for_case` fell through to its fail-safe ``None``.

    Maps to the contract's ``PRICE_UNRESOLVABLE`` (503). Never invent a price
    here — the one legal source is `pricing.py:price_for_case`.
    """


class IdempotencyConflict(RuntimeError):
    """The same scoped key is already bound to a different canonical payload.

    Maps to the contract's ``IDEMPOTENCY_CONFLICT`` (409).
    """


def _dedup_reason_codes(codes: list[str]) -> list[DeclineCode]:
    """Validate + dedup, preserving first-seen order (contract: uniqueItems).

    Every code `build_verdict` can ever emit is drawn from the closed
    `DeclineCode` enum (see that module's docstring) — an unknown value here
    would mean the engine and this wire-safe boundary have drifted, which
    must never reach a visitor as anything but a fail-closed shape.
    """
    seen: set[DeclineCode] = set()
    ordered: list[DeclineCode] = []
    for raw in codes:
        code = DeclineCode(raw)  # raises ValueError on an unknown code — caller fails closed
        if code in seen:
            continue
        seen.add(code)
        ordered.append(code)
    return ordered


@dataclass(frozen=True, slots=True)
class EligibilityCheckOutcome:
    """The wire-safe verdict this seam hands the router — nothing more.

    Structurally cannot carry D-14/D-10/D-3/D-1 (see `intake.VoaVerdict`
    docstring) or raw decline prose: only what `EligibilityResult` in the
    frozen contract may ever serialize.
    """

    accepted: bool
    reason_codes: list[DeclineCode] = field(default_factory=list)
    published_filing_deadline: date | None = None  # ACCEPT only — D-7
    price_idr: int | None = None  # ACCEPT only
    price_source: str | None = None  # ACCEPT only, never serialized on the wire


def evaluate_public_check(
    *,
    case_type: CaseType,
    nationality: str,
    entry_date: date,
    passport_expiry_date: date,
    voa_expiry_date: date | None,
    purpose: Purpose,
    travellers: int,
    self_pay: bool,
    extension_already_used: bool,
    today: date,
) -> EligibilityCheckOutcome:
    """Orchestrate engine verdict + price resolution for the public request.

    Raises `PriceUnresolvable` on an ACCEPT whose price cannot be resolved —
    the router's job is to turn that into 503 PRICE_UNRESOLVABLE and never to
    persist or serialize a guessed price.
    """
    request = VoaIntakeRequest(
        case_type=case_type,
        nationality=nationality,
        entry_date=entry_date,
        passport_expiry_date=passport_expiry_date,
        purpose=purpose,
        travellers=travellers,
        self_pay=self_pay,
        voa_expiry_date=voa_expiry_date,
        extension_already_used=extension_already_used,
    )
    verdict = build_verdict(request, today=today)
    reason_codes = _dedup_reason_codes(verdict.decline_codes)

    if not verdict.accepted:
        return EligibilityCheckOutcome(accepted=False, reason_codes=reason_codes)

    amount, source = price_for_case(case_type, today=today)
    if amount is None:
        raise PriceUnresolvable(f"no catalogue price for case_type={case_type.value}")

    return EligibilityCheckOutcome(
        accepted=True,
        reason_codes=[],
        published_filing_deadline=verdict.published_filing_deadline,
        price_idr=amount,
        price_source=source,
    )


@dataclass(frozen=True, slots=True)
class StoredCheck:
    """What a `CheckStore` hands back for a persisted (or replayed) check.

    `session_secret` is populated ONLY on the create path that just minted
    it — a `get`/replay never re-exposes it (Set-Cookie is emitted once, at
    creation, and omitted on replay per the contract's
    `x-result-session-cookie-header`).
    """

    result_id: str
    outcome: EligibilityCheckOutcome
    idempotency_replayed: bool
    session_secret: str | None = None


@runtime_checkable
class CheckStore(Protocol):
    """Persistence port L2 depends on and does not implement.

    A real adapter binds `garuda_voa_checks` to the retention policy L1 adds
    (D2) and is wired in by overriding `get_garuda_check_store` — this
    Protocol is the seam, never a place to grow ad-hoc SQL.
    """

    async def create(
        self,
        *,
        idempotency_key: str,
        canonical_request: dict[str, object],
        outcome: EligibilityCheckOutcome,
    ) -> StoredCheck: ...

    async def get(self, *, result_id: str, session_secret: str) -> StoredCheck | None: ...

    async def delete(
        self,
        *,
        result_id: str,
        session_secret: str | None,
        idempotency_key: str,
    ) -> bool:
        """Return True iff this call actually erased authorized data."""
        ...


class UnconfiguredCheckStore:
    """The only `CheckStore` this lane ships — fails closed on every call.

    See the module docstring: this is correct fail-closed behaviour, not a
    placeholder to silence. Every method raises `PersistencePolicyUnavailable`.
    """

    async def create(
        self,
        *,
        idempotency_key: str,
        canonical_request: dict[str, object],
        outcome: EligibilityCheckOutcome,
    ) -> StoredCheck:
        raise PersistencePolicyUnavailable("no garuda check store configured")

    async def get(self, *, result_id: str, session_secret: str) -> StoredCheck | None:
        raise PersistencePolicyUnavailable("no garuda check store configured")

    async def delete(
        self,
        *,
        result_id: str,
        session_secret: str | None,
        idempotency_key: str,
    ) -> bool:
        raise PersistencePolicyUnavailable("no garuda check store configured")
