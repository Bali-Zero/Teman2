# 🤖 GUIDA MULTI-AI SYSTEM - Qwen, Gemini, Claude, Cursor

## 🎯 SISTEMA MULTI-AI IMPLEMENTATO

Il sistema ora integra **4 AI tools** per il coding del sistema Nuzantara:

1. **Qwen (Ollama)** - Locale, test generation
2. **Gemini CLI** - Code analysis, documentation
3. **Claude Code** - Architecture, complex reasoning
4. **Cursor** - IDE integration, code editing

---

## 🚀 COME USARE

### **1. Test Generation (Qwen)**

```bash
cd apps/backend-rag
python3 -m backend.agents.agents.multi_ai_orchestrator \
    --task=test \
    --file="backend/app/main.py" \
    --code="$(cat backend/app/main.py)"
```

### **2. Code Analysis (Gemini)**

```bash
python3 -m backend.agents.agents.multi_ai_orchestrator \
    --task=analyze \
    --file="backend/app/main.py" \
    --code="$(cat backend/app/main.py)"
```

### **3. Architecture Design (Claude)**

```bash
python3 -m backend.agents.agents.multi_ai_orchestrator \
    --task=architecture \
    --code="Design a new payment system with..."
```

### **4. Code Refactoring (Gemini)**

```bash
python3 -m backend.agents.agents.multi_ai_orchestrator \
    --task=refactor \
    --file="backend/app/main.py" \
    --code="$(cat backend/app/main.py)"
```

### **5. Documentation (Gemini)**

```bash
python3 -m backend.agents.agents.multi_ai_orchestrator \
    --task=docs \
    --file="backend/app/main.py" \
    --code="$(cat backend/app/main.py)"
```

### **6. Code Review (Gemini)**

```bash
python3 -m backend.agents.agents.multi_ai_orchestrator \
    --task=review \
    --file="backend/app/main.py" \
    --code="$(cat backend/app/main.py)"
```

---

## 🎯 ROUTING AUTOMATICO

Il sistema route automaticamente al tool migliore:

| Task              | Tool   | Perché                     |
| ----------------- | ------ | -------------------------- |
| Test Generation   | Qwen   | Locale, veloce, privacy    |
| Code Analysis     | Gemini | Multimodale, buona analisi |
| Architecture      | Claude | Ragionamento complesso     |
| Refactoring       | Gemini | Buona comprensione codice  |
| Documentation     | Gemini | Generazione documentazione |
| Code Review       | Gemini | Analisi approfondita       |
| Simple Tasks      | Qwen   | Locale, veloce             |
| Privacy-Sensitive | Qwen   | Locale, sicuro             |

---

## 🔧 CONFIGURAZIONE

### **Gemini CLI:**

```bash
# Già installato: /Users/antonellosiano/.npm-global/bin/gemini
gemini --version
```

### **Claude API:**

```bash
# Set API key
export ANTHROPIC_API_KEY="your-key-here"

# Install package
pip install anthropic
```

### **Cursor:**

```bash
# Già installato: /Users/antonellosiano/.local/bin/cursor
cursor --version
```

### **Qwen (Ollama):**

```bash
# Già configurato e funzionante
ollama list
```

---

## 📊 ESEMPI D'USO

### **Esempio 1: Genera Test**

```python
from backend.agents.services.multi_ai_adapter import (
    AIRequest,
    TaskType,
    get_multi_ai_adapter,
)

multi_ai = get_multi_ai_adapter()

request = AIRequest(
    task_type=TaskType.TEST_GENERATION,
    prompt="Generate pytest test for: def add(a, b): return a + b",
)

response = await multi_ai.generate(request)
print(response.text)  # Test code generato da Qwen
```

### **Esempio 2: Analizza Codice**

```python
request = AIRequest(
    task_type=TaskType.CODE_ANALYSIS,
    prompt="Analyze this code for bugs and improvements: ...",
)

response = await multi_ai.generate(request)
print(response.text)  # Analisi da Gemini
```

### **Esempio 3: Design Architettura**

```python
request = AIRequest(
    task_type=TaskType.ARCHITECTURE,
    prompt="Design payment system architecture...",
)

response = await multi_ai.generate(request)
print(response.text)  # Architettura da Claude
```

---

## ✅ VANTAGGI

1. **Best Tool for Task:** Usa AI migliore per ogni task
2. **Resilienza:** Fallback automatico se un AI è down
3. **Costi:** Usa locale (Qwen) quando possibile
4. **Qualità:** Migliore qualità per task complessi
5. **Flessibilità:** Puoi forzare tool specifico se vuoi

---

## 🎯 PROSSIMI PASSI

1. ✅ Multi-AI Adapter implementato
2. ✅ Routing logic implementato
3. ✅ Fallback strategy implementato
4. 🔄 Testare con task reali
5. 🔄 Integrare nel Unified Test Force

---

## 📝 NOTA

**Deploy non necessario** - Tutto funziona localmente:

- Qwen: Locale (Ollama)
- Gemini: CLI locale
- Claude: API (ma opzionale)
- Cursor: IDE locale

**Sistema pronto per uso!** 🚀
