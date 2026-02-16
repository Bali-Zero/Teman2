# Entity Detection Fix Summary

## Problem
Query "Apa itu KITAS?" (What is KITAS?) returned wrong KBLI codes:
- **Got**: 25910 (Metal Forging), 69103 (IP Consultant), 84220 (Defense)
- **Expected**: Should detect "KITAS" as visa entity, not return random KBLI codes

Same issue affected:
- "Apa itu NPWP?" → should be tax domain, not KBLI
- "Apa itu Hak Pakai?" → should be property domain, not KBLI

## Root Cause
1. **Entity extraction** only extracted basic entities without domain classification
2. **Query understanding node** relied solely on LLM intent classification which could misclassify
3. **Entity resolution** performed fuzzy matching against all KG nodes including KBLI codes
4. **No domain-based routing** to prevent visa/tax/property queries from hitting KBLI resolution

## Solution

### 1. Enhanced Entity Extraction (`entity_extractor.py`)
**Added domain classification:**
```python
class EntityExtractionService:
    DOMAIN_VISA = "visa"
    DOMAIN_TAX = "tax"
    DOMAIN_PROPERTY = "property"
    DOMAIN_KBLI = "kbli"
    DOMAIN_COMPANY = "company"
    DOMAIN_GENERAL = "general"
```

**New extraction methods:**
- `_extract_visa_entities()` - Detects KITAS, KITAP, VITAS, RPTKA, IMTA, visa codes
- `_extract_tax_entities()` - Detects NPWP, PPh, PPN, PBB, general tax terms
- `_extract_property_entities()` - Detects Hak Pakai, HGB, Hak Milik, property terms
- `_extract_kbli_entities()` - Detects 5-digit KBLI codes
- `_extract_company_entities()` - Detects PT PMA, CV, NIB, etc.

**Returns structured output:**
```python
{
    "domain": "visa",
    "entity_types": ["visa"],
    "primary_entity": "KITAS",
    "visa_type": "KITAS",
    ...
}
```

**Added helper method:**
```python
def is_non_kbli_domain(self, query: str, entities: dict) -> bool:
    """Check if query is visa/tax/property (should NOT match KBLI)"""
    return domain in [DOMAIN_VISA, DOMAIN_TAX, DOMAIN_PROPERTY]
```

### 2. Updated Graph State (`kg_graph_state.py`)
Added `domain` field to `KGAgentState`:
```python
class KGAgentState(TypedDict):
    ...
    domain: str | None  # visa, tax, property, kbli, company, general
```

### 3. Enhanced Query Understanding (`kg_graph_nodes.py`)
**Added fast domain detection:**
```python
def _detect_domain_from_query(query_lower: str) -> dict:
    # Fast-path detection without LLM call
    # Checks explicit keywords for visa/tax/property/kbli/company
```

**Updated prompt to include domain classification:**
```
2. **Domain Classification** (critical for routing):
   - visa: Query is about KITAS, KITAP, visas, work permits
   - tax: Query is about taxes, NPWP, PPh, PPN
   - property: Query is about real estate, Hak Pakai, HGB
   ...
   
   IMPORTANT: If query asks "What is KITAS?" → domain MUST be "visa"
```

**Added entity type filtering in resolution:**
```python
NON_KBLI_ENTITY_TYPES = {"visa_type", "tax_concept", "tax_code", "property_type"}

def _is_non_kbli_entity(entity_str: str) -> bool:
    # Returns True for visa/tax/property entities
    # Prevents them from being matched against KBLI codes
```

### 4. Updated Routing (`kg_langgraph_orchestrator.py`)
**Domain-based routing (highest priority):**
```python
def route_after_query_understanding(state: KGAgentState) -> str:
    # PHASE 1: Domain-based routing
    if domain == "visa":
        return "visa_subgraph"
    if domain == "tax":
        return "tax_subgraph"
    if domain == "property":
        return "property_subgraph"
    # ... etc
```

**CRITICAL:** Visa/Tax/Property queries are now routed to their respective subgraphs **before** any KBLI resolution can occur.

## Test Results

### New Tests (`test_entity_detection_fix.py`)
**28 tests covering:**
- ✅ KITAS detected as visa domain
- ✅ KITAP detected as visa domain  
- ✅ VITAS detected as visa domain
- ✅ NPWP detected as tax domain
- ✅ PPh/PPN detected as tax domain
- ✅ Hak Pakai detected as property domain
- ✅ HGB detected as property domain
- ✅ KBLI codes still detected correctly
- ✅ PT PMA detected as company domain
- ✅ Edge cases (case insensitivity, mixed entities, etc.)

### Backward Compatibility
**12 existing tests updated and passing:**
- ✅ Empty query returns domain="general"
- ✅ Visa codes detected with domain classification
- ✅ All original functionality preserved

## Expected Behavior After Fix

| Query | Before Fix | After Fix |
|-------|-----------|-----------|
| "Apa itu KITAS?" | Random KBLI codes (25910, 69103) | Routed to VisaSubgraph |
| "Apa itu NPWP?" | Random KBLI codes | Routed to TaxSubgraph |
| "Apa itu Hak Pakai?" | Random KBLI codes | Routed to PropertySubgraph |
| "KBLI 56101" | Correctly handled | Still routed to Company/KBLI |
| "PT PMA setup" | Correctly handled | Still routed to CompanySubgraph |

## Files Modified

1. `backend/services/rag/agentic/entity_extractor.py` - Complete rewrite with domain detection
2. `backend/services/rag/kg_graph_state.py` - Added `domain` field
3. `backend/services/rag/kg_graph_nodes.py` - Enhanced query understanding & entity resolution
4. `backend/services/rag/kg_langgraph_orchestrator.py` - Domain-based routing

## Files Added

1. `backend/tests/unit/services/rag/agentic/test_entity_detection_fix.py` - 28 new tests

## Files Updated (Tests)

1. `backend/tests/unit/services/rag/agentic/test_entity_extractor.py` - Updated for new return format
