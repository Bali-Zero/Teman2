# Domain knowledge — KBLI, pricing, evidence scoring, embeddings, resources

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.

## 5. Domain-Specific Knowledge

### KBLI (Indonesian Business Classification)

**Storage:** Qdrant vector collection  
**Format:** **FLAT payload structure**, NOT nested  
**Fields:** `code`, `title_id`, `title_en`, `description`, `category`, `section`

❌ **WRONG:**

```json
{
  "code": "47911",
  "details": {
    "title": "...",
    "description": "..."
  }
}
```

✅ **CORRECT:**

```json
{
  "code": "47911",
  "title_id": "Perdagangan Eceran...",
  "title_en": "Retail Sale...",
  "description": "...",
  "category": "G",
  "section": "Perdagangan"
}
```

### Pricing System

**CRITICAL:** All prices MUST come from `PricingTool`.  
**Never:** Hardcode, guess, or cache prices outside the tool.  
**Files:** Reference only `PRICING_REFERENCE.md` and `VISA_TYPES_REFERENCE.md`.

### Evidence Scoring System

Classification confidence thresholds:

- **< 0.15:** `ABSTAIN` - Insufficient confidence, refuse to answer
- **0.15 - 0.60:** `CAUTIOUS` - Provide answer with clear uncertainty disclaimer
- **> 0.60:** `NORMAL` - Confident answer

### Embedding Model

**Model:** `text-embedding-3-small` (OpenAI)  
**Dimensions:** 1536  
**CRITICAL:** This model is FROZEN. Changing it would invalidate the existing vector index.
**Never:** Switch to another model without explicit authorization and full re-indexing plan.

## 12. Resources

- **Architecture:** `docs/architecture.md`
- **API Docs:** `http://localhost:8000/docs` (Swagger UI)
- **Golden Rules:** This file + `AI_ONBOARDING.md`
- **Pricing:** `PRICING_REFERENCE.md`
- **Visa Info:** `VISA_TYPES_REFERENCE.md`

### KBLI Navigator (Frontend)

| Route             | Description                             |
| ----------------- | --------------------------------------- |
| `/kbli`           | KBLI 2025 Navigator homepage (Next.js)  |
| `/kbli/[code]`    | KBLI code detail page (1,559 SSG pages) |
| `/kbli-navigator` | **Redirect** → `/kbli` (permanent 301)  |
| `/kbli-explorer`  | AI chat explorer (complementary)        |

---
