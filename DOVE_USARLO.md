# 📍 DOVE USARE IL SISTEMA MULTI-AI

## 🎯 DOVE PUOI USARLO

### **1. Nel Unified Test Force (già esistente)**

Il tuo sistema `unified_test_force_orchestrator.py` usa Qwen per generare test.
Puoi sostituirlo con `MultiAIAdapter` per usare Claude Max automaticamente.

**File:** `apps/backend-rag/backend/agents/agents/unified_test_force_orchestrator.py`

**Dove:** Nel metodo `_generate_test_with_qwen`

---

### **2. In qualsiasi script Python**

Puoi usarlo in qualsiasi script Python del progetto.

**Esempio:**

```python
from backend.agents.services.multi_ai_adapter import (
    AIRequest,
    TaskType,
    get_multi_ai_adapter,
)

# Analizza codice
multi_ai = get_multi_ai_adapter()
request = AIRequest(
    task_type=TaskType.CODE_ANALYSIS,
    prompt="Analizza questo codice...",
)
response = await multi_ai.generate(request)
```

---

### **3. Per aprire file in Cursor/Windsurf**

```python
from backend.agents.services.cursor_adapter import get_cursor_adapter

cursor = get_cursor_adapter()
cursor.open_file("path/to/file.py")  # Apre in Cursor IDE
```

---

## 🔧 ESEMPIO PRATICO: INTEGRARE NEL TEST FORCE

### **PRIMA (codice attuale):**

```python
# unified_test_force_orchestrator.py
async def _generate_test_with_qwen(self, file_path: str, code: str):
    # Usa Qwen direttamente
    llm_request = LLMRequest(
        prompt=prompt,
        max_tokens=2000,
        provider=LLMProvider.OLLAMA,
    )
    response = await self.llm_adapter.generate(llm_request)
```

### **DOPO (con Multi-AI):**

```python
# unified_test_force_orchestrator.py
from backend.agents.services.multi_ai_adapter import (
    AIRequest,
    TaskType,
    get_multi_ai_adapter,
)

async def _generate_test_with_qwen(self, file_path: str, code: str):
    # Usa Multi-AI (route automaticamente a Qwen per test)
    multi_ai = get_multi_ai_adapter()
    request = AIRequest(
        task_type=TaskType.TEST_GENERATION,  # → Route a Qwen
        prompt=prompt,
    )
    response = await multi_ai.generate(request)
```

---

## 📝 DOVE INTEGRARLO NEL TUO CODICE

### **Opzione 1: Nel Unified Test Force**

- **File:** `unified_test_force_orchestrator.py`
- **Metodo:** `_generate_test_with_qwen`
- **Cosa fa:** Genera test usando Qwen (o Claude Max se vuoi)

### **Opzione 2: Nuovo script per analisi codice**

- **Crea:** `scripts/analyze_code.py`
- **Cosa fa:** Analizza codice usando Claude Max

### **Opzione 3: Script per aprire file IDE**

- **Crea:** `scripts/open_in_ide.py`
- **Cosa fa:** Apre file in Cursor/Windsurf

---

## 🚀 VUOI CHE LO INTEGRI?

Posso integrare `MultiAIAdapter` nel tuo `unified_test_force_orchestrator.py` per:

- ✅ Usare Claude Max per analisi codice
- ✅ Mantenere Qwen per test generation
- ✅ Aprire file in Cursor/Windsurf quando necessario

**Vuoi che lo faccia ora?**
