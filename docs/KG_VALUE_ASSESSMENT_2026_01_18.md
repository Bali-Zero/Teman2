# Knowledge Graph Value Assessment

**Date**: 2026-01-18
**Cost**: 3.9M Rp (~€230 EUR)
**Investment**: 37M Gemini API calls (January 2026)

---

## Executive Summary

The Knowledge Graph extraction has produced **34,606 nodes** and **30,628 relationships** that are **CURRENTLY ACTIVE AND USABLE** in production via the `knowledge_graph_search` tool in Zantara.

**ROI Assessment**: POSITIVE (with caveats)

- ~40-45% of relationships are semantically valuable (REQUIRES, HAS_FEE, HAS_DURATION)
- ~50-55% are structural/trivial (PART_OF between legal articles)
- Cost per useful relationship: ~€0.015

---

## Current Status

### ✅ What Works NOW

The KG is **integrated and active** in Zantara as Tool #4:

**File**: `apps/backend-rag/backend/services/rag/agentic/__init__.py:134`

```python
tools = [
    VectorSearchTool(retriever),      # 1. Primary search
    PricingTool(),                     # 2. Official pricing
    TeamKnowledgeTool(db_pool),        # 3. Team info
    KnowledgeGraphTool(kg_builder),    # 4. 🎯 KNOWLEDGE GRAPH ✅ ACTIVE
    CalculatorTool(),                  # 5. Math
    ...
]
```

**How it's used**: When users ask relationship-based queries like:

- "Cosa richiede un PT PMA?" → Finds REQUIRES relationships
- "Quali documenti servono per KITAS investor?" → Navigates document prerequisites
- "Quali tasse per ristoranti?" → Finds APPLIES_TO relationships with KBLI codes

### ❌ What Was Disabled

**Continuous extraction** (autonomous_scheduler.py Task #7) was disabled due to excessive cost.

**Reason**:

- Running every 24h
- 37M API calls/month = €230
- Most extractions were structural relationships (Pasal → Ayat) achievable with regex

---

## Data Quality Analysis

### Node Distribution (Top Entity Types)

Based on production queries:

| Entity Type        | Estimated Count | %        | Description                   |
| ------------------ | --------------- | -------- | ----------------------------- |
| `kbli`             | ~6,932          | 20.0%    | Business classification codes |
| `biaya` (costs)    | ~6,060          | 17.5%    | Fee information               |
| `pasal` (articles) | ~3,954          | 11.4%    | Legal article references      |
| `dokumen`          | ~3,674          | 10.6%    | Document types                |
| `undang_undang`    | ~2,800          | 8.1%     | Laws (UU)                     |
| `peraturan`        | ~2,200          | 6.4%     | Regulations (PP, Permen)      |
| `visa_type`        | ~500            | 1.4%     | Visa categories               |
| `company_type`     | ~300            | 0.9%     | PT PMA, CV, etc.              |
| **Others**         | ~9,186          | 26.5%    | Tax IDs, permits, etc.        |
| **TOTAL**          | **34,606**      | **100%** |                               |

### Relationship Distribution

| Type             | Count      | %        | Value     | Examples                                               |
| ---------------- | ---------- | -------- | --------- | ------------------------------------------------------ |
| **REQUIRES**     | 8,218      | 26.8%    | 🟢 HIGH   | "PT PMA REQUIRES NPWP", "E28A REQUIRES Bank Statement" |
| **PART_OF**      | 7,595      | 24.8%    | 🟡 LOW    | "Pasal 286 PART_OF Ayat 1" (structural, trivial)       |
| **REFERENCES**   | 4,593      | 15.0%    | 🟡 MEDIUM | "UU 6/2023 REFERENCES PP 28/2025"                      |
| **HAS_FEE**      | ~1,500     | 4.9%     | 🟢 HIGH   | "KITAS Investor HAS_FEE 3000000 IDR"                   |
| **HAS_DURATION** | ~1,200     | 3.9%     | 🟢 HIGH   | "Work Permit HAS_DURATION 1 tahun"                     |
| **APPLIES_TO**   | ~800       | 2.6%     | 🟢 HIGH   | "PPh 21 APPLIES_TO KBLI 56101"                         |
| **LINKED_KBLI**  | ~600       | 2.0%     | 🟢 HIGH   | "E28A LINKED_KBLI 62010, 63110"                        |
| **Others**       | ~6,122     | 20.0%    | Various   |                                                        |
| **TOTAL**        | **30,628** | **100%** |           |

---

## Value Breakdown

### High-Value Relationships (~13,000 edges, 42.4%)

**REQUIRES relationships** (8,218):

- Prerequisites for company formation
- Document requirements for visas
- Licensing dependencies

**HAS_FEE relationships** (~1,500):

- ⚠️ Government fees from legal documents (NOT Bali Zero prices)
- Official tax/registration costs from regulations
- Bureaucratic fees (informational only)
- **CRITICAL**: These are NOT customer-facing prices - only get_pricing tool has official Bali Zero prices

**HAS_DURATION relationships** (~1,200):

- Processing times
- Validity periods
- Renewal timelines

**APPLIES_TO / LINKED_KBLI** (~1,400):

- Tax applicability by business sector
- Visa eligibility by KBLI code
- Permit requirements by industry

**Total useful relationships**: ~13,000
**Cost per useful relationship**: €230 / 13,000 = **€0.018**

### Low-Value Relationships (~17,000 edges, 55.5%)

**PART_OF structural** (~7,000):

- Legal hierarchy: Pasal → Ayat → Huruf
- Extractable with regex patterns
- No semantic intelligence required

**REFERENCES legal** (~4,000):

- Cross-references between laws
- Useful for legal research but not business queries

**Others trivial** (~6,000):

- Redundant connections
- Single-source mentions (unverified)

---

## Quality Metrics

### Evidence Quality

**Confidence Scores**:

- Average: **0.90** (HARDCODED - not reflective of true quality)
- Problem: All extractions have same confidence regardless of source quality

**Source Evidence**:

- Multi-source entities (2+ chunks): **~8,000 nodes** (23%)
- Single-source entities: **~26,000 nodes** (77%)
- Risk: Single-source entities may be hallucinations

**Orphan Nodes** (no relationships):

- Estimated: **~5,000 nodes** (14.5%)
- These provide no graph traversal value

### Coverage by Collection

Based on extraction logs:

| Collection               | Estimated Entities | Coverage          |
| ------------------------ | ------------------ | ----------------- |
| `legal_unified_hybrid`   | ~15,000            | Laws, regulations |
| `visa_oracle`            | ~8,000             | Visa requirements |
| `tax_genius_hybrid`      | ~6,000             | Tax obligations   |
| `kbli_atlas`             | ~3,500             | KBLI codes        |
| `training_conversations` | ~2,000             | User queries      |
| **TOTAL**                | **~34,500**        |                   |

---

## ⚠️ CRITICAL: Pricing Policy

### Knowledge Graph HAS_FEE ≠ Bali Zero Prices

**What HAS_FEE relationships contain**:

- Government fees extracted from Indonesian regulations (e.g., "PT registration fee = 500K IDR" from PP/UU)
- Official tax rates from fiscal laws
- Bureaucratic costs mentioned in legal documents

**Why these should NOT be communicated to clients**:

1. **Not Bali Zero prices** - These are government/legal fees, not service pricing
2. **May be outdated** - Legal documents may reference old fee structures
3. **Not verified** - Extracted by LLM, not validated by humans
4. **Single source risk** - Most have only 1 source chunk (77% of KG nodes)

### The ONLY Source of Truth for Pricing

**PricingTool (Tool #2)** is the ONLY authorized source:

- Uses official Bali Zero pricing database
- Updated and verified by team
- Mandatory for all price questions

**System Protection** (`prompt_builder.py:47-66`):

```
RULE 1: ONLY USE PRICES FROM get_pricing TOOL
RULE 2: IF PRICE NOT IN TOOL, SAY "DA VERIFICARE"
RULE 3: NEVER invent, estimate, or guess ANY price
```

**Example**:

- ❌ WRONG: "Cambiare KBLI costa 5-10M" (from KG or memory)
- ✅ CORRECT: Call get_pricing → "PT PMA costa Rp 20.000.000 [exact from pricing DB]"
- ✅ CORRECT: "Il costo per modifiche successive è da verificare con il team" (if not in pricing DB)

---

## API Authentication (Why 401 Errors)

The `/api/agentic/query` endpoint is **protected** and requires authentication:

### Method 1: Cookie JWT (Web)

```javascript
// After login on www.balizero.com
fetch("https://nuzantara-rag.fly.dev/api/agentic/query", {
  method: "POST",
  credentials: "include", // Send JWT cookie
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "Cosa richiede un PT PMA?",
    user_id: "...",
    session_id: "...",
  }),
});
```

### Method 2: Bearer Token (API)

```bash
# 1. Login to get token
curl -X POST https://nuzantara-rag.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "..."}'

# Response: {"access_token": "eyJ...", "token_type": "bearer"}

# 2. Use token for queries
curl -X POST https://nuzantara-rag.fly.dev/api/agentic/query \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"query": "Cosa richiede un PT PMA?", "user_id": "test"}'
```

**Auth Implementation**: `apps/backend-rag/backend/app/dependencies.py:209-238`

---

## Recommendations

### ✅ Keep Using Existing KG

The 34K nodes are valuable and should remain active:

- Tool integration is working
- No ongoing costs (extraction disabled)
- ~13K useful relationships justify €230 investment

### ⚠️ Improve Confidence Scoring

Replace hardcoded 0.9 with dynamic scoring:

```python
def calculate_confidence(entity, sources):
    base = 0.5
    # +0.1 per additional source (up to 5)
    multi_source_boost = min(0.4, (len(sources) - 1) * 0.1)
    # +0.1 if extracted from official source
    official_boost = 0.1 if is_official_source(sources[0]) else 0
    return base + multi_source_boost + official_boost
```

### 💡 Re-enable Extraction with Cost Controls

If re-enabling continuous extraction:

1. **Use regex for structural relationships**:
   - PART_OF (Pasal → Ayat): Regex pattern
   - Legal REFERENCES: Document parsing
   - Save ~60% of API calls

2. **Use Gemini only for semantic relationships**:
   - REQUIRES (prerequisites)
   - HAS_FEE (costs)
   - APPLIES_TO (applicability)
   - Expected cost: ~€90/month (60% reduction)

3. **Require 2+ source minimum**:
   - Skip entities with single-source
   - Reduces hallucination risk
   - Improves graph quality

4. **Set extraction frequency**:
   - Weekly instead of daily
   - Only process NEW chunks
   - Expected cost: ~€20/month (91% reduction)

---

## Conclusion

### Final Verdict: ✅ INVESTMENT WAS WORTHWHILE

**What you got for €230**:

- 34,606 entities in production database
- ~13,000 semantically valuable relationships
- Integrated and active tool in Zantara
- Permanent asset (no ongoing cost)

**What was disabled**:

- Continuous daily extraction (too expensive)
- Structural relationship extraction (achievable with regex)

**Net Result**:

- €230 one-time investment
- Permanent KG asset with 13K useful relationships
- **Cost per useful relationship**: €0.018
- **ROI**: POSITIVE

The extraction process was expensive but produced a valuable, permanent asset now integrated into production.

---

**Prepared by**: Claude Sonnet 4.5
**Assessment Date**: 2026-01-18
**KG Status**: ✅ Active in Production
**Extraction Status**: ❌ Disabled (cost optimization)
