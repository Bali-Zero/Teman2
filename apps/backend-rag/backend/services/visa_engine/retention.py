"""Policy-gated retention boundary for durable Visa Oracle decisions.

No retention duration lives in application code. Zero-approved policy rows
are the only source of a duration/anchor, and PostgreSQL remains the final
authority for binding and purging. This module exposes read/check and bounded
worker primitives without inventing a scheduler cadence.

A third governed store joined this module via migration 282:
``visa_oracle_consultant_requests`` (migration 281, the durable "Talk to a
consultant" request log). Unlike the decisions/idempotency pair above, that
table carries no ``environment`` column and is not bound to a policy at
INSERT time -- migration 282's own header explains why (a live,
contract-frozen customer control that must not start fail-closing writes the
instant a policy is missing). ``purge_expired_consultant_requests`` and
``consultant_request_retention_evidence`` below resolve the governing policy
dynamically, at read time, against ``visa_oracle_consultant_request_retention_policies``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

_REQUESTED_BY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_ENVIRONMENTS = frozenset({"TEST", "STAGING", "PRODUCTION"})


@dataclass(frozen=True, slots=True)
class IdempotencyRetentionEvidence:
    """Applicant/key-identifier-free evidence for backlog/lag alerting."""

    expired_rows: int
    max_lag_seconds: float
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class IdempotencyKeyUsageEvidence:
    """Grouped active replay dependency on one configured HMAC key."""

    key_purpose: str
    key_id: str
    active_rows: int
    latest_expiry: datetime
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class DecisionRetentionEvidence:
    """Decision-identifier-free evidence for purge backlog/lag alerting."""

    expired_rows: int
    expired_held_rows: int
    max_lag_seconds: float
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ConsultantRequestRetentionEvidence:
    """Evaluation/client-identifier-free evidence for
    ``visa_oracle_consultant_requests`` purge backlog/lag alerting."""

    expired_rows: int
    max_lag_seconds: float
    observed_at: datetime


async def active_policy_available(
    db_pool: asyncpg.Pool,
    *,
    environment: str,
    evaluated_at: datetime,
) -> bool:
    """Return whether one Zero-approved policy covers this evaluation clock.

    Missing schema, DB failure, overlap corruption, or no policy propagates or
    returns false to the caller, which must abstain in ENFORCE. The exclusion
    constraint makes more than one active policy structurally impossible.
    """

    if environment not in _ENVIRONMENTS:
        raise ValueError("environment must be TEST, STAGING, or PRODUCTION")
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("evaluated_at must be timezone-aware")
    async with db_pool.acquire() as conn:
        active_count = await conn.fetchval(
            """
            SELECT count(*)
            FROM public.visa_decision_retention_policies
            WHERE environment = $1
              AND effective_period @> $2::timestamptz
            """,
            environment,
            evaluated_at,
        )
    return active_count == 1


async def purge_expired_decisions(
    db_pool: asyncpg.Pool,
    *,
    limit: int,
    requested_by: str,
) -> int:
    """Run one bounded, DB-enforced purge batch and return deleted rows.

    ``limit`` and actor are mandatory: cadence and batch sizing remain an
    explicit operator/scheduler decision. PostgreSQL independently rejects
    out-of-range limits, non-expired rows, and legal holds, and records every
    successful deletion batch as append-only aggregate evidence.
    """

    if type(limit) is not int or not 1 <= limit <= 1_000:
        raise ValueError("limit must be an integer between 1 and 1000")
    if not isinstance(requested_by, str) or _REQUESTED_BY_RE.fullmatch(requested_by) is None:
        raise ValueError("requested_by has an invalid format")
    async with db_pool.acquire() as conn:
        deleted = await conn.fetchval(
            "SELECT public.purge_visa_decisions($1, $2)",
            limit,
            requested_by,
        )
    return int(deleted)


async def purge_expired_idempotency(
    db_pool: asyncpg.Pool,
    *,
    limit: int,
    requested_by: str,
) -> int:
    """Run one bounded policy-expired replay purge batch."""

    if type(limit) is not int or not 1 <= limit <= 1_000:
        raise ValueError("limit must be an integer between 1 and 1000")
    if not isinstance(requested_by, str) or _REQUESTED_BY_RE.fullmatch(requested_by) is None:
        raise ValueError("requested_by has an invalid format")
    async with db_pool.acquire() as conn:
        deleted = await conn.fetchval(
            "SELECT public.purge_visa_evaluate_idempotency($1, $2)",
            limit,
            requested_by,
        )
    return int(deleted)


async def purge_expired_consultant_requests(
    db_pool: asyncpg.Pool,
    *,
    limit: int,
    requested_by: str,
) -> int:
    """Run one bounded, DB-enforced purge batch over
    ``visa_oracle_consultant_requests`` and return deleted rows.

    ``limit`` and actor are mandatory, same as the decisions/idempotency
    purgers above: cadence and batch sizing remain an explicit
    operator/scheduler decision. PostgreSQL independently rejects
    out-of-range limits and non-expired rows, and records every successful
    deletion batch as append-only aggregate evidence. Unlike the two purgers
    above, "expired" is resolved dynamically against whichever
    Zero-approved policy (if any) governed the row's anchor timestamp at
    write time -- see migration 282's header. While no policy exists, or a
    row's anchor timestamp falls outside every policy's effective_period,
    this is a documented no-op: it returns 0 and writes no evidence batch.
    """

    if type(limit) is not int or not 1 <= limit <= 1_000:
        raise ValueError("limit must be an integer between 1 and 1000")
    if not isinstance(requested_by, str) or _REQUESTED_BY_RE.fullmatch(requested_by) is None:
        raise ValueError("requested_by has an invalid format")
    async with db_pool.acquire() as conn:
        deleted = await conn.fetchval(
            "SELECT public.purge_visa_oracle_consultant_requests($1, $2)",
            limit,
            requested_by,
        )
    return int(deleted)


async def erase_decision_for_dsr(
    db_pool: asyncpg.Pool,
    *,
    decision_id: UUID,
    case_reference: str,
    requested_by: str,
) -> int:
    """Erase one decision through the bounded, legal-hold-aware DSR path."""

    if not isinstance(decision_id, UUID):
        raise ValueError("decision_id must be a UUID")
    if not isinstance(case_reference, str) or _REQUESTED_BY_RE.fullmatch(case_reference) is None:
        raise ValueError("case_reference has an invalid format")
    if not isinstance(requested_by, str) or _REQUESTED_BY_RE.fullmatch(requested_by) is None:
        raise ValueError("requested_by has an invalid format")
    async with db_pool.acquire() as conn:
        deleted = await conn.fetchval(
            "SELECT public.erase_visa_decision_for_dsr($1, $2, $3)",
            decision_id,
            case_reference,
            requested_by,
        )
    return int(deleted)


async def set_decision_legal_hold(
    db_pool: asyncpg.Pool,
    *,
    decision_id: UUID,
    legal_hold: bool,
    requested_by: str,
    case_reference: str,
    reason_code: str,
    approved_by: str,
    review_due_at: datetime | None,
) -> bool:
    """Set/release one hold through the audited bounded capability."""

    if not isinstance(decision_id, UUID):
        raise ValueError("decision_id must be a UUID")
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
            "SELECT public.set_visa_decision_legal_hold($1, $2, $3, $4, $5, $6, $7)",
            decision_id,
            legal_hold,
            requested_by,
            case_reference,
            reason_code,
            approved_by,
            review_due_at,
        )
    return bool(changed)


async def idempotency_retention_evidence(
    db_pool: asyncpg.Pool,
) -> IdempotencyRetentionEvidence:
    """Read aggregate expired-row count and maximum lag without identifiers."""

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM public.visa_idempotency_retention_evidence()")
    if row is None:  # pragma: no cover - SQL function always returns one row
        raise RuntimeError("idempotency retention evidence unavailable")
    return IdempotencyRetentionEvidence(
        expired_rows=int(row["expired_rows"]),
        max_lag_seconds=float(row["max_lag_seconds"]),
        observed_at=row["observed_at"],
    )


async def decision_retention_evidence(
    db_pool: asyncpg.Pool,
) -> DecisionRetentionEvidence:
    """Read aggregate decision backlog, legal holds and maximum purge lag."""

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM public.visa_decision_retention_evidence()")
    if row is None:  # pragma: no cover - SQL function always returns one row
        raise RuntimeError("decision retention evidence unavailable")
    return DecisionRetentionEvidence(
        expired_rows=int(row["expired_rows"]),
        expired_held_rows=int(row["expired_held_rows"]),
        max_lag_seconds=float(row["max_lag_seconds"]),
        observed_at=row["observed_at"],
    )


async def consultant_request_retention_evidence(
    db_pool: asyncpg.Pool,
) -> ConsultantRequestRetentionEvidence:
    """Read aggregate expired-row count and maximum lag for
    ``visa_oracle_consultant_requests``, without evaluation_id/client_id."""

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM public.visa_oracle_consultant_requests_retention_evidence()"
        )
    if row is None:  # pragma: no cover - SQL function always returns one row
        raise RuntimeError("consultant request retention evidence unavailable")
    return ConsultantRequestRetentionEvidence(
        expired_rows=int(row["expired_rows"]),
        max_lag_seconds=float(row["max_lag_seconds"]),
        observed_at=row["observed_at"],
    )


async def idempotency_key_usage_evidence(
    db_pool: asyncpg.Pool,
) -> tuple[IdempotencyKeyUsageEvidence, ...]:
    """Return grouped active key dependencies without replay/applicant IDs."""

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM public.visa_idempotency_key_usage_evidence()")
    return tuple(
        IdempotencyKeyUsageEvidence(
            key_purpose=str(row["key_purpose"]),
            key_id=str(row["key_id"]),
            active_rows=int(row["active_rows"]),
            latest_expiry=row["latest_expiry"],
            observed_at=row["observed_at"],
        )
        for row in rows
    )


__all__ = [
    "ConsultantRequestRetentionEvidence",
    "DecisionRetentionEvidence",
    "IdempotencyKeyUsageEvidence",
    "IdempotencyRetentionEvidence",
    "active_policy_available",
    "consultant_request_retention_evidence",
    "decision_retention_evidence",
    "erase_decision_for_dsr",
    "idempotency_key_usage_evidence",
    "idempotency_retention_evidence",
    "purge_expired_consultant_requests",
    "purge_expired_decisions",
    "purge_expired_idempotency",
    "set_decision_legal_hold",
]
