"""Offline ops CLI: insert + activate a signed RulePack in the database.

OFFLINE-ONLY — an operator ceremony tool, never imported by the FastAPI
process (mirrors ``sign_pack.py``'s posture). Pipeline, fail-closed at
every step:

1. Load the signed bundle JSON from disk.
2. ``bundle.verify_rule_pack`` against ``StaticTrustStore.from_env`` — a
   pack that does not verify is NEVER inserted.
3. ``bundle.validate_activation`` (anti-rollback pre-gate) with the
   current on-disk sequence/hash supplied by the operator (first pack:
   ``--current-sequence 0``, no previous hash).
4. ``repository.insert_rule_pack`` — skipped cleanly (idempotent) when the
   row already exists with the identical ``payload_sha256``; a payload
   mismatch for the same id is a hard error (packs are immutable).
5. Close the pack-writer connection, then use a distinct activation identity
   to call ``repository.activate_rule_pack`` — the SECURITY DEFINER bitemporal
   writer is the only ledger write path. Production refuses a combined login.

Usage:
    VISA_ENGINE_PACK_WRITER_DATABASE_URL=... \\
    VISA_ENGINE_ACTIVATION_DATABASE_URL=... PYTHONPATH=. \\
      python -m backend.scripts.visa_engine.activate_pack \\
        backend/services/visa_engine/contracts/packs/rulepack-prod-001.signed.json \\
        --actor operator.zero-2026-07 --reason w2-first-prod-pack --yes
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    validate_activation,
    verify_rule_pack,
)
from backend.services.visa_engine.repository import VisaEngineRepository

logger = logging.getLogger("visa_engine.activate_pack")

#: Actor/reason opaque tokens — the same regex the DB function enforces
#: (migration 253). Validating here keeps the error local and readable.
_TOKEN_RE = re.compile(r"^[A-Za-z0-9._:-]{1,120}$")

PACK_WRITER_DATABASE_URL_ENV = "VISA_ENGINE_PACK_WRITER_DATABASE_URL"
ACTIVATION_DATABASE_URL_ENV = "VISA_ENGINE_ACTIVATION_DATABASE_URL"


def _b64url_nopad_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _parse_iso_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"datetime must be timezone-aware: {value!r}")
    return parsed


def _validate_token(label: str, value: str) -> str:
    if not _TOKEN_RE.fullmatch(value):
        raise SystemExit(
            f"FAIL: --{label} must match {_TOKEN_RE.pattern} (opaque token, no free text): {value!r}"
        )
    return value


def _build_insert_kwargs(bundle: dict[str, Any], verified: Any) -> dict[str, Any]:
    """Map a signed bundle JSON to ``insert_rule_pack`` kwargs.

    Field shapes mirror the signed artifact written by ``sign_pack.py``:
    top-level ``protected``/``payload``/``payload_sha256``/``signature``
    (the last two as base64url/hex strings).
    """
    protected = bundle["protected"]
    payload = bundle["payload"]
    valid_period = payload["valid_period"]
    legal_from = _parse_iso_utc(valid_period["from"])
    legal_to = _parse_iso_utc(valid_period["to"]) if valid_period.get("to") is not None else None
    return {
        "id": UUID(payload["rule_pack_id"]),
        "environment": payload["environment"],
        "sequence": int(payload["sequence"]),
        "pack_version": payload["version"],
        "engine_contract_version": payload["engine_contract_version"],
        "engine_min_version": payload["engine_min_version"],
        "engine_max_version": payload["engine_max_version"],
        "legal_period": asyncpg.Range(
            lower=legal_from, upper=legal_to, lower_inc=True, upper_inc=False
        ),
        "protected_header": protected,
        "payload": payload,
        "payload_sha256": verified.payload_sha256,
        "previous_payload_sha256": (
            bytes.fromhex(payload["previous_payload_sha256"])
            if payload.get("previous_payload_sha256")
            else None
        ),
        "signature": _b64url_nopad_decode(bundle["signature"]),
        "signing_key_id": protected["kid"],
        "signed_at": _parse_iso_utc(protected["signed_at"]),
    }


async def _pack_row_payload_hash(db: asyncpg.Pool, pack_id: UUID) -> bytes | None:
    row = await db.fetchrow(
        "SELECT payload_sha256 FROM public.visa_rule_packs WHERE id = $1", pack_id
    )
    return bytes(row["payload_sha256"]) if row is not None else None


async def _database_identity(db: asyncpg.Pool) -> tuple[str, bool]:
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT current_user::text AS current_user, "
            "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user) AS is_superuser"
        )
    if row is None:
        raise RuntimeError("database identity unavailable")
    return str(row["current_user"]), bool(row["is_superuser"])


async def _assert_production_separation(
    writer_pool: asyncpg.Pool,
    activation_pool: asyncpg.Pool,
) -> None:
    """Prove distinct, non-superuser, least-privilege ceremony identities."""

    writer_identity, writer_superuser = await _database_identity(writer_pool)
    activation_identity, activation_superuser = await _database_identity(activation_pool)
    if writer_superuser or activation_superuser:
        raise RuntimeError("production pack activation refuses superuser sessions")
    if writer_identity == activation_identity:
        raise RuntimeError("production pack write and activation require distinct database logins")
    async with writer_pool.acquire() as conn:
        writer_can_activate = await conn.fetchval(
            "SELECT has_function_privilege(current_user, "
            "'public.visa_activate_rule_pack(uuid,text,text)', 'EXECUTE')"
        )
        writer_can_insert = await conn.fetchval(
            "SELECT has_table_privilege(current_user, 'public.visa_rule_packs', 'INSERT')"
        )
    async with activation_pool.acquire() as conn:
        activator_can_activate = await conn.fetchval(
            "SELECT has_function_privilege(current_user, "
            "'public.visa_activate_rule_pack(uuid,text,text)', 'EXECUTE')"
        )
        activator_can_insert = await conn.fetchval(
            "SELECT has_table_privilege(current_user, 'public.visa_rule_packs', 'INSERT')"
        )
    if not writer_can_insert or writer_can_activate:
        raise RuntimeError("pack writer does not have the required write-only capability boundary")
    if not activator_can_activate or activator_can_insert:
        raise RuntimeError("activation identity must be EXECUTE-only and unable to insert packs")


async def run(args: argparse.Namespace) -> int:
    bundle_path = Path(args.signed_bundle)
    bundle = json.loads(bundle_path.read_text())

    trust_store = StaticTrustStore.from_env()
    verified = verify_rule_pack(
        bundle, trust_store=trust_store, observed_at=datetime.now().astimezone()
    )
    logger.info("verified against trust store: kid=%s", bundle["protected"]["kid"])

    validate_activation(
        verified,
        current_sequence=args.current_sequence,
        current_payload_sha256=(
            bytes.fromhex(args.current_payload_sha256) if args.current_payload_sha256 else None
        ),
        environment=bundle["protected"]["environment"],
        engine_version=args.engine_version,
    )
    logger.info("anti-rollback pre-gate passed")

    insert_kwargs = _build_insert_kwargs(bundle, verified)
    pack_id: UUID = insert_kwargs["id"]

    if not args.yes:
        logger.info(
            "dry_run=true would_insert_and_activate=true rule_pack_id=%s sequence=%s "
            "environment=%s payload_sha256=%s actor=%s reason=%s",
            pack_id,
            insert_kwargs["sequence"],
            insert_kwargs["environment"],
            verified.payload_sha256.hex(),
            args.actor,
            args.reason,
        )
        return 0

    writer_database_url = os.environ.get(args.pack_writer_database_url_env)
    activation_database_url = os.environ.get(args.activation_database_url_env)
    if not writer_database_url:
        raise SystemExit(f"FAIL: ${args.pack_writer_database_url_env} is not set")
    if not activation_database_url:
        raise SystemExit(f"FAIL: ${args.activation_database_url_env} is not set")

    writer_pool = await asyncpg.create_pool(writer_database_url, min_size=1, max_size=2)
    try:
        activation_pool = await asyncpg.create_pool(activation_database_url, min_size=1, max_size=2)
        try:
            if insert_kwargs["environment"] == "PRODUCTION":
                await _assert_production_separation(writer_pool, activation_pool)

            existing_hash = await _pack_row_payload_hash(writer_pool, pack_id)
            if existing_hash is not None:
                if existing_hash != verified.payload_sha256:
                    raise SystemExit(
                        f"FAIL: visa_rule_packs already holds {pack_id} with a DIFFERENT "
                        f"payload_sha256 ({existing_hash.hex()[:16]}… vs "
                        f"{verified.payload_sha256.hex()[:16]}…) — packs are immutable"
                    )
                logger.info("pack row already present with identical hash — skipping insert")
            else:
                repo = VisaEngineRepository(writer_pool)
                await repo.insert_rule_pack(**insert_kwargs)
                logger.info("pack row inserted")

            # The activation identity never receives the pack-writer pool. Even
            # a future refactor cannot accidentally reuse the broader capability.
            repo = VisaEngineRepository(activation_pool)
            activation_id = await repo.activate_rule_pack(
                rule_pack_id=pack_id,
                activated_by=args.actor,
                activation_reason=args.reason,
            )
            logger.info("activated rule_pack_id=%s activation_id=%s", pack_id, activation_id)
        finally:
            await activation_pool.close()
    finally:
        await writer_pool.close()
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("signed_bundle", help="path to the signed bundle JSON")
    parser.add_argument("--actor", required=True, type=lambda v: _validate_token("actor", v))
    parser.add_argument("--reason", required=True, type=lambda v: _validate_token("reason", v))
    parser.add_argument(
        "--current-sequence",
        type=int,
        default=0,
        help="currently active sequence (0 for the first pack)",
    )
    parser.add_argument(
        "--current-payload-sha256",
        default=None,
        help="hex sha256 of the currently active pack (omit for the first)",
    )
    parser.add_argument(
        "--engine-version",
        default="1.0.0",
        help="engine contract version gate (matches the pack's contract)",
    )
    parser.add_argument(
        "--pack-writer-database-url-env",
        default=PACK_WRITER_DATABASE_URL_ENV,
        help="env var holding the separated immutable-pack writer URL",
    )
    parser.add_argument(
        "--activation-database-url-env",
        default=ACTIVATION_DATABASE_URL_ENV,
        help="env var holding the separated activation-executor URL",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="execute the writes (default is a dry run that only verifies)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
