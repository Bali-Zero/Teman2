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
import threading
import time
import uuid
from typing import TypeVar

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.app.core.config import settings
from backend.app.deps.database import get_database_pool
from backend.services.integrations import wa_broker

logger = logging.getLogger(__name__)

_ModelT = TypeVar("_ModelT", bound=BaseModel)

router = APIRouter(prefix="/api/wa-broker", tags=["wa-broker"])

# Rate limiting (spec H13) — TWO buckets, split BY AUTH OUTCOME (S2
# cross-family review, finding 1). The first build shared one pre-auth
# bucket across all callers, which handed any unauthenticated remote a kill
# switch: 121 bad-key requests starved the legitimate broker — including
# completion delivery — for the rest of the window.
#
#  - AUTH bucket: consumed only by requests carrying the VALID key. Bounds
#    DB work from a runaway authenticated broker; unauthenticated traffic
#    cannot touch it, so it cannot be weaponized for denial of service.
#  - FAIL buckets: per-source, consumed only by FAILED auths. Damps the
#    401-response rate per source. The actual brute-force defense is the
#    credential itself (dedicated high-entropy key, constant-time compare)
#    — an in-process counter is damping, not the security boundary, and
#    this docstring deliberately does not claim otherwise.
#
# Windows are fixed and per-process (two api workers => 2x the aggregate),
# guarded by a lock because sync FastAPI dependencies run in a threadpool.
_AUTH_LIMIT_PER_MINUTE = 120
_FAIL_LIMIT_PER_MINUTE = 30
_FAIL_SOURCES_MAX = 1024  # bound the dict so a spoofed-source flood can't grow it

_rate_lock = threading.Lock()
_auth_window_start: float = 0.0
_auth_window_count: int = 0
_fail_windows: dict[str, tuple[float, int]] = {}


def _auth_bucket_take() -> bool:
    """One slot from the authenticated bucket. True = allowed."""
    global _auth_window_start, _auth_window_count
    now = time.monotonic()
    with _rate_lock:
        if now - _auth_window_start >= 60.0:
            _auth_window_start = now
            _auth_window_count = 0
        _auth_window_count += 1
        return _auth_window_count <= _AUTH_LIMIT_PER_MINUTE


def _fail_bucket_take(source: str) -> bool:
    """One slot from the per-source failed-auth bucket. True = respond 401
    normally; False = damp with 429. When the table is full, new sources
    fall through to 401 undamped — a full table must degrade against the
    ATTACKER (less damping), never against the legitimate broker."""
    now = time.monotonic()
    with _rate_lock:
        window = _fail_windows.get(source)
        if window is None or now - window[0] >= 60.0:
            if window is None and len(_fail_windows) >= _FAIL_SOURCES_MAX:
                # Drop expired windows before giving up on tracking.
                for key in [k for k, (start, _) in _fail_windows.items() if now - start >= 60.0]:
                    del _fail_windows[key]
                if len(_fail_windows) >= _FAIL_SOURCES_MAX:
                    return True
            _fail_windows[source] = (now, 1)
            return True
        start, count = window
        _fail_windows[source] = (start, count + 1)
        return count + 1 <= _FAIL_LIMIT_PER_MINUTE


def require_wa_broker_key(request: Request) -> None:
    """Reject unless X-API-Key equals the dedicated broker key exactly.

    Constant-time comparison; 401 when the key is missing, wrong, or not
    configured server-side (unconfigured = the surface is OFF, not open).
    Auth runs FIRST; each request is then charged to the bucket matching
    its outcome — see the module comment for why the split is load-bearing.
    """
    configured = getattr(settings, "wa_broker_key", None)
    provided = request.headers.get("X-API-Key")
    # Encoded-bytes comparison (Codex re-verdict r3): compare_digest on two
    # str objects REFUSES non-ASCII with a TypeError, and Starlette hands
    # headers through as latin-1 text, so a raw `X-API-Key: \xff` from an
    # UNAUTHENTICATED client raised here — before _fail_bucket_take — turning
    # the auth gate into an unthrottled 500 amplifier. Bytes accept anything.
    if (
        configured
        and provided
        and hmac.compare_digest(provided.encode("utf-8"), configured.encode("utf-8"))
    ):
        if not _auth_bucket_take():
            raise HTTPException(status_code=429, detail="wa-broker rate limit")
        return
    source = request.client.host if request.client else "unknown"
    if not _fail_bucket_take(source):
        raise HTTPException(status_code=429, detail="wa-broker rate limit")
    raise HTTPException(status_code=401, detail="wa-broker key required")


# PostgreSQL INT ceiling: values above it pass an unbounded Pydantic field
# and then 500 in asyncpg instead of 422 here (S2 cross-family review,
# finding 10).
_PG_INT_MAX = 2**31 - 1


class ClaimRequest(BaseModel):
    # Broker-reported queue state — the /claim poll IS the liveness heartbeat
    # (spec 2.1), including polls that find no job.
    in_flight: int = Field(0, ge=0, le=16)
    last_exec_ms: int | None = Field(None, ge=0, le=_PG_INT_MAX)


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
    exec_ms: int | None = Field(None, ge=0, le=_PG_INT_MAX)

    @field_validator("result_text")
    @classmethod
    def _result_text_not_blank(cls, v: str | None) -> str | None:
        # Empty/whitespace output is a failure wearing the success shape
        # (Codex re-verdict r6, finding 1): it would pass the XOR, mint a
        # completed_pending_consume with nothing to send, and fold
        # success=True — a half_open canary returning nothing would close
        # the breaker. The vocabulary names it: error_class='empty_output'.
        # complete_job enforces the same rule for direct callers.
        if v is not None and not v.strip():
            raise ValueError(
                "empty result_text is not a completion — report "
                "error_class='empty_output' instead"
            )
        return v

    @field_validator("error_class")
    @classmethod
    def _error_class_in_vocabulary(cls, v: str | None) -> str | None:
        # error_class is RETAINED on terminal rows, outside the payload-NULL
        # guarantee — free text here would let a buggy broker persist
        # exception messages or identifiers indefinitely (S2 cross-family
        # review, finding 7). Closed vocabulary, one SSOT in the service.
        if v is not None and v not in wa_broker.ALLOWED_ERROR_CLASSES:
            raise ValueError(
                "error_class must be one of: " + ", ".join(sorted(wa_broker.ALLOWED_ERROR_CLASSES))
            )
        return v


class CompleteResponse(BaseModel):
    status: str


# These routes are exempt from HybridAuthMiddleware (PUBLIC_ENDPOINTS), so
# require_wa_broker_key is the ONLY thing in front of them — and a Pydantic
# body parameter would silently move it: FastAPI buffers and JSON-parses the
# COMPLETE body before resolving dependencies, so an unauthenticated caller
# could force arbitrary allocation/parsing pre-auth, and malformed JSON
# answered 422 without ever charging the failed-auth bucket (Codex
# re-verdict r7, proven by probe: dependency_called=False on a bad body).
# Cure: no body parameter in the signature (dependencies then resolve
# without touching the body), and the handler reads the body itself AFTER
# auth, streaming under a hard cap.
_MAX_BODY_BYTES = 128 * 1024  # complete's legit max ≈ 64KiB text + overhead


async def _read_bounded_body(request: Request, model: type[_ModelT]) -> _ModelT:
    body = bytearray()
    async for chunk in request.stream():
        # Cap check BEFORE buffering (Codex re-verdict r8): ASGI does not
        # bound chunk size — cached-body middleware or a transport may yield
        # the ENTIRE request as one chunk, and extending first would copy a
        # multi-hundred-MB body into this buffer before the 413 ever fired.
        if len(body) + len(chunk) > _MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="body too large")
        body.extend(chunk)
    try:
        return model.model_validate_json(bytes(body) or b"{}")
    except ValidationError as exc:
        # include_input=False: complete bodies carry client-conversation
        # text — never echo it back in an error payload.
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_url=False, include_context=False, include_input=False),
        ) from exc


@router.post(
    "/claim",
    response_model=ClaimResponse,
    dependencies=[Depends(require_wa_broker_key)],
)
async def claim(
    request: Request,
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> ClaimResponse:
    body = await _read_bounded_body(request, ClaimRequest)
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
    request: Request,
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> CompleteResponse:
    body = await _read_bounded_body(request, CompleteRequest)
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
