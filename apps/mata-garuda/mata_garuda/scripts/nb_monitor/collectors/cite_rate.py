"""Placeholder collector for downstream_cite_rate.

Returns None until FASE 4 wires Oracle citation logging in
apps/backend-rag/backend/services/oracle/. When ready, this module will
read the citation log and compute the rate of Zantara responses citing
source URLs that map to the NB UUID.

Spec §3.3, §7.3. ADR-006.
"""
from __future__ import annotations

INSTRUMENTATION_STATUS = "pending_oracle_logging_post_fase4"


def compute_rate_for_uuid(uuid: str) -> float | None:
    """Always None pre-FASE-4. Returns the cite rate post-FASE-4."""
    return None
