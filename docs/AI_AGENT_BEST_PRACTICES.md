# AI Agent Best Practices - Summary & Recommendations

**Date:** 2026-01-13  
**Updated Section:** `docs/AI_ONBOARDING.md` - Section 3.6

---

## 📋 **Cosa Ho Aggiunto**

### **Section 3.6: MANDATORY RULES FOR AI AGENTS**

Nuova sezione completa con 7 sub-sezioni:

1. **Testing Before Deploy** (MANDATORY)
2. **Deployment Method** (MANDATORY)
3. **Coverage Testing** (RECOMMENDED - quando farla)
4. **Logging & Metrics** (BEST PRACTICES - quando aggiungerli)
5. **Error Handling Pattern** (MANDATORY)
6. **Code Quality Checklist** (prima di commit)
7. **Communication Protocol** (come chiedere aiuto)

---

## ✅ **Risposta alle Tue Domande**

### **Q1: "AI devono fare i test prima di deploy?"**

**✅ SÌ - OBBLIGATORIO**

Aggiunto in Section 3.6.1:
```markdown
**RULE:** AI agents MUST run tests before EVERY deployment, no exceptions.

# ✅ CORRECT - AI must always do this
cd apps/backend-rag
PYTHONPATH=backend pytest tests/unit/ -q --tb=short

# ❌ FORBIDDEN - AI must NEVER skip tests
./scripts/safe-deploy.sh --skip-tests
```

**Rationale:**
- AI non ha intuizione per valutare "questo deploy è sicuro"
- Test automatici cattureranno bug introdotti da AI
- Evidence di qualità prima di production

---

### **Q2: "Quando fare coverage test 99%?"**

**📊 MIA RACCOMANDAZIONE:**

#### **Coverage Testing: 3 Scenari**

**Scenario A - New Feature Implementation** ⭐ (SEMPRE)
```bash
# Dopo implementazione feature, prima di deploy
cd apps/backend-rag
PYTHONPATH=backend pytest --cov=backend.services.rag.agentic \
  --cov=backend.app.routers \
  --cov-report=html \
  --cov-fail-under=90
```

**Target:** ≥90% (current: 95.01%)

**Scenario B - Critical Path Changes** (SEMPRE)
- Modified `reasoning.py`, `orchestrator.py`, `llm_gateway.py`
- Changed core routers (auth, RAG, CRM)
- Database models/migrations

**Scenario C - Weekly Quality Check** (RACCOMANDATO)
```bash
# Ogni venerdì o prima di major release
PYTHONPATH=backend pytest --cov=backend --cov-report=html --cov-fail-under=90
```

**NON necessario per:**
- Documentation changes
- UI-only changes (frontend)
- Config tweaks (no code)

---

### **Q3: "Quando aggiungere logging e metriche?"**

**📝 MIA RACCOMANDAZIONE:**

#### **Logging: 3 Momenti Chiave**

**A) New Service/Router** (SEMPRE)
```python
import logging
logger = logging.getLogger(__name__)

class NewService:
    async def operation(self):
        logger.info("Starting operation")  # ✅ Entry point
        try:
            result = await work()
            logger.info(f"✅ Success: {result}")  # ✅ Success
            return result
        except Exception as e:
            logger.error(f"❌ Failed: {e}", exc_info=True)  # ✅ Error
            raise
```

**B) External API Calls** (SEMPRE)
```python
logger.debug(f"Calling API: {endpoint}")
response = await client.post(endpoint)
logger.info(f"API: status={response.status}, time={elapsed}ms")
```

**C) Decision Points** (AI Reasoning)
```python
logger.info(f"🤔 Evidence score: {score:.2f}")
if score < threshold:
    logger.warning("🛡️ ABSTAIN - insufficient evidence")
```

#### **Metrics: 2 Momenti Chiave**

**A) Performance-Critical** (SEMPRE)
```python
from backend.app.metrics import metrics_collector

@trace_span("service.operation")
async def expensive_operation():
    start = time.time()
    result = await work()
    duration = time.time() - start
    metrics_collector.record_operation_duration("op", duration)
```

**B) Business KPIs** (RACCOMANDATO)
```python
# Tool usage
metrics_collector.increment_counter("tool_calls", {"tool": tool_name})

# Cache performance
metrics_collector.record_cache_hit("semantic_cache", hit=True)

# LLM costs
metrics_collector.record_llm_tokens(prompt, completion, model)
```

**EVITA over-logging:**
- ❌ Tight loops (usa sampling: `if i % 100 == 0`)
- ❌ Sensitive data (PII, keys, passwords)
- ❌ DEBUG level in production hot paths

---

## 🎯 **Altri Approcci Importanti Aggiunti**

### **1. Error Handling Pattern** (Section 3.6.5)

Pattern standard per AI:
```python
try:
    result = await operation()
    return result
except SpecificError as e:
    logger.error(f"Specific: {e}", exc_info=True)
    return fallback
except Exception as e:
    logger.exception("Unexpected error")
    raise ServiceError("Failed") from e
```

**Evita:**
- ❌ Bare `except:` (swallows tutto)
- ❌ `raise e` (perde context)
- ❌ String exceptions

---

### **2. Code Quality Checklist** (Section 3.6.6)

**Prima di ogni commit, AI verifica:**
- [ ] ✅ Tests scritti e passano
- [ ] ✅ Type hints aggiunti
- [ ] ✅ Docstrings per funzioni public
- [ ] ✅ No hardcoded values
- [ ] ✅ Error handling implementato
- [ ] ✅ Logging aggiunto
- [ ] ✅ No `print()` (usa `logger`)
- [ ] ✅ Code formatted (`ruff format`)
- [ ] ✅ Lint clean (`ruff check`)

---

### **3. Communication Protocol** (Section 3.6.7)

**Quando AI si blocca:**

**❌ BAD:**
> "Non funziona, cosa devo fare?"

**✅ GOOD:**
> "Implementato feature X ma test falliscono con error Y.
> Tentato:
> 1. Approach A - fallito per Z
> 2. Approach B - parziale ma edge case W
> 
> Due opzioni:
> - Option 1: Refactor con pattern P
> - Option 2: Validazione a layer L
> 
> Quale allineata meglio con architettura?"

---

## 📊 **Comparison: AI vs Human**

| Aspetto | AI Agent | Human Developer |
|---------|----------|-----------------|
| **Tests before deploy** | ✅ MANDATORY | 🟡 Recommended |
| **Coverage testing** | ✅ Always on new features | 🟡 Periodic |
| **Deploy method** | ✅ ONLY safe-deploy.sh | 🟢 Flexible (3 options) |
| **Skip tests flag** | ❌ FORBIDDEN | 🟢 Allowed (judgment call) |
| **Logging level** | ✅ INFO/ERROR standard | 🟢 DEBUG when debugging |
| **Error handling** | ✅ Always try/except | 🟡 Judgment call |
| **Code review** | ✅ Checklist mandatory | 🟡 Experience-based |

**Perché più strict per AI?**
- ❌ AI non ha intuizione
- ❌ AI non monitora post-deploy
- ❌ AI non valuta risk/reward
- ✅ AI beneficia di guardrails automatici

---

## 🎓 **Best Practices Non Ovvie** (Aggiunte)

### **1. Sampling in Loops**
```python
# ❌ BAD - log spam
for i, item in enumerate(large_list):
    logger.debug(f"Processing item {i}")

# ✅ GOOD - sample logging
for i, item in enumerate(large_list):
    if i % 100 == 0:  # Log ogni 100 items
        logger.info(f"Progress: {i}/{len(large_list)}")
```

### **2. Context in Exceptions**
```python
# ❌ BAD - perde context
except ValueError as e:
    raise ValueError("Failed")

# ✅ GOOD - mantiene chain
except ValueError as e:
    raise ServiceError("Failed to parse") from e
```

### **3. Structured Logging**
```python
# ❌ BAD - string concatenation
logger.info("User " + user_id + " performed action " + action)

# ✅ GOOD - structured
logger.info(f"User action", extra={
    "user_id": user_id,
    "action": action,
    "timestamp": now()
})
```

### **4. Defensive Type Checking**
```python
# ✅ GOOD - AI-friendly defensive code
def process(data: dict | None) -> Result:
    if not isinstance(data, dict):
        logger.warning(f"Invalid data type: {type(data)}")
        return Result.empty()
    
    if "required_field" not in data:
        logger.error("Missing required_field")
        raise ValueError("required_field missing")
```

---

## 🔄 **Workflow Completo AI Agent**

```bash
# 1. Implementa feature
# ... code changes ...

# 2. Auto-format & lint
cd apps/backend-rag
ruff format backend/
ruff check backend/

# 3. Run tests (MANDATORY)
PYTHONPATH=backend pytest tests/unit/ -q --tb=short

# 4. Coverage test (if new feature)
PYTHONPATH=backend pytest --cov=backend.services.new_feature \
  --cov-report=html --cov-fail-under=90

# 5. Review coverage report
open htmlcov/index.html

# 6. Commit changes
git add .
git commit -m "feat: implement feature X with tests"

# 7. Deploy with safe-deploy (MANDATORY)
cd ../..
./scripts/safe-deploy.sh

# 8. Monitor logs post-deploy
flyctl logs -a nuzantara-rag
```

**Tempo stimato:** ~6-8 minuti (ma AI non ha fretta)

---

## 📝 **Summary Checklist per AI**

Prima di ogni deploy, AI verifica:

- [ ] ✅ **Tests scritti** per nuovo codice
- [ ] ✅ **Tests passano** localmente
- [ ] ✅ **Coverage ≥90%** su nuovo codice
- [ ] ✅ **Logging aggiunto** per decision points
- [ ] ✅ **Metrics aggiunte** se performance-critical
- [ ] ✅ **Error handling** implementato
- [ ] ✅ **Type hints** aggiunti
- [ ] ✅ **No hardcoded values**
- [ ] ✅ **Code formatted** (ruff)
- [ ] ✅ **Deploy con safe-deploy.sh** (no skip-tests)

---

## 🎯 **Action Items**

**Completato:**
- ✅ Aggiunta Section 3.6 a `docs/AI_ONBOARDING.md`
- ✅ 7 sub-sezioni con regole dettagliate
- ✅ Code examples per ogni pattern
- ✅ Comparison AI vs Human
- ✅ Best practices non ovvie

**Prossimi passi:**
- 🟡 Considera aggiungere pre-commit hooks per AI
- 🟡 Template per PR descriptions AI-generated
- 🟡 Automated quality gates (GitHub Actions for quality checks)

---

**Tutto è documentato e pronto per essere usato dalle future AI sessions!** ✅
