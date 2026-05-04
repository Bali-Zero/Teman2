"""mata-garuda data access layer (backend-rag side).

Sprint 3 W2 — public Python API for the asset_provenance schema. Lives in
backend-rag because:

* mata-garuda's local CLAUDE.md mandates minimal runtime deps
  (only ``pydantic>=2``); ``asyncpg`` is forbidden there.
* The cell adapter is consumed BY other backend-rag services
  (welcome_practice_service, intel-scraper consumers, oracle citation
  guard) — keeping it inside backend-rag avoids cross-app imports.
* The L4.5 cell.yaml at apps/mata-garuda/cell.yaml still declares the
  cell as Pro-only; ONLY the data-access shim lives here.

The adapter exposes:

* :func:`tag_provenance` — INSERT or UPSERT a provenance row.
* :func:`get_provenance` — fetch the current provenance for an asset.
* :func:`list_expired_assets` — enumerate rows whose ``valid_until``
  has elapsed (used by the daily ``invalidation_sweeper`` cron on Pro).
* :func:`confidence_tier` — collapse the 30-cell admiralty matrix to
  a 4-tier human-readable label.

Reference: docs/sprint3/mata-garuda-cell-design.md +
docs/sprint3/review-synthesis-2026-05-04.md (B3 finding 2026-05-04).
"""
from __future__ import annotations

from .cell_adapter import (
    ASSET_KIND_AUTHORITATIVE,
    CREDIBILITY_VALUES,
    INVALIDATION_MODES,
    RELIABILITY_VALUES,
    TLP_VALUES,
    ProvenanceRow,
    confidence_tier,
    get_provenance,
    list_expired_assets,
    tag_provenance,
)

__all__ = [
    "ASSET_KIND_AUTHORITATIVE",
    "CREDIBILITY_VALUES",
    "INVALIDATION_MODES",
    "RELIABILITY_VALUES",
    "TLP_VALUES",
    "ProvenanceRow",
    "confidence_tier",
    "get_provenance",
    "list_expired_assets",
    "tag_provenance",
]
