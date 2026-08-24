"""Policy-gated retention boundary for ``garuda_voa_checks``.

Mirrors ``backend.services.visa_engine.retention`` deliberately: this is the
SAME retention authority (``visa_decision_retention_policies``, scoped
``GARUDA_CHECK`` — see migration 281), so the Python surface shares its
shape. No retention duration lives in application code here either — a
Zero-approved policy row is the only source of a duration/anchor, and
PostgreSQL remains the final authority for binding and purging.

L1 (products/garuda-voa/LANES.md) owns this file. No caller exists yet:
L2's public funnel router is still blocked on CONTRACT FREEZE, so nothing
in this repo calls ``insert``-shaped code against ``garuda_voa_checks``
today. This module is the primitive L2/L7 build against once they land.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

import asyncpg

_REQUESTED_BY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_HASH_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
_ENVIRONMENTS = frozenset({"TEST", "STAGING", "PRODUCTION"})


@dataclass(frozen=True, slots=True)
class GarudaCheckRetentionEvidence:
    """Hash/decision-identifier-free evidence for backlog/lag alerting."""

    expired_rows: int
    expired_held_rows: int
    max_lag_seconds: float
    observed_at: datetime


async def active_garuda_check_policy_available(
    db_pool: asyncpg.Pool,
    *,
    environment: str,
    created_at: datetime,
) -> bool:
    """Return whether one Zero-approved GARUDA_CHECK policy covers this clock.

    Missing schema, DB failure, overlap corruption, or no policy propagates
    or returns false to the caller, which must fail closed
    (``PERSISTENCE_POLICY_UNAVAILABLE``) rather than persist. The widened
    EXCLUDE constraint (migration 281) makes more than one active
    GARUDA_CHECK policy per environment structurally impossible.
    """

    if environment not in _ENVIRONMENTS:
        raise ValueError("environment must be TEST, STAGING, or PRODUCTION")
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    async with db_pool.acquire() as conn:
        active_count = await conn.fetchval(
            """
            SELECT count(*)
            FROM public.visa_decision_retention_policies
            WHERE environment = $1
              AND policy_scope = 'GARUDA_CHECK'
              AND effective_period @> $2::timestamptz
            """,
            environment,
            created_at,
        )
    return active_count == 1


async def purge_expired_garuda_checks(
    db_pool: asyncpg.Pool,
    *,
    limit: int,
    requested_by: str,
) -> int:
    """Run one bounded, DB-enforced purge batch and return deleted rows.

    ``limit`` and actor are mandatory: cadence and batch sizing remain an
    explicit operator/scheduler decision, same as the Visa Oracle purge
    worker. PostgreSQL independently rejects out-of-range limits,
    non-expired rows, and legal holds, and records every successful
    deletion batch as append-only aggregate evidence (reusing
    ``visa_decision_retention_batches`` — one retention authority, one
    evidence trail).
    """

    if type(limit) is not int or not 1 <= limit <= 1_000:
        raise ValueError("limit must be an integer between 1 and 1000")
    if not isinstance(requested_by, str) or _REQUESTED_BY_RE.fullmatch(requested_by) is None:
        raise ValueError("requested_by has an invalid format")
    async with db_pool.acquire() as conn:
        deleted = await conn.fetchval(
            "SELECT public.purge_garuda_voa_checks($1, $2)",
            limit,
            requested_by,
        )
    return int(deleted)


async def set_garuda_check_legal_hold(
    db_pool: asyncpg.Pool,
    *,
    hash_: str,
    legal_hold: bool,
    requested_by: str,
    case_reference: str,
    reason_code: str,
    approved_by: str,
    review_due_at: datetime | None,
) -> bool:
    """Set/release one hold through the audited bounded capability."""

    if not isinstance(hash_, str) or _HASH_RE.fullmatch(hash_) is None:
        raise ValueError("hash has an invalid format")
    if type(legal_hold) is not bool:
        raise ValueError("legal_hold must be a boolean")
    if not isinstance(requested_by, str) or _REQUESTED_BY_RE.fullmatch(requested_by) is None:
        raise ValueError("requested_by has an invalid format")
    if not isinstance(case_reference, str) or _REQUESTED_BY_RE.fullmatch(case_reference) is None:
        raise ValueError("case_reference has an invalid format")
    if not isinstance(reason_code, str) or _REQUESTED_BY_RE.fullmatch(reason_code) is None:
        raise ValueError("reason_code has an invalid format")
    if not isinstance(approved_by, str) or _REQUESTED_BY_RE.fullmatch(approved_by) is None:
        raise ValueError("approved_by has an invalid format")
    if legal_hold and (
        not isinstance(review_due_at, datetime)
        or review_due_at.tzinfo is None
        or review_due_at.utcoffset() is None
    ):
        raise ValueError("a timezone-aware review_due_at is required for a legal hold")
    if not legal_hold and review_due_at is not None:
        raise ValueError("review_due_at must be absent when releasing a legal hold")
    async with db_pool.acquire() as conn:
        changed = await conn.fetchval(
            "SELECT public.set_garuda_voa_check_legal_hold($1, $2, $3, $4, $5, $6, $7)",
            hash_,
            legal_hold,
            requested_by,
            case_reference,
            reason_code,
            approved_by,
            review_due_at,
        )
    return bool(changed)


async def bind_legacy_garuda_checks(
    db_pool: asyncpg.Pool,
    *,
    limit: int,
    requested_by: str,
) -> int:
    """Run one bounded legacy-disposition batch and return newly bound rows.

    Never invents coverage: a legacy row whose environment has no active
    GARUDA_CHECK policy for its ``created_at`` is left ungoverned, not
    counted. See migration 281's ``bind_legacy_garuda_voa_checks_retention_
    policy`` for the full contract.
    """

    if type(limit) is not int or not 1 <= limit <= 1_000:
        raise ValueError("limit must be an integer between 1 and 1000")
    if not isinstance(requested_by, str) or _REQUESTED_BY_RE.fullmatch(requested_by) is None:
        raise ValueError("requested_by has an invalid format")
    async with db_pool.acquire() as conn:
        bound = await conn.fetchval(
            "SELECT public.bind_legacy_garuda_voa_checks_retention_policy($1, $2)",
            limit,
            requested_by,
        )
    return int(bound)


async def garuda_check_retention_evidence(
    db_pool: asyncpg.Pool,
) -> GarudaCheckRetentionEvidence:
    """Read aggregate purge backlog, legal holds and maximum purge lag."""

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM public.garuda_voa_check_retention_evidence()")
    if row is None:  # pragma: no cover - SQL function always returns one row
        raise RuntimeError("garuda check retention evidence unavailable")
    return GarudaCheckRetentionEvidence(
        expired_rows=int(row["expired_rows"]),
        expired_held_rows=int(row["expired_held_rows"]),
        max_lag_seconds=float(row["max_lag_seconds"]),
        observed_at=row["observed_at"],
    )


__all__ = [
    "GarudaCheckRetentionEvidence",
    "active_garuda_check_policy_available",
    "bind_legacy_garuda_checks",
    "garuda_check_retention_evidence",
    "purge_expired_garuda_checks",
    "set_garuda_check_legal_hold",
]
