"""
NUZANTARA PRIME - Feedback Module Data Layer
SQLModel models for conversation ratings and review queue
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, Text
from sqlmodel import Field, Relationship, SQLModel


class ConversationRating(SQLModel, table=True):
    """
    Conversation Rating model
    Maps to existing 'conversation_ratings' table created by migration 025
    """

    __tablename__ = "conversation_ratings"
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(primary_key=True, default=None)
    session_id: UUID = Field(nullable=False, index=True)
    user_id: UUID | None = Field(default=None, foreign_key="user_profiles.id", nullable=True)

    # Rating (1-5 stars)
    rating: int = Field(nullable=False, ge=1, le=5)

    # Feedback qualitative
    feedback_type: str | None = Field(
        default=None, max_length=20
    )  # 'positive', 'negative', 'issue'
    feedback_text: str | None = Field(default=None, sa_column=Column(Text))

    # Metadata
    turn_count: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    # Relationships
    review_queue_entries: list["ReviewQueue"] = Relationship(back_populates="source_feedback")


class ReviewQueue(SQLModel, table=True):
    """
    Review Queue model
    Maps to 'review_queue' table created by migration 026
    Stores feedback items that need manual review (low ratings or corrections)
    """

    __tablename__ = "review_queue"
    __table_args__ = {"extend_existing": True}

    id: UUID = Field(primary_key=True, default=None)
    source_feedback_id: UUID = Field(
        foreign_key="conversation_ratings.id", nullable=False, index=True
    )

    # Status tracking
    status: str = Field(
        default="pending",
        nullable=False,
        max_length=20,
        description="Status: 'pending', 'resolved', or 'ignored'",
    )

    # Priority (optional, for manual prioritization)
    priority: str | None = Field(
        default=None, max_length=20, description="Priority: 'low', 'medium', 'high', 'urgent'"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    resolved_at: datetime | None = Field(default=None)

    # Optional resolution notes
    resolution_notes: str | None = Field(default=None, sa_column=Column(Text))

    # Relationships
    source_feedback: ConversationRating = Relationship(back_populates="review_queue_entries")
