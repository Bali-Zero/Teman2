"""
NUZANTARA PRIME - OpenClaw Message Logging
SQLModel for CRM interaction logs from OpenClaw webhook
"""

from datetime import datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class MessageLog(SQLModel, table=True):
    """
    OpenClaw Message Log model
    Stores CRM interaction logs received from OpenClaw webhook
    """

    __tablename__ = "openclaw_message_logs"

    # Primary key - message_id from OpenClaw
    message_id: str = Field(
        primary_key=True, max_length=255, description="Unique message ID from OpenClaw",
    )

    # Timestamp
    timestamp: datetime = Field(
        nullable=False, index=True, description="Message timestamp from OpenClaw",
    )

    # Channel and direction
    channel: str = Field(
        nullable=False, max_length=50, description="Communication channel (e.g., whatsapp, sms)",
    )
    direction: str = Field(
        nullable=False, max_length=20, description="Message direction (inbound/outbound)",
    )

    # Contact information
    from_number: str = Field(nullable=False, max_length=50, description="Sender phone number")
    to_number: str = Field(nullable=False, max_length=50, description="Recipient phone number")
    contact_name: str | None = Field(
        default=None, max_length=255, description="Contact name if available",
    )

    # Message content
    message_text: str | None = Field(
        default=None, sa_column=Column(Text), description="Message text content",
    )
    media_type: str | None = Field(
        default=None, max_length=50, description="Media type if present (image, video, etc.)",
    )

    # Metadata
    session_id: str | None = Field(
        default=None, max_length=255, index=True, description="Session ID from metadata",
    )
    reply_to: str | None = Field(
        default=None, max_length=255, description="Reply-to message ID from metadata",
    )

    # System timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, nullable=False, description="Record creation timestamp",
    )
