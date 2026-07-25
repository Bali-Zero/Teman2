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
5. ``repository.activate_rule_pack`` — the SECURITY DEFINER bitemporal
   writer (migration 251) is the only ledger write path; requires the
   operator-provisioned ``visa_activation_executor`` role.

Usage:
    PYTHONPATH=. python -m backend.scripts.visa_engine.activate_pack \\
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

DATABASE_URL_ENV = "DATABASE_URL"


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
        print(
            f"DRY RUN — would insert+activate rule_pack_id={pack_id} "
            f"sequence={insert_kwargs['sequence']} env={insert_kwargs['environment']} "
            f"payload_sha256={verified.payload_sha256.hex()} "
            f"actor={args.actor} reason={args.reason}. Re-run with --yes to execute."
        )
        return 0

    database_url = os.environ.get(args.database_url_env)
    if not database_url:
        raise SystemExit(f"FAIL: ${args.database_url_env} is not set")

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    try:
        existing_hash = await _pack_row_payload_hash(pool, pack_id)
        if existing_hash is not None:
            if existing_hash != verified.payload_sha256:
                raise SystemExit(
                    f"FAIL: visa_rule_packs already holds {pack_id} with a DIFFERENT "
                    f"payload_sha256 ({existing_hash.hex()[:16]}… vs "
                    f"{verified.payload_sha256.hex()[:16]}…) — packs are immutable"
                )
            logger.info("pack row already present with identical hash — skipping insert")
        else:
            repo = VisaEngineRepository(pool)
            await repo.insert_rule_pack(**insert_kwargs)
            logger.info("pack row inserted")

        repo = VisaEngineRepository(pool)
        activation_id = await repo.activate_rule_pack(
            rule_pack_id=pack_id,
            activated_by=args.actor,
            activation_reason=args.reason,
        )
        print(f"ACTIVATED rule_pack_id={pack_id} activation_id={activation_id}")
    finally:
        await pool.close()
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
        "--database-url-env",
        default=DATABASE_URL_ENV,
        help="env var holding the database URL (default DATABASE_URL)",
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
