"""Offline, fail-closed ceremony for an atomic RulePack activation-set replacement.

Every replacement segment is a separately signed RulePack. The CLI verifies
all bundles and the operator-supplied crypto-chain head, inserts packs through
the pack-writer identity, and closes that pool before invoking migration 267's
set writer through a separately preflighted EXECUTE-only activation identity.
The database function atomically re-derives and validates the real activation
head and exact legal coverage. Dry-run is the default; it proves signature,
chain, scope and interval shape, but deliberately makes no DB-coverage claim.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

from backend.scripts.visa_engine.activate_pack import (
    _build_insert_kwargs,
    _pack_row_payload_hash,
    _validate_token,
)
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    VerifiedRulePack,
    validate_activation,
    verify_rule_pack,
)
from backend.services.visa_engine.repository import VisaEngineRepository

logger = logging.getLogger("visa_engine.replace_activation_set")

PACK_WRITER_DATABASE_URL_ENV = "VISA_ENGINE_PACK_WRITER_DATABASE_URL"
ACTIVATION_DATABASE_URL_ENV = "VISA_ENGINE_ACTIVATION_DATABASE_URL"
MAX_REPLACEMENT_PACKS = 64
MAX_SIGNED_BUNDLE_BYTES = 2 * 1024 * 1024
ACTIVATION_FUNCTION = "public.visa_activate_rule_pack(uuid,text,text)"
ACTIVATION_SET_FUNCTION = "public.visa_replace_activation_set(uuid[],text,text)"
TABLE_PRIVILEGES = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "REFERENCES",
    "TRIGGER",
)
PG17_TABLE_PRIVILEGES = ("MAINTAIN",)

Interval = tuple[datetime, datetime | None]


@dataclass(frozen=True, slots=True)
class ReplacementBundle:
    raw: dict[str, Any]
    verified: VerifiedRulePack
    insert_kwargs: dict[str, Any]

    @property
    def pack_id(self) -> UUID:
        return self.insert_kwargs["id"]

    @property
    def sequence(self) -> int:
        return self.insert_kwargs["sequence"]

    @property
    def environment(self) -> str:
        return self.insert_kwargs["environment"]

    @property
    def legal_interval(self) -> Interval:
        legal: asyncpg.Range[datetime] = self.insert_kwargs["legal_period"]
        return legal.lower, legal.upper


def _reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError("duplicate JSON object key rejected")
        parsed[key] = value
    return parsed


def _reject_non_finite_json_number(_value: str) -> None:
    raise ValueError("non-finite JSON number rejected")


def _load_strict_json(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        raw_document = handle.read(MAX_SIGNED_BUNDLE_BYTES + 1)
    if len(raw_document) > MAX_SIGNED_BUNDLE_BYTES:
        raise ValueError("signed bundle exceeds the 2 MiB ceremony limit")
    value = json.loads(
        raw_document.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_object_pairs,
        parse_constant=_reject_non_finite_json_number,
    )
    if not isinstance(value, dict):
        raise ValueError("signed bundle must be a JSON object")
    return value


def _normalize_disjoint_coverage(intervals: list[Interval], *, label: str) -> tuple[Interval, ...]:
    """Return canonical coverage, merging adjacency and rejecting overlap."""

    if not intervals:
        raise SystemExit(f"FAIL: {label} coverage is empty")
    ordered = sorted(intervals, key=lambda interval: interval[0])
    merged: list[Interval] = []
    for lower, upper in ordered:
        if upper is not None and lower >= upper:
            raise SystemExit(f"FAIL: {label} contains an empty/reversed legal interval")
        if not merged:
            merged.append((lower, upper))
            continue
        prior_lower, prior_upper = merged[-1]
        if prior_upper is None or lower < prior_upper:
            raise SystemExit(f"FAIL: {label} legal intervals overlap")
        if lower == prior_upper:
            merged[-1] = (prior_lower, upper)
        else:
            merged.append((lower, upper))
    return tuple(merged)


def _load_and_verify_bundles(
    paths: list[str],
    *,
    trust_store: StaticTrustStore,
    observed_at: datetime,
) -> list[ReplacementBundle]:
    if not paths:
        raise SystemExit("FAIL: at least one signed replacement bundle is required")
    if len(paths) > MAX_REPLACEMENT_PACKS:
        raise SystemExit(
            f"FAIL: replacement set exceeds {MAX_REPLACEMENT_PACKS} signed segments"
        )
    replacements: list[ReplacementBundle] = []
    for raw_path in paths:
        raw = _load_strict_json(Path(raw_path))
        verified = verify_rule_pack(raw, trust_store=trust_store, observed_at=observed_at)
        replacements.append(
            ReplacementBundle(
                raw=raw,
                verified=verified,
                insert_kwargs=_build_insert_kwargs(raw, verified),
            )
        )
    replacements.sort(key=lambda bundle: bundle.sequence)
    if len({bundle.pack_id for bundle in replacements}) != len(replacements):
        raise SystemExit("FAIL: replacement bundle IDs must be unique")
    scopes = {
        (
            bundle.environment,
            bundle.raw["payload"]["jurisdiction"],
            bundle.raw["payload"]["decision_domain"],
        )
        for bundle in replacements
    }
    if len(scopes) != 1:
        raise SystemExit("FAIL: every replacement bundle must share one scope")
    return replacements


def _validate_chain(
    replacements: list[ReplacementBundle],
    *,
    current_sequence: int,
    current_payload_sha256: bytes,
    engine_version: str,
) -> None:
    sequence = current_sequence
    payload_hash = current_payload_sha256
    environment = replacements[0].environment
    for replacement in replacements:
        validate_activation(
            replacement.verified,
            current_sequence=sequence,
            current_payload_sha256=payload_hash,
            environment=environment,
            engine_version=engine_version,
        )
        sequence = replacement.sequence
        payload_hash = replacement.verified.payload_sha256


async def _insert_verified_packs(
    pool: asyncpg.Pool,
    replacements: list[ReplacementBundle],
) -> None:
    repo = VisaEngineRepository(pool)
    for replacement in replacements:
        existing_hash = await _pack_row_payload_hash(pool, replacement.pack_id)
        if existing_hash is not None:
            if existing_hash != replacement.verified.payload_sha256:
                raise SystemExit(
                    f"FAIL: immutable pack {replacement.pack_id} exists with a different hash"
                )
            continue
        await repo.insert_rule_pack(**replacement.insert_kwargs)


async def _assert_pack_writer_capability(pool: asyncpg.Pool) -> str:
    principal = str(await pool.fetchval("SELECT session_user"))
    is_superuser = await pool.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = session_user")
    if is_superuser:
        raise SystemExit("FAIL: pack-writer identity must not be superuser")
    can_select_pack = await pool.fetchval(
        "SELECT has_table_privilege(current_user, $1, $2)",
        "public.visa_rule_packs",
        "SELECT",
    )
    can_insert_pack = await pool.fetchval(
        "SELECT has_table_privilege(current_user, $1, $2)",
        "public.visa_rule_packs",
        "INSERT",
    )
    supported_table_privileges = await _supported_table_privileges(pool)
    forbidden_pack_privilege = await _has_any_table_privilege(
        pool,
        table="public.visa_rule_packs",
        privileges=tuple(
            privilege
            for privilege in supported_table_privileges
            if privilege not in {"SELECT", "INSERT"}
        ),
    )
    activation_table_privilege = await _has_any_table_privilege(
        pool,
        table="public.visa_ruleset_activations",
        privileges=supported_table_privileges,
    )
    can_activate = await pool.fetchval(
        "SELECT has_function_privilege(current_user, $1, 'EXECUTE')",
        ACTIVATION_FUNCTION,
    )
    can_replace = await pool.fetchval(
        "SELECT has_function_privilege(current_user, $1, 'EXECUTE')",
        ACTIVATION_SET_FUNCTION,
    )
    if (
        not can_select_pack
        or not can_insert_pack
        or forbidden_pack_privilege
        or activation_table_privilege
        or can_activate
        or can_replace
    ):
        raise SystemExit(
            "FAIL: pack-writer identity must have only pack SELECT/INSERT and no activation capability"
        )
    return principal


async def _has_any_table_privilege(
    pool: asyncpg.Pool,
    *,
    table: str,
    privileges: tuple[str, ...],
) -> bool:
    """Return whether the current identity has any listed PG15 table privilege."""

    for privilege in privileges:
        allowed = await pool.fetchval(
            "SELECT has_table_privilege(current_user, $1, $2)",
            table,
            privilege,
        )
        if allowed:
            return True
    return False


async def _supported_table_privileges(pool: asyncpg.Pool) -> tuple[str, ...]:
    """Return table privileges understood by the connected PG15/PG17 server."""

    server_version_num = int(
        await pool.fetchval("SELECT current_setting('server_version_num')::integer")
    )
    if server_version_num >= 170000:
        return (*TABLE_PRIVILEGES, *PG17_TABLE_PRIVILEGES)
    return TABLE_PRIVILEGES


async def _assert_activation_capability(
    pool: asyncpg.Pool,
    *,
    pack_writer_principal: str,
) -> str:
    principal = str(await pool.fetchval("SELECT session_user"))
    if principal == pack_writer_principal:
        raise SystemExit("FAIL: pack-writer and activation identities must be distinct")
    is_superuser = await pool.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = session_user")
    if is_superuser:
        raise SystemExit("FAIL: activation identity must not be superuser")
    can_execute = await pool.fetchval(
        "SELECT has_function_privilege(current_user, $1, 'EXECUTE')",
        ACTIVATION_SET_FUNCTION,
    )
    if not can_execute:
        raise SystemExit("FAIL: activation identity lacks replace-set EXECUTE capability")
    supported_table_privileges = await _supported_table_privileges(pool)
    for table in ("public.visa_rule_packs", "public.visa_ruleset_activations"):
        direct = await _has_any_table_privilege(
            pool,
            table=table,
            privileges=supported_table_privileges,
        )
        if direct:
            raise SystemExit(
                f"FAIL: activation identity has forbidden direct table capability on {table}"
            )
    return principal


async def run(args: argparse.Namespace) -> int:
    observed_at = datetime.now(timezone.utc)
    replacements = _load_and_verify_bundles(
        args.signed_bundles,
        trust_store=StaticTrustStore.from_env(),
        observed_at=observed_at,
    )
    environment = replacements[0].environment
    _normalize_disjoint_coverage(
        [bundle.legal_interval for bundle in replacements],
        label="replacement",
    )
    try:
        current_hash = bytes.fromhex(args.current_payload_sha256)
    except ValueError as exc:
        raise SystemExit("FAIL: --current-payload-sha256 must be hexadecimal") from exc
    if len(current_hash) != 32:
        raise SystemExit("FAIL: --current-payload-sha256 must encode exactly 32 bytes")
    if args.current_sequence < 1:
        raise SystemExit("FAIL: --current-sequence must identify an existing activated head")
    _validate_chain(
        replacements,
        current_sequence=args.current_sequence,
        current_payload_sha256=current_hash,
        engine_version=args.engine_version,
    )

    if not args.yes:
        logger.info(
            "DRY RUN crypto/shape preflight passed (DB coverage not checked): "
            "env=%s sequences=%s pack_ids=%s",
            environment,
            [bundle.sequence for bundle in replacements],
            [str(bundle.pack_id) for bundle in replacements],
        )
        return 0

    pack_database_url = os.environ.get(args.pack_database_url_env)
    if not pack_database_url:
        raise SystemExit(f"FAIL: ${args.pack_database_url_env} is not set")
    activation_database_url = os.environ.get(args.activation_database_url_env)
    if not activation_database_url:
        raise SystemExit(f"FAIL: ${args.activation_database_url_env} is not set")

    pack_pool = await asyncpg.create_pool(pack_database_url, min_size=1, max_size=2)
    activation_pool: asyncpg.Pool | None = None
    pack_pool_open = True
    try:
        pack_principal = await _assert_pack_writer_capability(pack_pool)
        activation_pool = await asyncpg.create_pool(
            activation_database_url,
            min_size=1,
            max_size=2,
        )
        principal = await _assert_activation_capability(
            activation_pool,
            pack_writer_principal=pack_principal,
        )
        await _insert_verified_packs(pack_pool, replacements)

        # Make accidental cross-capability reuse impossible before the ledger
        # mutation. The activation pool was opened only to preflight it before
        # any pack insert could leave an avoidable inert row behind.
        await pack_pool.close()
        pack_pool_open = False

        activation_ids = await VisaEngineRepository(activation_pool).replace_activation_set(
            rule_pack_ids=[bundle.pack_id for bundle in replacements],
            activated_by=args.actor,
            activation_reason=args.reason,
        )
        logger.info(
            "activation set replaced: principal=%s activation_ids=%s",
            principal,
            [str(activation_id) for activation_id in activation_ids],
        )
    finally:
        if pack_pool_open:
            await pack_pool.close()
        if activation_pool is not None:
            await activation_pool.close()
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("signed_bundles", nargs="+", help="signed replacement bundle JSON paths")
    parser.add_argument(
        "--actor", required=True, type=lambda value: _validate_token("actor", value)
    )
    parser.add_argument(
        "--reason", required=True, type=lambda value: _validate_token("reason", value)
    )
    parser.add_argument("--current-sequence", required=True, type=int)
    parser.add_argument("--current-payload-sha256", required=True)
    parser.add_argument("--engine-version", default="1.0.0")
    parser.add_argument("--pack-database-url-env", default=PACK_WRITER_DATABASE_URL_ENV)
    parser.add_argument("--activation-database-url-env", default=ACTIVATION_DATABASE_URL_ENV)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="insert verified packs and replace activations (default: verified dry-run)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(run(_parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
