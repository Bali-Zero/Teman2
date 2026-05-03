"""
Portal Notification Preferences.

GET/PUT for the authenticated client's preferred channel mix (email,
WhatsApp) and WA phone number. Backed by the `notification_prefs` table
created in migration 110.

The cron `portal_deadline_watchdog.py` (Task 7) reads this table to decide
who gets WA reminders.
"""

from __future__ import annotations

import re
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/notifications/prefs", tags=["portal-notifications"])


# E.164 without the leading '+' (up to 15 digits, first digit 1-9).
_E164_RE = re.compile(r"^[1-9]\d{6,14}$")


class NotificationPrefsIn(BaseModel):
    email_enabled: bool = Field(default=True)
    wa_enabled: bool = Field(default=False)
    wa_phone: str | None = Field(default=None)

    @field_validator("wa_phone")
    @classmethod
    def _validate_phone(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not _E164_RE.match(v):
            raise ValueError("wa_phone must be E.164 digits only (no +)")
        return v


class NotificationPrefsOut(BaseModel):
    email_enabled: bool
    wa_enabled: bool
    wa_phone: str | None


def _default_prefs() -> dict[str, Any]:
    return {"email_enabled": True, "wa_enabled": False, "wa_phone": None}


@router.get("", response_model=NotificationPrefsOut)
async def get_prefs(
    client: dict = Depends(get_current_client),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    user_id = client.get("user_id")
    if not user_id:
        return _default_prefs()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                SELECT email_enabled, wa_enabled, wa_phone
                FROM notification_prefs
                WHERE user_id = $1
                """,
                user_id,
            )
        except Exception as e:
            logger.warning(f"prefs fetch failed: {e}")
            return _default_prefs()
    if not row:
        return _default_prefs()
    return {
        "email_enabled": row["email_enabled"],
        "wa_enabled": row["wa_enabled"],
        "wa_phone": row["wa_phone"],
    }


@router.put("", response_model=NotificationPrefsOut)
async def put_prefs(
    payload: NotificationPrefsIn,
    client: dict = Depends(get_current_client),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    user_id = client.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="missing user_id")

    if payload.wa_enabled and not payload.wa_phone:
        raise HTTPException(
            status_code=422,
            detail="wa_phone is required when wa_enabled is true",
        )

    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO notification_prefs
                    (user_id, email_enabled, wa_enabled, wa_phone, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    email_enabled = EXCLUDED.email_enabled,
                    wa_enabled    = EXCLUDED.wa_enabled,
                    wa_phone      = EXCLUDED.wa_phone,
                    updated_at    = NOW()
                """,
                user_id,
                payload.email_enabled,
                payload.wa_enabled,
                payload.wa_phone,
            )
        except Exception as e:
            logger.error(f"prefs upsert failed: {e}")
            raise HTTPException(
                status_code=503,
                detail="notification_prefs unavailable — run migration 110",
            ) from e

    return {
        "email_enabled": payload.email_enabled,
        "wa_enabled": payload.wa_enabled,
        "wa_phone": payload.wa_phone,
    }
