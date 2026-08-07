"""Durable idempotency store for the public Visa Oracle evaluate endpoint."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

import asyncpg

from backend.services.visa_engine.api_models import VisaOracleEvaluateResponse
from backend.services.visa_engine.bundle import JsonValue, canonicalize_json
from backend.services.visa_engine.crypto import FactsFingerprintKey
from backend.services.visa_engine.decision_seal import verify_decision_seal
from backend.services.visa_engine.enums import DecisionState

logger = logging.getLogger(__name__)


class IdempotencyConflictError(ValueError):
    """The same key was already bound to a different canonical request."""


class IdempotencyIntegrityError(RuntimeError):
    """A stored replay body failed its persisted JCS/SHA-256 integrity check."""


@dataclass(frozen=True, slots=True)
class IdempotencyReservation:
    key_sha256: bytes
    request_hmac: bytes
    request_hmac_key_id: str
    reserved_at: datetime
    environment: str
    retention_policy_id: uuid.UUID
    expires_at: datetime
    response: VisaOracleEvaluateResponse | None


def hash_idempotency_key(key: str) -> bytes:
    """Hash a caller key before persistence; the raw header is never stored."""

    return hashlib.sha256(key.encode("utf-8")).digest()


def _request_hmac(canonical_request: bytes, key: FactsFingerprintKey) -> bytes:
    """Domain-separated keyed digest; raw or plain-hashed facts never persist."""

    return hmac.new(
        key.secret,
        b"visa-oracle-evaluate-request-v1\x00" + canonical_request,
        hashlib.sha256,
    ).digest()


def _decode_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        decoded = json.loads(value)
    else:
        decoded = value
    if not isinstance(decoded, dict):
        raise ValueError("stored idempotency response must be a JSON object")
    return decoded


def _canonical_response(payload: dict[str, Any]) -> bytes:
    return canonicalize_json(cast(dict[str, JsonValue], payload))


def _response_hmac(canonical_response: bytes, key: FactsFingerprintKey) -> bytes:
    """Authenticate the complete projection, domain-separated from Decision seals."""

    return hmac.new(
        key.secret,
        b"visa-oracle-evaluate-response-v1\x00" + canonical_response,
        hashlib.sha256,
    ).digest()


def _verify_stored_response(
    raw_response: Any,
    raw_sha256: Any,
    raw_hmac: Any,
    raw_hmac_key_id: Any,
    verification_keys: tuple[FactsFingerprintKey, ...],
    verification_time: datetime,
) -> tuple[VisaOracleEvaluateResponse, bytes]:
    payload = _decode_json_object(raw_response)
    canonical = _canonical_response(payload)
    computed_sha256 = hashlib.sha256(canonical).digest()
    if raw_sha256 is None or not hmac.compare_digest(bytes(raw_sha256), computed_sha256):
        raise IdempotencyIntegrityError("stored idempotency response integrity mismatch")
    if not isinstance(raw_hmac_key_id, str) or raw_hmac is None:
        raise IdempotencyIntegrityError("stored idempotency response authentication missing")
    keys_by_id = {key.kid: key for key in verification_keys}
    response_key = keys_by_id.get(raw_hmac_key_id)
    if (
        response_key is None
        or response_key.valid_from > verification_time
        or (response_key.revoked_at is not None and response_key.revoked_at <= verification_time)
        or not hmac.compare_digest(
            bytes(raw_hmac),
            _response_hmac(canonical, response_key),
        )
    ):
        raise IdempotencyIntegrityError("stored idempotency response authentication mismatch")

    response = VisaOracleEvaluateResponse.model_validate(payload)
    if response.decision.state is not DecisionState.TEMPORARILY_UNAVAILABLE:
        integrity = response.decision.decision_integrity
        if integrity is None:
            raise IdempotencyIntegrityError("stored evaluated decision seal missing")
        decision_key = keys_by_id.get(integrity.key_id)
        if (
            decision_key is None
            or decision_key.valid_from > verification_time
            or (
                decision_key.revoked_at is not None and decision_key.revoked_at <= verification_time
            )
            or not verify_decision_seal(
                response.decision,
                key=decision_key,
            )
        ):
            raise IdempotencyIntegrityError("stored evaluated decision seal invalid")
    return response, computed_sha256


async def reserve(
    db_pool: asyncpg.Pool,
    *,
    key_sha256: bytes,
    canonical_request: bytes,
    environment: str,
    minting_key: FactsFingerprintKey,
    verification_keys: tuple[FactsFingerprintKey, ...],
) -> IdempotencyReservation:
    """Create or load a key binding using a database-owned frozen clock."""

    if environment not in {"TEST", "STAGING", "PRODUCTION"}:
        raise ValueError("environment must be TEST, STAGING, or PRODUCTION")

    minting_hmac = _request_hmac(canonical_request, minting_key)
    verification_hmacs = {
        key.kid: _request_hmac(canonical_request, key) for key in verification_keys
    }

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            # The SECURITY DEFINER capability reclaims this exact expired key
            # first, then performs a globally capped SKIP LOCKED sweep. The app
            # needs EXECUTE only and cannot issue unaudited table DELETEs.
            await conn.fetchval(
                """
                SELECT public.prepare_visa_evaluate_idempotency_reservation(
                    $1, 128, 'evaluate-reservation'
                )
                """,
                key_sha256,
            )
            await conn.execute(
                """
                INSERT INTO visa_evaluate_idempotency (
                    key_sha256, request_hmac, request_hmac_key_id, environment
                ) VALUES ($1, $2, $3, $4)
                ON CONFLICT (key_sha256) DO NOTHING
                """,
                key_sha256,
                minting_hmac,
                minting_key.kid,
                environment,
            )
            row = await conn.fetchrow(
                """
                SELECT key_sha256, request_hmac, request_hmac_key_id,
                       reserved_at, environment, retention_policy_id, expires_at,
                       response_body, response_sha256,
                       response_hmac, response_hmac_key_id,
                       clock_timestamp() AS verification_time
                FROM visa_evaluate_idempotency
                WHERE key_sha256 = $1
                """,
                key_sha256,
            )
    if row is None:  # pragma: no cover - INSERT/SELECT invariant
        raise RuntimeError("idempotency reservation disappeared after insert")
    stored_environment = row["environment"]
    raw_policy_id = row["retention_policy_id"]
    expires_at = row["expires_at"]
    if stored_environment is None or raw_policy_id is None or expires_at is None:
        raise IdempotencyIntegrityError(
            "legacy idempotency reservation has no Zero-approved retention binding"
        )
    if str(stored_environment) != environment:
        raise IdempotencyIntegrityError("idempotency reservation environment mismatch")
    if expires_at <= row["verification_time"]:
        raise IdempotencyIntegrityError("idempotency reservation expired")
    retention_policy_id = uuid.UUID(str(raw_policy_id))
    stored_key_id = str(row["request_hmac_key_id"])
    expected_hmac = verification_hmacs.get(stored_key_id)
    if expected_hmac is None or not hmac.compare_digest(bytes(row["request_hmac"]), expected_hmac):
        raise IdempotencyConflictError("idempotency key is bound to another request")

    raw_response = row["response_body"]
    response = None
    if raw_response is not None:
        response, _ = _verify_stored_response(
            raw_response,
            row["response_sha256"],
            row["response_hmac"],
            row["response_hmac_key_id"],
            verification_keys,
            row["verification_time"],
        )
    return IdempotencyReservation(
        key_sha256=bytes(row["key_sha256"]),
        request_hmac=bytes(row["request_hmac"]),
        request_hmac_key_id=stored_key_id,
        reserved_at=row["reserved_at"],
        environment=environment,
        retention_policy_id=retention_policy_id,
        expires_at=expires_at,
        response=response,
    )


async def complete(
    db_pool: asyncpg.Pool,
    *,
    reservation: IdempotencyReservation,
    response: VisaOracleEvaluateResponse,
    response_signing_key: FactsFingerprintKey,
    verification_keys: tuple[FactsFingerprintKey, ...],
) -> VisaOracleEvaluateResponse:
    """Atomically store the first response and return the canonical winner.

    Concurrent evaluators use the same DB-frozen ``reserved_at`` and should
    compute identical output.  ``UPDATE ... response_body IS NULL`` makes
    the first completion authoritative; every loser reads and returns that
    exact stored envelope.
    """

    payload = response.model_dump(mode="json")
    canonical = _canonical_response(payload)
    response_sha256 = hashlib.sha256(canonical).digest()
    response_hmac = _response_hmac(canonical, response_signing_key)
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE visa_evaluate_idempotency
                SET response_body = $2::text::jsonb,
                    response_sha256 = $3,
                    response_hmac = $4,
                    response_hmac_key_id = $5,
                    completed_at = clock_timestamp()
                WHERE key_sha256 = $1
                  AND request_hmac = $6
                  AND request_hmac_key_id = $7
                  AND reserved_at = $8
                  AND environment = $9
                  AND retention_policy_id = $10
                  AND expires_at = $11
                  AND expires_at > clock_timestamp()
                  AND response_body IS NULL
                """,
                reservation.key_sha256,
                canonical.decode("utf-8"),
                response_sha256,
                response_hmac,
                response_signing_key.kid,
                reservation.request_hmac,
                reservation.request_hmac_key_id,
                reservation.reserved_at,
                reservation.environment,
                reservation.retention_policy_id,
                reservation.expires_at,
            )
            row = await conn.fetchrow(
                """
                SELECT request_hmac, request_hmac_key_id, reserved_at,
                       environment, retention_policy_id, expires_at,
                       response_body, response_sha256,
                       response_hmac, response_hmac_key_id,
                       clock_timestamp() AS verification_time
                FROM visa_evaluate_idempotency
                WHERE key_sha256 = $1
                FOR UPDATE
                """,
                reservation.key_sha256,
            )
            if row is None:
                raise IdempotencyIntegrityError("idempotency reservation no longer available")
            if (
                not hmac.compare_digest(bytes(row["request_hmac"]), reservation.request_hmac)
                or str(row["request_hmac_key_id"]) != reservation.request_hmac_key_id
                or row["reserved_at"] != reservation.reserved_at
                or row["environment"] != reservation.environment
                or row["retention_policy_id"] != reservation.retention_policy_id
                or row["expires_at"] != reservation.expires_at
            ):
                raise IdempotencyConflictError("idempotency key changed request binding")
            if row["expires_at"] <= row["verification_time"]:
                raise IdempotencyIntegrityError("idempotency reservation expired")
            if row["response_body"] is None:  # pragma: no cover - matching CAS invariant
                raise RuntimeError("idempotency completion did not persist a response")
            stored_response, stored_hash = _verify_stored_response(
                row["response_body"],
                row["response_sha256"],
                row["response_hmac"],
                row["response_hmac_key_id"],
                verification_keys,
                row["verification_time"],
            )
    if not hmac.compare_digest(stored_hash, response_sha256):
        logger.warning(
            "visa evaluate idempotency deterministic mismatch: computed=%s stored=%s",
            response_sha256.hex()[:12],
            stored_hash.hex()[:12],
        )
    return stored_response


__all__ = [
    "IdempotencyConflictError",
    "IdempotencyIntegrityError",
    "IdempotencyReservation",
    "complete",
    "hash_idempotency_key",
    "reserve",
]
