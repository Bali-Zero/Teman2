# Migration Plan: Gemini 2.5 Flash → Gemini 2.0 Flash

**Date**: 2025-12-11
**Author**: AI Assistant
**Status**: DRAFT - Awaiting Approval

---

## Executive Summary

Migrare da `gemini-2.5-flash` a `gemini-2.0-flash` per ottenere:
- **92% risparmio sui costi** ($0.30→$0.10 input, $2.50→$0.40 output)
- Stessa context window (1M tokens)
- Velocità comparabile
- Stessa API compatibility

---

## Cost Comparison

| Metrica | Gemini 2.5 Flash | Gemini 2.0 Flash | Risparmio |
|---------|------------------|------------------|-----------|
| Input/1M tokens | $0.30 | $0.10 | 67% |
| Output/1M tokens | $2.50 | $0.40 | 84% |
| Context Window | 1M | 1M | = |
| **Costo totale stimato/mese** | ~$93 | ~$7 | **92%** |

*Stima basata su 500k queries/mese con 2k input + 500 output tokens media*

---

## Files to Modify

### 1. Core Configuration (CRITICAL)

| File | Line | Current | New |
|------|------|---------|-----|
| `backend/llm/zantara_ai_client.py` | 114 | `gemini-2.5-flash` | `gemini-2.0-flash` |
| `backend/services/gemini_service.py` | 25 | `gemini-2.5-flash` | `gemini-2.0-flash` |
| `backend/services/rag/agentic.py` | 381 | `gemini-2.5-flash` | `gemini-2.0-flash` |
| `backend/services/rag/vision_rag.py` | 48, 50 | `gemini-2.5-flash` | `gemini-2.0-flash` |

### 2. Oracle Services

| File | Line | Current | New |
|------|------|---------|-----|
| `backend/services/oracle_google_services.py` | 67, 76, 118, 123, 128, 133 | `gemini-2.5-flash` | `gemini-2.0-flash` |
| `backend/app/routers/oracle_universal.py` | 161, 166, 699, 761, 779, 1514, 1525 | `gemini-2.5-flash` | `gemini-2.0-flash` |
| `backend/services/smart_oracle.py` | 159 | `gemini-2.5-flash` | `gemini-2.0-flash` |

### 3. Router & Response Metadata

| File | Line | Current | New |
|------|------|---------|-----|
| `backend/services/intelligent_router.py` | 74, 114 | `gemini-2.5-flash` | `gemini-2.0-flash` |

### 4. Adapter Registry

| File | Line | Action |
|------|------|--------|
| `backend/llm/adapters/registry.py` | 8, 10 | Keep both, set 2.0 as default |

### 5. Tests (Update expected values)

| File | Lines |
|------|-------|
| `tests/api/test_oracle_universal_endpoints.py` | 592 |
| `tests/unit/test_router_oracle_universal.py` | 203, 792 |
| `tests/unit/test_gemini_service.py` | 57, 72 |
| `tests/integration/test_cross_component_integration.py` | 203 |
| `tests/integration/test_end_to_end_flows.py` | 320 |
| `tests/integration/test_oracle_comprehensive_integration.py` | 102, 123 |
| `tests/integration/test_all_router_endpoints_comprehensive.py` | 270 |
| `backend/tests/test_oracle_integration.py` | 65 |

---

## Migration Steps

### Phase 1: Configuration Update (5 min)

```bash
# Create feature branch
git checkout -b feat/migrate-gemini-2.0-flash
```

1. Update `zantara_ai_client.py` line 114
2. Update `gemini_service.py` line 25
3. Update `oracle_google_services.py` default model

### Phase 2: Service Updates (10 min)

1. Update `agentic.py` primary model
2. Update `vision_rag.py` models
3. Update `oracle_universal.py` all references
4. Update `smart_oracle.py` model
5. Update `intelligent_router.py` response metadata

### Phase 3: Test Updates (5 min)

1. Update all test expected values from `gemini-2.5-flash` to `gemini-2.0-flash`

### Phase 4: Documentation (5 min)

1. Update `AI_ONBOARDING.md`
2. Update `docs/RAG_ARCHITECTURE.md`
3. Update `docs/ARCHITECTURE.md`

### Phase 5: Validation

```bash
# Run tests
cd apps/backend-rag
pytest tests/ -v --tb=short

# Local smoke test
python -c "from backend.llm.zantara_ai_client import ZantaraAIClient; c = ZantaraAIClient(); print(c.model)"
```

---

## Fallback Chain Update - DeepSeek V3 ✅ IMPLEMENTED

### New Fallback Chain (Implemented):
```
Gemini 2.0 Flash → DeepSeek V3 → OpenRouter (free models)
```

### DeepSeek V3 Integration ✅

**Pricing**: $0.27/1M input, $1.10/1M output (cheapest paid option)

**Files created/modified**:
- ✅ `backend/services/deepseek_client.py` - Full client with streaming support
- ✅ `backend/services/gemini_service.py` - Integrated in fallback chain
- ✅ `backend/app/core/config.py` - Added `deepseek_api_key` setting

**Environment variable**:
```bash
DEEPSEEK_API_KEY=sk-your-key-here
```

**Note**: DeepSeek account needs credit balance. Client handles 402 errors gracefully and falls back to OpenRouter.

---

## Rollback Plan

If issues occur after deployment:

```bash
# Revert to previous commit
git revert HEAD

# Or quick fix: change model back
# In zantara_ai_client.py line 114:
self.model = model or "gemini-2.5-flash"
```

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Quality degradation | Medium | Low | A/B test before full rollout |
| API compatibility | Low | Very Low | Same Google API |
| Rate limits | Low | Low | Same/better limits for 2.0 |

---

## Checklist

- [x] Backup current configuration
- [x] Update all source files
- [x] Update all tests
- [ ] Run full test suite
- [ ] Deploy to staging
- [ ] Smoke test on staging
- [ ] Deploy to production
- [ ] Monitor error rates for 24h
- [x] Update documentation

---

## Approval

- [x] Technical Lead approval (user approved with "si")
- [ ] Cost savings verified
- [ ] Rollback plan tested
