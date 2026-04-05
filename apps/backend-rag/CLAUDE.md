# Backend RAG — Non-Inferable Knowledge

> Archive of session notes: `docs/sessions/CLAUDE-archive-2026-04-06.md`
> Only things the agent CANNOT discover independently belong here.

---

## Critical Gotchas

### ABSTAIN Override (reasoning.py)
`calculate_evidence_score()` returns 0.00 when Gemini answers directly without calling tools. Score < 0.15 = ABSTAIN → blocks all valid business answers.

**Three-layer fix** (both streaming + non-streaming paths in `reasoning.py`):
1. `intent_classifier.py`: 17 pricing keywords in `GENERAL_TASK_KEYWORDS` trigger `skip_rag=True`
2. If `final_answer` contains pricing markers (Rp, IDR, USD), set `trusted_tools_used = True`
3. **KEY**: If LLM had `_gemini_tools` configured and produced `final_answer`, trust it → `trusted_tools_used = True`

### Rogue AI Import Removal
AI refactors (Gemini/Windsurf) silently remove `Any` from `typing` imports. `dependencies.py` is imported by EVERY router — missing `Any` crashes entire app at startup.

**Prevention**: Always run before deploy:
```bash
python -c "from backend.app.dependencies import get_current_user; print('OK')"
PYTHONPATH=. pytest backend/tests/services/rag/ -q
```

### Service Injection Pattern (avoid circular imports)
Use `get_service()` lazy loading pattern, NOT direct imports between services. Circular imports between services will crash FastAPI startup silently.

---

## Pricing Rules (ABSOLUTE)

### HAS_FEE in KG ≠ Bali Zero Prices
KG `HAS_FEE` relations (~1,500) contain government PNBP fees and legal regulation costs extracted from imigrasi.go.id — NOT Bali Zero service prices.

**Bali Zero prices are ONLY in:**
- File: `backend/data/bali_zero_official_prices_2025.json`
- Tool: `PricingTool` (Tool #2)
- Loaded by: `PricingService._load_prices()`

**Rules enforced in `prompt_builder.py:47-66`:**
1. ONLY use prices from `get_pricing` tool
2. NEVER invent, estimate, or guess ANY price
3. If price not in tool → "Questo costo specifico è da verificare con il team"

---

## Model Configuration

| Use Case | Model | Fallback | Notes |
|----------|-------|----------|-------|
| KBLI chat | `claude-haiku-4-5-20251001` | Gemini Flash | In `kbli_notebook.py` |
| RAG orchestrator | Gemini 2.5 Flash | Gemini 2.0 Flash | Primary reasoning |
| Embedding | `text-embedding-3-small` | NONE | **FROZEN** — changing invalidates 93K+ vectors |
| Evidence threshold | 0.15 | — | Below = ABSTAIN |

---

## Test Commands

```bash
# Full backend tests
PYTHONPATH=. pytest backend/tests/ -v --tb=short -x

# Critical path (RAG + KG)
PYTHONPATH=. pytest backend/tests/services/rag/ -q

# Coverage with gate
PYTHONPATH=. pytest backend/tests/ --cov=backend --cov-report=term-missing --cov-fail-under=40

# Import chain validation (catches rogue AI removals)
python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

---

## Deploy Checklist

```bash
# 1. Check for rogue changes
git diff --name-only HEAD -- apps/backend-rag/backend/

# 2. Test import chain
python -c "from backend.app.dependencies import get_current_user; print('OK')"

# 3. Run core tests
PYTHONPATH=. pytest backend/tests/services/rag/ -q

# 4. Deploy
fly deploy --app nuzantara-rag --strategy rolling

# 5. Verify
curl -s https://nuzantara-rag.fly.dev/health | jq .
```

---

## Non-Standard Patterns

- Routers are in `backend/app/routers/`, NOT `backend/routers/`
- `PYTHONPATH=.` is REQUIRED for all pytest commands
- Qdrant payloads must be **flat** (no nested dicts)
- `zantara_core.py` is the SINGLE source of truth for core config — edit ONLY there
- bali-intel-scraper runs LOCALLY on Pro only, NOT on Fly.io
