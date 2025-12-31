# Agentic RAG - Fix History & Critical Knowledge

**Last Updated:** 2025-12-31
**Maintainer:** AI Dev Team

> Questo documento registra i fix critici applicati al sistema Agentic RAG. Ogni AI agent deve leggerlo prima di modificare `reasoning.py`, `orchestrator.py`, o il sistema di evidence scoring.

---

## 1. Evidence Score System

### Architettura

Il sistema calcola un **evidence_score** (0.0 - 1.0) per determinare la qualità delle fonti trovate:

```
┌─────────────────────────────────────────────────────────────┐
│                    EVIDENCE SCORE FORMULA                    │
├─────────────────────────────────────────────────────────────┤
│  base_score = 0.0                                           │
│  + 0.5 if at least 1 source with score > 0.3               │
│  + 0.2 if total sources > 3                                 │
│  + 0.3 if context contains query keywords                   │
│  ─────────────────────────────────────                      │
│  MAX = 1.0                                                  │
└─────────────────────────────────────────────────────────────┘
```

**File:** `backend/services/rag/agentic/reasoning.py:63-120`

### Soglie Critiche

| Soglia | Valore | Comportamento |
|--------|--------|---------------|
| **ABSTAIN** | < 0.3 | Sistema rifiuta di rispondere |
| **WEAK EVIDENCE** | 0.3 - 0.6 | Risponde con linguaggio cauto |
| **CONFIDENT** | > 0.6 | Risposta normale |

---

## 2. FIX #1: Evidence Score Threshold (2025-12-30)

### Problema
Zantara trovava fonti valide ma rifiutava di rispondere. Il messaggio era:
> "Mi dispiace, non ho trovato informazioni verificate sufficienti..."

### Causa Root
La soglia per considerare una fonte "di alta qualità" era troppo alta (0.8). Il re-ranker ZeroEntropy produce tipicamente score tra 0.2-0.5, quindi quasi nessuna fonte superava la soglia.

### Fix Applicato

**File:** `reasoning.py:88-94`

```python
# PRIMA (broken)
high_quality_sources = [s for s in sources if s.get("score", 0.0) > 0.8]

# DOPO (fixed)
high_quality_sources = [s for s in sources if s.get("score", 0.0) > 0.3]
```

### Impatto
- Le fonti con score > 0.3 ora contribuiscono +0.5 all'evidence score
- Query con fonti valide non vengono più rifiutate

---

## 3. FIX #2: Trusted Tools Bypass (2025-12-31)

### Problema
Query di calcolo pure (es. "22% tax on 500M IDR") venivano rifiutate nonostante il calculator tool funzionasse correttamente.

**Log tipico:**
```
🔧 [Native Function Call] Detected: calculator with args: {'expression': '500000000 * 0.22'}
🛡️ [Uncertainty Stream] Evidence Score: 0.00
🛡️ [Uncertainty Stream] Triggered ABSTAIN (Score: 0.00)
```

### Causa Root
1. Calculator esegue correttamente e restituisce risultato
2. Ma evidence_score = 0.00 perché non ci sono fonti KB
3. Sistema triggera ABSTAIN ignorando che il calculator è una fonte affidabile

### Fix Applicato

**File:** `reasoning.py:503-515` (non-streaming) e `reasoning.py:867-883` (streaming)

```python
# ==================== TRUSTED TOOLS CHECK ====================
# Check if trusted tools (calculator, pricing, team) were used successfully
# These tools provide their own evidence and don't need KB sources
trusted_tools_used = False
trusted_tool_names = {"calculator", "pricing_lookup", "team_lookup"}

for step in state.steps:
    if step.action and hasattr(step.action, "tool_name"):
        if step.action.tool_name in trusted_tool_names and step.observation:
            # Tool was used and produced output
            if "error" not in step.observation.lower():
                trusted_tools_used = True
                logger.info(f"🧮 [Trusted Tool] {step.action.tool_name} used successfully, bypassing evidence check")
                break
```

**Policy Enforcement modificato:**
```python
# PRIMA
if evidence_score < 0.3 and not state.skip_rag:
    # ABSTAIN

# DOPO
if evidence_score < 0.3 and not state.skip_rag and not trusted_tools_used:
    # ABSTAIN
```

### Tool Affidabili

| Tool | Descrizione | Bypass Evidence |
|------|-------------|-----------------|
| `calculator` | Calcoli matematici | ✅ Sì |
| `pricing_lookup` | Prezzi servizi Bali Zero | ✅ Sì |
| `team_lookup` | Info team members | ✅ Sì |
| `vector_search` | Ricerca KB | ❌ No (richiede evidence) |

### Verifica

**Log di successo:**
```
🔧 [Native Function Call] Detected: calculator with args: {'expression': '500000000 * 0.22'}
🛡️ [Uncertainty Stream] Evidence Score: 0.00
🔍 [Trusted Tools Debug] Checking 3 steps for trusted tools
🔍 [Step Debug] tool=calculator, obs=Result: 110,000,000
🧮 [Trusted Tool Stream] calculator used successfully, bypassing evidence check
```

---

## 4. Intent Classifier & Skip RAG

### Come Funziona

L'intent classifier può settare `skip_rag=True` per query che non richiedono KB:

**File:** `backend/services/classification/intent_classifier.py`

```python
GENERAL_TASK_KEYWORDS = [
    # Translations
    "traduci", "translate", "terjemahkan",
    # Summaries
    "riassumi", "summarize", "rangkum",
    # Math/Calculations
    "calcola", "calculate", "quanto fa", "how much is",
    "quanto devo", "quanto pago", "berapa", "hitung",
    # Format conversions
    "converti", "convert",
]
```

Se una query matcha questi keyword → `skip_rag=True` → bypass evidence check.

### Interazione con Trusted Tools

```
Query: "22% tax on 500M"
    │
    ▼
Intent Classifier: "business_medium" (skip_rag=False)
    │
    ▼
ReAct Loop: Calculator called → Result: 110,000,000
    │
    ▼
Evidence Score: 0.00 (no KB sources)
    │
    ▼
Trusted Tools Check: calculator detected → trusted_tools_used=True
    │
    ▼
Policy: skip_rag=False BUT trusted_tools_used=True → BYPASS ABSTAIN
    │
    ▼
Response Generated Successfully ✅
```

---

## 5. Debug Logging

### Log Utili per Diagnosi

| Pattern | Significato |
|---------|-------------|
| `🛡️ [Uncertainty] Evidence Score: X.XX` | Score calcolato |
| `🧮 [Trusted Tool] X used successfully` | Tool affidabile usato |
| `🔍 [Trusted Tools Debug] Checking N steps` | Debug check attivo |
| `🏷️ [General Task] Skipping evidence check` | skip_rag=True |
| `🛡️ [Uncertainty] Triggered ABSTAIN` | Sistema rifiuta risposta |

### Come Attivare Debug Extra

Aggiungere in `reasoning.py` nel trusted tools loop:
```python
logger.info(f"🔍 [Step Debug] tool={step.action.tool_name}, obs={step.observation[:50]}")
```

---

## 6. Test Cases Critici

### Test Calculator (deve passare)
```
Query: "If I pay 22% corporate tax on 500M IDR profit, how much do I pay?"
Expected: "110,000,000 IDR" (o equivalente)
Expected Log: "🧮 [Trusted Tool Stream] calculator used successfully"
```

### Test ABSTAIN (deve rifiutare)
```
Query: "What are the nuclear regulations in Antarctica?"
Expected: "Mi dispiace, non ho trovato informazioni..."
Expected Log: "🛡️ [Uncertainty Stream] Triggered ABSTAIN"
```

### Test Evidence Normale (deve rispondere)
```
Query: "What is KITAS?"
Expected: Risposta con info KITAS da KB
Expected Log: "🛡️ [Uncertainty] Evidence Score: 0.XX" (> 0.3)
```

---

## 7. File Critici

| File | Responsabilità |
|------|----------------|
| `reasoning.py` | ReAct loop, evidence scoring, policy enforcement |
| `orchestrator.py` | Orchestrazione flusso RAG |
| `tools.py` | Definizione CalculatorTool e altri |
| `intent_classifier.py` | Classificazione intent e skip_rag |
| `tool_executor.py` | Esecuzione tool e parsing |

---

## 8. Checklist Pre-Modifica

Prima di modificare il sistema di evidence/abstain:

- [ ] Leggi questo documento
- [ ] Leggi `reasoning.py` (specialmente `calculate_evidence_score` e policy enforcement)
- [ ] Verifica i test esistenti: `pytest tests/unit/services/rag/agentic/`
- [ ] Testa localmente con query calculator e KB
- [ ] Deploy e verifica logs per pattern critici

---

**Deployed Version:** v1175 (2025-12-31)
