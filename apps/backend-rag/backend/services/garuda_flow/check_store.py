"""``CheckStore`` adapter over ``garuda_voa_check_results`` (migration 286).

Real persistence for `public_api.py`'s L2 seam. See migration 286's header
for why this is a NEW table rather than an extension of the retired
``garuda_voa_checks`` archive, and why it shares the ``GARUDA_CHECK``
retention-policy scope with that archive table rather than inventing a
second one (ARCHITECTURE.md D2).

Nothing here invents a retention duration -- `_policy_available` reads the
SAME Python primitive `garuda_flow.retention.active_garuda_check_policy_
available` already uses for the legacy table, and the database's own
`BEFORE INSERT` trigger (286) is the actual authority; this adapter's
pre-check only turns a would-be trigger exception into the contract's
`PersistencePolicyUnavailable` -> 503 shape without a wasted round trip.

Unlike L3's `create_order_and_checkout` (which must call an external
payment provider between reserving an idempotency key and completing it),
`create()` here has no I/O between the two -- the whole operation is one
DB transaction, so there is no crash-mid-flight "reserved but not
completed" state to resume from.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import UTC, date, datetime
from typing import Any

import asyncpg

from backend.services.garuda_flow import retention
from backend.services.garuda_flow.eligibility import DeclineCode
from backend.services.garuda_flow.intake import CaseType, Purpose
from backend.services.garuda_flow.public_api import (
    EligibilityCheckOutcome,
    IdempotencyConflict,
    PersistencePolicyUnavailable,
    StoredCheck,
)

# CodeQL finding (unused global, PR #4920 review 2026-08-25): a `logger` was
# declared here with no call site. Checked for a dropped warning before
# removing rather than assuming dead code: the purge path this module owns
# (`purge_expired_garuda_voa_check_results` below) delegates to
# `public.purge_garuda_voa_check_results`, which already writes its own
# append-only audit trail to `visa_decision_retention_batches` on every
# successful batch (migration 286) -- the SAME pattern the sibling
# `garuda_flow.retention` module uses for its own purge function, and that
# module has no logger either. No warning belongs on this path; the global
# was genuinely unused.

__all__ = ["PostgresCheckStore", "purge_expired_garuda_voa_check_results"]

# Mirrors `garuda_flow.retention._REQUESTED_BY_RE` exactly (same shape as the
# legacy archive table's actor-format guard) -- duplicated rather than
# imported because that module is L1-owned (retention.py header) and this
# table's purge path is L2's, not a reason to reach into a sibling lane's
# private regex.
_REQUESTED_BY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")

# Bytes of entropy for the opaque ids this adapter mints. 24 raw bytes ->
# 32 base64url chars (no padding), inside the contract's ResultId
# {22,128} bound and comfortably >=128 bits (contract: "an identifier,
# never a credential"). The session secret uses more entropy (32 bytes)
# because it IS a bearer credential.
_RESULT_ID_BYTES = 24
_SESSION_SECRET_BYTES = 32

# Namespace prefixes keep create-path and delete-path idempotency keys in
# disjoint hash spaces even if a caller reuses the identical literal
# Idempotency-Key header value for both operations (the contract scopes
# Idempotency-Key per-operation, never globally).
_CREATE_KEY_NAMESPACE = "create-eligibility-check"
_DELETE_KEY_NAMESPACE = "delete-eligibility-result"


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _scoped_key_sha256(*, namespace: str, raw_key: str) -> bytes:
    identity = f"{namespace}\x1f{raw_key}".encode()
    return hashlib.sha256(identity).digest()


def _hash_secret(raw_secret: str) -> str:
    return hashlib.sha256(raw_secret.encode()).hexdigest()


def _as_date(value: object) -> date | None:
    if value is None or isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"expected a date, ISO date string, or None, got {type(value)!r}")


def _outcome_from_row(row: asyncpg.Record) -> EligibilityCheckOutcome:
    reason_codes_raw = row["reason_codes"]
    if isinstance(reason_codes_raw, str):
        reason_codes_raw = json.loads(reason_codes_raw)
    accepted = row["decision"] == "ACCEPT"
    return EligibilityCheckOutcome(
        accepted=accepted,
        reason_codes=[DeclineCode(code) for code in (reason_codes_raw or [])],
        published_filing_deadline=row["published_filing_deadline"] if accepted else None,
        price_idr=row["price_idr"] if accepted else None,
        price_source=row["price_source"] if accepted else None,
    )


class PostgresCheckStore:
    """Real ``CheckStore`` over ``garuda_voa_check_results``."""

    def __init__(self, pool: asyncpg.Pool, *, environment: str) -> None:
        self._pool = pool
        self._environment = environment

    async def _policy_available(self, *, created_at: datetime) -> bool:
        return await retention.active_garuda_check_policy_available(
            self._pool, environment=self._environment, created_at=created_at
        )

    async def create(
        self,
        *,
        idempotency_key: str,
        canonical_request: dict[str, object],
        outcome: EligibilityCheckOutcome,
    ) -> StoredCheck:
        key_sha256 = _scoped_key_sha256(namespace=_CREATE_KEY_NAMESPACE, raw_key=idempotency_key)
        payload_sha256 = hashlib.sha256(_canonical_json(canonical_request)).digest()

        async with self._pool.acquire() as conn, conn.transaction():
            existing = await conn.fetchrow(
                """
                SELECT canonical_payload_sha256, result_id
                  FROM garuda_voa_check_idempotency
                 WHERE key_sha256 = $1
                 FOR UPDATE
                """,
                key_sha256,
            )
            if existing is not None:
                if bytes(existing["canonical_payload_sha256"]) != payload_sha256:
                    raise IdempotencyConflict("Idempotency-Key bound to a different payload")
                row = await conn.fetchrow(
                    """
                    SELECT decision, reason_codes, published_filing_deadline,
                           price_idr, price_source
                      FROM garuda_voa_check_results
                     WHERE result_id = $1
                    """,
                    existing["result_id"],
                )
                if row is None:  # pragma: no cover - defensive, cannot happen post-commit
                    raise PersistencePolicyUnavailable(
                        "idempotency row bound to a missing check result"
                    )
                return StoredCheck(
                    result_id=existing["result_id"],
                    outcome=_outcome_from_row(row),
                    idempotency_replayed=True,
                    session_secret=None,
                )

            now = datetime.now(UTC)
            if not await self._policy_available(created_at=now):
                raise PersistencePolicyUnavailable("no active GARUDA_CHECK retention policy")

            result_id = secrets.token_urlsafe(_RESULT_ID_BYTES)
            raw_secret = secrets.token_urlsafe(_SESSION_SECRET_BYTES)
            secret_hash = _hash_secret(raw_secret)

            case_type = CaseType(canonical_request["case_type"])
            purpose = Purpose(canonical_request["purpose"])

            # The LIST, deliberately not `json.dumps(...)` of it. Every pool this
            # store runs on registers a `jsonb` type codec whose encoder IS
            # `json.dumps` (`service_initializer.py::_light_init_connection` for
            # the `api` process, `init_db_connection` for `rag`), so handing it a
            # pre-serialized string makes asyncpg serialize it a SECOND time: the
            # array `["X"]` lands as the JSONB scalar string `"[\"X\"]"`.
            # Migration 286's CHECK constraint then calls
            # `jsonb_array_length(reason_codes)` on that scalar — on BOTH the
            # ACCEPT and the DECLINE branch — and Postgres raises SQLSTATE 22023
            # `cannot get array length of a scalar`. That is not a
            # `PersistencePolicyUnavailable` nor an `IdempotencyConflict`, the only
            # two the router catches, so it escaped as a bare HTTP 500 on EVERY
            # create() call. Measured live 2026-08-27: the funnel's first action
            # 500'd for every payload shape, and both check tables held 0 rows.
            # An explicit `$N::jsonb` cast does NOT dodge the codec — measured
            # with a real INSERT: with the codec active, `$1` and `$1::jsonb` both
            # store `jsonb_typeof = string`. Do not "fix" a future instance of
            # this by adding a cast.
            reason_codes_list = [code.value for code in outcome.reason_codes]

            # `canonical_request` is `EligibilityCheckRequest.model_dump(mode="json")`
            # at the real call site -- dates arrive as ISO strings, never
            # `datetime.date` objects, but asyncpg's date codec requires the
            # latter. `_as_date` accepts both so a caller passing real
            # `date` objects directly (as this file's own tests do) also works.
            entry_date = _as_date(canonical_request["entry_date"])
            passport_expiry_date = _as_date(canonical_request["passport_expiry_date"])
            voa_expiry_date = _as_date(canonical_request.get("voa_expiry_date"))

            await conn.execute(
                """
                INSERT INTO garuda_voa_check_results (
                    result_id, session_secret_hash, environment,
                    case_type, nationality, entry_date, passport_expiry_date,
                    voa_expiry_date, extension_already_used, purpose, travellers, self_pay,
                    decision, reason_codes, published_filing_deadline, price_idr, price_source,
                    retention_notice_acknowledged_at
                ) VALUES (
                    $1, $2, $3,
                    $4, $5, $6, $7,
                    $8, $9, $10, $11, $12,
                    $13, $14, $15, $16, $17,
                    statement_timestamp()
                )
                """,
                result_id,
                secret_hash,
                self._environment,
                case_type.value,
                canonical_request["nationality"],
                entry_date,
                passport_expiry_date,
                voa_expiry_date,
                bool(canonical_request.get("extension_already_used", False)),
                purpose.value,
                int(canonical_request["travellers"]),
                bool(canonical_request["self_pay"]),
                "ACCEPT" if outcome.accepted else "DECLINE",
                reason_codes_list,
                outcome.published_filing_deadline,
                outcome.price_idr,
                outcome.price_source,
            )
            await conn.execute(
                """
                INSERT INTO garuda_voa_check_idempotency
                    (key_sha256, canonical_payload_sha256, result_id, completed_at)
                VALUES ($1, $2, $3, statement_timestamp())
                """,
                key_sha256,
                payload_sha256,
                result_id,
            )
            return StoredCheck(
                result_id=result_id,
                outcome=outcome,
                idempotency_replayed=False,
                session_secret=raw_secret,
            )

    async def get(self, *, result_id: str, session_secret: str) -> StoredCheck | None:
        secret_hash = _hash_secret(session_secret)
        row = await self._pool.fetchrow(
            """
            SELECT decision, reason_codes, published_filing_deadline, price_idr, price_source
              FROM garuda_voa_check_results
             WHERE result_id = $1 AND session_secret_hash = $2
            """,
            result_id,
            secret_hash,
        )
        if row is None:
            return None
        return StoredCheck(
            result_id=result_id,
            outcome=_outcome_from_row(row),
            idempotency_replayed=False,
            session_secret=None,
        )

    async def delete(
        self,
        *,
        result_id: str,
        session_secret: str | None,
        idempotency_key: str,
    ) -> bool:
        key_sha256 = _scoped_key_sha256(namespace=_DELETE_KEY_NAMESPACE, raw_key=idempotency_key)
        payload_sha256 = hashlib.sha256(
            _canonical_json({"result_id": result_id, "session_secret": session_secret})
        ).digest()

        async with self._pool.acquire() as conn, conn.transaction():
            existing = await conn.fetchrow(
                """
                SELECT canonical_payload_sha256
                  FROM garuda_voa_check_idempotency
                 WHERE key_sha256 = $1
                 FOR UPDATE
                """,
                key_sha256,
            )
            if existing is not None:
                if bytes(existing["canonical_payload_sha256"]) != payload_sha256:
                    raise IdempotencyConflict("Idempotency-Key bound to a different payload")
                return False  # already processed by a prior attempt with this exact key+payload

            deleted = False
            if session_secret is not None:
                secret_hash = _hash_secret(session_secret)
                row = await conn.fetchrow(
                    """
                    DELETE FROM garuda_voa_check_results
                     WHERE result_id = $1 AND session_secret_hash = $2
                     RETURNING result_id
                    """,
                    result_id,
                    secret_hash,
                )
                deleted = row is not None

            await conn.execute(
                """
                INSERT INTO garuda_voa_check_idempotency
                    (key_sha256, canonical_payload_sha256, completed_at)
                VALUES ($1, $2, statement_timestamp())
                """,
                key_sha256,
                payload_sha256,
            )
            return deleted


async def purge_expired_garuda_voa_check_results(
    db_pool: asyncpg.Pool,
    *,
    limit: int,
    requested_by: str,
) -> int:
    """Run one bounded, DB-enforced purge batch and return deleted rows.

    Mirrors ``garuda_flow.retention.purge_expired_garuda_checks`` exactly
    (same limit bound, same actor-format guard, same append-only evidence
    trail via ``visa_decision_retention_batches`` inside migration 286's
    ``purge_garuda_voa_check_results`` function) -- this is the erasure path
    for the table that actually receives live traffic, so it cannot be left
    unwired the way the archive table's caller-less primitive briefly was:
    the ``garuda_voa_check_idempotency`` guard trigger and the ``GARUDA_CHECK``
    scope's ``INTO STRICT`` binding trigger both fail closed until Zero signs
    a policy row (no migration seeds one), so this stays inert in every
    environment today -- but the instant that signature lands, real rows
    start accumulating and this is the only thing that can erase them.

    No scheduler calls this yet -- wiring the cadence (cron/synthetic-probe
    stage) is an operator/orchestrator decision, same as
    ``purge_expired_garuda_checks`` before it, not something this adapter
    should invent.
    """

    if type(limit) is not int or not 1 <= limit <= 1_000:
        raise ValueError("limit must be an integer between 1 and 1000")
    if not isinstance(requested_by, str) or _REQUESTED_BY_RE.fullmatch(requested_by) is None:
        raise ValueError("requested_by has an invalid format")
    async with db_pool.acquire() as conn:
        deleted = await conn.fetchval(
            "SELECT public.purge_garuda_voa_check_results($1, $2)",
            limit,
            requested_by,
        )
    return int(deleted)
