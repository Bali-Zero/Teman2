"""Offline Visa Oracle DSR/legal-hold ceremony, dry-run by default."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from datetime import datetime
from uuid import UUID

import asyncpg

from backend.services.visa_engine import retention

logger = logging.getLogger("visa_engine.privacy_ops")

PRIVACY_OPERATOR_DSN_ENV = "VISA_ENGINE_PRIVACY_OPERATOR_DATABASE_URL"
FORBIDDEN_RUNTIME_ROLE = "backend_rag_v2"
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")


def _token(value: str) -> str:
    if TOKEN_RE.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("must be an opaque token without spaces")
    return value


def _aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("must include an explicit UTC offset")
    return parsed


async def _assert_operator_boundary(
    db_pool: asyncpg.Pool,
    *,
    function_signature: str,
) -> None:
    async with db_pool.acquire() as conn:
        identity = await conn.fetchrow(
            "SELECT current_user::text AS current_user, "
            "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user) AS is_superuser"
        )
        if identity is None:
            raise RuntimeError("database identity unavailable")
        if str(identity["current_user"]) == FORBIDDEN_RUNTIME_ROLE:
            raise RuntimeError("refusing privacy operation through the serving runtime role")
        if bool(identity["is_superuser"]):
            raise RuntimeError("refusing superuser privacy operation; use the bounded role")
        allowed = await conn.fetchval(
            "SELECT has_function_privilege(current_user, $1, 'EXECUTE')",
            function_signature,
        )
        if not allowed:
            raise RuntimeError(f"privacy operator lacks EXECUTE on {function_signature}")


async def run(args: argparse.Namespace) -> int:
    logger.info(
        "privacy_operation action=%s case_reference=%s apply=%s",
        args.action,
        args.case_reference,
        args.apply,
    )
    if not args.apply:
        logger.info("dry_run=true no_database_write=true")
        return 0

    database_url = os.environ.get(args.database_url_env, "").strip()
    if not database_url:
        raise RuntimeError(f"${args.database_url_env} is required with --apply")
    db_pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    try:
        if args.action == "erase":
            signature = "public.erase_visa_decision_for_dsr(uuid,text,text)"
            await _assert_operator_boundary(db_pool, function_signature=signature)
            deleted = await retention.erase_decision_for_dsr(
                db_pool,
                decision_id=args.decision_id,
                case_reference=args.case_reference,
                requested_by=args.actor,
            )
            logger.info("privacy_operation_result action=erase decision_rows_deleted=%d", deleted)
            return 0 if deleted == 1 else 2

        signature = (
            "public.set_visa_decision_legal_hold("
            "uuid,boolean,text,text,text,text,timestamp with time zone)"
        )
        await _assert_operator_boundary(db_pool, function_signature=signature)
        changed = await retention.set_decision_legal_hold(
            db_pool,
            decision_id=args.decision_id,
            legal_hold=args.action == "hold",
            requested_by=args.actor,
            case_reference=args.case_reference,
            reason_code=args.reason_code,
            approved_by=args.approved_by,
            review_due_at=args.review_due_at if args.action == "hold" else None,
        )
        logger.info("privacy_operation_result action=%s changed=%s", args.action, changed)
        return 0
    finally:
        await db_pool.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("hold", "release", "erase"))
    parser.add_argument("--decision-id", required=True, type=UUID)
    parser.add_argument("--case-reference", required=True, type=_token)
    parser.add_argument("--actor", required=True, type=_token)
    parser.add_argument("--reason-code", type=_token)
    parser.add_argument("--approved-by", type=_token)
    parser.add_argument("--review-due-at", type=_aware_datetime)
    parser.add_argument("--database-url-env", default=PRIVACY_OPERATOR_DSN_ENV)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "hold" and args.review_due_at is None:
        parser.error("hold requires --review-due-at")
    if args.action != "hold" and args.review_due_at is not None:
        parser.error("--review-due-at is valid only for hold")
    if args.action in {"hold", "release"} and (
        args.reason_code is None or args.approved_by is None
    ):
        parser.error("hold/release requires --reason-code and --approved-by")
    return args


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(run(_parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
