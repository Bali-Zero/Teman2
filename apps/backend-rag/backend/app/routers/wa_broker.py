"""WA broker endpoints — the Pro-side codex broker's ONLY two doors (BOT-V4 S2).

POST /api/wa-broker/claim     — CAS one offered job -> leased, return package
POST /api/wa-broker/complete  — CAS leased -> completed_pending_consume (or a
                                typed terminal failure), idempotent

Spec: research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md
(#4333), section 2 diagram + H5/H6/H13. These endpoints exist regardless of
flags (spec 5 "dormant endpoints" row) — the standing control is the
dedicated key + per-endpoint scope + rate limit below, not the flag.

Auth model — same least-privilege shape as wa_inbox.py: the transport header
is ``X-API-Key`` and its value must EQUAL the dedicated broker key
(``settings.wa_broker_key``), constant-time. The spec names the credential
"X-WA-Broker-Key"; it is realized here as a DEDICATED KEY on the standard
header so the HybridAuthMiddleware path stays identical to every other
internal surface — the control the spec asks for (dedicated credential,
per-endpoint scope, constant-time compare, rate limit) is intact, only the
header NAME differs. A generic admin key is rejected by construction.

PII discipline: request/response bodies carry the package/result text; the
log lines here carry job ids, states and HTTP codes ONLY.
"""

from __future__ import annotations

import hmac
import logging
import time
import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.deps.database import get_database_pool
from backend.services.integrations import wa_broker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wa-broker", tags=["wa-broker"])

# Rate limit (spec H13): the legitimate broker is single-flight and polls
# ~1/s, so this ceiling is far above any honest cadence and far below a
# useful brute-force rate. In-process sliding window — two api workers means
# two windows, which still bounds the aggregate at 2x this figure.
_RATE_LIMIT_PER_MINUTE = 120
_rate_window_start: float = 0.0
_rate_window_count: int = 0


def _rate_limit_check() -> None:
    global _rate_window_start, _rate_window_count
    now = time.monotonic()
    if now - _rate_window_start >= 60.0:
        _rate_window_start = now
        _rate_window_count = 0
    _rate_window_count += 1
    if _rate_window_count > _RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="wa-broker rate limit")


def require_wa_broker_key(request: Request) -> None:
    """Reject unless X-API-Key equals the dedicated broker key exactly.

    Constant-time comparison; 401 when the key is missing, wrong, or not
    configured server-side (unconfigured = the surface is OFF, not open).
    """
    # Rate limit BEFORE the auth verdict, so failed attempts count too: a
    # limiter that increments only on successful auth throttles a legitimate
    # caller misbehaving but leaves credential-guessing completely unthrottled
    # — the opposite of the brute-force bound the ceiling exists for. (Found
    # by the S2 test lane's adversarial pass, 2026-08-19.)
    _rate_limit_check()
    configured = getattr(settings, "wa_broker_key", None)
    provided = request.headers.get("X-API-Key")
    if not configured or not provided or not hmac.compare_digest(provided, configured):
        raise HTTPException(status_code=401, detail="wa-broker key required")


class ClaimRequest(BaseModel):
    # Broker-reported queue state — the /claim poll IS the liveness heartbeat
    # (spec 2.1), including polls that find no job.
    in_flight: int = Field(0, ge=0, le=16)
    last_exec_ms: int | None = Field(None, ge=0)


class ClaimResponse(BaseModel):
    job_id: uuid.UUID | None = None
    fence_token: uuid.UUID | None = None
    package: str | None = None
    package_hash: str | None = None
    deadline_at: str | None = None
    server_now: str | None = None


class CompleteRequest(BaseModel):
    job_id: uuid.UUID
    fence_token: uuid.UUID
    # Minted once per exec attempt on the broker; the retry of a lost HTTP
    # response re-sends the same key -> idempotent 200 (spec H5/H6).
    completion_key: str = Field(min_length=8, max_length=128)
    result_text: str | None = Field(None, max_length=65536)
    error_class: str | None = Field(None, max_length=64)
    exec_ms: int | None = Field(None, ge=0)


class CompleteResponse(BaseModel):
    status: str


@router.post(
    "/claim",
    response_model=ClaimResponse,
    dependencies=[Depends(require_wa_broker_key)],
)
async def claim(
    body: ClaimRequest,
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> ClaimResponse:
    async with pool.acquire() as conn:
        row = await wa_broker.claim_job(
            conn,
            in_flight=body.in_flight,
            last_exec_ms=body.last_exec_ms,
        )
    if row is None:
        return ClaimResponse()
    return ClaimResponse(
        job_id=row["job_id"],
        fence_token=row["fence_token"],
        package=row["package"],
        package_hash=row["package_hash"],
        deadline_at=row["deadline_at"].isoformat(),
        server_now=row["server_now"].isoformat(),
    )


@router.post(
    "/complete",
    response_model=CompleteResponse,
    dependencies=[Depends(require_wa_broker_key)],
)
async def complete(
    body: CompleteRequest,
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> CompleteResponse:
    if (body.result_text is None) == (body.error_class is None):
        raise HTTPException(
            status_code=422,
            detail="exactly one of result_text / error_class is required",
        )
    async with pool.acquire() as conn:
        status = await wa_broker.complete_job(
            conn,
            job_id=body.job_id,
            fence_token=body.fence_token,
            completion_key=body.completion_key,
            result_text=body.result_text,
            error_class=body.error_class,
            exec_ms=body.exec_ms,
        )
    if status is wa_broker.CompleteStatus.CONFLICT:
        logger.warning("wa-broker: conflicting completion for job %s", body.job_id)
        raise HTTPException(status_code=409, detail="job already completed")
    if status is wa_broker.CompleteStatus.GONE:
        logger.info("wa-broker: late/unknown completion for job %s", body.job_id)
        raise HTTPException(status_code=410, detail="job not leased under this fence")
    logger.info("wa-broker: completion %s for job %s", status.value, body.job_id)
    return CompleteResponse(status=status.value)
