# KG Property + Tax Gap Analysis — Design Spec

**Date:** 2026-04-05
**Status:** Approved
**Author:** Claude Opus 4.6 + Zero

## Problem

The Knowledge Graph has 34,606 nodes and 30,628 edges. Company and Visa subgraphs query the KG via `kg_nodes`/`kg_edges` tables. Property and Tax subgraphs exist as LangGraph workflows but return **100% hardcoded data** — zero KG queries. This means:

- GraphTraversalTool cannot answer multi-hop queries crossing Property/Tax domains
- No cross-domain traversal (e.g., "what taxes apply to a foreigner buying property via PT PMA?")
- Confidence scoring reports `has_db_validation=False` for both subgraphs

## Solution: Two-Phase KG Population + Subgraph Rewiring

### Approach C: Hardcoded-first extraction, then Qdrant enrichment, then rewire subgraphs

1. **Phase 1** — Convert existing hardcoded data in subgraph files to KG nodes/edges (deterministic, zero LLM cost)
2. **Phase 2** — Targeted LLM extraction from Qdrant collections for cross-domain relationships
3. **Phase 3** — Rewire subgraph nodes to query KG with hardcoded fallback (same pattern as Visa 2026-03-28)

## New Entity Types (6)

| Entity Type | Examples | Source |
|---|---|---|
| `property_type` | `hak_pakai`, `hgb`, `hak_milik`, `rental` | Hardcoded `_LEGACY_REQUIREMENTS_DB` |
| `ownership_right` | `shm`, `hgb_certificate`, `girik` | Training data + Qdrant legal |
| `zoning` | `residensial`, `pariwisata`, `pertanian` | PostGIS `bali_zoning_layers` |
| `tax_type` | `pph_badan`, `pph_21`, `pph_23`, `pph_26`, `ppn` | Hardcoded `tax_obligations_db` |
| `tax_obligation` | `npwp_registration`, `pkp_registration`, `monthly_filing`, `annual_spt` | Hardcoded subgraph steps |
| `government_fee` | `bphtb_5pct`, `pnbp_kitas`, `notary_deed_fee` | Hardcoded + Qdrant legal |

These extend the existing 6 types (`law`, `topic`, `company`, `location`, `practice_type`, `concept`) to 12.

## New Relationship Types (6)

| Relationship | Meaning | Example |
|---|---|---|
| `ALLOWS_OWNERSHIP` | Property type → who can own | `property_type:hak_pakai` → `concept:foreigner` |
| `REQUIRES_ENTITY` | Property/tax → company type needed | `property_type:hgb` → `company:pt_pma` |
| `HAS_TAX` | Entity type → applicable tax | `company:pt_pma` → `tax_type:pph_badan` |
| `HAS_DEADLINE` | Tax obligation → filing deadline | `tax_obligation:monthly_filing` → `concept:20th_following_month` |
| `APPLIES_IN_ZONE` | Property type → allowed zoning | `property_type:hak_pakai` → `zoning:residensial` |
| `HAS_REQUIREMENT` | Property/tax → required document/condition | `property_type:hak_pakai` → `concept:kitas_or_kitap` |

These complement existing types (`REQUIRES`, `HAS_FEE`, `HAS_DURATION`, `PART_OF`).

## Phase 1: Hardcoded → KG (Deterministic)

Script: `apps/backend-rag/scripts/kg_populate_property_tax.py`

### Property Nodes (from `_LEGACY_REQUIREMENTS_DB`)

4 `property_type` nodes:
- `property_type:hak_pakai` — `allowed_for_foreigners: true`, `max_duration: "30+20+30 years"`
- `property_type:hgb` — `allowed_for_foreigners: false` (via PT PMA only)
- `property_type:hak_milik` — `allowed_for_foreigners: false`, `max_duration: "permanent"`
- `property_type:rental` — `allowed_for_foreigners: true`, `max_duration: "1-5 years"`

7 workflow step nodes (as `concept` type):
- `concept:bpn_certificate_check`, `concept:ppjb_agreement`, `concept:notary_deed`, `concept:bphtb_tax`, `concept:bpn_registration`, `concept:negotiation`, `concept:due_diligence`

Edges:
- `property_type:hak_pakai` → `ALLOWS_OWNERSHIP` → `concept:foreigner`
- `property_type:hak_pakai` → `HAS_REQUIREMENT` → `concept:kitas_or_kitap`
- `property_type:hak_pakai` → `HAS_REQUIREMENT` → `concept:notary_deed`
- `property_type:hak_pakai` → `HAS_REQUIREMENT` → `concept:bpn_certificate_check`
- `property_type:hgb` → `REQUIRES_ENTITY` → `company:pt_pma`
- `property_type:hak_milik` → `ALLOWS_OWNERSHIP` → `concept:indonesian_citizen`
- Each property type → `HAS_FEE` → `government_fee:bphtb_5pct`
- Workflow chain: step 1 → `REQUIRES` → step 2 → ... → step 7

### Tax Nodes (from `tax_obligations_db`)

5 `tax_type` nodes:
- `tax_type:pph_badan` — `rate: 0.22`, `description: "Corporate Income Tax"`, `filing_deadline: "4 months after FY end"`
- `tax_type:pph_21` — `progressive_rates: [{bracket, rate}...]`, `description: "Employee withholding"`
- `tax_type:pph_23` — `rate: 0.02`, `description: "Service/rent withholding"`
- `tax_type:pph_26` — `rate: 0.20`, `description: "Foreign payment withholding"`, `note: "treaty-reducible"`
- `tax_type:ppn` — `rate: 0.11`, `description: "Value Added Tax"`, `threshold: 4_800_000_000`

5 `tax_obligation` nodes:
- `tax_obligation:npwp_registration` — `processing_time: "1-3 days"`, `system: "DJP online"`
- `tax_obligation:pkp_registration` — `requirement: "revenue > 4.8B IDR"`, `processing_time: "7-14 days"`
- `tax_obligation:bookkeeping_setup` — `requirement: "all business entities"`
- `tax_obligation:monthly_filing` — `filings: ["PPh 21", "PPh 23", "PPh 25", "PPN"]`
- `tax_obligation:annual_spt` — `deadline_corporate: "4 months post-FY"`, `deadline_personal: "March 31"`

Edges:
- `company:pt_pma` → `HAS_TAX` → `tax_type:pph_badan`
- `company:pt_pma` → `HAS_TAX` → `tax_type:pph_21`
- `company:pt_pma` → `HAS_TAX` → `tax_type:pph_23`
- `company:pt_pma` → `HAS_TAX` → `tax_type:pph_26`
- `company:cv` → `HAS_TAX` → `tax_type:pph_badan`
- `tax_type:pph_21` → `HAS_DEADLINE` → `concept:20th_following_month`
- `tax_type:ppn` → `HAS_DEADLINE` → `concept:end_following_month`
- `tax_obligation:npwp_registration` → `REQUIRES` → `tax_obligation:pkp_registration` (sequence)
- Cross-domain: `property_type:hak_pakai` → `HAS_FEE` → `government_fee:bphtb_5pct`
- Cross-domain: `property_type:hgb` → `REQUIRES_ENTITY` → `company:pt_pma` → `HAS_TAX` → `tax_type:pph_badan`

**Estimated Phase 1 yield**: ~30 nodes, ~50 edges. All verified data.

## Phase 2: Qdrant Enrichment (Targeted LLM Extraction)

Same script with `--phase 2` flag.

### Process

1. Query Qdrant `tax_genius_hybrid` — top 20 chunks for tax regulations
2. Query Qdrant `legal_unified_hybrid_hybrid` — top 20 chunks for property regulations
3. Run domain-specific LLM extraction prompt per chunk
4. Extract entities matching the 6 new types + relationships
5. Upsert into KG, merging with Phase 1 nodes (JSONB merge on conflict)

### Extraction Prompt (per domain)

```
Extract entities and relationships from this {domain} regulation text.

Entity types to extract:
{domain_entity_types_with_descriptions}

Relationship types to extract:
{domain_relationship_types_with_descriptions}

Output as JSON:
{
  "entities": [{"type": "...", "name": "...", "canonical_name": "...", "properties": {...}}],
  "relationships": [{"source": "...", "target": "...", "relationship": "...", "strength": 0.0-1.0, "evidence": "..."}]
}
```

### LLM Provider

- **Test (10 docs)**: Ollama `qwen3.5:27b` via `ollama_chat_kg()` (4 tok/s, ~30s per chunk)
- **Batch (40 docs)**: Gemini API (requires user approval before running)

**Estimated Phase 2 yield**: ~50-100 nodes, ~80-150 edges per domain.

## Phase 3: Subgraph Rewiring

### Property Subgraph (`kg_subgraph_property.py`)

Modify `get_property_requirements_node` (legacy wrapper):

```python
async def get_property_requirements_node(state: Any, db_pool: Any = None) -> dict:
    prop_type = state.get("property_type", "unknown")
    requirements = []
    kg_sources = 0

    if db_pool:
        async with db_pool.acquire() as conn:
            # Query KG for property type requirements
            rows = await conn.fetch("""
                SELECT n.entity_id, n.name, n.properties, e.relationship_type
                FROM kg_edges e
                JOIN kg_nodes n ON e.target_entity_id = n.entity_id
                WHERE e.source_entity_id = $1
                  AND e.relationship_type IN (
                      'HAS_REQUIREMENT', 'REQUIRES_ENTITY',
                      'ALLOWS_OWNERSHIP', 'HAS_FEE'
                  )
            """, f"property_type:{prop_type}")

            if rows:
                for row in rows:
                    requirements.append({
                        "type": row["relationship_type"],
                        "name": row["name"],
                        "details": row["properties"] or {},
                    })
                kg_sources = len(rows)

    # Fallback to hardcoded if KG empty
    if not requirements:
        reqs = _LEGACY_REQUIREMENTS_DB.get(prop_type, {})
        requirements = [{"requirement_type": "ownership", "details": reqs}]

    return {
        "property_requirements": requirements,
        "kg_sources_used": kg_sources,
    }
```

### Tax Subgraph (`kg_subgraph_tax.py`)

Modify `get_tax_obligations_node`:

```python
async def get_tax_obligations_node(state: TaxState, db_pool: asyncpg.Pool) -> TaxState:
    entity_type = state.get("business_entity_type", "unknown")
    kg_sources = 0

    try:
        async with db_pool.acquire() as conn:
            # Query KG for tax obligations by company type
            rows = await conn.fetch("""
                SELECT n.entity_id, n.name, n.properties
                FROM kg_edges e
                JOIN kg_nodes n ON e.target_entity_id = n.entity_id
                WHERE e.source_entity_id = $1
                  AND e.relationship_type = 'HAS_TAX'
            """, f"company:{entity_type}")

            if rows:
                obligations = {}
                for row in rows:
                    tax_id = row["entity_id"].split(":")[-1]
                    obligations[tax_id] = row["properties"] or {}
                    obligations[tax_id]["name"] = row["name"]

                state.setdefault("tax_obligations", []).append({
                    "obligation_type": "tax_overview",
                    "entity_type": entity_type,
                    "details": obligations,
                    "source": "knowledge_graph",
                })
                kg_sources = len(rows)
    except Exception as e:
        logger.warning(f"KG tax query failed, using fallback: {e}")

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

    state["kg_sources_used"] = state.get("kg_sources_used", 0) + kg_sources
    return state
```

### Confidence Scoring Update

Both subgraphs already use `calculate_subgraph_confidence()`. The rewiring changes `has_db_validation` from always-False to conditional on actual KG data found:

```python
kg_sources = state.get("kg_sources_used", 0)
breakdown = calculate_subgraph_confidence(
    workflow_source="{domain}_subgraph",
    steps_count=len(steps),
    has_db_validation=kg_sources > 0,
    unique_sources=max(1, kg_sources),
)
```

## GraphTraversalTool Integration

**No changes needed.** GraphTraversalTool queries `kg_nodes` by name (`find_entity_by_name`) and traverses `kg_edges` (`traverse(max_depth=3)`). New entity types and relationships are immediately discoverable.

Example multi-hop query: "tax for foreigner buying property"
1. `find_entity_by_name("hak pakai")` → `property_type:hak_pakai`
2. `traverse(depth=2)` → `REQUIRES_ENTITY → company:pt_pma → HAS_TAX → tax_type:pph_badan`

## File Plan

| File | Action | Purpose |
|---|---|---|
| `apps/backend-rag/scripts/kg_populate_property_tax.py` | CREATE | Phase 1+2 extraction script |
| `apps/backend-rag/backend/services/rag/kg_subgraph_property.py` | MODIFY | KG queries in legacy nodes, `kg_sources_used` tracking |
| `apps/backend-rag/backend/services/rag/kg_subgraph_tax.py` | MODIFY | KG queries in `get_tax_obligations_node` + `identify_tax_type_node` |
| `apps/backend-rag/backend/tests/services/rag/test_kg_property_tax_population.py` | CREATE | Tests for extraction + rewired subgraph nodes |

## Test Strategy

1. **Phase 1 extraction**: Run on local PostgreSQL, verify node/edge counts, validate `entity_id` format matches existing pattern (`type_name`)
2. **Phase 2 extraction**: Test with 10 Qdrant chunks per domain using Ollama `qwen3.5:27b`, manually validate
3. **Subgraph rewiring**: Mock `db_pool` with expected KG query results, verify outputs match current hardcoded outputs (regression)
4. **GraphTraversalTool**: Integration test querying new entity types, verify multi-hop traversal
5. **Sample validation**: Run extraction on 10 docs, print results, manually verify before batch

## Constraints

- Embedding model `text-embedding-3-small` (1536 dims) — NOT TOUCHED (this is KG, not vector search)
- Prices from `PricingTool` only — KG stores government fees (PNBP), NOT Bali Zero commercial prices
- Script must be idempotent (safe to re-run, uses `ON CONFLICT DO UPDATE`)
- No batch extraction without user approval
- Extraction script requires `cd apps/backend-rag && source .venv/bin/activate`
