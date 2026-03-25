"""NLM HTTP Bridge — lightweight FastAPI service wrapping notebooklm-tools.

Runs on Pro Mac (port 18790). Allows Fly.io backend to query NotebookLM
notebooks over HTTP with HMAC authentication.

Usage:
    uvicorn main:app --host 0.0.0.0 --port 18790
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from hmac_verify import verify_signature

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nlm-bridge")

# ---------------------------------------------------------------------------
# NLM backend — library import with subprocess fallback
# ---------------------------------------------------------------------------
try:
    import notebooklm_tools  # type: ignore[import-untyped]

    _HAS_NLM_LIB = True
    logger.info("notebooklm_tools library available")
except ImportError:
    _HAS_NLM_LIB = False
    logger.info("notebooklm_tools not installed — using CLI subprocess fallback")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
_start_time: float = 0.0
_request_count: int = 0

# Rate-limit: 10 req/min, in-memory
_rate_window: dict[str, list[float]] = {}
_RATE_LIMIT = 10
_RATE_WINDOW_SECONDS = 60


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    global _start_time
    _start_time = time.monotonic()
    logger.info("NLM Bridge started on port 18790")
    yield
    logger.info("NLM Bridge shutting down")


app = FastAPI(title="NLM HTTP Bridge", version="1.0.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class NLMQueryRequest(BaseModel):
    notebook_id: str
    question: str
    timeout: int = Field(default=60, ge=1, le=120)


class NLMCitation(BaseModel):
    source: str = ""
    text: str = ""


class NLMQueryResponse(BaseModel):
    answer: str
    citations: list[dict[str, Any]]
    confidence: float
    processing_time: float


class HealthResponse(BaseModel):
    status: str
    uptime: float
    request_count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _check_rate_limit(client_ip: str) -> None:
    """Enforce 10 req/min per client IP."""
    now = time.time()
    timestamps = _rate_window.setdefault(client_ip, [])
    # Prune old entries
    cutoff = now - _RATE_WINDOW_SECONDS
    _rate_window[client_ip] = [t for t in timestamps if t > cutoff]
    if len(_rate_window[client_ip]) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded (10 req/min)")
    _rate_window[client_ip].append(now)


def _verify_hmac(body: bytes, signature: str | None) -> None:
    """Verify HMAC signature. Skip if NLM_BRIDGE_SECRET is unset (local dev)."""
    import os

    secret = os.getenv("NLM_BRIDGE_SECRET", "")
    if not secret:
        return  # Local testing — no verification
    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-Bridge-Signature header")
    if not verify_signature(body, signature, secret):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")


async def _query_via_library(
    notebook_id: str, question: str, timeout: int
) -> dict[str, Any]:
    """Query NLM using the Python library."""
    result = await asyncio.wait_for(
        asyncio.to_thread(
            notebooklm_tools.notebook_query,  # type: ignore[union-attr]
            notebook_id,
            question,
        ),
        timeout=timeout,
    )
    return result if isinstance(result, dict) else {"answer": str(result), "citations": []}


async def _query_via_subprocess(
    notebook_id: str, question: str, timeout: int
) -> dict[str, Any]:
    """Query NLM using the CLI as a subprocess fallback."""
    nlm_bin = os.getenv("NLM_BIN", os.path.expanduser("~/.local/bin/nlm"))
    cmd = [
        nlm_bin, "notebook", "query", notebook_id, question,
        "--timeout", str(timeout),
    ]
    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=timeout + 5,  # Extra buffer for process startup
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"NLM query timed out after {timeout}s")

    if proc.returncode != 0:
        error_msg = stderr.decode().strip() if stderr else "Unknown NLM error"
        logger.error("NLM CLI failed (rc=%d): %s", proc.returncode, error_msg)
        raise HTTPException(status_code=502, detail=f"NLM query failed: {error_msg}")

    try:
        parsed = json.loads(stdout.decode())
        # NLM CLI wraps response in {"value": {...}} — unwrap if present
        if isinstance(parsed, dict) and "value" in parsed:
            parsed = parsed["value"]
        return parsed
    except json.JSONDecodeError:
        # CLI returned non-JSON — wrap as plain answer
        return {"answer": stdout.decode().strip(), "citations": []}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/nlm/query", response_model=NLMQueryResponse)
async def nlm_query(
    request: Request,
    x_bridge_signature: str | None = Header(default=None),
) -> NLMQueryResponse:
    """Query a NotebookLM notebook with HMAC-authenticated request."""
    global _request_count

    body = await request.body()
    _verify_hmac(body, x_bridge_signature)

    # Parse body after HMAC check (verify raw bytes, not parsed)
    payload = NLMQueryRequest.model_validate_json(body)

    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    _request_count += 1
    logger.info(
        "NLM query #%d: notebook=%s question=%s timeout=%ds",
        _request_count,
        payload.notebook_id,
        payload.question[:80],
        payload.timeout,
    )

    t0 = time.monotonic()
    try:
        if _HAS_NLM_LIB:
            raw = await _query_via_library(payload.notebook_id, payload.question, payload.timeout)
        else:
            raw = await _query_via_subprocess(payload.notebook_id, payload.question, payload.timeout)
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"NLM query timed out after {payload.timeout}s")
    except Exception as exc:
        logger.error("NLM query error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"NLM query failed: {exc}")

    processing_time = round(time.monotonic() - t0, 2)

    answer = raw.get("answer", "")
    citations = raw.get("citations", [])
    confidence = raw.get("confidence", 0.5 if answer else 0.0)

    logger.info(
        "NLM query complete: %.2fs, %d citations, confidence=%.2f",
        processing_time,
        len(citations),
        confidence,
    )

    return NLMQueryResponse(
        answer=answer,
        citations=citations,
        confidence=confidence,
        processing_time=processing_time,
    )


@app.get("/nlm/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check — no auth required."""
    uptime = round(time.monotonic() - _start_time, 1) if _start_time else 0.0
    status = "healthy" if _HAS_NLM_LIB else "degraded"
    return HealthResponse(
        status=status,
        uptime=uptime,
        request_count=_request_count,
    )
