"""
NUZANTARA PRIME - Webhooks Router
Handles incoming webhooks from external services (OpenClaw, etc.)
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.app.models.openclaw_message import MessageLog
from backend.app.utils.openclaw_security import verify_openclaw_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class OpenClawMetadata(BaseModel):
    """Metadata from OpenClaw webhook payload"""

    session_id: str | None = None
    reply_to: str | None = None


class OpenClawWebhookPayload(BaseModel):
    """OpenClaw webhook payload schema"""

    message_id: str = Field(..., description="Unique message ID")
    timestamp: datetime = Field(..., description="Message timestamp")
    channel: str = Field(..., description="Communication channel")
    direction: str = Field(..., description="Message direction (inbound/outbound)")
    from_number: str = Field(..., alias="from", description="Sender phone number")
    to_number: str = Field(..., alias="to", description="Recipient phone number")
    contact_name: str | None = Field(None, description="Contact name if available")
    message_text: str | None = Field(None, description="Message text content")
    media_type: str | None = Field(None, description="Media type if present")
    metadata: OpenClawMetadata | None = Field(None, description="Additional metadata")

    class Config:
        populate_by_name = True


@router.post(
    "/openclaw/crm-logging",
    status_code=200,
    summary="OpenClaw CRM Logging Webhook",
    description="Receives message logs from OpenClaw service for CRM tracking",
)
async def openclaw_crm_logging(
    payload: OpenClawWebhookPayload,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_openclaw_signature),
) -> dict[str, Any]:
    """
    Receive and store CRM message logs from OpenClaw webhook.

    Security: Requires valid HMAC signature in X-OpenClaw-Signature header.

    Args:
        payload: OpenClaw webhook payload
        db: Database session
        _: Signature verification dependency

    Returns:
        Success confirmation with message_id
    """
    try:
        # Extract metadata fields
        session_id = None
        reply_to = None
        if payload.metadata:
            session_id = payload.metadata.session_id
            reply_to = payload.metadata.reply_to

        # Create MessageLog record
        message_log = MessageLog(
            message_id=payload.message_id,
            timestamp=payload.timestamp,
            channel=payload.channel,
            direction=payload.direction,
            from_number=payload.from_number,
            to_number=payload.to_number,
            contact_name=payload.contact_name,
            message_text=payload.message_text,
            media_type=payload.media_type,
            session_id=session_id,
            reply_to=reply_to,
        )

        # Save to database
        db.add(message_log)
        await db.commit()
        await db.refresh(message_log)

        return {
            "status": "success",
            "message": "Message log received and stored",
            "message_id": message_log.message_id,
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store message log: {str(e)}",
        ) from e
