# 🎯 CONFIGURAZIONE CLAUDE MAX (OPUS)

## ✅ STATO

**Claude Max (Opus) configurato come AI principale** per la maggior parte dei task.

---

## 🔧 CONFIGURAZIONE

### **1. Con Abbonamento Claude:**

Se hai un **abbonamento Claude**, il sistema può usare le credenziali dell'abbonamento.
Non serve configurare API key separata se l'abbonamento è già attivo.

**Opzionale - Se vuoi usare API key esplicita:**

```bash
# Nel file .env o esporta variabile
export ANTHROPIC_API_KEY=sk-your-api-key-here
```

### **2. Verifica Installazione:**

```bash
pip install anthropic
```

### **3. Modello Configurato:**

- **Modello:** `claude-3-opus-20240229` (Claude Max/Opus)
- **Max Tokens:** 8192 (supporto completo)
- **Uso:** Primary per la maggior parte dei task
- **Abbonamento:** Usa abbonamento Claude invece di API key separata

---

## 🎯 ROUTING STRATEGY

**Claude Max è ora il tool principale per:**

| Task          | Tool           | Perché                     |
| ------------- | -------------- | -------------------------- |
| Code Analysis | **Claude Max** | Analisi approfondita       |
| Documentation | **Claude Max** | Generazione documentazione |
| Refactoring   | **Claude Max** | Refactoring intelligente   |
| Code Review   | **Claude Max** | Review approfondita        |
| Architecture  | **Claude Max** | Design complesso           |
| Simple Tasks  | **Claude Max** | Versatile e potente        |

**Qwen rimane per:**

- Test Generation (locale, veloce)
- Privacy-sensitive tasks (locale, sicuro)

---

## 📊 CONFIGURAZIONE ATTUALE

### **ClaudeAdapter:**

```python
class ClaudeAdapter:
    def __init__(self, model: str = "claude-3-opus-20240229"):
        # Claude Max (Opus) - modello più potente
        self.model = model
        self.max_tokens = 8192
```

### **Routing:**

```python
routing_map = {
    TaskType.CODE_ANALYSIS: AITool.CLAUDE,  # Claude Max
    TaskType.DOCUMENTATION: AITool.CLAUDE,  # Claude Max
    TaskType.REFACTORING: AITool.CLAUDE,    # Claude Max
    TaskType.CODE_REVIEW: AITool.CLAUDE,    # Claude Max
    TaskType.ARCHITECTURE: AITool.CLAUDE,   # Claude Max
    TaskType.SIMPLE_TASK: AITool.CLAUDE,     # Claude Max
    # ...
}
```

---

## 🚀 COME USARE

### **Via Multi-AI Adapter:**

```python
from backend.agents.services.multi_ai_adapter import (
    AIRequest,
    TaskType,
    get_multi_ai_adapter,
)

multi_ai = get_multi_ai_adapter()

# Claude Max sarà usato automaticamente
request = AIRequest(
    task_type=TaskType.CODE_ANALYSIS,
    prompt="Analyze this code...",
)
response = await multi_ai.generate(request)
# → Usa Claude Max automaticamente
```

### **Forzare Claude Max:**

```python
from backend.agents.services.multi_ai_adapter import AITool

request = AIRequest(
    task_type=TaskType.CODE_ANALYSIS,
    prompt="Analyze this code...",
    preferred_tool=AITool.CLAUDE,  # Forza Claude Max
)
response = await multi_ai.generate(request)
```

---

## ✅ VERIFICA

### **Test Configurazione:**

```python
from backend.agents.services.multi_ai_adapter import get_multi_ai_adapter

multi_ai = get_multi_ai_adapter()

# Verifica che Claude sia disponibile
if multi_ai.claude.client:
    print("✅ Claude Max configurato correttamente")
else:
    print("❌ Claude Max non disponibile - verifica ANTHROPIC_API_KEY")
```

---

## 📝 NOTA

**Claude Max (Opus)** è il modello più potente di Anthropic:

- ✅ Migliore qualità per task complessi
- ✅ Supporto fino a 8192 tokens
- ✅ Ragionamento avanzato
- ✅ Ideale per coding tasks complessi

**Sistema configurato per usare Claude Max come AI principale!** 🚀
