"""
Mata Garuda — Bridge Envelope.

Standard envelope a 5 campi obbligatori per tutti i messaggi sui nuovi stream
(bridge:outbound, bridge:inbound, organism:metrics).

Stream esistenti (garuda:raw, nexus:gaps, garuda:enriched, garuda:alerts) NON
sono migrati subito — lo saranno gradualmente quando i consumer vengono
riscritti.

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §3
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


WITA = timezone(timedelta(hours=8))


def _now_wita() -> str:
    """Current ISO 8601 timestamp in WITA timezone."""
    return datetime.now(WITA).isoformat(timespec="seconds")


class Envelope(BaseModel):
    """Standard envelope per tutti gli stream nuovi.

    5 campi obbligatori, payload libero. Puro JSON, zero dipendenze esterne
    oltre pydantic. Compatibile con redis-cli XADD/XREADGROUP.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str = Field(..., description="dot notation: category.subtype")
    source: str = Field(..., description="organo produttore")
    timestamp: str = Field(default_factory=_now_wita)
    priority: int = Field(..., ge=1, le=5, description="1=urgente, 5=bassa")
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _validate_dot_notation(cls, v: str) -> str:
        if "." not in v:
            raise ValueError(f"type must use dot notation (got {v!r})")
        return v

    def to_redis_dict(self) -> dict[str, str]:
        """Flat dict ready for redis-cli XADD (all values stringified)."""
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "timestamp": self.timestamp,
            "priority": str(self.priority),
            "payload": json.dumps(self.payload, ensure_ascii=False),
        }

    @classmethod
    def from_redis_dict(cls, data: dict[str, str]) -> "Envelope":
        """Reconstruct an Envelope from XREADGROUP output."""
        return cls(
            id=data["id"],
            type=data["type"],
            source=data["source"],
            timestamp=data["timestamp"],
            priority=int(data["priority"]),
            payload=json.loads(data["payload"]) if data.get("payload") else {},
        )

    def matches_prefix(self, prefix: str) -> bool:
        """True if self.type equals prefix or starts with prefix at a dot-segment boundary.

        Matching is always at a segment boundary (dot or end-of-string) to avoid
        false positives across unrelated categories.

        Examples:
            "crm.client_created".matches_prefix("crm")          → True
            "crm.client.details".matches_prefix("crm.client")   → True
            "crm.clientele.foo".matches_prefix("crm.client")    → False
            "crm.client_created".matches_prefix("intel")        → False
        """
        return self.type == prefix or self.type.startswith(prefix + ".")
