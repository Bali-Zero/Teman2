"""
KG Phase 1: Property + Tax Node/Edge Population
=================================================

Converts hardcoded data from kg_subgraph_property.py and kg_subgraph_tax.py
into kg_nodes / kg_edges database entries so the subgraphs can query the KG
instead of returning static dictionaries.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/kg_populate_property_tax.py --phase property --dry-run
    PYTHONPATH=. python scripts/kg_populate_property_tax.py --phase tax --dry-run
    PYTHONPATH=. python scripts/kg_populate_property_tax.py --phase all

Author: Nuzantara Team
Date: 2026-04-05
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any

import asyncpg

# Ensure backend is importable when run from monorepo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# SQL HELPERS — match KnowledgeGraphRepository patterns (kg_repository.py)
# ═══════════════════════════════════════════════════════════════════════════════

_UPSERT_NODE_SQL = """
INSERT INTO kg_nodes (
    entity_id, entity_type, name, properties,
    confidence, source_chunk_ids, created_at, updated_at
)
VALUES ($1, $2, $3, $4::jsonb, 1.0, $5, NOW(), NOW())
ON CONFLICT (entity_id) DO UPDATE SET
    properties = kg_nodes.properties || EXCLUDED.properties,
    updated_at = NOW()
"""

_UPSERT_EDGE_SQL = """
INSERT INTO kg_edges (
    relationship_id, source_entity_id, target_entity_id,
    relationship_type, properties, confidence,
    source_chunk_ids, created_at
)
VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, NOW())
ON CONFLICT (relationship_id) DO UPDATE SET
    confidence = (kg_edges.confidence + EXCLUDED.confidence) / 2,
    properties = jsonb_set(
        kg_edges.properties,
        '{evidence}',
        COALESCE(kg_edges.properties->'evidence', '[]'::jsonb) ||
        COALESCE(EXCLUDED.properties->'evidence', '[]'::jsonb)
    )
"""


async def _upsert_node(
    conn: asyncpg.Connection,
    entity_id: str,
    entity_type: str,
    name: str,
    properties: dict[str, Any],
    source_chunk_ids: list[str] | None = None,
) -> None:
    """Insert or merge a node into kg_nodes."""
    await conn.execute(
        _UPSERT_NODE_SQL,
        entity_id,
        entity_type,
        name,
        json.dumps(properties),
        source_chunk_ids or [],
    )


async def _upsert_edge(
    conn: asyncpg.Connection,
    source_id: str,
    target_id: str,
    rel_type: str,
    properties: dict[str, Any] | None = None,
    confidence: float = 1.0,
    source_chunk_ids: list[str] | None = None,
) -> None:
    """Insert or merge an edge into kg_edges."""
    relationship_id = f"{source_id}_{rel_type}_{target_id}"
    await conn.execute(
        _UPSERT_EDGE_SQL,
        relationship_id,
        source_id,
        target_id,
        rel_type,
        json.dumps(properties or {}),
        confidence,
        source_chunk_ids or [],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY DOMAIN
# Source: _LEGACY_REQUIREMENTS_DB in kg_subgraph_property.py
# ═══════════════════════════════════════════════════════════════════════════════

PROPERTY_TYPE_NODES: list[dict[str, Any]] = [
    {
        "entity_id": "property_type:hak_pakai",
        "entity_type": "property_type",
        "name": "Hak Pakai (Right to Use)",
        "properties": {
            "allowed_for_foreigners": True,
            "max_duration": "30 years (renewable 20+30 years)",
            "notes": "Most common for foreign property ownership",
            "source": "kg_subgraph_property._LEGACY_REQUIREMENTS_DB",
        },
    },
    {
        "entity_id": "property_type:hgb",
        "entity_type": "property_type",
        "name": "HGB (Hak Guna Bangunan)",
        "properties": {
            "allowed_for_foreigners": False,
            "max_duration": "30 years (renewable)",
            "notes": "Foreigners can acquire via PT PMA",
            "source": "kg_subgraph_property._LEGACY_REQUIREMENTS_DB",
        },
    },
    {
        "entity_id": "property_type:hak_milik",
        "entity_type": "property_type",
        "name": "Hak Milik (Full Ownership)",
        "properties": {
            "allowed_for_foreigners": False,
            "max_duration": "Permanent",
            "notes": "Full ownership, not available to foreigners",
            "source": "kg_subgraph_property._LEGACY_REQUIREMENTS_DB",
        },
    },
    {
        "entity_id": "property_type:rental",
        "entity_type": "property_type",
        "name": "Rental / Lease",
        "properties": {
            "allowed_for_foreigners": True,
            "max_duration": "Varies (typically 1-5 years)",
            "notes": "Simplest option for short-term stay",
            "source": "kg_subgraph_property._LEGACY_REQUIREMENTS_DB",
        },
    },
]

PROPERTY_CONCEPT_NODES: list[dict[str, Any]] = [
    {
        "entity_id": "concept:foreigner",
        "entity_type": "concept",
        "name": "Foreigner (WNA)",
        "properties": {"domain": "property", "description": "Foreign national buyer"},
    },
    {
        "entity_id": "concept:indonesian_citizen",
        "entity_type": "concept",
        "name": "Indonesian Citizen (WNI)",
        "properties": {"domain": "property", "description": "Indonesian national buyer"},
    },
    {
        "entity_id": "concept:kitas_or_kitap",
        "entity_type": "concept",
        "name": "KITAS or KITAP Holder",
        "properties": {
            "domain": "property",
            "description": "Temporary/permanent residence permit holder",
        },
    },
    {
        "entity_id": "concept:notary_deed",
        "entity_type": "concept",
        "name": "Notary Deed",
        "properties": {
            "domain": "property",
            "description": "PPAT notarial deed for property transfer",
        },
    },
    {
        "entity_id": "concept:bpn_certificate_check",
        "entity_type": "concept",
        "name": "BPN Certificate Check",
        "properties": {
            "domain": "property",
            "description": "Land certificate verification at BPN office",
        },
    },
    {
        "entity_id": "concept:ppjb_agreement",
        "entity_type": "concept",
        "name": "PPJB Agreement",
        "properties": {
            "domain": "property",
            "description": "Preliminary sale & purchase agreement",
        },
    },
    {
        "entity_id": "concept:bpn_registration",
        "entity_type": "concept",
        "name": "BPN Registration",
        "properties": {
            "domain": "property",
            "description": "Final registration at Land Office (BPN)",
        },
    },
]

PROPERTY_FEE_NODES: list[dict[str, Any]] = [
    {
        "entity_id": "government_fee:bphtb_5pct",
        "entity_type": "government_fee",
        "name": "BPHTB 5% Tax",
        "properties": {
            "rate": 0.05,
            "description": "Bea Perolehan Hak atas Tanah dan Bangunan",
            "domain": "property",
        },
    },
]

# 14 property edges
PROPERTY_EDGES: list[dict[str, Any]] = [
    # ALLOWS_OWNERSHIP (4)
    {"source": "property_type:hak_pakai", "target": "concept:foreigner", "type": "ALLOWS_OWNERSHIP",
     "properties": {"condition": "Must hold KITAS/KITAP"}},
    {"source": "property_type:hak_pakai", "target": "concept:indonesian_citizen", "type": "ALLOWS_OWNERSHIP",
     "properties": {}},
    {"source": "property_type:hak_milik", "target": "concept:indonesian_citizen", "type": "ALLOWS_OWNERSHIP",
     "properties": {"condition": "Indonesian citizens only"}},
    {"source": "property_type:rental", "target": "concept:foreigner", "type": "ALLOWS_OWNERSHIP",
     "properties": {"condition": "Rental agreement + passport copy"}},
    # HAS_REQUIREMENT (3)
    {"source": "property_type:hak_pakai", "target": "concept:kitas_or_kitap", "type": "HAS_REQUIREMENT",
     "properties": {"evidence": ["KITAS/KITAP holder requirement for Hak Pakai"]}},
    {"source": "property_type:hak_pakai", "target": "concept:notary_deed", "type": "HAS_REQUIREMENT",
     "properties": {"evidence": ["Notary deed required for Hak Pakai transfer"]}},
    {"source": "property_type:hak_pakai", "target": "concept:bpn_certificate_check", "type": "HAS_REQUIREMENT",
     "properties": {"evidence": ["BPN certificate check required for Hak Pakai"]}},
    # HAS_FEE (3)
    {"source": "property_type:hak_pakai", "target": "government_fee:bphtb_5pct", "type": "HAS_FEE",
     "properties": {"evidence": ["BPHTB 5% tax on Hak Pakai acquisition"]}},
    {"source": "property_type:hgb", "target": "government_fee:bphtb_5pct", "type": "HAS_FEE",
     "properties": {"evidence": ["BPHTB 5% tax on HGB acquisition"]}},
    {"source": "property_type:hak_milik", "target": "government_fee:bphtb_5pct", "type": "HAS_FEE",
     "properties": {"evidence": ["BPHTB 5% tax on Hak Milik acquisition"]}},
    # REQUIRES_ENTITY — cross-domain (1)
    {"source": "property_type:hgb", "target": "company:pt_pma", "type": "REQUIRES_ENTITY",
     "properties": {"evidence": ["Foreigners acquire HGB via PT PMA company"]}},
    # REQUIRES — workflow chain (3)
    {"source": "concept:bpn_certificate_check", "target": "concept:ppjb_agreement", "type": "REQUIRES",
     "properties": {"step_order": 1, "evidence": ["BPN check before signing PPJB"]}},
    {"source": "concept:ppjb_agreement", "target": "concept:notary_deed", "type": "REQUIRES",
     "properties": {"step_order": 2, "evidence": ["PPJB before notary deed execution"]}},
    {"source": "concept:notary_deed", "target": "concept:bpn_registration", "type": "REQUIRES",
     "properties": {"step_order": 3, "evidence": ["Notary deed before BPN registration"]}},
]


async def populate_property_nodes(conn: asyncpg.Connection) -> int:
    """Insert all property-domain nodes. Returns count inserted."""
    all_nodes = PROPERTY_TYPE_NODES + PROPERTY_CONCEPT_NODES + PROPERTY_FEE_NODES
    for node in all_nodes:
        await _upsert_node(
            conn,
            entity_id=node["entity_id"],
            entity_type=node["entity_type"],
            name=node["name"],
            properties=node["properties"],
            source_chunk_ids=["phase1_property_extraction"],
        )
    logger.info("Property nodes inserted: %d", len(all_nodes))
    return len(all_nodes)


async def populate_property_edges(conn: asyncpg.Connection) -> int:
    """Insert all property-domain edges. Returns count inserted."""
    for edge in PROPERTY_EDGES:
        await _upsert_edge(
            conn,
            source_id=edge["source"],
            target_id=edge["target"],
            rel_type=edge["type"],
            properties=edge.get("properties"),
            confidence=1.0,
            source_chunk_ids=["phase1_property_extraction"],
        )
    logger.info("Property edges inserted: %d", len(PROPERTY_EDGES))
    return len(PROPERTY_EDGES)


# ═══════════════════════════════════════════════════════════════════════════════
# TAX DOMAIN
# Source: tax_obligations_db in kg_subgraph_tax.py
# ═══════════════════════════════════════════════════════════════════════════════

TAX_TYPE_NODES: list[dict[str, Any]] = [
    {
        "entity_id": "tax_type:pph_badan",
        "entity_type": "tax_type",
        "name": "PPh Badan (Corporate Income Tax)",
        "properties": {
            "rate": 0.22,
            "description": "Corporate Income Tax",
            "filing_deadline": "4 months after fiscal year end",
            "source": "kg_subgraph_tax.tax_obligations_db",
        },
    },
    {
        "entity_id": "tax_type:pph_21",
        "entity_type": "tax_type",
        "name": "PPh 21 (Employee Withholding)",
        "properties": {
            "description": "Withholding tax on employee salaries",
            "progressive_rates": [
                {"bracket": "0-60M", "rate": 0.05},
                {"bracket": "60-250M", "rate": 0.15},
                {"bracket": "250-500M", "rate": 0.25},
                {"bracket": "500M+", "rate": 0.30},
            ],
            "filing_deadline": "20th of following month",
            "source": "kg_subgraph_tax.tax_obligations_db",
        },
    },
    {
        "entity_id": "tax_type:pph_23",
        "entity_type": "tax_type",
        "name": "PPh 23 (Service/Rent Withholding)",
        "properties": {
            "rate": 0.02,
            "description": "Withholding tax on services/rent",
            "filing_deadline": "20th of following month",
            "source": "kg_subgraph_tax.tax_obligations_db",
        },
    },
    {
        "entity_id": "tax_type:pph_26",
        "entity_type": "tax_type",
        "name": "PPh 26 (Foreign Payment Withholding)",
        "properties": {
            "rate": 0.20,
            "description": "Withholding tax on payments to non-residents",
            "filing_deadline": "20th of following month",
            "treaty_reducible": True,
            "source": "kg_subgraph_tax.tax_obligations_db",
        },
    },
    {
        "entity_id": "tax_type:ppn",
        "entity_type": "tax_type",
        "name": "PPN (Value Added Tax)",
        "properties": {
            "rate": 0.11,
            "description": "Value Added Tax",
            "threshold_idr": 4_800_000_000,
            "filing_deadline": "End of following month",
            "source": "kg_subgraph_tax.tax_obligations_db",
        },
    },
]

TAX_OBLIGATION_NODES: list[dict[str, Any]] = [
    {
        "entity_id": "tax_obligation:npwp_registration",
        "entity_type": "tax_obligation",
        "name": "NPWP Registration",
        "properties": {
            "description": "Obtain NPWP (Tax ID)",
            "requirement": "Mandatory for all businesses",
            "processing_time": "1-3 days",
            "registration": "Online via DJP",
        },
    },
    {
        "entity_id": "tax_obligation:pkp_registration",
        "entity_type": "tax_obligation",
        "name": "PKP Registration",
        "properties": {
            "description": "Register as VAT Taxable Entrepreneur",
            "requirement": "Revenue > 4.8B IDR annually",
            "processing_time": "7-14 days",
            "registration": "Online via DJP",
        },
    },
    {
        "entity_id": "tax_obligation:bookkeeping_setup",
        "entity_type": "tax_obligation",
        "name": "Bookkeeping Setup",
        "properties": {
            "description": "Set up bookkeeping and accounting system",
            "requirement": "Required for all business entities",
        },
    },
    {
        "entity_id": "tax_obligation:monthly_filing",
        "entity_type": "tax_obligation",
        "name": "Monthly Tax Filing",
        "properties": {
            "description": "Monthly PPh 21/23/25 and PPN filing",
            "deadline": "20th of following month (withholding), end of month (VAT)",
        },
    },
    {
        "entity_id": "tax_obligation:annual_spt",
        "entity_type": "tax_obligation",
        "name": "Annual SPT Filing",
        "properties": {
            "description": "Annual tax return (SPT Tahunan)",
            "deadline": "4 months after fiscal year end (corporate), March 31 (personal)",
        },
    },
]

TAX_DEADLINE_NODES: list[dict[str, Any]] = [
    {
        "entity_id": "concept:20th_following_month",
        "entity_type": "concept",
        "name": "20th of Following Month",
        "properties": {
            "domain": "tax",
            "description": "Monthly withholding tax filing deadline",
        },
    },
    {
        "entity_id": "concept:end_following_month",
        "entity_type": "concept",
        "name": "End of Following Month",
        "properties": {
            "domain": "tax",
            "description": "Monthly PPN filing deadline",
        },
    },
]

# 14 tax edges
TAX_EDGES: list[dict[str, Any]] = [
    # HAS_TAX — pt_pma (4)
    {"source": "company:pt_pma", "target": "tax_type:pph_badan", "type": "HAS_TAX",
     "properties": {"evidence": ["PT PMA subject to 22% Corporate Income Tax"]}},
    {"source": "company:pt_pma", "target": "tax_type:pph_21", "type": "HAS_TAX",
     "properties": {"evidence": ["PT PMA must withhold PPh 21 on employee salaries"]}},
    {"source": "company:pt_pma", "target": "tax_type:pph_23", "type": "HAS_TAX",
     "properties": {"evidence": ["PT PMA must withhold PPh 23 on service payments"]}},
    {"source": "company:pt_pma", "target": "tax_type:pph_26", "type": "HAS_TAX",
     "properties": {"evidence": ["PT PMA must withhold PPh 26 on foreign payments"]}},
    # HAS_TAX — cv (2)
    {"source": "company:cv", "target": "tax_type:pph_badan", "type": "HAS_TAX",
     "properties": {"evidence": ["CV taxed as corporate entity at 22%"]}},
    {"source": "company:cv", "target": "tax_type:ppn", "type": "HAS_TAX",
     "properties": {"evidence": ["CV subject to PPN if revenue > 4.8B IDR"]}},
    # HAS_DEADLINE (4)
    {"source": "tax_type:pph_21", "target": "concept:20th_following_month", "type": "HAS_DEADLINE",
     "properties": {"evidence": ["PPh 21 filing due 20th of following month"]}},
    {"source": "tax_type:pph_23", "target": "concept:20th_following_month", "type": "HAS_DEADLINE",
     "properties": {"evidence": ["PPh 23 filing due 20th of following month"]}},
    {"source": "tax_type:pph_26", "target": "concept:20th_following_month", "type": "HAS_DEADLINE",
     "properties": {"evidence": ["PPh 26 filing due 20th of following month"]}},
    {"source": "tax_type:ppn", "target": "concept:end_following_month", "type": "HAS_DEADLINE",
     "properties": {"evidence": ["PPN filing due end of following month"]}},
    # REQUIRES — obligation chain (4)
    {"source": "tax_obligation:npwp_registration", "target": "tax_obligation:pkp_registration",
     "type": "REQUIRES", "properties": {"step_order": 1, "evidence": ["NPWP before PKP registration"]}},
    {"source": "tax_obligation:pkp_registration", "target": "tax_obligation:bookkeeping_setup",
     "type": "REQUIRES", "properties": {"step_order": 2, "evidence": ["PKP registration before bookkeeping"]}},
    {"source": "tax_obligation:bookkeeping_setup", "target": "tax_obligation:monthly_filing",
     "type": "REQUIRES", "properties": {"step_order": 3, "evidence": ["Bookkeeping before monthly filing"]}},
    {"source": "tax_obligation:monthly_filing", "target": "tax_obligation:annual_spt",
     "type": "REQUIRES", "properties": {"step_order": 4, "evidence": ["Monthly filing before annual SPT"]}},
]


async def populate_tax_nodes(conn: asyncpg.Connection) -> int:
    """Insert all tax-domain nodes. Returns count inserted."""
    all_nodes = TAX_TYPE_NODES + TAX_OBLIGATION_NODES + TAX_DEADLINE_NODES
    for node in all_nodes:
        await _upsert_node(
            conn,
            entity_id=node["entity_id"],
            entity_type=node["entity_type"],
            name=node["name"],
            properties=node["properties"],
            source_chunk_ids=["phase1_tax_extraction"],
        )
    logger.info("Tax nodes inserted: %d", len(all_nodes))
    return len(all_nodes)


async def populate_tax_edges(conn: asyncpg.Connection) -> int:
    """Insert all tax-domain edges. Returns count inserted."""
    for edge in TAX_EDGES:
        await _upsert_edge(
            conn,
            source_id=edge["source"],
            target_id=edge["target"],
            rel_type=edge["type"],
            properties=edge.get("properties"),
            confidence=1.0,
            source_chunk_ids=["phase1_tax_extraction"],
        )
    logger.info("Tax edges inserted: %d", len(TAX_EDGES))
    return len(TAX_EDGES)


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED RUNNER
# ═══════════════════════════════════════════════════════════════════════════════


async def run_phase1(
    conn: asyncpg.Connection,
    dry_run: bool = False,
    phase: str = "all",
) -> dict[str, int]:
    """
    Execute Phase 1 population for property and/or tax domains.

    Args:
        conn: asyncpg connection (caller manages transaction).
        dry_run: If True, log what would be inserted but skip DB writes.
        phase: One of "property", "tax", or "all".

    Returns:
        Dict with counts: {"property_nodes": N, "property_edges": N, ...}
    """
    results: dict[str, int] = {}

    if phase in ("property", "all"):
        if dry_run:
            p_nodes = PROPERTY_TYPE_NODES + PROPERTY_CONCEPT_NODES + PROPERTY_FEE_NODES
            results["property_nodes"] = len(p_nodes)
            results["property_edges"] = len(PROPERTY_EDGES)
            logger.info(
                "[DRY-RUN] Would insert %d property nodes, %d property edges",
                results["property_nodes"],
                results["property_edges"],
            )
        else:
            results["property_nodes"] = await populate_property_nodes(conn)
            results["property_edges"] = await populate_property_edges(conn)

    if phase in ("tax", "all"):
        if dry_run:
            t_nodes = TAX_TYPE_NODES + TAX_OBLIGATION_NODES + TAX_DEADLINE_NODES
            results["tax_nodes"] = len(t_nodes)
            results["tax_edges"] = len(TAX_EDGES)
            logger.info(
                "[DRY-RUN] Would insert %d tax nodes, %d tax edges",
                results["tax_nodes"],
                results["tax_edges"],
            )
        else:
            results["tax_nodes"] = await populate_tax_nodes(conn)
            results["tax_edges"] = await populate_tax_edges(conn)

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


async def _main(args: argparse.Namespace) -> None:
    """Async entry point: connect to DB and run population."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set — aborting.")
        sys.exit(1)

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    assert pool is not None

    try:
        async with pool.acquire() as conn:
            results = await run_phase1(conn, dry_run=args.dry_run, phase=args.phase)
            logger.info("Phase 1 results: %s", results)
    finally:
        await pool.close()


def main() -> None:
    """CLI entry point with --phase, --dry-run, --limit args."""
    parser = argparse.ArgumentParser(
        description="KG Phase 1: Populate property + tax nodes/edges",
    )
    parser.add_argument(
        "--phase",
        choices=["property", "tax", "all"],
        default="all",
        help="Which domain to populate (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without writing to DB",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max items to process (0 = unlimited, reserved for future batching)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info(
        "Starting KG Phase 1 — phase=%s dry_run=%s limit=%d",
        args.phase,
        args.dry_run,
        args.limit,
    )

    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
