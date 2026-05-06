"""Placeholder collector for Qdrant local skill_derivation_count.

Returns None until FASE 1 ships `bali_zero_skills_local` Qdrant collection
on Pro. When ready, this module will query
`point.payload.source_cell` for matches against the NB UUID and return the count.

Spec §3.3, §7.3. ADR-006.
"""
from __future__ import annotations

INSTRUMENTATION_STATUS = "pending_qdrant_local_post_fase1"


def count_skills_for_uuid(uuid: str) -> int | None:
    """Always None pre-FASE-1. Returns the count post-FASE-1."""
    return None
