"""mata-garuda-cell adapter — public Python API for asset_provenance.

Sprint 3 W2 deliverable. Reference:
  docs/sprint3/mata-garuda-cell-design.md
  docs/sprint3/review-synthesis-2026-05-04.md (B3 — relocated 2026-05-04)

Lives in ``apps/backend-rag/backend/services/mata_garuda/`` because (a) the
host backend-rag image already has ``asyncpg`` and the service-injection
pattern, and (b) the mata-garuda app's local CLAUDE.md forbids ``asyncpg``
as a runtime dep (minimal-stack rule: ``SOLO pydantic>=2``). Multi-LLM W2
review surfaced this constraint mismatch; the W1 design had not accounted
for it.

The cell-yaml declaration at ``apps/mata-garuda/cell.yaml`` still defines
the L4.5 cell as Pro-only; ONLY the SQL data-access shim lives here.

This module is the ONLY public entry point for other cells to interact with
Mata-Garuda's provenance schema. It provides three operations:

* :func:`tag_provenance` — INSERT or UPSERT a provenance row.
* :func:`get_provenance` — fetch the current provenance for an asset.
* :func:`list_expired_assets` — enumerate rows whose ``valid_until`` has
  elapsed (used by the daily ``invalidation_sweeper`` sub-organelle).

The schema lives in PostgreSQL (migrations 154 + 155). This adapter speaks
asyncpg directly and assumes a connection pool is provided by the caller.

Symbiosis Law 2 enforcement note:
  Although the DDL has ``tlp DEFAULT 'red'``, that is a *safe default*, NOT
  enforcement. Real OSINT-blindato enforcement happens here in the adapter:
  any caller running outside Pro (e.g. Fly.io ``api`` machine) cannot reach
  the Pro-local PostgreSQL anyway, so the adapter is the practical
  Symbiosis Law 2 boundary. The X1 finding from the multi-LLM review is
  honored — DDL claim downgraded to "safe default".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

import asyncpg

logger = logging.getLogger(__name__)

# 12 canonical asset_kind values, pinned to match the CHECK enum in mig 154.
# Adding a new value requires (a) ALTER TYPE migration AND (b) updating this
# tuple in the same PR. Out-of-range kinds are rejected at this layer before
# the DB ever sees them, giving callers a clearer error than the asyncpg
# CHECK constraint violation.
ASSET_KIND_AUTHORITATIVE: tuple[str, ...] = (
    "war_room_draft",
    "war_room_post",
    "intel_finding",
    "research_dossier",
    "cross_dossier_thesis",
    "weekly_strategic_brief",
    "ultra_move",
    "kg_entity",
    "kg_proposal",
    "crm_enrichment_lookup",
    "compliance_alert",
    "measurer_metric",
)

# MISP admiralty 2-axis allowed values. Cf. mig 154 CHECK constraints.
RELIABILITY_VALUES: frozenset[str] = frozenset({"A", "B", "C", "D", "E", "F"})
CREDIBILITY_VALUES: frozenset[int] = frozenset({1, 2, 3, 4, 5, 6})

# TLP allowed values. Cf. mig 154 CHECK constraint.
TLP_VALUES: frozenset[str] = frozenset({"white", "green", "amber", "red", "black"})

# Invalidation mode allowed values. Cf. mig 154 CHECK constraint.
INVALIDATION_MODES: frozenset[str] = frozenset({"auto", "manual", "never"})

# Self-tagging guard intentionally EMPTY for the current schema:
# none of the 12 canonical asset_kind values represent Mata-Garuda's
# own outputs (the cell tags assets produced by other cells —
# war_room_*, intel_finding, kg_*, etc.). The cell.yaml
# meta_awareness.does_not_observe: [self] declaration is the formal
# contract. Revisit (and populate this set) only if a future
# asset_kind represents Mata-Garuda-produced data.
# Multi-LLM W2 review M1: kept as `frozenset()` instead of deleting
# entirely — the guard branch in `_validate_inputs` references it,
# and an explicit empty set + `# pragma: no cover` is more readable
# than maintaining "removed the check, must re-instate" lore.
_SELF_REFERENCING_KINDS: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ProvenanceRow:
    """Snapshot of a single asset_provenance row (READ-ONLY)."""

    id: int
    asset_kind: str
    asset_id: str
    source: str
    reliability: str
    credibility: int
    owner: str
    valid_until: datetime | None
    invalidation_event_topic: str | None
    invalidation_mode: str
    invalidated_at: datetime | None
    invalidated_by: str | None
    tlp: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]


def _validate_inputs(
    *,
    asset_kind: str,
    reliability: str,
    credibility: int,
    invalidation_mode: str,
    tlp: str,
) -> None:
    """Defensive enum check — fail fast with clear message before DB roundtrip."""
    if asset_kind not in ASSET_KIND_AUTHORITATIVE:
        raise ValueError(
            f"asset_kind={asset_kind!r} not in canonical 12-value set; "
            f"adding new kinds requires an ALTER TYPE migration. "
            f"Allowed: {ASSET_KIND_AUTHORITATIVE!r}"
        )
    # _SELF_REFERENCING_KINDS is intentionally empty for the current 12-value
    # enum (no asset_kind represents Mata-Garuda's own output). The check
    # below is dormant; if a future asset_kind becomes self-referential,
    # populate the set above and the guard re-activates without code change.
    if asset_kind in _SELF_REFERENCING_KINDS:  # pragma: no cover  (empty set)
        raise ValueError(
            f"Mata-Garuda must NOT tag its own outputs (asset_kind={asset_kind!r}) — "
            f"feedback-loop guard per cell.yaml meta_awareness.does_not_observe"
        )
    if reliability not in RELIABILITY_VALUES:
        raise ValueError(f"reliability={reliability!r} not in {sorted(RELIABILITY_VALUES)!r}")
    if credibility not in CREDIBILITY_VALUES:
        raise ValueError(f"credibility={credibility!r} not in {sorted(CREDIBILITY_VALUES)!r}")
    if invalidation_mode not in INVALIDATION_MODES:
        raise ValueError(f"invalidation_mode={invalidation_mode!r} not in {sorted(INVALIDATION_MODES)!r}")
    if tlp not in TLP_VALUES:
        raise ValueError(f"tlp={tlp!r} not in {sorted(TLP_VALUES)!r}")


async def tag_provenance(
    pool: asyncpg.Pool,
    *,
    asset_kind: str,
    asset_id: str,
    source: str,
    reliability: str,
    credibility: int,
    owner: str,
    invalidation_mode: str = "auto",
    valid_until: datetime | None = None,
    invalidation_event_topic: str | None = None,
    tlp: str = "red",
    metadata: dict[str, Any] | None = None,
) -> int:
    """INSERT or UPSERT a provenance row.

    UNIQUE (asset_kind, asset_id) means re-tagging the same asset UPDATEs in
    place rather than creating a duplicate row. The mig 155 trigger fires
    on both INSERT (event_type=provenance_recorded) and UPDATE
    (event_type=provenance_updated), so subscribers see both initial tag
    and any subsequent re-grading.

    Returns the provenance row id.
    """
    _validate_inputs(
        asset_kind=asset_kind,
        reliability=reliability,
        credibility=credibility,
        invalidation_mode=invalidation_mode,
        tlp=tlp,
    )

    sql = """
        INSERT INTO asset_provenance (
            asset_kind, asset_id, source,
            reliability, credibility,
            owner,
            valid_until, invalidation_event_topic, invalidation_mode,
            tlp,
            metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        ON CONFLICT (asset_kind, asset_id) DO UPDATE SET
            source = EXCLUDED.source,
            reliability = EXCLUDED.reliability,
            credibility = EXCLUDED.credibility,
            owner = EXCLUDED.owner,
            valid_until = EXCLUDED.valid_until,
            invalidation_event_topic = EXCLUDED.invalidation_event_topic,
            invalidation_mode = EXCLUDED.invalidation_mode,
            tlp = EXCLUDED.tlp,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING id
    """
    async with pool.acquire() as conn:
        row_id: int = await conn.fetchval(
            sql,
            asset_kind, asset_id, source,
            reliability, credibility,
            owner,
            valid_until, invalidation_event_topic, invalidation_mode,
            tlp,
            metadata or {},
        )
    logger.debug(
        "provenance tagged: kind=%s id=%s reliability=%s credibility=%s tlp=%s row_id=%s",
        asset_kind, asset_id, reliability, credibility, tlp, row_id,
    )
    return row_id


async def get_provenance(
    pool: asyncpg.Pool,
    *,
    asset_kind: str,
    asset_id: str,
) -> ProvenanceRow | None:
    """Fetch the current provenance row for an asset, or None if not tagged."""
    if asset_kind not in ASSET_KIND_AUTHORITATIVE:
        raise ValueError(
            f"asset_kind={asset_kind!r} not in canonical 12-value set"
        )
    sql = """
        SELECT
            id, asset_kind, asset_id, source,
            reliability, credibility,
            owner,
            valid_until, invalidation_event_topic, invalidation_mode,
            invalidated_at, invalidated_by,
            tlp,
            created_at, updated_at, metadata
        FROM asset_provenance
        WHERE asset_kind = $1 AND asset_id = $2
    """
    async with pool.acquire() as conn:
        record = await conn.fetchrow(sql, asset_kind, asset_id)
    if record is None:
        return None
    return ProvenanceRow(
        id=record["id"],
        asset_kind=record["asset_kind"],
        asset_id=record["asset_id"],
        source=record["source"],
        reliability=record["reliability"],
        credibility=record["credibility"],
        owner=record["owner"],
        valid_until=record["valid_until"],
        invalidation_event_topic=record["invalidation_event_topic"],
        invalidation_mode=record["invalidation_mode"],
        invalidated_at=record["invalidated_at"],
        invalidated_by=record["invalidated_by"],
        tlp=record["tlp"],
        created_at=record["created_at"],
        updated_at=record["updated_at"],
        metadata=dict(record["metadata"] or {}),
    )


async def list_expired_assets(
    pool: asyncpg.Pool,
    *,
    asset_kind: str | None = None,
    limit: int = 1000,
) -> list[ProvenanceRow]:
    """Return rows whose TTL has elapsed and that are still active.

    "Expired" = ``valid_until < NOW() AND invalidated_at IS NULL AND
    invalidation_mode='auto'``. Used by the daily ``invalidation_sweeper``
    sub-organelle to know which rows to mark invalidated and emit
    asset_invalidated events for.
    """
    if asset_kind is not None and asset_kind not in ASSET_KIND_AUTHORITATIVE:
        raise ValueError(
            f"asset_kind={asset_kind!r} not in canonical 12-value set"
        )
    where = (
        "valid_until < NOW() "
        "AND invalidated_at IS NULL "
        "AND invalidation_mode = 'auto'"
    )
    args: list[Any] = []
    if asset_kind is not None:
        where += " AND asset_kind = $1"
        args.append(asset_kind)
    args.append(limit)
    limit_placeholder = f"${len(args)}"
    sql = (
        "SELECT id, asset_kind, asset_id, source, reliability, credibility, "
        "owner, valid_until, invalidation_event_topic, invalidation_mode, "
        "invalidated_at, invalidated_by, tlp, created_at, updated_at, metadata "
        f"FROM asset_provenance WHERE {where} "
        f"ORDER BY valid_until ASC LIMIT {limit_placeholder}"
    )
    async with pool.acquire() as conn:
        records = await conn.fetch(sql, *args)
    return [
        ProvenanceRow(
            id=r["id"],
            asset_kind=r["asset_kind"],
            asset_id=r["asset_id"],
            source=r["source"],
            reliability=r["reliability"],
            credibility=r["credibility"],
            owner=r["owner"],
            valid_until=r["valid_until"],
            invalidation_event_topic=r["invalidation_event_topic"],
            invalidation_mode=r["invalidation_mode"],
            invalidated_at=r["invalidated_at"],
            invalidated_by=r["invalidated_by"],
            tlp=r["tlp"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            metadata=dict(r["metadata"] or {}),
        )
        for r in records
    ]


def confidence_tier(reliability: str, credibility: int) -> str:
    """Collapse the 30-cell admiralty matrix to a 4-tier human-readable label.

    The DDL stores both axes (reliability A-F + credibility 1-6 = 30 cells)
    so machine consumers and OSINT analysts can filter on full granularity.
    Human dashboards typically want a 4-tier summary; this is the canonical
    mapping (corresponds to the X2 review compromise: keep 30-cell DDL,
    expose 4-tier summary in adapter).

    Mapping:
        VERIFIED   = (A, 1)                    "completely reliable + confirmed"
        HIGH       = A2, A3, B1, B2, B3        "usually-fairly reliable + confirmed-possibly"
        LOW        = C, D × any                "fairly-unusually reliable, any credibility"
        UNVERIFIED = E, F × any OR any × 4-6   "unreliable OR cannot judge OR doubtful+"
    """
    if reliability == "A" and credibility == 1:
        return "VERIFIED"
    if reliability in {"A", "B"} and credibility <= 3:
        return "HIGH"
    if reliability in {"C", "D"} and credibility <= 3:
        return "LOW"
    return "UNVERIFIED"


__all__ = [
    "ASSET_KIND_AUTHORITATIVE",
    "RELIABILITY_VALUES",
    "CREDIBILITY_VALUES",
    "TLP_VALUES",
    "INVALIDATION_MODES",
    "ProvenanceRow",
    "tag_provenance",
    "get_provenance",
    "list_expired_assets",
    "confidence_tier",
]
