"""Pydantic schema for nlm_shadow_hybrid Qdrant collection (Sprint 2).

The Shadow Graphing pattern projects claims extracted offline by NotebookLM
into a Qdrant collection that the runtime RAG can query in sub-second time
without ever waking the NLM CLI. Each row is one atomic claim, validated by
DeepSeek before write, with full provenance back to the NB and the run.

Why a separate model from HierarchicalChunk:
  - HierarchicalChunk is rigid (parent_id chains, level integer, doc-level
    metadata) and is consumed by `legal/hierarchical_indexer.py` retrieval
    paths that would Pydantic-fail on extra/missing fields.
  - Shadow chunks are not legal documents — they are derived statements with
    different lifecycle (24h-72h TTL, not permanent), different retrieval
    surface (always grounded in nb_id), and a deepseek-validated flag the
    other collections don't carry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class NLMShadowChunk(BaseModel):
    """A single atomic claim extracted from a NotebookLM notebook.

    Stored in the ``nlm_shadow_hybrid`` Qdrant collection. Payload is FLAT
    per the Nuzantara golden rule (no nested dicts in Qdrant payloads).
    """

    chunk_id: str = Field(..., description="Stable id, e.g. nlm_shadow_NB-3_20260425_001")
    claim_text: str = Field(..., min_length=10, description="The atomic claim itself")

    # Provenance (all flat strings/ints to play nice with Qdrant filters)
    nb_id: str = Field(..., description="Source notebook UUID")
    nb_label: str = Field(..., description="Domain label: immigration|company|tax|...")
    nlm_source_id: Optional[str] = Field(
        default=None, description="Originating source within the NB, when known"
    )
    extraction_run_id: str = Field(..., description="UUID of the extractor cron run")
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    # DeepSeek validation outcome
    deepseek_validated: bool = Field(
        default=False, description="True iff DeepSeek confirmed the claim is well-formed"
    )
    deepseek_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence reported by DeepSeek validator"
    )
    deepseek_notes: Optional[str] = Field(
        default=None, description="Short DeepSeek note (rejection reason, caveat)"
    )

    # Lifecycle
    source: str = Field(default="nlm_shadow", description="Always 'nlm_shadow' for this collection")
    ttl_hours: int = Field(default=72, ge=1, description="Soft TTL — runtime should ignore beyond this")

    @field_validator("claim_text")
    @classmethod
    def _strip_claim(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("claim_text must not be blank after strip")
        return cleaned

    def to_qdrant_payload(self) -> dict:
        """Render flat payload for Qdrant upsert.

        Datetimes are converted to ISO strings (Qdrant payload type-safe).
        """
        return {
            "chunk_id": self.chunk_id,
            "claim_text": self.claim_text,
            "nb_id": self.nb_id,
            "nb_label": self.nb_label,
            "nlm_source_id": self.nlm_source_id or "",
            "extraction_run_id": self.extraction_run_id,
            "extracted_at": self.extracted_at.isoformat(),
            "deepseek_validated": self.deepseek_validated,
            "deepseek_confidence": self.deepseek_confidence,
            "deepseek_notes": self.deepseek_notes or "",
            "source": self.source,
            "ttl_hours": self.ttl_hours,
        }

    @classmethod
    def from_qdrant_payload(cls, payload: dict) -> "NLMShadowChunk":
        """Re-hydrate a chunk from a Qdrant payload."""
        # Datetime parsing — string back to datetime
        ext = payload.get("extracted_at")
        if isinstance(ext, str):
            try:
                payload = {**payload, "extracted_at": datetime.fromisoformat(ext)}
            except ValueError:
                payload = {**payload, "extracted_at": datetime.now(tz=timezone.utc)}
        # Treat empty strings as None for the optional fields
        for k in ("nlm_source_id", "deepseek_notes"):
            if payload.get(k) == "":
                payload[k] = None
        return cls(**payload)


__all__ = ["NLMShadowChunk"]
