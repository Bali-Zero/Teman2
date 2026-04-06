# NB-RAG v2 — Architecture Design Spec

**Date:** 2026-04-06
**Status:** Approved
**Author:** Claude Opus + Zero

---

## 1. Problem Statement

Zantara's RAG pipeline has structural weaknesses that NLM notebooks (NB-2 through NB-13) can help resolve. Testing on 2026-04-06 revealed:

1. **Visa retrieval fails** — Query "B211A" returns C7, D7, C10A (score 0.53-0.57). The old naming (B211A) doesn't match the new code system (B1, C6, E28A) in `visa_oracle`
2. **KBLI retrieval weak** — "restaurant" scores 0.53, returns cafe (56303) before restoran (56101)
3. **Immigration Circulars near-empty** — Only 4 documents. Golden Visa absent
4. **Tax from training only** — 332 chunks all from conversations, zero normative sources (PMK, SE DJP)
5. **Golden Visa missing from pricing** — No match in `bali_zero_pricing_hybrid`
6. **RAG Worker DOWN** — Fly.io RAG process group not responding (separate from API process)

### What works well (don't touch)
- **KG PostgreSQL**: 113,854 nodes / 251,522 edges — excellent coverage
- **Legal Unified**: 81,251 chunks, scores 0.65+
- **Training Conversations**: 3,638 chunks, good visa comparisons
- **Pricing**: 70 docs, accurate KITAS prices
- **BaliZero News**: 3,513 editorial chunks, 2026-current

---

## 2. Architecture Overview

```
                    QUERY
                      │
                 ┌────▼────┐
                 │ LAYER 0  │  FAQ Cache + Semantic Cache (Redis)
                 │  <1ms    │  hit rate ~70%
                 └────┬────┘
                      │ miss
                 ┌────▼────┐
                 │ LAYER 1  │  Smart Router (Intent + Domain)
                 │  ~50ms   │
                 └────┬────┘
                      │
           ┌──────────┼──────────┐
           ▼          ▼          ▼
      ┌────────┐ ┌────────┐ ┌────────┐
      │QDRANT  │ │  KG    │ │GOLDEN  │
      │Vector  │ │Graph   │ │ANSWERS │  ← NEW
      │Search  │ │Traverse│ │ <50ms  │
      │~200ms  │ │~100ms  │ │        │
      └───┬────┘ └───┬────┘ └───┬────┘
           └──────────┼──────────┘
                 ┌────▼────┐
                 │ LAYER 2  │  Gemini 3 Flash ReAct
                 │ 300-800  │  Evidence Scoring + Synthesis
                 │ ms/iter  │
                 └────┬────┘
                      │
                 ┌────▼────┐
                 │ LAYER 3  │  NLM Async Verification
                 │  async   │  Fire-and-forget, audit trail
                 └────┬────┘
                      │
                  RESPONSE
```

---

## 3. Component Design

### 3.1 NLM Golden Answers Collection

**Purpose:** Pre-generated, grounded answers from curated NLM notebooks, served as a Qdrant collection for sub-50ms retrieval.

**Collection name:** `zantara_golden_answers`

**Source notebooks:**
| NB | Domain | Content |
|----|--------|---------|
| NB-2 | Immigration/Visa | B211A/B211, KITAS types, Golden Visa, Second Home, Digital Nomad |
| NB-3 | Investment/Business | PT PMA setup, BKPM, company formation |
| NB-4 | Tax | PPh Badan, PPN, tax compliance for PT PMA |
| NB-5 | Property/ATR-BPN | Hak Pakai, land ownership rules for WNA |
| NB-6 | Company Formation | NIB, OSS, business licensing |

**Generation process:**
1. Define ~300 canonical questions covering the top user queries per domain
2. For each question, query the relevant NLM notebook via `nlm_bridge.py`
3. NLM returns grounded answer with citations to source documents
4. Embed the question + answer pair using `text-embedding-3-small`
5. Store in Qdrant with payload: `{ question, answer, domain, sources, generated_at, nb_id, confidence }`

**Payload schema (flat, per Qdrant rules):**
```json
{
  "question": "What are the requirements for a B211A visa?",
  "answer": "The B211A (now coded as B1 Visit Visa) requires...",
  "domain": "visa",
  "nb_id": "NB-2",
  "sources": "Permenkumham 22/2023, Permenkumham 11/2024",
  "generated_at": "2026-04-06T00:00:00Z",
  "confidence": 0.85,
  "aliases": "B211A, B211, social budaya, visit visa sosial"
}
```

**Refresh schedule:** Weekly cron (Sunday 03:00 WITA) via `scripts/golden_answers_refresh.py`

**Query integration:**
- In `orchestrator_core.py`, after cache miss and before full RAG
- Embed user query → search `zantara_golden_answers` with threshold 0.75
- If match found (score >= 0.75): return golden answer directly, skip full RAG
- If no match: proceed to standard Qdrant + KG + Gemini flow

### 3.2 Collection Gap Fixes

#### 3.2.1 Visa Oracle — Alias Mapping

**Problem:** Users search "B211A" but collection uses new codes (C7, E28A, etc.)

**Fix:** Add `aliases` field to visa_oracle metadata with old naming conventions:
- B211A → maps to C316 (social budaya) or relevant new code
- B211 → maps to visit visa category
- KITAS → maps to E-series codes
- Retirement Visa → maps to E33E, E33F

**Implementation:** Update ingestion script to include alias field. Add re-ranking boost when query matches an alias.

#### 3.2.2 Immigration Circulars — Enrichment

**Problem:** Only 4 documents. Golden Visa, Digital Nomad, Second Home circulars absent.

**Fix:** Ingest from:
- Existing NLM NB-2 sources (already curated)
- T4 Social Monitor captured circulars (ditjen_imigrasi channel)
- Manual Surat Edaran from imigrasi.go.id
- Target: 4 → 100+ documents

#### 3.2.3 Tax Genius — Normative Sources

**Problem:** 332 chunks all from training conversations, zero PMK/SE DJP.

**Fix:** Ingest:
- PMK tax regulations from legal_unified (cross-reference, not duplicate)
- SE DJP circulars
- Target: add ~200 normative chunks alongside existing 332 training chunks

#### 3.2.4 Pricing — Missing Products

**Problem:** Golden Visa, Second Home, Digital Nomad not in pricing collection.

**Fix:** Add entries from `bali_zero_official_prices_2025.json` if they exist, or flag as "contact team for pricing" entries.

### 3.3 Gemini 3 Flash Upgrade

**Current:** `gemini-2.5-flash` (and `gemini-2.0-flash` fallback)
**Target:** `gemini-3-flash` (and `gemini-2.5-flash` fallback)

**Changes required:**
- `backend/services/rag/reasoning.py` — update model constant
- `backend/app/routers/agentic_rag.py` — update model references
- Any config in `backend/core/config.py` or `.env`

**Expected improvements:**
- 3x faster output generation
- GPQA Diamond 90.4% (PhD-level reasoning)
- Better tool use and structured output
- Pricing: $0.50/M input, $3.00/M output (vs $0.30/$2.50)

**Backward compatibility:** Same API format (Gemini API). Drop-in replacement.

### 3.4 NLM Async Verification (Layer 3)

**Purpose:** Post-response quality assurance. NOT in the hot path.

**Flow:**
1. User gets response in 0.5-1.5s (normal flow)
2. Background task fires NLM query for the same question to relevant notebook
3. Compare NLM answer with Zantara response
4. If significant discrepancy detected:
   - Log to `nlm_verification_log` table
   - Send Telegram alert if confidence delta > 0.3
5. Weekly report of discrepancies for human review

**Trigger conditions (not all queries):**
- Domain is visa, tax, or legal
- Evidence score is in CAUTIOUS range (0.15-0.60)
- Query is a factual question (not greeting, not pricing)

**Implementation:** `backend/services/rag/nlm_verifier.py`
- Uses existing `nlm_bridge.py` for NLM calls
- Async task via `asyncio.create_task()` after response is sent
- Timeout: 30s (if NLM doesn't respond, skip silently)
- Rate limit: max 10 verifications per hour to avoid NLM quota issues

---

## 4. Data Flow

### 4.1 Query-time flow (hot path)

```
User Query
  → Redis FAQ Cache check (<1ms)
  → Redis Semantic Cache check (10-50ms)
  → [MISS] Smart Router classifies domain (~50ms)
  → PARALLEL:
      Golden Answers search (<50ms)
      Qdrant collection search (~200ms)
      KG graph traversal (~100ms)
  → IF golden_answer.score >= 0.75:
      Return golden answer (total: ~300ms)
  → ELSE:
      Merge Qdrant + KG context
      Gemini 3 Flash ReAct loop (300-800ms × 2-3 iterations)
      Evidence scoring
      Return synthesized answer (total: 0.5-1.5s)
  → [ASYNC] NLM verification if domain=critical
```

### 4.2 Golden Answers refresh (cold path)

```
Weekly Cron (Sun 03:00 WITA)
  → Load canonical questions from YAML/JSON config
  → For each question:
      Query relevant NLM notebook via nlm_bridge
      Embed question with text-embedding-3-small
      Upsert to zantara_golden_answers collection
  → Log refresh stats
  → Telegram notification with summary
```

---

## 5. Files to Create/Modify

### New files
| File | Purpose |
|------|---------|
| `backend/services/rag/golden_answers.py` | Golden Answers retrieval service |
| `backend/services/rag/nlm_verifier.py` | Async NLM verification service |
| `scripts/golden_answers_refresh.py` | Weekly refresh script |
| `scripts/golden_answers_questions.yaml` | Canonical questions config |
| `scripts/enrich_immigration_circulars.py` | Circulars enrichment script |
| `scripts/enrich_tax_normative.py` | Tax normative sources enrichment |

### Modified files
| File | Change |
|------|--------|
| `backend/core/collection_registry.py` | Add `zantara_golden_answers` to registry |
| `backend/services/rag/reasoning.py` | Gemini 2.5 Flash → 3 Flash |
| `backend/app/routers/agentic_rag.py` | Model update, integrate golden answers |
| `backend/services/rag/orchestrator_core.py` | Insert golden answers layer after cache miss |
| `.env` | Add `GEMINI_MODEL=gemini-3-flash` |

### Not modified
| File | Reason |
|------|--------|
| `backend/prompts/zantara_core.py` | No prompt changes needed |
| `backend/services/knowledge_graph/*` | KG is excellent as-is |
| Embedding model | FROZEN — text-embedding-3-small (1536 dims) |

---

## 6. Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| Visa "B211A" retrieval score | 0.57 (wrong result) | 0.75+ (correct result via golden answer or alias) |
| KBLI "restaurant" retrieval | 0.53 (#2 position) | 0.65+ (#1 position) |
| Immigration circulars coverage | 4 docs | 100+ docs |
| Tax normative sources | 0 | 200+ chunks |
| Golden Visa pricing match | 0.53 (wrong) | 0.70+ (correct or "contact team") |
| P50 response latency | ~1.5s | ~0.8s (Gemini 3 Flash) |
| NLM verification coverage | 0% | 100% of critical domain queries |
| RAG Worker availability | DOWN | 100% (fix as prerequisite) |

---

## 7. Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| NLM golden answers become stale | Weekly refresh + `generated_at` timestamp for freshness check |
| Gemini 3 Flash API not available | Fallback to Gemini 2.5 Flash (already configured) |
| Golden answer false positive (wrong match) | Score threshold 0.75 is conservative; below → full RAG |
| NLM verification quota exceeded | Rate limit 10/hour, skip silently on timeout |
| Collection enrichment introduces noise | Quality filter: only ingest docs with confidence > 0.5 |

---

## 8. Implementation Order

1. **Fix RAG Worker** — prerequisite, nothing works without it
2. **Gemini 3 Flash upgrade** — drop-in, immediate speed gain
3. **Golden Answers infrastructure** — collection + retrieval service + refresh script
4. **Collection gap fixes** — visa aliases, immigration circulars, tax normative, pricing
5. **NLM async verification** — last, because it's enhancement not fix
6. **Testing and validation** — re-run the same queries from this spec against each collection

---

## 9. Estimated Costs

| Component | Cost Impact |
|-----------|-----------|
| Gemini 3 Flash | +$0.20/M input, +$0.50/M output (marginal) |
| Golden Answers refresh | ~$0.50/week NLM + embedding costs |
| NLM verification | ~$0.10/day at 10 verifications/hour max |
| Qdrant Cloud storage | Negligible — golden_answers is ~300 points |
| **Total incremental** | **~$5-10/month** |
