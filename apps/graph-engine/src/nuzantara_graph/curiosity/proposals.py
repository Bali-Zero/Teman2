"""KG Proposals Store — propose-only gateway to kg_nodes/kg_edges.

# Organo: graph-engine/curiosity → produce kg_proposals rows → consuma da CLI kg-propose

SACRED INVARIANT: This module NEVER writes directly to kg_nodes or kg_edges.
All mutations go through kg_proposals table and require Zero approval via CLI.
The apply() method is the ONLY path to kg_nodes/kg_edges and requires
an explicit approved_by identifier.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from nuzantara_graph.curiosity.models import (
    KGProposal,
    ProposalStatus,
    ProposalType,
)

logger = logging.getLogger(__name__)

# Safety constants
DEDUP_WINDOW_DAYS = 7
EXPIRY_DAYS = 14
BLACKLIST_FAILURES = 3
BLACKLIST_DAYS = 30


class KGProposalStore:
    """Persists and manages KG proposals.

    PROPOSE-ONLY: save() writes to kg_proposals.
    apply_approved() writes to kg_nodes/kg_edges ONLY after Zero approval.
    """

    def __init__(self, database_url: str = "") -> None:
        self.database_url = database_url
        self._pool: asyncpg.Pool | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=5,
                command_timeout=30,
            )
        return self._pool

    async def save(self, proposal: KGProposal) -> str:
        """Save a proposal to kg_proposals. NEVER touches kg_nodes/kg_edges.

        Returns:
            proposal_id of the saved proposal.
        """
        pool = await self._get_pool()

        await pool.execute(
            """
            INSERT INTO kg_proposals (
                proposal_id, gap_id, domain, proposal_type,
                node_label, node_type, node_properties,
                source_entity_id, target_entity_id, relationship_type, edge_properties,
                target_entity_id_prop, property_key, property_value,
                evidence_sources, self_rag_score, tier, research_method,
                status, metadata
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6, $7::jsonb,
                $8, $9, $10, $11::jsonb,
                $12, $13, $14::jsonb,
                $15::jsonb, $16, $17, $18,
                $19, $20::jsonb
            )
            ON CONFLICT (proposal_id) DO NOTHING
            """,
            proposal.proposal_id,
            proposal.gap_id,
            proposal.domain,
            proposal.proposal_type.value,
            proposal.node_label,
            proposal.node_type,
            json.dumps(proposal.node_properties),
            proposal.source_entity_id,
            proposal.target_entity_id,
            proposal.relationship_type,
            json.dumps(proposal.edge_properties),
            proposal.target_entity_id_prop,
            proposal.property_key,
            json.dumps(proposal.property_value) if proposal.property_value is not None else "null",
            json.dumps(proposal.evidence_sources),
            proposal.self_rag_score,
            proposal.tier.value,
            proposal.research_method,
            proposal.status.value,
            json.dumps(proposal.metadata),
        )

        logger.info(
            "Saved proposal %s: domain=%s type=%s score=%.2f",
            proposal.proposal_id[:8],
            proposal.domain,
            proposal.proposal_type,
            proposal.self_rag_score,
        )
        return proposal.proposal_id

    async def list_proposals(
        self,
        domain: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List proposals with optional filters."""
        pool = await self._get_pool()

        conditions: list[str] = []
        params: list[Any] = []
        idx = 1

        if domain:
            conditions.append(f"domain = ${idx}")
            params.append(domain)
            idx += 1

        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sql = f"""
            SELECT * FROM kg_proposals
            {where}
            ORDER BY created_at DESC
            LIMIT ${idx}
        """
        params.append(limit)

        rows = await pool.fetch(sql, *params)
        return [dict(row) for row in rows]

    async def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        """Get a single proposal by ID."""
        pool = await self._get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM kg_proposals WHERE proposal_id = $1",
            proposal_id,
        )
        return dict(row) if row else None

    async def is_duplicate(self, gap_id: str, domain: str) -> bool:
        """Check if a proposal for this gap was created in the last DEDUP_WINDOW_DAYS."""
        pool = await self._get_pool()
        cutoff = datetime.now(timezone.utc) - timedelta(days=DEDUP_WINDOW_DAYS)

        row = await pool.fetchrow(
            """
            SELECT 1 FROM kg_proposals
            WHERE gap_id = $1 AND domain = $2
              AND created_at > $3
              AND status IN ('pending', 'rejected')
            LIMIT 1
            """,
            gap_id, domain, cutoff,
        )
        return row is not None

    async def is_blacklisted(self, gap_id: str) -> bool:
        """Check if a gap has been rejected >= BLACKLIST_FAILURES times recently."""
        pool = await self._get_pool()
        cutoff = datetime.now(timezone.utc) - timedelta(days=BLACKLIST_DAYS)

        row = await pool.fetchrow(
            """
            SELECT COUNT(*) as reject_count FROM kg_proposals
            WHERE gap_id = $1
              AND status = 'rejected'
              AND created_at > $2
            """,
            gap_id, cutoff,
        )
        return (row["reject_count"] if row else 0) >= BLACKLIST_FAILURES

    async def approve(self, proposal_id: str, approved_by: str) -> bool:
        """Approve a proposal. Does NOT apply it yet."""
        pool = await self._get_pool()
        result = await pool.execute(
            """
            UPDATE kg_proposals
            SET status = 'approved',
                approved_by = $2,
                approved_at = NOW()
            WHERE proposal_id = $1 AND status = 'pending'
            """,
            proposal_id, approved_by,
        )
        return result == "UPDATE 1"

    async def reject(self, proposal_id: str, reason: str = "") -> bool:
        """Reject a proposal."""
        pool = await self._get_pool()
        result = await pool.execute(
            """
            UPDATE kg_proposals
            SET status = 'rejected',
                rejection_reason = $2
            WHERE proposal_id = $1 AND status = 'pending'
            """,
            proposal_id, reason,
        )
        return result == "UPDATE 1"

    async def apply_approved(self, proposal_id: str) -> bool:
        """Apply an APPROVED proposal to kg_nodes/kg_edges.

        SAFETY: Only works on status='approved'. Requires prior approve() call.
        This is the ONLY path to mutate kg_nodes/kg_edges from Curiosity Loop.

        Returns:
            True if applied successfully, False otherwise.
        """
        pool = await self._get_pool()

        # Fetch proposal — must be approved
        row = await pool.fetchrow(
            "SELECT * FROM kg_proposals WHERE proposal_id = $1 AND status = 'approved'",
            proposal_id,
        )
        if not row:
            logger.warning("Cannot apply %s: not found or not approved", proposal_id)
            return False

        proposal = dict(row)

        async with pool.acquire() as conn:
            async with conn.transaction():
                try:
                    ptype = proposal["proposal_type"]

                    if ptype == ProposalType.NODE:
                        entity_id = f"{proposal['node_type']}_{proposal['node_label']}".upper().replace(" ", "_")
                        props = proposal.get("node_properties", {})
                        if isinstance(props, str):
                            props = json.loads(props)

                        await conn.execute(
                            """
                            INSERT INTO kg_nodes (
                                entity_id, entity_type, name, description,
                                properties, confidence, source_collection,
                                created_at, updated_at
                            ) VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, NOW(), NOW())
                            ON CONFLICT (entity_id) DO UPDATE SET
                                properties = kg_nodes.properties || $5::jsonb,
                                updated_at = NOW()
                            """,
                            entity_id,
                            proposal["node_type"],
                            proposal["node_label"],
                            props.get("description", ""),
                            json.dumps(props),
                            proposal["self_rag_score"],
                            "curiosity_loop",
                        )

                    elif ptype == ProposalType.EDGE:
                        edge_props = proposal.get("edge_properties", {})
                        if isinstance(edge_props, str):
                            edge_props = json.loads(edge_props)

                        rel_id = f"{proposal['source_entity_id']}__{proposal['relationship_type']}__{proposal['target_entity_id']}"
                        await conn.execute(
                            """
                            INSERT INTO kg_edges (
                                relationship_id, source_entity_id, target_entity_id,
                                relationship_type, properties, confidence,
                                source_collection, created_at
                            ) VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, NOW())
                            ON CONFLICT (relationship_id) DO NOTHING
                            """,
                            rel_id,
                            proposal["source_entity_id"],
                            proposal["target_entity_id"],
                            proposal["relationship_type"],
                            json.dumps(edge_props),
                            proposal["self_rag_score"],
                            "curiosity_loop",
                        )

                    elif ptype == ProposalType.PROPERTY:
                        prop_val = proposal.get("property_value")
                        if isinstance(prop_val, str):
                            prop_val = json.loads(prop_val)
                        key = proposal["property_key"]
                        await conn.execute(
                            """
                            UPDATE kg_nodes
                            SET properties = jsonb_set(
                                COALESCE(properties, '{}'), $2::text[], $3::jsonb
                            ),
                            updated_at = NOW()
                            WHERE entity_id = $1
                            """,
                            proposal["target_entity_id_prop"],
                            [key],
                            json.dumps(prop_val),
                        )

                    # Mark as applied
                    await conn.execute(
                        """
                        UPDATE kg_proposals
                        SET status = 'applied', applied_at = NOW()
                        WHERE proposal_id = $1
                        """,
                        proposal_id,
                    )

                    logger.info(
                        "Applied proposal %s: type=%s domain=%s",
                        proposal_id[:8], ptype, proposal["domain"],
                    )
                    return True

                except Exception as e:
                    logger.error("Failed to apply proposal %s: %s", proposal_id, e)
                    # Transaction rolls back automatically
                    return False

    async def expire_stale(self) -> int:
        """Expire proposals unapproved for > EXPIRY_DAYS. Returns count expired."""
        pool = await self._get_pool()
        cutoff = datetime.now(timezone.utc) - timedelta(days=EXPIRY_DAYS)

        result = await pool.execute(
            """
            UPDATE kg_proposals
            SET status = 'auto_expired'
            WHERE status = 'pending' AND created_at < $1
            """,
            cutoff,
        )
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            logger.info("Expired %d stale proposals (>%d days)", count, EXPIRY_DAYS)
        return count

    async def stats(self) -> dict[str, Any]:
        """Get proposal statistics."""
        pool = await self._get_pool()

        rows = await pool.fetch(
            """
            SELECT status, COUNT(*) as cnt
            FROM kg_proposals
            GROUP BY status
            """
        )
        status_counts = {row["status"]: row["cnt"] for row in rows}

        domain_rows = await pool.fetch(
            """
            SELECT domain, COUNT(*) as cnt
            FROM kg_proposals
            WHERE status = 'pending'
            GROUP BY domain
            """
        )
        pending_by_domain = {row["domain"]: row["cnt"] for row in domain_rows}

        # Ontological density
        density_row = await pool.fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM kg_nodes) as node_count,
                (SELECT COUNT(*) FROM kg_edges) as edge_count
            """
        )
        node_count = density_row["node_count"] if density_row else 0
        edge_count = density_row["edge_count"] if density_row else 0
        density = edge_count / node_count if node_count > 0 else 0.0

        return {
            "status_counts": status_counts,
            "pending_by_domain": pending_by_domain,
            "total": sum(status_counts.values()),
            "ontological_density": round(density, 3),
            "node_count": node_count,
            "edge_count": edge_count,
        }

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
