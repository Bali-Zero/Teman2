"""Unified document-intake package (FASE 1B).

Public surface:
- enqueue(): idempotent blob registration + queue insert (ZERO CRM writes).
- WhatsApp / Drive / Zoho adapters: drain a source, call enqueue() per blob.
"""

from backend.services.intake.enqueue import (
    PIPELINE_VERSION,
    EnqueueResult,
    compute_blob_hash,
    compute_intake_key,
    enqueue,
)

__all__ = [
    "PIPELINE_VERSION",
    "EnqueueResult",
    "compute_blob_hash",
    "compute_intake_key",
    "enqueue",
]
