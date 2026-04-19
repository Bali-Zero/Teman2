"""
Bridge from Intel validation to KG proposals (m108 kg_proposals).

Valid Intel tier-3 matches are PROPOSED to kg_proposals, never auto-promoted
— decision #3 (Zero is the last instance for all KG mutations).

Schema adaptation (m108 actual columns):
  proposal_id TEXT UNIQUE   — generated as "intel-{staging_id}-{entity_id}"
  gap_id TEXT               — "intel_staging:{staging_id}"
  domain TEXT               — "intel"
  proposal_type TEXT        — always 'node' for Intel entities
  node_label TEXT           — entity name
  node_type TEXT            — entity type (from KG crossref result)
  node_properties JSONB     — full entity dict
  evidence_sources JSONB    — empty list (URL comes from staging)
  self_rag_score FLOAT      — 0.0 (not graded here)
  status TEXT               — 'pending' (default)
  metadata JSONB            — {"source": "intel_validator", "staging_id": ...}

Idempotency: ON CONFLICT (proposal_id) DO NOTHING.
"""
from __future__ import annotations

import json
import logging

import asyncpg

logger = logging.getLogger(__name__)

_SOURCE_TAG = "intel_validator"


async def propose_kg_entities(
    conn: asyncpg.Connection,
    *,
    staging_id: int,
    entities: list[dict],
) -> int:
    """Insert one row per entity into kg_proposals; return count actually inserted.

    Uses m108 actual schema (proposal_id, gap_id, domain, proposal_type, …).
    Idempotent: ON CONFLICT (proposal_id) DO NOTHING.
    Falls back to existence check + INSERT if the unique constraint is absent.
    """
    if not entities:
        return 0

    gap_id = f"intel_staging:{staging_id}"
    inserted = 0

    for entity in entities:
        eid = str(entity.get("id") or "").strip()
        if not eid:
            continue

        proposal_id = f"intel-{staging_id}-{eid}"
        node_label = str(entity.get("name") or eid)
        node_type = str(entity.get("type") or "unknown")
        node_properties = json.dumps(entity)
        metadata = json.dumps({
            "source": _SOURCE_TAG,
            "staging_id": staging_id,
        })

        try:
            result = await conn.execute(
                """
                INSERT INTO kg_proposals (
                    proposal_id, gap_id, domain, proposal_type,
                    node_label, node_type, node_properties,
                    evidence_sources, self_rag_score,
                    status, metadata
                ) VALUES (
                    $1, $2, 'intel', 'node',
                    $3, $4, $5::jsonb,
                    '[]'::jsonb, 0.0,
                    'pending', $6::jsonb
                )
                ON CONFLICT (proposal_id) DO NOTHING
                """,
                proposal_id, gap_id, node_label, node_type,
                node_properties, metadata,
            )
            # asyncpg returns 'INSERT 0 1' on success, 'INSERT 0 0' on conflict
            if result and result.endswith(" 1"):
                inserted += 1

        except (asyncpg.UndefinedObjectError, asyncpg.PostgresSyntaxError) as exc:
            # Constraint may be missing — fall back to existence check + insert
            logger.debug("ON CONFLICT path failed, falling back: %s", exc)
            exists = await conn.fetchval(
                "SELECT 1 FROM kg_proposals WHERE proposal_id = $1 LIMIT 1",
                proposal_id,
            )
            if not exists:
                await conn.execute(
                    """
                    INSERT INTO kg_proposals (
                        proposal_id, gap_id, domain, proposal_type,
                        node_label, node_type, node_properties,
                        evidence_sources, self_rag_score,
                        status, metadata
                    ) VALUES (
                        $1, $2, 'intel', 'node',
                        $3, $4, $5::jsonb,
                        '[]'::jsonb, 0.0,
                        'pending', $6::jsonb
                    )
                    """,
                    proposal_id, gap_id, node_label, node_type,
                    node_properties, metadata,
                )
                inserted += 1

    return inserted


__all__ = ["propose_kg_entities"]
