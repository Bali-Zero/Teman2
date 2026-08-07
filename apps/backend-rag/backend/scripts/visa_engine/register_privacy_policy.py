"""Register the approved Visa Oracle privacy policy, dry-run by default.

This is an offline operator ceremony. It never changes engine mode and refuses
to use the serving runtime role. The effective timestamp is supplied at the
actual change window so approval is not backdated.

Usage from ``apps/backend-rag``::

    PYTHONPATH=. .venv/bin/python -m \
      backend.scripts.visa_engine.register_privacy_policy \
      --effective-from 2026-08-10T02:00:00+00:00

Add ``--apply`` only inside the approved production change window with a
separated policy-writer DSN in ``VISA_ENGINE_POLICY_WRITER_DATABASE_URL``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import asyncpg

from backend.services.visa_engine.privacy_policy import (
    ApprovedPrivacyPolicy,
    default_policy_path,
    load_approved_privacy_policy,
)

logger = logging.getLogger("visa_engine.register_privacy_policy")

POLICY_WRITER_DSN_ENV = "VISA_ENGINE_POLICY_WRITER_DATABASE_URL"
APPROVAL_REFERENCE = "docs/policies/visa-oracle-privacy-policy-v1.md"
FORBIDDEN_RUNTIME_ROLE = "backend_rag_v2"
EFFECTIVE_FROM_CLOCK_SKEW = timedelta(minutes=5)


def _parse_aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include an explicit UTC offset")
    return parsed


def _assert_new_effective_window(
    *,
    policy: ApprovedPrivacyPolicy,
    effective_from: datetime,
    database_now: datetime,
) -> None:
    """Reject a newly inserted policy whose legal effect would be backdated."""

    approval_date = date.fromisoformat(policy.approved_on)
    approval_start = datetime.combine(approval_date, datetime.min.time(), tzinfo=timezone.utc)
    effective_utc = effective_from.astimezone(timezone.utc)
    database_now_utc = database_now.astimezone(timezone.utc)
    if effective_utc < approval_start:
        raise RuntimeError("effective-from predates the recorded policy approval")
    if effective_utc < database_now_utc - EFFECTIVE_FROM_CLOCK_SKEW:
        raise RuntimeError("refusing to backdate a new policy registration")


async def _register(
    connection: asyncpg.Connection,
    *,
    policy: ApprovedPrivacyPolicy,
    effective_from: datetime,
) -> tuple[str, str]:
    """Insert once or prove that an identical policy row already exists."""

    identity = await connection.fetchrow(
        "SELECT current_user::text AS current_user, session_user::text AS session_user, "
        "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user) AS is_superuser"
    )
    if identity is None:
        raise RuntimeError("database identity unavailable")
    current_user = str(identity["current_user"])
    if current_user == FORBIDDEN_RUNTIME_ROLE:
        raise RuntimeError("refusing to register policy through the serving runtime role")
    if bool(identity["is_superuser"]):
        raise RuntimeError("refusing a superuser session; use the separated policy-writer role")

    if not await connection.fetchval(
        "SELECT to_regclass('public.visa_decision_retention_policies') IS NOT NULL"
    ):
        raise RuntimeError("migration 264 is not applied")
    if not await connection.fetchval(
        "SELECT has_table_privilege(current_user, "
        "'public.visa_decision_retention_policies', 'INSERT')"
    ):
        raise RuntimeError("current role lacks the narrow retention-policy INSERT capability")

    existing = await connection.fetchrow(
        """
        SELECT id::text, retention_interval, idempotency_retention_interval,
               legal_hold_review_interval, retention_anchor,
               lower(effective_period) AS effective_from,
               upper(effective_period) AS effective_to, approved_by,
               approval_reference
          FROM public.visa_decision_retention_policies
         WHERE environment = 'PRODUCTION' AND policy_version = $1
        """,
        policy.policy_id,
    )
    expected_retention = timedelta(days=policy.decision_retention_days)
    expected_idempotency = timedelta(hours=policy.idempotency_retention_hours)
    expected_hold_review = timedelta(days=policy.legal_hold_review_interval_days)
    if existing is not None:
        exact = (
            existing["retention_interval"] == expected_retention
            and existing["idempotency_retention_interval"] == expected_idempotency
            and existing["legal_hold_review_interval"] == expected_hold_review
            and existing["retention_anchor"] == policy.retention_anchor
            and existing["effective_from"] == effective_from
            and existing["effective_to"] is None
            and existing["approved_by"] == policy.approved_by
            and existing["approval_reference"] == APPROVAL_REFERENCE
        )
        if not exact:
            raise RuntimeError("policy version already exists with different immutable values")
        return str(existing["id"]), "ALREADY_REGISTERED"

    database_now = await connection.fetchval("SELECT clock_timestamp()")
    if not isinstance(database_now, datetime):
        raise RuntimeError("database clock unavailable")
    _assert_new_effective_window(
        policy=policy,
        effective_from=effective_from,
        database_now=database_now,
    )

    policy_id = await connection.fetchval(
        """
        INSERT INTO public.visa_decision_retention_policies (
            environment, policy_version, retention_interval,
            idempotency_retention_interval, legal_hold_review_interval,
            retention_anchor,
            effective_period, approved_by, approval_reference
        ) VALUES (
            'PRODUCTION', $1, $2, $3, $4, $5,
            tstzrange($6, NULL, '[)'), $7, $8
        )
        RETURNING id::text
        """,
        policy.policy_id,
        expected_retention,
        expected_idempotency,
        expected_hold_review,
        policy.retention_anchor,
        effective_from,
        policy.approved_by,
        APPROVAL_REFERENCE,
    )
    return str(policy_id), "REGISTERED"


async def run(args: argparse.Namespace) -> int:
    policy = load_approved_privacy_policy(Path(args.policy_file))
    logger.info(
        "policy_plan policy_id=%s decision_days=%d idempotency_hours=%d "
        "telemetry_days=%d effective_from=%s",
        policy.policy_id,
        policy.decision_retention_days,
        policy.idempotency_retention_hours,
        policy.telemetry_retention_days,
        args.effective_from.isoformat(),
    )
    if not args.apply:
        logger.info("dry_run=true no_database_write=true")
        return 0

    database_url = os.environ.get(args.database_url_env, "").strip()
    if not database_url:
        raise RuntimeError(f"${args.database_url_env} is required with --apply")

    connection = await asyncpg.connect(database_url)
    try:
        async with connection.transaction(isolation="serializable"):
            policy_id, result = await _register(
                connection,
                policy=policy,
                effective_from=args.effective_from,
            )
        logger.info("policy_registration result=%s policy_row_id=%s", result, policy_id)
    finally:
        await connection.close()
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    # `--policy-file` used to default to `str(default_policy_path())` --
    # an argparse `default=` expression that argparse evaluates EAGERLY,
    # every time this function runs, before `parser.parse_args()` even
    # looks at `argv`. `default_policy_path()` derives the checked-in
    # policy path as `Path(__file__).resolve().parents[5]` (repo root),
    # which raises `IndexError` in any container that only has a partial
    # checkout (fewer than 6 ancestor directories above this file) -- so
    # every invocation crashed before argument parsing, including a bare
    # `--help`. The default is now `None` and resolved lazily, below, only
    # when the caller did not pass `--policy-file` explicitly -- an
    # explicit `--policy-file` never touches the filesystem in this
    # function at all.
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--effective-from", required=True, type=_parse_aware_datetime)
    parser.add_argument(
        "--policy-file",
        default=None,
        help=(
            "defaults to the checked-in canonical policy JSON, resolved only "
            "when this flag is omitted (never touches the filesystem otherwise)"
        ),
    )
    parser.add_argument("--database-url-env", default=POLICY_WRITER_DSN_ENV)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the idempotent insert; default only validates and reports",
    )
    args = parser.parse_args(argv)
    if args.policy_file is None:
        try:
            canonical = default_policy_path()
        except IndexError:
            parser.error(
                "--policy-file was not provided and the canonical checked-in "
                "policy path could not be derived from this module's location "
                "(no full repository checkout present); pass --policy-file explicitly"
            )
        if not canonical.is_file():
            parser.error(
                f"--policy-file was not provided and the canonical checked-in "
                f"policy path does not exist: {canonical}; pass --policy-file explicitly"
            )
        args.policy_file = str(canonical)
    return args


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(run(_parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
