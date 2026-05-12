"""Intel Lake API — Wave 1 (2026-05-12).

Endpoint:
    POST /api/intel/lake/observations        — single observation
    POST /api/intel/lake/observations:batch  — batched (used by outbox drain)

Auth: header `X-Producer-Token` matched against env INTEL_LAKE_PRODUCER_TOKEN.

Design: research/symbiosis/2026-05-12-intel-lake-design.md
Plan:   research/symbiosis/2026-05-12-intel-lake-wave1-plan.md
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.services.intel.intel_lake_service import (
    IntelLakeError,
    IntelLakeService,
    ObservationInput,
    PayloadTooLargeError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intel/lake", tags=["intel-lake"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class ObservationPayload(BaseModel):
    producer_name: str = Field(..., min_length=1, max_length=80)
    canonical_url: str = Field(..., min_length=8, max_length=2048)
    content_hash: str = Field(..., min_length=8, max_length=64)
    title: str = Field(..., min_length=1, max_length=2000)
    summary: str | None = Field(None, max_length=8000)
    source_domain: str = Field(..., min_length=3, max_length=255)
    language: str | None = Field(None, max_length=8)
    jurisdiction: str | None = Field(None, max_length=64)
    topic_tags: list[str] | None = None
    published_at: str | None = None
    score: float | None = Field(None, ge=0.0, le=1.0)
    raw_payload: dict[str, Any] | None = None

    @field_validator("topic_tags")
    @classmethod
    def _tags_capped(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        if len(v) > 50:
            raise ValueError("topic_tags max 50")
        return [t[:64] for t in v]


class ObservationResponse(BaseModel):
    item_id: str
    is_new_item: bool
    is_content_drift: bool
    observation_id: int


class BatchObservationPayload(BaseModel):
    observations: list[ObservationPayload] = Field(..., min_length=1, max_length=200)


class BatchObservationResponse(BaseModel):
    accepted: int
    rejected: int
    results: list[ObservationResponse | dict[str, Any]]


# ─── Auth dependency ────────────────────────────────────────────────────────


def _verify_producer_token(
    x_producer_token: str | None = Header(default=None, alias="X-Producer-Token"),
) -> str:
    expected = os.environ.get("INTEL_LAKE_PRODUCER_TOKEN", "").strip()
    if not expected:
        # If server has no token configured, refuse all (fail-closed)
        logger.error("INTEL_LAKE_PRODUCER_TOKEN env not set on server — rejecting all")
        raise HTTPException(status_code=500, detail="server token not configured")
    if not x_producer_token or x_producer_token.strip() != expected:
        raise HTTPException(status_code=401, detail="invalid producer token")
    return x_producer_token


# ─── Service dependency ─────────────────────────────────────────────────────


async def _get_service(request: Request) -> IntelLakeService:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="db pool not initialized")
    return IntelLakeService(pool)


# ─── Routes ─────────────────────────────────────────────────────────────────


@router.post("/observations", response_model=ObservationResponse)
async def post_observation(
    payload: ObservationPayload,
    request: Request,
    _token: str = Depends(_verify_producer_token),
    service: IntelLakeService = Depends(_get_service),
) -> ObservationResponse:
    client_ip = request.client.host if request.client else None
    payload_size = len(payload.model_dump_json().encode())

    try:
        result = await service.record_observation(
            ObservationInput(
                producer_name=payload.producer_name,
                canonical_url=payload.canonical_url,
                content_hash=payload.content_hash,
                title=payload.title,
                summary=payload.summary,
                source_domain=payload.source_domain,
                language=payload.language,
                jurisdiction=payload.jurisdiction,
                topic_tags=payload.topic_tags,
                published_at=payload.published_at,
                score=payload.score,
                raw_payload=payload.raw_payload,
            )
        )
    except PayloadTooLargeError as e:
        await service.log_audit(
            payload.producer_name, client_ip, request.url.path, 413, payload_size, str(e)
        )
        raise HTTPException(status_code=413, detail=str(e))
    except IntelLakeError as e:
        await service.log_audit(
            payload.producer_name, client_ip, request.url.path, 400, payload_size, str(e)
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # pragma: no cover — defensive only
        logger.exception("unexpected error in post_observation")
        await service.log_audit(
            payload.producer_name, client_ip, request.url.path, 500, payload_size, str(e)
        )
        raise HTTPException(status_code=500, detail="internal error")

    await service.log_audit(payload.producer_name, client_ip, request.url.path, 200, payload_size)
    return ObservationResponse(
        item_id=result.item_id,
        is_new_item=result.is_new_item,
        is_content_drift=result.is_content_drift,
        observation_id=result.observation_id,
    )


@router.post("/observations-batch", response_model=BatchObservationResponse)
async def post_observations_batch(
    payload: BatchObservationPayload,
    request: Request,
    _token: str = Depends(_verify_producer_token),
    service: IntelLakeService = Depends(_get_service),
) -> BatchObservationResponse:
    """Used by producer outbox drain workers. Best-effort: partial success allowed.

    Each observation processed independently; failures returned per-row, not
    failing the whole batch.
    """
    client_ip = request.client.host if request.client else None
    results: list[ObservationResponse | dict[str, Any]] = []
    accepted = 0
    rejected = 0

    for obs_payload in payload.observations:
        size = len(obs_payload.model_dump_json().encode())
        try:
            r = await service.record_observation(
                ObservationInput(
                    producer_name=obs_payload.producer_name,
                    canonical_url=obs_payload.canonical_url,
                    content_hash=obs_payload.content_hash,
                    title=obs_payload.title,
                    summary=obs_payload.summary,
                    source_domain=obs_payload.source_domain,
                    language=obs_payload.language,
                    jurisdiction=obs_payload.jurisdiction,
                    topic_tags=obs_payload.topic_tags,
                    published_at=obs_payload.published_at,
                    score=obs_payload.score,
                    raw_payload=obs_payload.raw_payload,
                )
            )
            results.append(
                ObservationResponse(
                    item_id=r.item_id,
                    is_new_item=r.is_new_item,
                    is_content_drift=r.is_content_drift,
                    observation_id=r.observation_id,
                )
            )
            accepted += 1
            await service.log_audit(
                obs_payload.producer_name, client_ip, request.url.path, 200, size
            )
        except PayloadTooLargeError as e:
            results.append({"error": "payload_too_large", "detail": str(e)})
            rejected += 1
            await service.log_audit(
                obs_payload.producer_name, client_ip, request.url.path, 413, size, str(e)
            )
        except Exception as e:
            results.append({"error": "internal", "detail": str(e)[:200]})
            rejected += 1
            await service.log_audit(
                obs_payload.producer_name, client_ip, request.url.path, 500, size, str(e)
            )

    return BatchObservationResponse(accepted=accepted, rejected=rejected, results=results)
