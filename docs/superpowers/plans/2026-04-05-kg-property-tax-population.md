# KG Property + Tax Population Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate the Knowledge Graph with Property and Tax domain entities, then rewire the subgraphs to query KG with hardcoded fallback.

**Architecture:** Three-phase approach — (1) deterministic extraction from hardcoded data already in subgraph files into `kg_nodes`/`kg_edges`, (2) targeted LLM extraction from Qdrant collections, (3) rewire subgraph nodes to query KG first. All changes use existing `KnowledgeGraphRepository` patterns.

**Tech Stack:** Python 3.11, asyncpg, PostgreSQL (kg_nodes/kg_edges), Qdrant (tax_genius_hybrid, legal_unified_hybrid_hybrid), Ollama qwen3.5:27b (test extraction), LangGraph StateGraph

**Spec:** `docs/superpowers/specs/2026-04-05-kg-property-tax-gap-analysis-design.md`

**Working directory:** `apps/backend-rag/` with `.venv` activated

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `scripts/kg_populate_property_tax.py` | CREATE | Phase 1 (hardcoded→KG) + Phase 2 (Qdrant enrichment) extraction script |
| `backend/tests/services/rag/test_kg_property_tax_population.py` | CREATE | Tests for extraction logic + rewired subgraph nodes |
| `backend/services/rag/kg_subgraph_property.py` | MODIFY (lines 485-498) | KG queries in `get_property_requirements_node`, `kg_sources_used` in synthesize |
| `backend/services/rag/kg_subgraph_tax.py` | MODIFY (lines 114-224, 312-436) | KG queries in `get_tax_obligations_node`, `kg_sources_used` in synthesize |

---

### Task 1: Phase 1 Extraction Script — Property Nodes

**Files:**
- Create: `scripts/kg_populate_property_tax.py`
- Test: `backend/tests/services/rag/test_kg_property_tax_population.py`

- [ ] **Step 1: Write the test for property node insertion**

Create `backend/tests/services/rag/test_kg_property_tax_population.py`:

```python
"""Tests for KG Property + Tax population script."""

import json
from unittest.mock import AsyncMock, MagicMock, call

import pytest


# ---------------------------------------------------------------------------
# Helpers: mock asyncpg pool + connection
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Mock asyncpg pool returning a mock connection via acquire()."""
    pool = MagicMock()
    conn = AsyncMock()

    class _Ctx:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, *a):
            pass

    pool.acquire = MagicMock(return_value=_Ctx())
    # Also support pool.acquire() as async context AND conn as transaction
    conn.transaction = MagicMock(return_value=_Ctx())
    return pool, conn


# ---------------------------------------------------------------------------
# Phase 1 — Property
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_populate_property_nodes(mock_db):
    """Phase 1 inserts 4 property_type nodes into kg_nodes."""
    from scripts.kg_populate_property_tax import populate_property_nodes

    pool, conn = mock_db
    stats = await populate_property_nodes(conn)

    assert stats["nodes_inserted"] == 4
    assert stats["domain"] == "property"

    # Verify conn.execute was called for each node
    insert_calls = [
        c for c in conn.execute.call_args_list
        if "kg_nodes" in str(c)
    ]
    assert len(insert_calls) >= 4

    # Verify entity_id format
    first_call_args = insert_calls[0].args
    entity_id = first_call_args[1]  # $1 = entity_id
    assert "property_type:" in entity_id


@pytest.mark.asyncio
async def test_populate_property_edges(mock_db):
    """Phase 1 inserts property edges (ALLOWS_OWNERSHIP, HAS_REQUIREMENT, etc.)."""
    from scripts.kg_populate_property_tax import populate_property_edges

    pool, conn = mock_db
    stats = await populate_property_edges(conn)

    assert stats["edges_inserted"] >= 10  # At minimum: 4 ownership + 4 requirement + cross-domain
    assert stats["domain"] == "property"

    # Verify ALLOWS_OWNERSHIP edge exists
    edge_calls = [
        c for c in conn.execute.call_args_list
        if "kg_edges" in str(c)
    ]
    assert len(edge_calls) >= 10
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_property_tax_population.py::test_populate_property_nodes -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.kg_populate_property_tax'`

- [ ] **Step 3: Write the Phase 1 property extraction functions**

Create `scripts/kg_populate_property_tax.py`:

```python
"""
KG Population Script — Property + Tax Domains

Phase 1: Convert hardcoded data from kg_subgraph_property.py and kg_subgraph_tax.py
         into kg_nodes/kg_edges (deterministic, zero LLM cost).
Phase 2: Targeted LLM extraction from Qdrant collections (requires --phase 2 flag).

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/kg_populate_property_tax.py --phase 1
    PYTHONPATH=. python scripts/kg_populate_property_tax.py --phase 2 --limit 10
    PYTHONPATH=. python scripts/kg_populate_property_tax.py --phase 1 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

import asyncpg

logger = logging.getLogger(__name__)

# ============================================================================
# Entity/Edge definitions — Property domain
# ============================================================================

PROPERTY_TYPE_NODES: list[dict] = [
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
        },
    },
]

PROPERTY_CONCEPT_NODES: list[dict] = [
    {"entity_id": "concept:foreigner", "entity_type": "concept", "name": "Foreign National"},
    {"entity_id": "concept:indonesian_citizen", "entity_type": "concept", "name": "Indonesian Citizen"},
    {"entity_id": "concept:kitas_or_kitap", "entity_type": "concept", "name": "KITAS or KITAP Holder"},
    {"entity_id": "concept:notary_deed", "entity_type": "concept", "name": "Notary Deed Execution"},
    {"entity_id": "concept:bpn_certificate_check", "entity_type": "concept", "name": "BPN Certificate Check (Due Diligence)"},
    {"entity_id": "concept:ppjb_agreement", "entity_type": "concept", "name": "PPJB (Sale & Purchase Agreement)"},
    {"entity_id": "concept:bpn_registration", "entity_type": "concept", "name": "BPN Land Office Registration"},
    {"entity_id": "government_fee:bphtb_5pct", "entity_type": "government_fee", "name": "BPHTB Tax (5% of transaction value)"},
]

PROPERTY_EDGES: list[dict] = [
    # Ownership rights
    {"source": "property_type:hak_pakai", "target": "concept:foreigner", "type": "ALLOWS_OWNERSHIP", "strength": 1.0, "evidence": "PP 18/2021 — foreigners may hold Hak Pakai"},
    {"source": "property_type:hak_pakai", "target": "concept:indonesian_citizen", "type": "ALLOWS_OWNERSHIP", "strength": 1.0, "evidence": "Hak Pakai available to all"},
    {"source": "property_type:hak_milik", "target": "concept:indonesian_citizen", "type": "ALLOWS_OWNERSHIP", "strength": 1.0, "evidence": "Hak Milik restricted to WNI"},
    {"source": "property_type:rental", "target": "concept:foreigner", "type": "ALLOWS_OWNERSHIP", "strength": 1.0, "evidence": "Rental available to all"},
    # Requirements
    {"source": "property_type:hak_pakai", "target": "concept:kitas_or_kitap", "type": "HAS_REQUIREMENT", "strength": 1.0, "evidence": "KITAS/KITAP required for Hak Pakai"},
    {"source": "property_type:hak_pakai", "target": "concept:notary_deed", "type": "HAS_REQUIREMENT", "strength": 1.0, "evidence": "Notary deed required for Hak Pakai transfer"},
    {"source": "property_type:hak_pakai", "target": "concept:bpn_certificate_check", "type": "HAS_REQUIREMENT", "strength": 0.9, "evidence": "Due diligence at BPN recommended"},
    {"source": "property_type:hak_pakai", "target": "government_fee:bphtb_5pct", "type": "HAS_FEE", "strength": 1.0, "evidence": "BPHTB 5% payable on transfer"},
    # Cross-domain: HGB requires PT PMA for foreigners
    {"source": "property_type:hgb", "target": "company:pt_pma", "type": "REQUIRES_ENTITY", "strength": 0.9, "evidence": "Foreigners acquire HGB through PT PMA legal entity"},
    {"source": "property_type:hgb", "target": "government_fee:bphtb_5pct", "type": "HAS_FEE", "strength": 1.0, "evidence": "BPHTB 5% payable on transfer"},
    {"source": "property_type:hak_milik", "target": "government_fee:bphtb_5pct", "type": "HAS_FEE", "strength": 1.0, "evidence": "BPHTB 5% payable on transfer"},
    # Workflow chain
    {"source": "concept:bpn_certificate_check", "target": "concept:ppjb_agreement", "type": "REQUIRES", "strength": 0.8, "evidence": "Due diligence before signing PPJB"},
    {"source": "concept:ppjb_agreement", "target": "concept:notary_deed", "type": "REQUIRES", "strength": 0.9, "evidence": "PPJB precedes notary execution"},
    {"source": "concept:notary_deed", "target": "concept:bpn_registration", "type": "REQUIRES", "strength": 1.0, "evidence": "Notary deed required for BPN registration"},
]


# ============================================================================
# Upsert helpers (mirror KnowledgeGraphRepository pattern)
# ============================================================================

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


async def _upsert_node(conn: asyncpg.Connection, node: dict) -> None:
    """Insert or update a single KG node."""
    await conn.execute(
        _UPSERT_NODE_SQL,
        node["entity_id"],
        node["entity_type"],
        node["name"],
        json.dumps(node.get("properties", {})),
        ["kg_populate_property_tax"],  # source_chunk_ids
    )


async def _upsert_edge(conn: asyncpg.Connection, edge: dict) -> None:
    """Insert or update a single KG edge."""
    rel_id = f"{edge['source']}_{edge['type']}_{edge['target']}"
    properties = {
        "evidence": [edge.get("evidence", "")],
        "source_references": [{"script": "kg_populate_property_tax"}],
    }
    await conn.execute(
        _UPSERT_EDGE_SQL,
        rel_id,
        edge["source"],
        edge["target"],
        edge["type"],
        json.dumps(properties),
        edge.get("strength", 0.9),
        ["kg_populate_property_tax"],  # source_chunk_ids
    )


# ============================================================================
# Phase 1 — Property
# ============================================================================

async def populate_property_nodes(conn: asyncpg.Connection) -> dict:
    """Insert property_type + concept nodes into kg_nodes."""
    all_nodes = PROPERTY_TYPE_NODES + PROPERTY_CONCEPT_NODES
    for node in all_nodes:
        await _upsert_node(conn, node)
    logger.info(f"✅ Property: {len(all_nodes)} nodes upserted")
    return {"nodes_inserted": len(PROPERTY_TYPE_NODES), "domain": "property"}


async def populate_property_edges(conn: asyncpg.Connection) -> dict:
    """Insert property edges into kg_edges."""
    for edge in PROPERTY_EDGES:
        await _upsert_edge(conn, edge)
    logger.info(f"✅ Property: {len(PROPERTY_EDGES)} edges upserted")
    return {"edges_inserted": len(PROPERTY_EDGES), "domain": "property"}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_property_tax_population.py::test_populate_property_nodes backend/tests/services/rag/test_kg_property_tax_population.py::test_populate_property_edges -v
```

Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/kg_populate_property_tax.py backend/tests/services/rag/test_kg_property_tax_population.py
git commit -m "feat(kg): Phase 1 property node/edge extraction script with tests"
```

---

### Task 2: Phase 1 Extraction Script — Tax Nodes

**Files:**
- Modify: `scripts/kg_populate_property_tax.py`
- Modify: `backend/tests/services/rag/test_kg_property_tax_population.py`

- [ ] **Step 1: Write the test for tax node insertion**

Append to `backend/tests/services/rag/test_kg_property_tax_population.py`:

```python
# ---------------------------------------------------------------------------
# Phase 1 — Tax
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_populate_tax_nodes(mock_db):
    """Phase 1 inserts 5 tax_type + 5 tax_obligation nodes."""
    from scripts.kg_populate_property_tax import populate_tax_nodes

    pool, conn = mock_db
    stats = await populate_tax_nodes(conn)

    assert stats["nodes_inserted"] == 10  # 5 tax_type + 5 tax_obligation
    assert stats["domain"] == "tax"


@pytest.mark.asyncio
async def test_populate_tax_edges(mock_db):
    """Phase 1 inserts tax edges (HAS_TAX, HAS_DEADLINE, etc.)."""
    from scripts.kg_populate_property_tax import populate_tax_edges

    pool, conn = mock_db
    stats = await populate_tax_edges(conn)

    assert stats["edges_inserted"] >= 8  # pt_pma→4 taxes, cv→2 taxes, deadlines
    assert stats["domain"] == "tax"


@pytest.mark.asyncio
async def test_cross_domain_edges(mock_db):
    """Phase 1 creates cross-domain edges (property→company→tax)."""
    from scripts.kg_populate_property_tax import populate_property_edges, populate_tax_edges

    pool, conn = mock_db
    prop_stats = await populate_property_edges(conn)
    tax_stats = await populate_tax_edges(conn)

    # Verify cross-domain: property_type:hgb → REQUIRES_ENTITY → company:pt_pma
    all_calls = [str(c) for c in conn.execute.call_args_list]
    has_cross_domain = any(
        "property_type:hgb" in c and "company:pt_pma" in c
        for c in all_calls
    )
    assert has_cross_domain, "Missing cross-domain edge: hgb → pt_pma"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_property_tax_population.py::test_populate_tax_nodes -v
```

Expected: FAIL with `ImportError: cannot import name 'populate_tax_nodes'`

- [ ] **Step 3: Add tax node/edge definitions and functions to the script**

Append to `scripts/kg_populate_property_tax.py` (after property section, before `if __name__`):

```python
# ============================================================================
# Entity/Edge definitions — Tax domain
# ============================================================================

TAX_TYPE_NODES: list[dict] = [
    {
        "entity_id": "tax_type:pph_badan",
        "entity_type": "tax_type",
        "name": "PPh Badan (Corporate Income Tax)",
        "properties": {
            "rate": 0.22,
            "description": "Corporate Income Tax",
            "filing_deadline": "4 months after fiscal year end",
            "monthly_installment": "PPh 25 (estimated tax)",
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
            "note": "May be reduced by tax treaty",
        },
    },
    {
        "entity_id": "tax_type:ppn",
        "entity_type": "tax_type",
        "name": "PPN (Value Added Tax)",
        "properties": {
            "rate": 0.11,
            "description": "Value Added Tax — 11% standard rate (verified 2026-02-09)",
            "filing_deadline": "End of following month",
            "threshold": 4_800_000_000,
        },
    },
]

TAX_OBLIGATION_NODES: list[dict] = [
    {
        "entity_id": "tax_obligation:npwp_registration",
        "entity_type": "tax_obligation",
        "name": "NPWP Registration (Tax ID)",
        "properties": {
            "processing_time": "1-3 days",
            "system": "DJP Online (Direktorat Jenderal Pajak)",
            "requirement": "Mandatory for all businesses",
        },
    },
    {
        "entity_id": "tax_obligation:pkp_registration",
        "entity_type": "tax_obligation",
        "name": "PKP Registration (VAT Taxable Entrepreneur)",
        "properties": {
            "processing_time": "7-14 days",
            "system": "DJP Online",
            "requirement": "Revenue > 4.8B IDR annually",
        },
    },
    {
        "entity_id": "tax_obligation:bookkeeping_setup",
        "entity_type": "tax_obligation",
        "name": "Bookkeeping System Setup",
        "properties": {
            "requirement": "Required for all business entities",
            "software": "E.g., Jurnal, Accurate, or custom",
        },
    },
    {
        "entity_id": "tax_obligation:monthly_filing",
        "entity_type": "tax_obligation",
        "name": "Monthly Tax Filing",
        "properties": {
            "filings": ["PPh 21", "PPh 23", "PPh 25", "PPN"],
            "deadline_withholding": "20th of following month",
            "deadline_vat": "End of following month",
        },
    },
    {
        "entity_id": "tax_obligation:annual_spt",
        "entity_type": "tax_obligation",
        "name": "Annual Tax Return (SPT Tahunan)",
        "properties": {
            "deadline_corporate": "4 months after fiscal year end",
            "deadline_personal": "March 31 of following year",
            "requirement": "Audited financial statements for revenue > 50B IDR",
        },
    },
]

TAX_DEADLINE_NODES: list[dict] = [
    {"entity_id": "concept:20th_following_month", "entity_type": "concept", "name": "20th of Following Month"},
    {"entity_id": "concept:end_following_month", "entity_type": "concept", "name": "End of Following Month"},
]

TAX_EDGES: list[dict] = [
    # PT PMA tax obligations
    {"source": "company:pt_pma", "target": "tax_type:pph_badan", "type": "HAS_TAX", "strength": 1.0, "evidence": "PT PMA subject to 22% corporate income tax"},
    {"source": "company:pt_pma", "target": "tax_type:pph_21", "type": "HAS_TAX", "strength": 1.0, "evidence": "PT PMA must withhold PPh 21 on employee salaries"},
    {"source": "company:pt_pma", "target": "tax_type:pph_23", "type": "HAS_TAX", "strength": 1.0, "evidence": "PT PMA must withhold PPh 23 on services/rent"},
    {"source": "company:pt_pma", "target": "tax_type:pph_26", "type": "HAS_TAX", "strength": 1.0, "evidence": "PT PMA must withhold PPh 26 on foreign payments"},
    # CV tax obligations
    {"source": "company:cv", "target": "tax_type:pph_badan", "type": "HAS_TAX", "strength": 1.0, "evidence": "CV taxed as corporate entity at 22%"},
    {"source": "company:cv", "target": "tax_type:ppn", "type": "HAS_TAX", "strength": 0.8, "evidence": "CV subject to PPN if revenue > 4.8B IDR"},
    # Deadlines
    {"source": "tax_type:pph_21", "target": "concept:20th_following_month", "type": "HAS_DEADLINE", "strength": 1.0, "evidence": "PPh 21 filing deadline: 20th of following month"},
    {"source": "tax_type:pph_23", "target": "concept:20th_following_month", "type": "HAS_DEADLINE", "strength": 1.0, "evidence": "PPh 23 filing deadline: 20th of following month"},
    {"source": "tax_type:pph_26", "target": "concept:20th_following_month", "type": "HAS_DEADLINE", "strength": 1.0, "evidence": "PPh 26 filing deadline: 20th of following month"},
    {"source": "tax_type:ppn", "target": "concept:end_following_month", "type": "HAS_DEADLINE", "strength": 1.0, "evidence": "PPN filing deadline: end of following month"},
    # Obligation sequence
    {"source": "tax_obligation:npwp_registration", "target": "tax_obligation:pkp_registration", "type": "REQUIRES", "strength": 0.8, "evidence": "NPWP required before PKP registration"},
    {"source": "tax_obligation:pkp_registration", "target": "tax_obligation:bookkeeping_setup", "type": "REQUIRES", "strength": 0.7, "evidence": "PKP requires bookkeeping system"},
    {"source": "tax_obligation:bookkeeping_setup", "target": "tax_obligation:monthly_filing", "type": "REQUIRES", "strength": 0.9, "evidence": "Bookkeeping enables monthly filing"},
    {"source": "tax_obligation:monthly_filing", "target": "tax_obligation:annual_spt", "type": "REQUIRES", "strength": 0.9, "evidence": "Monthly filings feed annual SPT"},
]


# ============================================================================
# Phase 1 — Tax
# ============================================================================

async def populate_tax_nodes(conn: asyncpg.Connection) -> dict:
    """Insert tax_type + tax_obligation + deadline nodes into kg_nodes."""
    all_nodes = TAX_TYPE_NODES + TAX_OBLIGATION_NODES + TAX_DEADLINE_NODES
    for node in all_nodes:
        await _upsert_node(conn, node)
    # Count only domain-specific nodes (not deadline concepts)
    domain_count = len(TAX_TYPE_NODES) + len(TAX_OBLIGATION_NODES)
    logger.info(f"✅ Tax: {len(all_nodes)} nodes upserted ({domain_count} domain-specific)")
    return {"nodes_inserted": domain_count, "domain": "tax"}


async def populate_tax_edges(conn: asyncpg.Connection) -> dict:
    """Insert tax edges into kg_edges."""
    for edge in TAX_EDGES:
        await _upsert_edge(conn, edge)
    logger.info(f"✅ Tax: {len(TAX_EDGES)} edges upserted")
    return {"edges_inserted": len(TAX_EDGES), "domain": "tax"}
```

- [ ] **Step 4: Run all Phase 1 tests**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_property_tax_population.py -v -k "phase" --no-header
```

Expected: 5 PASSED (property nodes, property edges, tax nodes, tax edges, cross-domain)

- [ ] **Step 5: Commit**

```bash
git add scripts/kg_populate_property_tax.py backend/tests/services/rag/test_kg_property_tax_population.py
git commit -m "feat(kg): Phase 1 tax node/edge extraction + cross-domain tests"
```

---

### Task 3: Phase 1 CLI Runner + Dry-Run Mode

**Files:**
- Modify: `scripts/kg_populate_property_tax.py`
- Test: `backend/tests/services/rag/test_kg_property_tax_population.py`

- [ ] **Step 1: Write test for dry-run mode**

Append to test file:

```python
# ---------------------------------------------------------------------------
# CLI + dry-run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_phase1_dry_run(mock_db):
    """Dry-run mode logs but does not call conn.execute."""
    from scripts.kg_populate_property_tax import run_phase1

    pool, conn = mock_db
    stats = await run_phase1(conn, dry_run=True)

    assert stats["property"]["nodes_inserted"] == 4
    assert stats["tax"]["nodes_inserted"] == 10
    # In dry-run, execute is never called
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_run_phase1_real(mock_db):
    """Real mode calls conn.execute for all nodes and edges."""
    from scripts.kg_populate_property_tax import run_phase1

    pool, conn = mock_db
    stats = await run_phase1(conn, dry_run=False)

    assert stats["property"]["nodes_inserted"] == 4
    assert stats["tax"]["nodes_inserted"] == 10
    assert conn.execute.call_count > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_property_tax_population.py::test_run_phase1_dry_run -v
```

Expected: FAIL with `ImportError: cannot import name 'run_phase1'`

- [ ] **Step 3: Add run_phase1 function and CLI entry point**

Append to `scripts/kg_populate_property_tax.py`:

```python
# ============================================================================
# Phase 1 — Combined runner
# ============================================================================

async def run_phase1(conn: asyncpg.Connection, dry_run: bool = False) -> dict:
    """Run Phase 1: insert all hardcoded property + tax nodes/edges.

    Args:
        conn: asyncpg connection (caller manages transaction)
        dry_run: if True, count nodes/edges but skip DB writes

    Returns:
        dict with property and tax stats
    """
    if dry_run:
        prop_node_count = len(PROPERTY_TYPE_NODES)
        prop_edge_count = len(PROPERTY_EDGES)
        tax_node_count = len(TAX_TYPE_NODES) + len(TAX_OBLIGATION_NODES)
        tax_edge_count = len(TAX_EDGES)
        logger.info(
            f"🔍 DRY RUN — would insert: "
            f"Property({prop_node_count} nodes, {prop_edge_count} edges), "
            f"Tax({tax_node_count} nodes, {tax_edge_count} edges)"
        )
        return {
            "property": {"nodes_inserted": prop_node_count, "edges_inserted": prop_edge_count, "domain": "property"},
            "tax": {"nodes_inserted": tax_node_count, "edges_inserted": tax_edge_count, "domain": "tax"},
            "dry_run": True,
        }

    prop_nodes = await populate_property_nodes(conn)
    prop_edges = await populate_property_edges(conn)
    tax_nodes = await populate_tax_nodes(conn)
    tax_edges = await populate_tax_edges(conn)

    return {
        "property": {**prop_nodes, "edges_inserted": prop_edges["edges_inserted"]},
        "tax": {**tax_nodes, "edges_inserted": tax_edges["edges_inserted"]},
        "dry_run": False,
    }


# ============================================================================
# CLI entry point
# ============================================================================

async def main() -> None:
    parser = argparse.ArgumentParser(description="KG Population — Property + Tax")
    parser.add_argument("--phase", type=int, choices=[1, 2], default=1, help="Phase to run (1=hardcoded, 2=Qdrant)")
    parser.add_argument("--dry-run", action="store_true", help="Log what would be inserted without writing to DB")
    parser.add_argument("--limit", type=int, default=10, help="Phase 2: max Qdrant chunks per domain")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                if args.phase == 1:
                    stats = await run_phase1(conn, dry_run=args.dry_run)
                    logger.info(f"📊 Phase 1 complete: {json.dumps(stats, indent=2)}")
                elif args.phase == 2:
                    logger.info("Phase 2 not yet implemented — run Phase 1 first")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run all tests**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_property_tax_population.py -v
```

Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/kg_populate_property_tax.py backend/tests/services/rag/test_kg_property_tax_population.py
git commit -m "feat(kg): Phase 1 CLI runner with dry-run mode"
```

---

### Task 4: Rewire Property Subgraph

**Files:**
- Modify: `backend/services/rag/kg_subgraph_property.py` (lines 485-549)
- Test: `backend/tests/services/rag/test_kg_property_tax_population.py`

- [ ] **Step 1: Write test for KG-wired property requirements**

Append to test file:

```python
# ---------------------------------------------------------------------------
# Subgraph rewiring — Property
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_property_requirements_from_kg(mock_db):
    """get_property_requirements_node queries KG when db_pool provided."""
    from backend.services.rag.kg_subgraph_property import get_property_requirements_node

    pool, conn = mock_db
    conn.fetch = AsyncMock(return_value=[
        {
            "entity_id": "concept:kitas_or_kitap",
            "name": "KITAS or KITAP Holder",
            "properties": {},
            "relationship_type": "HAS_REQUIREMENT",
        },
        {
            "entity_id": "concept:notary_deed",
            "name": "Notary Deed Execution",
            "properties": {},
            "relationship_type": "HAS_REQUIREMENT",
        },
        {
            "entity_id": "government_fee:bphtb_5pct",
            "name": "BPHTB Tax (5%)",
            "properties": {"rate": "5%"},
            "relationship_type": "HAS_FEE",
        },
    ])

    state = {"property_type": "hak_pakai", "query": "buy hak pakai", "user_context": {}}
    result = await get_property_requirements_node(state, pool)

    assert result["kg_sources_used"] == 3
    assert len(result["property_requirements"]) == 3
    assert result["property_requirements"][0]["type"] == "HAS_REQUIREMENT"


@pytest.mark.asyncio
async def test_property_requirements_fallback(mock_db):
    """get_property_requirements_node falls back to hardcoded when KG is empty."""
    from backend.services.rag.kg_subgraph_property import get_property_requirements_node

    pool, conn = mock_db
    conn.fetch = AsyncMock(return_value=[])

    state = {"property_type": "hak_pakai", "query": "buy hak pakai", "user_context": {}}
    result = await get_property_requirements_node(state, pool)

    assert result["kg_sources_used"] == 0
    assert len(result["property_requirements"]) == 1
    assert result["property_requirements"][0]["requirement_type"] == "ownership"


@pytest.mark.asyncio
async def test_property_workflow_confidence_with_kg():
    """synthesize_property_workflow_node uses kg_sources_used for confidence."""
    from backend.services.rag.kg_subgraph_property import synthesize_property_workflow_node

    state = {"property_type": "hak_pakai", "kg_sources_used": 3}
    result = await synthesize_property_workflow_node(state)

    assert result["workflow"]["confidence_breakdown"]["has_db_validation"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_property_tax_population.py::test_property_requirements_from_kg -v
```

Expected: FAIL (current function doesn't return `kg_sources_used`)

- [ ] **Step 3: Rewire get_property_requirements_node**

In `backend/services/rag/kg_subgraph_property.py`, replace lines 485-498:

```python
async def get_property_requirements_node(state: Any, db_pool: Any = None) -> dict:
    """Legacy node: return ownership requirements for the property type in state.

    Queries KG for requirements via kg_nodes/kg_edges. Falls back to
    hardcoded _LEGACY_REQUIREMENTS_DB when KG returns no results.
    """
    prop_type: str = state.get("property_type", "unknown")
    requirements: list[dict] = []
    kg_sources = 0

    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT n.entity_id, n.name, n.properties, e.relationship_type
                    FROM kg_edges e
                    JOIN kg_nodes n ON e.target_entity_id = n.entity_id
                    WHERE e.source_entity_id = $1
                      AND e.relationship_type IN (
                          'HAS_REQUIREMENT', 'REQUIRES_ENTITY',
                          'ALLOWS_OWNERSHIP', 'HAS_FEE'
                      )
                    """,
                    f"property_type:{prop_type}",
                )

                if rows:
                    for row in rows:
                        requirements.append({
                            "type": row["relationship_type"],
                            "name": row["name"],
                            "details": row["properties"] or {},
                        })
                    kg_sources = len(rows)
                    logger.info(
                        f"✅ [Property/legacy] Got {kg_sources} requirements from KG for {prop_type}",
                    )
        except Exception as e:
            logger.warning(f"⚠️ [Property/legacy] KG query failed, using fallback: {e}")

    # Fallback to hardcoded if KG empty
    if not requirements:
        reqs = _LEGACY_REQUIREMENTS_DB.get(prop_type, {})
        requirements = [{"requirement_type": "ownership", "details": reqs}]
        logger.info(f"📌 [Property/legacy] Using fallback requirements for {prop_type}")

    return {
        "property_requirements": requirements,
        "kg_sources_used": kg_sources,
    }
```

- [ ] **Step 4: Rewire synthesize_property_workflow_node to use kg_sources_used**

In `backend/services/rag/kg_subgraph_property.py`, replace lines 531-536 (the `calculate_subgraph_confidence` call):

```python
    kg_sources = state.get("kg_sources_used", 0)
    breakdown = calculate_subgraph_confidence(
        workflow_source="property_subgraph",
        steps_count=len(steps),
        has_db_validation=kg_sources > 0,
        unique_sources=max(1, kg_sources),
    )
```

- [ ] **Step 5: Run all property rewiring tests**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_property_tax_population.py -v -k "property"
```

Expected: 5 PASSED (nodes, edges, from_kg, fallback, confidence)

- [ ] **Step 6: Run existing subgraph tests to verify no regression**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_subgraphs.py -v -k "property"
```

Expected: All existing property tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/rag/kg_subgraph_property.py backend/tests/services/rag/test_kg_property_tax_population.py
git commit -m "feat(kg): rewire property subgraph to query KG with hardcoded fallback"
```

---

### Task 5: Rewire Tax Subgraph

**Files:**
- Modify: `backend/services/rag/kg_subgraph_tax.py` (lines 114-224, 410-436)
- Test: `backend/tests/services/rag/test_kg_property_tax_population.py`

- [ ] **Step 1: Write test for KG-wired tax obligations**

Append to test file:

```python
# ---------------------------------------------------------------------------
# Subgraph rewiring — Tax
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tax_obligations_from_kg(mock_db):
    """get_tax_obligations_node queries KG when data is available."""
    from backend.services.rag.kg_subgraph_tax import get_tax_obligations_node

    pool, conn = mock_db
    conn.fetch = AsyncMock(return_value=[
        {
            "entity_id": "tax_type:pph_badan",
            "name": "PPh Badan (Corporate Income Tax)",
            "properties": {"rate": 0.22, "description": "Corporate Income Tax"},
        },
        {
            "entity_id": "tax_type:pph_21",
            "name": "PPh 21 (Employee Withholding)",
            "properties": {"description": "Withholding tax on employee salaries"},
        },
    ])

    state: dict = {
        "query": "tax obligations for PT PMA",
        "user_context": {},
        "business_entity_type": "pt_pma",
        "npwp_required": True,
        "vat_applicable": False,
        "tax_obligations": [],
    }

    result = await get_tax_obligations_node(state, pool)

    assert result["kg_sources_used"] == 2
    tax_overview = result["tax_obligations"][0]
    assert tax_overview["source"] == "knowledge_graph"
    assert "pph_badan" in tax_overview["details"]


@pytest.mark.asyncio
async def test_tax_obligations_fallback(mock_db):
    """get_tax_obligations_node falls back to hardcoded when KG is empty."""
    from backend.services.rag.kg_subgraph_tax import get_tax_obligations_node

    pool, conn = mock_db
    conn.fetch = AsyncMock(return_value=[])

    state: dict = {
        "query": "tax obligations",
        "user_context": {},
        "business_entity_type": "pt_pma",
        "npwp_required": True,
        "vat_applicable": True,
        "tax_obligations": [],
    }

    result = await get_tax_obligations_node(state, pool)

    assert result.get("kg_sources_used", 0) == 0
    tax_overview = result["tax_obligations"][0]
    assert tax_overview["source"] == "hardcoded_fallback"
    assert "pph_corporate" in tax_overview["details"]  # Hardcoded key name


@pytest.mark.asyncio
async def test_tax_workflow_confidence_with_kg():
    """synthesize_tax_workflow_node uses kg_sources_used for confidence."""
    from backend.services.rag.kg_subgraph_tax import synthesize_tax_workflow_node

    state: dict = {
        "query": "tax",
        "user_context": {},
        "business_entity_type": "pt_pma",
        "vat_applicable": False,
        "tax_obligations": [],
        "kg_sources_used": 4,
    }

    result = await synthesize_tax_workflow_node(state)

    assert result["workflow"]["confidence_breakdown"]["has_db_validation"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_property_tax_population.py::test_tax_obligations_from_kg -v
```

Expected: FAIL (current function doesn't query KG or return `kg_sources_used`)

- [ ] **Step 3: Rewire get_tax_obligations_node**

In `backend/services/rag/kg_subgraph_tax.py`, replace lines 114-224:

```python
async def get_tax_obligations_node(state: TaxState, db_pool: asyncpg.Pool) -> TaxState:
    """
    Get tax obligations based on entity type.

    Queries KG for tax obligations via HAS_TAX edges. Falls back to
    hardcoded tax_obligations_db when KG returns no results.
    """
    logger.info("📋 [Tax Subgraph] Getting tax obligations...")

    entity_type = state.get("business_entity_type", "unknown")
    kg_sources = 0

    # Hardcoded fallback data (kept as safety net)
    tax_obligations_db = {
        "pt_pma": {
            "pph_corporate": {
                "rate": 0.22,
                "description": "Corporate Income Tax (PPh Badan)",
                "filing_deadline": "4 months after fiscal year end",
                "monthly_installment": "PPh 25 (estimated tax)",
            },
            "pph_21": {
                "description": "Withholding tax on employee salaries",
                "progressive_rates": [
                    {"bracket": "0-60M", "rate": 0.05},
                    {"bracket": "60-250M", "rate": 0.15},
                    {"bracket": "250-500M", "rate": 0.25},
                    {"bracket": "500M+", "rate": 0.30},
                ],
                "filing_deadline": "20th of following month",
            },
            "pph_23": {
                "rate": 0.02,
                "description": "Withholding tax on services/rent",
                "filing_deadline": "20th of following month",
            },
            "pph_26": {
                "rate": 0.20,
                "description": "Withholding tax on payments to non-residents",
                "filing_deadline": "20th of following month",
                "note": "May be reduced by tax treaty",
            },
            "ppn": {
                "rate": 0.11,
                "description": "Value Added Tax",
                "filing_deadline": "End of following month",
                "threshold": 4_800_000_000,
            },
        },
        "cv": {
            "pph_corporate": {
                "rate": 0.22,
                "description": "Corporate Income Tax (CV is taxed as corporate entity)",
                "filing_deadline": "4 months after fiscal year end",
            },
            "ppn": {
                "rate": 0.11,
                "description": "Value Added Tax",
                "filing_deadline": "End of following month",
                "threshold": 4_800_000_000,
            },
        },
        "perorangan": {
            "pph_personal": {
                "description": "Personal Income Tax",
                "progressive_rates": [
                    {"bracket": "0-60M", "rate": 0.05},
                    {"bracket": "60-250M", "rate": 0.15},
                    {"bracket": "250-500M", "rate": 0.25},
                    {"bracket": "500M+", "rate": 0.30},
                ],
                "filing_deadline": "March 31 of following year",
            },
            "ppn": {
                "rate": 0.11,
                "description": "Value Added Tax (if revenue > 4.8B IDR)",
                "filing_deadline": "End of following month",
                "threshold": 4_800_000_000,
            },
        },
    }

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT n.entity_id, n.name, n.properties
                FROM kg_edges e
                JOIN kg_nodes n ON e.target_entity_id = n.entity_id
                WHERE e.source_entity_id = $1
                  AND e.relationship_type = 'HAS_TAX'
                """,
                f"company:{entity_type}",
            )

            if rows:
                obligations = {}
                for row in rows:
                    tax_id = row["entity_id"].split(":")[-1]
                    props = row["properties"] or {}
                    props["name"] = row["name"]
                    obligations[tax_id] = props

                # Filter VAT if not applicable
                if not state.get("vat_applicable", False):
                    obligations.pop("ppn", None)

                state.setdefault("tax_obligations", []).append({
                    "obligation_type": "tax_overview",
                    "entity_type": entity_type,
                    "details": obligations,
                    "source": "knowledge_graph",
                })
                kg_sources = len(rows)
                logger.info(
                    f"✅ [Tax Subgraph] Got {kg_sources} tax obligations from KG for {entity_type}",
                )
    except Exception as e:
        logger.warning(f"⚠️ [Tax Subgraph] KG tax query failed, using fallback: {e}")

    # Fallback to hardcoded if KG empty
    if kg_sources == 0:
        obligations = tax_obligations_db.get(entity_type, {})
        if not state.get("vat_applicable", False):
            obligations.pop("ppn", None)
        state.setdefault("tax_obligations", []).append({
            "obligation_type": "tax_overview",
            "entity_type": entity_type,
            "details": obligations,
            "source": "hardcoded_fallback",
        })
        logger.info(f"📌 [Tax Subgraph] Using fallback tax obligations for {entity_type}")

    state["kg_sources_used"] = state.get("kg_sources_used", 0) + kg_sources
    logger.info(f"✅ [Tax Subgraph] Added tax obligations for {entity_type} (KG sources: {kg_sources})")

    return state
```

- [ ] **Step 4: Rewire synthesize_tax_workflow_node to use kg_sources_used**

In `backend/services/rag/kg_subgraph_tax.py`, replace lines 415-420 (the `calculate_subgraph_confidence` call in `synthesize_tax_workflow_node`):

```python
    kg_sources = state.get("kg_sources_used", 0)
    breakdown = calculate_subgraph_confidence(
        workflow_source="tax_subgraph",
        steps_count=len(steps),
        has_db_validation=kg_sources > 0,
        unique_sources=max(1, kg_sources),
    )
```

- [ ] **Step 5: Run all tax rewiring tests**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_property_tax_population.py -v -k "tax"
```

Expected: 5 PASSED (nodes, edges, from_kg, fallback, confidence)

- [ ] **Step 6: Run existing subgraph tests to verify no regression**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_subgraphs.py -v -k "tax"
```

Expected: All existing tax tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/rag/kg_subgraph_tax.py backend/tests/services/rag/test_kg_property_tax_population.py
git commit -m "feat(kg): rewire tax subgraph to query KG with hardcoded fallback"
```

---

### Task 6: Run Full Test Suite + Phase 1 on Local DB

**Files:** None modified — validation only

- [ ] **Step 1: Run complete test suite for all subgraphs**

```bash
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_kg_property_tax_population.py -v
```

Expected: All tests PASS (existing + new)

- [ ] **Step 2: Run Phase 1 dry-run against local PostgreSQL**

```bash
PYTHONPATH=. python scripts/kg_populate_property_tax.py --phase 1 --dry-run
```

Expected output:
```
DRY RUN — would insert: Property(4 nodes, 14 edges), Tax(10 nodes, 14 edges)
```

- [ ] **Step 3: Run Phase 1 for real against local PostgreSQL**

```bash
PYTHONPATH=. python scripts/kg_populate_property_tax.py --phase 1
```

Expected output:
```
✅ Property: 12 nodes upserted
✅ Property: 14 edges upserted
✅ Tax: 12 nodes upserted
✅ Tax: 14 edges upserted
📊 Phase 1 complete: {...}
```

- [ ] **Step 4: Verify nodes in database**

```bash
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
async def check():
    pool = await asyncpg.create_pool(os.environ['DATABASE_URL'], min_size=1, max_size=2)
    async with pool.acquire() as conn:
        prop = await conn.fetchval(\"SELECT COUNT(*) FROM kg_nodes WHERE entity_type = 'property_type'\")
        tax = await conn.fetchval(\"SELECT COUNT(*) FROM kg_nodes WHERE entity_type = 'tax_type'\")
        obl = await conn.fetchval(\"SELECT COUNT(*) FROM kg_nodes WHERE entity_type = 'tax_obligation'\")
        edges = await conn.fetchval(\"SELECT COUNT(*) FROM kg_edges WHERE relationship_type IN ('HAS_TAX', 'ALLOWS_OWNERSHIP', 'HAS_REQUIREMENT', 'HAS_DEADLINE', 'REQUIRES_ENTITY')\")
        print(f'property_type: {prop}, tax_type: {tax}, tax_obligation: {obl}, new edges: {edges}')
    await pool.close()
asyncio.run(check())
"
```

Expected: `property_type: 4, tax_type: 5, tax_obligation: 5, new edges: >= 20`

- [ ] **Step 5: Verify GraphTraversalTool can find new entities**

```bash
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
async def check():
    pool = await asyncpg.create_pool(os.environ['DATABASE_URL'], min_size=1, max_size=2)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(\"SELECT entity_id, name FROM kg_nodes WHERE name ILIKE '%hak pakai%' LIMIT 1\")
        if row:
            print(f'Found: {row[\"entity_id\"]} = {row[\"name\"]}')
            edges = await conn.fetch(
                'SELECT relationship_type, target_entity_id FROM kg_edges WHERE source_entity_id = \$1',
                row['entity_id']
            )
            for e in edges:
                print(f'  -> {e[\"relationship_type\"]} -> {e[\"target_entity_id\"]}')
        else:
            print('NOT FOUND')
    await pool.close()
asyncio.run(check())
"
```

Expected: Shows `property_type:hak_pakai` with edges to `concept:foreigner`, `concept:kitas_or_kitap`, etc.

- [ ] **Step 6: Commit (no code changes — just verify)**

No commit needed. All validation passed.

---

### Task 7: Save MOS Memory

**Files:** None

- [ ] **Step 1: Save discovery to MOS**

```bash
~/.claude/scripts/mem save decision "KG Property+Tax population Phase 1 completato: 4 property_type, 5 tax_type, 5 tax_obligation nodes + 28 edges. Subgraph rewired con KG query + hardcoded fallback. Cross-domain: property_type:hgb → company:pt_pma → tax_type:pph_badan traversable." 8
```
