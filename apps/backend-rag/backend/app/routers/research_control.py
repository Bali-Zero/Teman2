"""SOTA research control router — Telegram owner kill-switches for Loop 90gg.

Four POST endpoints under /api/research/control/* that flip `system_settings`
rows used by WR2 cron jobs (m13_collect, m13_weekly, m13_monthly) and by
the publisher. Keys persisted:

  - sota_research_enabled              (pause/resume)
  - sota_retrain_enabled               (off/on)
  - sota_playbook_frozen               (freeze/unfreeze)
  - wr2_publisher_enabled_<channel>    (off/on per channel)

Auth: X-API-Key == NUZANTARA_API_KEY env. Same shape as admin_practice_auto_create.
Caller: Telegram bot (owner only) routes /research, /publisher, /retrain,
/playbook slash commands to these endpoints.
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research/control", tags=["sota", "kill-switch"])


_UPSERT_SQL = """
INSERT INTO system_settings (key, value, updated_at)
VALUES ($1, $2, NOW())
ON CONFLICT (key) DO UPDATE
  SET value = EXCLUDED.value,
      updated_at = EXCLUDED.updated_at
"""


def _check_api_key(x_api_key: str | None) -> None:
    expected = os.environ.get("NUZANTARA_API_KEY", "")
    if not x_api_key or not expected or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="invalid api key")


async def _persist(request: Request, key: str, value: str) -> dict:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="db_pool unavailable")
    async with pool.acquire() as conn:
        await conn.execute(_UPSERT_SQL, key, value)
    logger.info("sota.kill_switch set %s=%s", key, value)
    return {"ok": True, "key": key, "value": value}


class _ResearchBody(BaseModel):
    action: Literal["pause", "resume"] = Field(...)


class _RetrainBody(BaseModel):
    action: Literal["off", "on"] = Field(...)


class _PlaybookBody(BaseModel):
    action: Literal["freeze", "unfreeze"] = Field(...)


class _PublisherBody(BaseModel):
    channel: str = Field(..., min_length=1, max_length=40)
    action: Literal["on", "off"] = Field(...)


@router.post("/research")
async def research_switch(
    request: Request,
    body: _ResearchBody,
    x_api_key: str | None = Header(default=None, alias="x-api-key", convert_underscores=False),
):
    _check_api_key(x_api_key)
    value = "true" if body.action == "resume" else "false"
    return await _persist(request, "sota_research_enabled", value)


@router.post("/retrain")
async def retrain_switch(
    request: Request,
    body: _RetrainBody,
    x_api_key: str | None = Header(default=None, alias="x-api-key", convert_underscores=False),
):
    _check_api_key(x_api_key)
    value = "true" if body.action == "on" else "false"
    return await _persist(request, "sota_retrain_enabled", value)


@router.post("/playbook")
async def playbook_switch(
    request: Request,
    body: _PlaybookBody,
    x_api_key: str | None = Header(default=None, alias="x-api-key", convert_underscores=False),
):
    _check_api_key(x_api_key)
    value = "true" if body.action == "freeze" else "false"
    return await _persist(request, "sota_playbook_frozen", value)


@router.post("/publisher")
async def publisher_switch(
    request: Request,
    body: _PublisherBody,
    x_api_key: str | None = Header(default=None, alias="x-api-key", convert_underscores=False),
):
    _check_api_key(x_api_key)
    safe_channel = body.channel.strip().lower().replace(" ", "_")
    if not safe_channel.isidentifier():
        raise HTTPException(status_code=400, detail="invalid channel name")
    key = f"wr2_publisher_enabled_{safe_channel}"
    value = "true" if body.action == "on" else "false"
    return await _persist(request, key, value)
