"""
KG Property + Tax Population Script
====================================

Phase 1: Convert hardcoded data from subgraph files into kg_nodes/kg_edges.
Phase 2: LLM extraction from Qdrant collections for cross-domain relationships.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/kg_populate_property_tax.py --phase all                    # Phase 1
    PYTHONPATH=. python scripts/kg_populate_property_tax.py --phase all --dry-run           # Phase 1 dry-run
    PYTHONPATH=. python scripts/kg_populate_property_tax.py --enrich --limit 10             # Phase 2 (10 chunks)
    PYTHONPATH=. python scripts/kg_populate_property_tax.py --enrich --limit 10 --dry-run   # Phase 2 dry-run

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
    source_chunk_ids = (
        SELECT array_agg(DISTINCT elem)
        FROM unnest(
            COALESCE(kg_nodes.source_chunk_ids, ARRAY[]::text[]) || $5
        ) elem
    ),
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
            "requirements": [
                "KITAS/KITAP holder",
                "Notary deed",
                "Land certificate check (BPN)",
                "Pay BPHTB (5% tax)",
            ],
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
            "requirements": ["Indonesian citizen or Indonesian legal entity only"],
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
            "requirements": ["Indonesian citizen only"],
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
            "requirements": [
                "Rental agreement",
                "Passport copy",
                "Deposit (usually 2-3 months rent)",
            ],
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
# PHASE 2 — QDRANT LLM ENRICHMENT
# ═══════════════════════════════════════════════════════════════════════════════

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")

# Entity types we want the LLM to extract
PROPERTY_ENTITY_TYPES = """
- property_type: Types of land/property ownership (e.g., Hak Pakai, HGB, Hak Milik, rental)
- ownership_right: Certificate types (SHM, HGB certificate, Girik)
- government_fee: Official government fees (BPHTB, PNBP, notary fees)
- concept: Requirements, processes, or conditions (e.g., BPN check, notary deed)
"""

TAX_ENTITY_TYPES = """
- tax_type: Types of tax (PPh Badan, PPh 21, PPh 23, PPh 26, PPN)
- tax_obligation: Filing/registration obligations (NPWP, PKP, SPT, monthly filing)
- government_fee: Official tax fees or penalties
- concept: Deadlines, thresholds, or conditions
"""

PROPERTY_RELATIONSHIP_TYPES = """
- ALLOWS_OWNERSHIP: Who can own this property type (source=property_type, target=concept)
- HAS_REQUIREMENT: What documents/conditions needed (source=property_type, target=concept)
- REQUIRES_ENTITY: What company type needed (source=property_type, target=company type)
- HAS_FEE: What government fees apply (source=property_type, target=government_fee)
- REQUIRES: Sequential prerequisite (source=step, target=next_step)
- REFERENCES: Legal reference between regulations
"""

TAX_RELATIONSHIP_TYPES = """
- HAS_TAX: What taxes apply to entity type (source=company type, target=tax_type)
- HAS_DEADLINE: Filing deadlines (source=tax_type, target=concept)
- HAS_FEE: Penalty or fee amounts (source=tax_obligation, target=government_fee)
- REQUIRES: Sequential prerequisite (source=obligation, target=next_obligation)
- REFERENCES: Legal reference between regulations
"""

EXTRACTION_PROMPT_TEMPLATE = """You are a knowledge graph extraction system. Extract entities and relationships from the text below.

ENTITY TYPES:
{entity_types}

RELATIONSHIP TYPES:
{relationship_types}

RULES:
1. entity_id MUST use format "type:canonical_name" (example: "tax_type:pph_21", "property_type:hak_pakai")
2. entity_type MUST be one of the types listed above (tax_type, tax_obligation, property_type, ownership_right, government_fee, concept)
3. name is the human-readable label
4. strength: 1.0 for explicit statements, 0.7-0.9 for implied
5. evidence: quote the text that supports each relationship

EXAMPLE OUTPUT:
{{"entities": [{{"entity_id": "tax_type:pph_21", "entity_type": "tax_type", "name": "PPh 21 Employee Withholding", "properties": {{"rate": 0.05}}}}], "relationships": [{{"source": "company:pt_pma", "target": "tax_type:pph_21", "type": "HAS_TAX", "strength": 1.0, "evidence": "PT PMA must withhold PPh 21"}}]}}

TEXT:
{text}
"""

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "entity_type": {"type": "string"},
                    "name": {"type": "string"},
                    "properties": {"type": "object"},
                },
                "required": ["entity_id", "entity_type", "name"],
            },
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "type": {"type": "string"},
                    "strength": {"type": "number"},
                    "evidence": {"type": "string"},
                },
                "required": ["source", "target", "type"],
            },
        },
    },
    "required": ["entities", "relationships"],
}


async def _query_qdrant_chunks(
    collection: str,
    keywords: list[str],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Scroll Qdrant collection and filter chunks locally by keyword relevance.

    No full-text index required — scrolls through points and picks those
    containing at least one keyword in their text.
    """
    import httpx

    chunks: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    offset: str | None = None
    batch_size = 50  # Scroll batch size
    max_scrolls = 20  # Safety limit: 20 * 50 = 1000 points max

    keywords_lower = [k.lower() for k in keywords]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for _ in range(max_scrolls):
            if len(chunks) >= limit:
                break

            body: dict[str, Any] = {"limit": batch_size, "with_payload": True}
            if offset:
                body["offset"] = offset

            resp = await client.post(
                f"{QDRANT_URL}/collections/{collection}/points/scroll",
                json=body,
            )
            if resp.status_code != 200:
                logger.warning("Qdrant scroll failed for %s: %s", collection, resp.status_code)
                break

            result = resp.json().get("result", {})
            points = result.get("points", [])
            next_offset = result.get("next_page_offset")

            for point in points:
                if len(chunks) >= limit:
                    break

                pid = str(point["id"])
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)

                text = point.get("payload", {}).get("text", "")
                metadata = point.get("payload", {}).get("metadata", {})

                # Skip short chunks
                if len(text) < 100:
                    continue

                # Check keyword relevance
                text_lower = text.lower()
                if any(kw in text_lower for kw in keywords_lower):
                    chunks.append({
                        "id": pid,
                        "text": text[:3000],
                        "source": metadata.get("source", "unknown"),
                        "category": metadata.get("category", ""),
                    })

            if not next_offset or not points:
                break
            offset = next_offset

    logger.info("Fetched %d keyword-matched chunks from %s (scanned %d points)", len(chunks), collection, len(seen_ids))
    return chunks


async def _extract_with_ollama(
    text: str,
    domain: str,
    entity_types: str,
    relationship_types: str,
) -> dict[str, list] | None:
    """Extract entities and relationships from text using Ollama gemma4:26b."""
    try:
        from backend.llm.ollama_client import ollama_chat_kg
    except ImportError:
        logger.warning("ollama_client not importable — skipping LLM extraction")
        return None

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        domain=domain,
        entity_types=entity_types,
        relationship_types=relationship_types,
        text=text,
    )

    # Use gemma4:26b MoE with extended timeout for quality extraction
    result = await ollama_chat_kg(prompt, EXTRACTION_SCHEMA, model="gemma4:26b", timeout=120.0)
    if not result:
        return None

    # Strip markdown code fences if present
    cleaned = result.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        parsed = json.loads(cleaned)
        # Handle various LLM output formats
        if isinstance(parsed, list):
            # LLM wrapped output in array — take first element if it's a dict
            parsed = parsed[0] if parsed and isinstance(parsed[0], dict) else {"entities": [], "relationships": []}
        if not isinstance(parsed, dict):
            logger.warning("LLM returned unexpected type: %s", type(parsed).__name__)
            return None
        entities = parsed.get("entities", [])
        relationships = parsed.get("relationships", [])
        if not isinstance(entities, list):
            entities = []
        if not isinstance(relationships, list):
            relationships = []
        return {"entities": entities, "relationships": relationships}
    except (json.JSONDecodeError, IndexError, KeyError) as e:
        logger.warning("LLM returned invalid JSON: %s", e)
        return None


async def _safe_upsert_extraction(
    conn: asyncpg.Connection,
    entities: list[dict],
    relationships: list[dict],
    chunk_id: str,
    dry_run: bool,
) -> tuple[int, int]:
    """Upsert extracted entities and edges with savepoint isolation.

    Each insert uses a savepoint so FK violations (from LLM-generated
    entity_ids that don't match existing nodes) don't abort the connection.

    Returns (nodes_inserted, edges_inserted).
    """
    if dry_run:
        return len(entities), len(relationships)

    nodes_ok = 0
    edges_ok = 0

    # Insert nodes first (edges reference them)
    for ent in entities:
        eid = ent.get("entity_id", "")
        etype = ent.get("entity_type", "")
        ename = ent.get("name", "")
        if not (eid and etype and ename):
            logger.debug("  Skipping entity with missing fields: %s", ent)
            continue
        try:
            async with conn.transaction():
                props = {**(ent.get("properties") or {}), "source_chunk": chunk_id}
                await _upsert_node(conn, eid, etype, ename, props)
                nodes_ok += 1
                logger.debug("  ✓ Node: %s (%s)", eid, ename)
        except Exception as e:
            logger.warning("  ⚠️ Node insert failed (%s): %s", eid, e)

    # Then insert edges
    for rel in relationships:
        src = rel.get("source", "")
        tgt = rel.get("target", "")
        rtype = rel.get("type", "")
        if not (src and tgt and rtype):
            continue
        try:
            async with conn.transaction():
                evidence = {"evidence": [rel.get("evidence", "")]}
                await _upsert_edge(
                    conn, src, tgt, rtype,
                    properties=evidence,
                    confidence=rel.get("strength", 0.8),
                    source_chunk_ids=[chunk_id],
                )
                edges_ok += 1
        except Exception as e:
            logger.warning("  ⚠️ Edge insert failed (%s→%s): %s", src, tgt, e)

    return nodes_ok, edges_ok


async def run_phase2(
    conn: asyncpg.Connection,
    limit: int = 10,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Phase 2: Extract entities/relationships from Qdrant chunks via LLM.

    Args:
        conn: asyncpg connection (caller manages transaction)
        limit: max chunks per domain to process
        dry_run: if True, extract but don't write to DB

    Returns:
        Stats dict with counts per domain
    """
    results: dict[str, Any] = {"dry_run": dry_run}

    # Property domain — query legal collection for property-related chunks
    property_keywords = [
        "hak pakai", "hak guna bangunan", "hak milik", "HGB",
        "BPHTB", "BPN", "property", "tanah", "bangunan",
        "sertifikat", "notaris", "PPJB", "pelepasan hak",
    ]
    property_chunks = await _query_qdrant_chunks(
        "legal_unified_hybrid_hybrid",
        property_keywords,
        limit=limit,
    )

    # Tax domain — query tax collection
    tax_keywords = [
        "PPh", "PPN", "NPWP", "pajak", "withholding",
        "SPT", "PKP", "tax", "corporate", "badan",
        "filing", "deadline", "penalty", "denda",
    ]
    tax_chunks = await _query_qdrant_chunks(
        "tax_genius_hybrid",
        tax_keywords,
        limit=limit,
    )

    total_nodes = 0
    total_edges = 0

    # Process property chunks
    for i, chunk in enumerate(property_chunks):
        logger.info(
            "🏠 Property chunk %d/%d (source=%s, %d chars)",
            i + 1, len(property_chunks), chunk["source"], len(chunk["text"]),
        )
        extraction = await _extract_with_ollama(
            chunk["text"], "property",
            PROPERTY_ENTITY_TYPES, PROPERTY_RELATIONSHIP_TYPES,
        )
        if not extraction:
            logger.warning("  ⚠️ No extraction result — skipping")
            continue

        entities = extraction.get("entities", [])
        relationships = extraction.get("relationships", [])
        logger.info("  → Extracted %d entities, %d relationships", len(entities), len(relationships))

        n, e = await _safe_upsert_extraction(conn, entities, relationships, chunk["id"], dry_run)
        total_nodes += n
        total_edges += e

    results["property"] = {
        "chunks_processed": len(property_chunks),
        "nodes": total_nodes,
        "edges": total_edges,
    }

    # Reset counters for tax
    tax_nodes = 0
    tax_edges = 0

    for i, chunk in enumerate(tax_chunks):
        logger.info(
            "🧾 Tax chunk %d/%d (source=%s, %d chars)",
            i + 1, len(tax_chunks), chunk["source"], len(chunk["text"]),
        )
        extraction = await _extract_with_ollama(
            chunk["text"], "tax",
            TAX_ENTITY_TYPES, TAX_RELATIONSHIP_TYPES,
        )
        if not extraction:
            logger.warning("  ⚠️ No extraction result — skipping")
            continue

        entities = extraction.get("entities", [])
        relationships = extraction.get("relationships", [])
        logger.info("  → Extracted %d entities, %d relationships", len(entities), len(relationships))

        n, e = await _safe_upsert_extraction(conn, entities, relationships, chunk["id"], dry_run)
        tax_nodes += n
        tax_edges += e

    results["tax"] = {
        "chunks_processed": len(tax_chunks),
        "nodes": tax_nodes,
        "edges": tax_edges,
    }

    prefix = "[DRY-RUN] Would insert" if dry_run else "Inserted"
    logger.info(
        "📊 Phase 2 %s: Property(%d nodes, %d edges from %d chunks), Tax(%d nodes, %d edges from %d chunks)",
        prefix,
        results["property"]["nodes"], results["property"]["edges"], results["property"]["chunks_processed"],
        results["tax"]["nodes"], results["tax"]["edges"], results["tax"]["chunks_processed"],
    )

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
            if args.enrich:
                # Phase 2: no outer transaction — each upsert is independent
                # (FK violations on LLM-generated entity_ids are expected and skipped)
                results = await run_phase2(
                    conn, limit=args.limit or 10, dry_run=args.dry_run,
                )
                logger.info("Phase 2 results: %s", results)
            else:
                # Phase 1: single transaction — all hardcoded data or nothing
                async with conn.transaction():
                    results = await run_phase1(conn, dry_run=args.dry_run, phase=args.phase)
                    logger.info("Phase 1 results: %s", results)
    finally:
        await pool.close()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="KG Population: Property + Tax nodes/edges",
    )
    parser.add_argument(
        "--phase",
        choices=["property", "tax", "all"],
        default="all",
        help="Phase 1: which domain to populate (default: all)",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Run Phase 2: LLM extraction from Qdrant collections",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without writing to DB",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Phase 2: max chunks per domain to process (default: 10)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.enrich:
        logger.info("Starting KG Phase 2 — enrich from Qdrant, limit=%d, dry_run=%s", args.limit, args.dry_run)
    else:
        logger.info("Starting KG Phase 1 — phase=%s dry_run=%s", args.phase, args.dry_run)

    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
