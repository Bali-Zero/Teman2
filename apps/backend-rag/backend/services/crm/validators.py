"""
CRM Data Validators

Validazione robusta per dati CRM con sanitizzazione input.
"""

import logging
import re
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator

logger = logging.getLogger(__name__)


class ClientValidator(BaseModel):
    """Validatore per dati cliente."""

    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    whatsapp: str | None = Field(None, max_length=50)
    nationality: str | None = Field(None, max_length=100)
    passport_number: str | None = Field(None, max_length=100)

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Valida e pulisce il nome."""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        # Remove multiple spaces
        return re.sub(r"\s+", " ", v)

    @field_validator("phone", "whatsapp")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Valida formato telefono."""
        if not v:
            return None
        # Remove all non-digit except +
        cleaned = re.sub(r"[^\d+]", "", v)
        if len(cleaned) < 8:
            raise ValueError("Phone number too short")
        return cleaned

    @field_validator("passport_number")
    @classmethod
    def validate_passport(cls, v: str | None) -> str | None:
        """Valida formato passport."""
        if not v:
            return None
        # Alphanumeric only
        if not re.match(r"^[A-Z0-9]+$", v.upper()):
            raise ValueError("Invalid passport format")
        return v.upper()


class PracticeValidator(BaseModel):
    """Validatore per pratiche."""

    client_id: int = Field(..., gt=0)
    practice_type_id: int = Field(..., gt=0)
    status: str = Field(default="inquiry")
    priority: str = Field(default="normal")
    quoted_price: float | None = Field(None, ge=0)
    actual_price: float | None = Field(None, ge=0)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status."""
        allowed = {
            "inquiry",
            "waiting_documents",
            "sending_invoice",
            "on_process",
            "completed",
        }
        if v not in allowed:
            raise ValueError(f"Status must be one of: {allowed}")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        """Validate priority."""
        allowed = {"low", "normal", "high", "urgent"}
        if v not in allowed:
            raise ValueError(f"Priority must be one of: {allowed}")
        return v


class InteractionValidator(BaseModel):
    """Validatore per interazioni."""

    client_id: int | None = Field(None, gt=0)
    practice_id: int | None = Field(None, gt=0)
    interaction_type: str
    channel: str | None = None
    subject: str | None = Field(None, max_length=500)
    summary: str | None = None
    sentiment: str | None = Field(None, max_length=20)

    @field_validator("interaction_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate type."""
        allowed = {"chat", "email", "whatsapp", "call", "meeting", "note"}
        if v not in allowed:
            raise ValueError(f"Type must be one of: {allowed}")
        return v

    @field_validator("sentiment")
    @classmethod
    def validate_sentiment(cls, v: str | None) -> str | None:
        """Validate sentiment."""
        if not v:
            return None
        allowed = {"positive", "neutral", "negative", "urgent"}
        if v not in allowed:
            raise ValueError(f"Sentiment must be one of: {allowed}")
        return v


def sanitize_input(value: str | None, max_length: int = 255) -> str | None:
    """Sanitizza input stringa."""
    if not value:
        return None
    value = value.strip()
    if len(value) > max_length:
        value = value[:max_length]
    # Remove control characters
    return re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", value)


def validate_uuid(uuid: str) -> bool:
    """Valida formato UUID."""
    pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    return bool(re.match(pattern, uuid.lower()))


def normalize_phone_e164(phone: str) -> str | None:
    """
    Normalizza numero telefono a formato E.164.

    Args:
        phone: Numero telefono in qualsiasi formato

    Returns:
        Numero normalizzato o None se invalido
    """
    if not phone:
        return None

    # Remove all non-digit characters
    digits = re.sub(r"\D", "", phone)

    if len(digits) < 8:
        return None

    # Handle Indonesian numbers
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits

    return "+" + digits


def extract_entities_from_text(text: str) -> dict[str, Any]:
    """
    Estrae entità rilevanti da testo conversazione.

    Returns:
        Dict con email, phone, passport trovati
    """
    entities = {"emails": [], "phones": [], "passports": [], "dates": []}

    # Email pattern
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    entities["emails"] = re.findall(email_pattern, text)

    # Phone pattern (Indonesian focus)
    phone_pattern = (
        r"(?:\+62|62|0)[\s-]?8[\s-]?[0-9]{1}[\s-]?[0-9]{3}[\s-]?[0-9]{2}[\s-]?[0-9]{2,3}"
    )
    phones = re.findall(phone_pattern, text)
    entities["phones"] = [normalize_phone_e164(p) for p in phones if normalize_phone_e164(p)]

    # Passport pattern (generic alphanumeric)
    passport_pattern = r"\b[A-Z]{1,2}[0-9]{6,9}\b"
    entities["passports"] = re.findall(passport_pattern, text.upper())

    return entities
