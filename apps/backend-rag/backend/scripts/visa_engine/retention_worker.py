"""One-shot, policy-bound Visa Oracle retention worker.

The worker is evidence-only by default. ``--apply`` invokes only the bounded
SECURITY DEFINER purge capabilities; it never issues table DELETE statements.
Run it from an external scheduler so a crashed API process cannot silently stop
retention.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import timedelta

import asyncpg

from backend.services.visa_engine import retention
from backend.services.visa_engine.privacy_policy import load_approved_privacy_policy

logger = logging.getLogger("visa_engine.retention_worker")

RETENTION_DSN_ENV = "VISA_ENGINE_RETENTION_DATABASE_URL"
FORBIDDEN_RUNTIME_ROLE = "backend_rag_v2"
REQUESTED_BY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


@dataclass(frozen=True, slots=True)
class RetentionCycleResult:
    """PII-free one-shot worker result."""

    decision_deleted: int
    idempotency_deleted: int
    decision_expired_remaining: int
    decision_expired_held: int
    decision_max_lag_seconds: float
    idempotency_expired_remaining: int
    idempotency_max_lag_seconds: float
    healthy: bool


@dataclass(frozen=True, slots=True)
class ActiveRetentionPolicy:
    policy_version: str
    retention_interval: timedelta
    idempotency_retention_interval: timedelta
    legal_hold_review_interval: timedelta
    retention_anchor: str
    approved_by: str


async def _active_policy(db_pool: asyncpg.Pool) -> ActiveRetentionPolicy:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT policy_version, retention_interval,
                   idempotency_retention_interval, legal_hold_review_interval,
                   retention_anchor, approved_by
              FROM public.visa_decision_retention_policies
             WHERE environment = 'PRODUCTION'
               AND policy_scope = 'VISA_DECISION'
               AND effective_period @> clock_timestamp()
            """
        )
    if len(rows) != 1:
        raise RuntimeError(
            "exactly one active PRODUCTION VISA_DECISION retention policy is required"
        )
    row = rows[0]
    return ActiveRetentionPolicy(
        policy_version=str(row["policy_version"]),
        retention_interval=row["retention_interval"],
        idempotency_retention_interval=row["idempotency_retention_interval"],
        legal_hold_review_interval=row["legal_hold_review_interval"],
        retention_anchor=str(row["retention_anchor"]),
        approved_by=str(row["approved_by"]),
    )


async def run_retention_cycle(
    db_pool: asyncpg.Pool,
    *,
    apply: bool,
    limit: int,
    max_batches: int,
    requested_by: str,
    max_lag_seconds: float,
) -> RetentionCycleResult:
    """Observe or drain bounded batches, then evaluate the PII-free SLO."""

    if type(limit) is not int or not 1 <= limit <= 1_000:
        raise ValueError("limit must be between 1 and 1000")
    if type(max_batches) is not int or not 1 <= max_batches <= 100:
        raise ValueError("max_batches must be between 1 and 100")
    if REQUESTED_BY_RE.fullmatch(requested_by) is None:
        raise ValueError("requested_by has an invalid format")
    if max_lag_seconds <= 0:
        raise ValueError("max_lag_seconds must be positive")

    approved = load_approved_privacy_policy()
    active = await _active_policy(db_pool)
    if active != ActiveRetentionPolicy(
        policy_version=approved.policy_id,
        retention_interval=timedelta(days=approved.decision_retention_days),
        idempotency_retention_interval=timedelta(hours=approved.idempotency_retention_hours),
        legal_hold_review_interval=timedelta(days=approved.legal_hold_review_interval_days),
        retention_anchor=approved.retention_anchor,
        approved_by=approved.approved_by,
    ):
        raise RuntimeError("active retention policy values do not match the checked-in approval")

    decision_deleted = 0
    idempotency_deleted = 0
    if apply:
        for _ in range(max_batches):
            deleted = await retention.purge_expired_idempotency(
                db_pool,
                limit=limit,
                requested_by=requested_by,
            )
            idempotency_deleted += deleted
            if deleted < limit:
                break
        for _ in range(max_batches):
            deleted = await retention.purge_expired_decisions(
                db_pool,
                limit=limit,
                requested_by=requested_by,
            )
            decision_deleted += deleted
            if deleted < limit:
                break

    decision_evidence = await retention.decision_retention_evidence(db_pool)
    idempotency_evidence = await retention.idempotency_retention_evidence(db_pool)
    healthy = (
        decision_evidence.expired_rows == 0
        and idempotency_evidence.expired_rows == 0
        and decision_evidence.max_lag_seconds <= max_lag_seconds
        and idempotency_evidence.max_lag_seconds <= max_lag_seconds
    )
    return RetentionCycleResult(
        decision_deleted=decision_deleted,
        idempotency_deleted=idempotency_deleted,
        decision_expired_remaining=decision_evidence.expired_rows,
        decision_expired_held=decision_evidence.expired_held_rows,
        decision_max_lag_seconds=decision_evidence.max_lag_seconds,
        idempotency_expired_remaining=idempotency_evidence.expired_rows,
        idempotency_max_lag_seconds=idempotency_evidence.max_lag_seconds,
        healthy=healthy,
    )


async def _assert_operator_boundary(db_pool: asyncpg.Pool, *, apply: bool) -> None:
    """Reject runtime/superuser use and prove the narrow capability set."""

    async with db_pool.acquire() as conn:
        identity = await conn.fetchrow(
            "SELECT current_user::text AS current_user, "
            "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user) AS is_superuser"
        )
        if identity is None:
            raise RuntimeError("database identity unavailable")
        if str(identity["current_user"]) == FORBIDDEN_RUNTIME_ROLE:
            raise RuntimeError("refusing to run retention through the serving runtime role")
        if bool(identity["is_superuser"]):
            raise RuntimeError("refusing superuser retention; use the bounded executor")
        can_read_policy = await conn.fetchval(
            "SELECT has_table_privilege(current_user, "
            "'public.visa_decision_retention_policies', 'SELECT')"
        )
        if not can_read_policy:
            raise RuntimeError(
                "retention executor lacks SELECT on the approved retention policy"
            )
        required_signatures = [
            "public.visa_decision_retention_evidence()",
            "public.visa_idempotency_retention_evidence()",
        ]
        if apply:
            required_signatures.extend(
                [
                    "public.purge_visa_decisions(integer,text)",
                    "public.purge_visa_evaluate_idempotency(integer,text)",
                ]
            )
        for signature in required_signatures:
            allowed = await conn.fetchval(
                "SELECT has_function_privilege(current_user, $1, 'EXECUTE')",
                signature,
            )
            if not allowed:
                raise RuntimeError(f"retention executor lacks EXECUTE on {signature}")


async def run(args: argparse.Namespace) -> int:
    database_url = os.environ.get(args.database_url_env, "").strip()
    if not database_url:
        raise RuntimeError(f"${args.database_url_env} is required")
    db_pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    try:
        await _assert_operator_boundary(db_pool, apply=args.apply)
        result = await run_retention_cycle(
            db_pool,
            apply=args.apply,
            limit=args.limit,
            max_batches=args.max_batches,
            requested_by=args.requested_by,
            max_lag_seconds=args.max_lag_seconds,
        )
    finally:
        await db_pool.close()

    logger.info(
        "retention_result apply=%s decision_deleted=%d idempotency_deleted=%d "
        "decision_expired_remaining=%d decision_expired_held=%d "
        "decision_max_lag_seconds=%.3f idempotency_expired_remaining=%d "
        "idempotency_max_lag_seconds=%.3f healthy=%s",
        args.apply,
        result.decision_deleted,
        result.idempotency_deleted,
        result.decision_expired_remaining,
        result.decision_expired_held,
        result.decision_max_lag_seconds,
        result.idempotency_expired_remaining,
        result.idempotency_max_lag_seconds,
        result.healthy,
    )
    return 0 if result.healthy else 2


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=1_000)
    parser.add_argument("--max-batches", type=int, default=20)
    parser.add_argument("--requested-by", default="visa-retention-scheduler")
    parser.add_argument("--max-lag-seconds", type=float, default=3_600)
    parser.add_argument("--database-url-env", default=RETENTION_DSN_ENV)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(run(_parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
