"""
NUZANTARA PRIME - CRM Module Data Layer
SQLModel models for CRM system (clients, practices, interactions)
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DECIMAL, JSON, Column, Text
from sqlmodel import Field, Relationship, SQLModel


class Client(SQLModel, table=True):
    """
    Client model - Anagrafica Clienti
    Maps to existing 'clients' table created by migration 007
    """

    __tablename__ = "clients"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    uuid: str | None = Field(default=None, unique=True, index=True)

    # Basic Info
    full_name: str = Field(max_length=255, nullable=False)
    email: str | None = Field(default=None, max_length=255, index=True)
    phone: str | None = Field(default=None, max_length=50, index=True)
    whatsapp: str | None = Field(default=None, max_length=50)
    nationality: str | None = Field(default=None, max_length=100)
    passport_number: str | None = Field(default=None, max_length=100)

    # Status
    status: str = Field(default="active", max_length=50)  # 'active', 'inactive', 'prospect'
    client_type: str = Field(default="individual", max_length=50)  # 'individual', 'company'

    # Assignment
    assigned_to: str | None = Field(default=None, max_length=255, index=True)
    first_contact_date: datetime | None = Field(default=None)
    last_interaction_date: datetime | None = Field(default=None)

    # Additional Data
    address: str | None = Field(default=None, sa_column=Column(Text))
    notes: str | None = Field(default=None, sa_column=Column(Text))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    custom_fields: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = Field(default=None, max_length=255)

    # Relationships
    practices: list["Practice"] = Relationship(back_populates="client")
    interactions: list["Interaction"] = Relationship(back_populates="client")


class PracticeType(SQLModel, table=True):
    """
    Practice Type model - Tipi di Pratiche
    Maps to existing 'practice_types' table
    """

    __tablename__ = "practice_types"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(unique=True, max_length=50, nullable=False, index=True)
    name: str = Field(max_length=255, nullable=False)
    category: str | None = Field(default=None, max_length=100, index=True)
    description: str | None = Field(default=None, sa_column=Column(Text))
    base_price: float | None = Field(
        default=None, sa_column=Column("base_price", type_=DECIMAL(12, 2))
    )
    currency: str = Field(default="IDR", max_length=10)
    duration_days: int | None = Field(default=None)
    required_documents: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    practices: list["Practice"] = Relationship(back_populates="practice_type")


class Practice(SQLModel, table=True):
    """
    Practice model - Pratiche in Corso/Completate
    Maps to existing 'practices' table
    """

    __tablename__ = "practices"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)
    uuid: str | None = Field(default=None, unique=True, index=True)

    # Relations
    client_id: int = Field(foreign_key="clients.id", nullable=False, index=True)
    practice_type_id: int = Field(foreign_key="practice_types.id", nullable=False, index=True)

    # Status Tracking
    status: str = Field(
        default="inquiry",
        max_length=50,
        index=True,
    )  # 'inquiry', 'quotation_sent', 'payment_pending', 'in_progress', etc.
    priority: str = Field(default="normal", max_length=20)  # 'low', 'normal', 'high', 'urgent'

    # Dates
    inquiry_date: datetime = Field(default_factory=datetime.utcnow)
    start_date: datetime | None = Field(default=None)
    completion_date: datetime | None = Field(default=None)
    expiry_date: datetime | None = Field(default=None, index=True)
    next_renewal_date: datetime | None = Field(default=None, index=True)

    # Financial
    quoted_price: float | None = Field(
        default=None, sa_column=Column("quoted_price", type_=DECIMAL(12, 2))
    )
    actual_price: float | None = Field(
        default=None, sa_column=Column("actual_price", type_=DECIMAL(12, 2))
    )
    currency: str = Field(default="IDR", max_length=10)
    payment_status: str = Field(default="unpaid", max_length=50)
    paid_amount: float = Field(default=0.0, sa_column=Column("paid_amount", type_=DECIMAL(12, 2)))

    # Assignment
    assigned_to: str | None = Field(default=None, max_length=255, index=True)

    # Documents
    documents: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    missing_documents: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Notes & Custom
    notes: str | None = Field(default=None, sa_column=Column(Text))
    internal_notes: str | None = Field(default=None, sa_column=Column(Text))
    custom_fields: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = Field(default=None, max_length=255)

    # Relationships
    client: Client | None = Relationship(back_populates="practices")
    practice_type: PracticeType | None = Relationship(back_populates="practices")
    interactions: list["Interaction"] = Relationship(back_populates="practice")


class Interaction(SQLModel, table=True):
    """
    Interaction model - Team-Client Communications
    Maps to existing 'interactions' table
    """

    __tablename__ = "interactions"
    __table_args__ = {"extend_existing": True}

    id: int | None = Field(default=None, primary_key=True)

    # Relations
    client_id: int | None = Field(default=None, foreign_key="clients.id", index=True)
    practice_id: int | None = Field(default=None, foreign_key="practices.id", index=True)
    conversation_id: int | None = Field(default=None, foreign_key="conversations.id", index=True)

    # Interaction Details
    interaction_type: str = Field(
        max_length=50, nullable=False
    )  # 'chat', 'email', 'whatsapp', etc.
    channel: str | None = Field(default=None, max_length=50)  # 'web_chat', 'gmail', etc.

    # Content
    subject: str | None = Field(default=None, max_length=500)
    summary: str | None = Field(default=None, sa_column=Column(Text))
    full_content: str | None = Field(default=None, sa_column=Column(Text))
    sentiment: str | None = Field(
        default=None, max_length=20
    )  # 'positive', 'neutral', 'negative', 'urgent'

    # Participants
    team_member: str | None = Field(default=None, max_length=255, index=True)
    direction: str = Field(default="inbound", max_length=20)  # 'inbound', 'outbound'

    # AI Extraction
    extracted_entities: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    action_items: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))

    # Metadata
    interaction_date: datetime = Field(default_factory=datetime.utcnow)
    duration_minutes: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    client: Client | None = Relationship(back_populates="interactions")
    practice: Practice | None = Relationship(back_populates="interactions")
