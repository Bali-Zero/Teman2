# 📍 COME USARLO NEL TUO CODICE

## 🎯 DOVE PUOI USARLO SUBITO

### **1. Nel Unified Test Force** ⭐ (Raccomandato)

**File:** `apps/backend-rag/backend/agents/agents/unified_test_force_orchestrator.py`

**Dove modificare:** Nel metodo `_generate_test_with_qwen`

**Prima:**

```python
async def _generate_test_with_qwen(self, file_path: str, code: str):
    # Usa Qwen direttamente
    llm_request = LLMRequest(
        prompt=prompt,
        max_tokens=2000,
        provider=LLMProvider.OLLAMA,
    )
    response = await self.llm_adapter.generate(llm_request)
```

**Dopo:**

```python
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
    return response.text
```

---

### **2. Nuovo script per analisi codice**

**Crea:** `scripts/analyze_code.py`

```python
#!/usr/bin/env python3
"""Analizza codice usando Claude Max"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend-rag"))

from backend.agents.services.multi_ai_adapter import (
    AIRequest,
    TaskType,
    get_multi_ai_adapter,
)


async def analizza_file(file_path: str):
    """Analizza un file usando Claude Max"""
    with open(file_path) as f:
        codice = f.read()

    multi_ai = get_multi_ai_adapter()
    request = AIRequest(
        task_type=TaskType.CODE_ANALYSIS,
        prompt=f"Analizza questo codice e suggerisci miglioramenti:\n\n{codice}",
    )

    response = await multi_ai.generate(request)
    print(response.text)


if __name__ == "__main__":
    import sys
    file_path = sys.argv[1] if len(sys.argv) > 1 else "backend/app/main.py"
    asyncio.run(analizza_file(file_path))
```

**Uso:**

```bash
python3 scripts/analyze_code.py backend/app/main.py
```

---

### **3. Script per aprire file in IDE**

**Crea:** `scripts/open_in_ide.py`

```python
#!/usr/bin/env python3
"""Apri file in Cursor o Windsurf"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend-rag"))

from backend.agents.services.cursor_adapter import get_cursor_adapter
from backend.agents.services.windsurf_adapter import get_windsurf_adapter


def apri_file(file_path: str, ide: str = "cursor"):
    """Apri file in IDE"""
    if ide == "cursor":
        cursor = get_cursor_adapter()
        cursor.open_file(file_path)
        print(f"✅ File aperto in Cursor: {file_path}")
    elif ide == "windsurf":
        windsurf = get_windsurf_adapter()
        if windsurf.is_available():
            windsurf.open_file(file_path)
            print(f"✅ File aperto in Windsurf: {file_path}")
        else:
            print("❌ Windsurf non disponibile")
    else:
        print(f"❌ IDE non supportato: {ide}")


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "backend/app/main.py"
    ide = sys.argv[2] if len(sys.argv) > 2 else "cursor"
    apri_file(file_path, ide)
```

**Uso:**

```bash
python3 scripts/open_in_ide.py backend/app/main.py cursor
python3 scripts/open_in_ide.py backend/app/main.py windsurf
```

---

## 🚀 ESEMPI PRATICI

### **Esempio 1: Analizza codice**

```python
from backend.agents.services.multi_ai_adapter import (
    AIRequest,
    TaskType,
    get_multi_ai_adapter,
)

multi_ai = get_multi_ai_adapter()

request = AIRequest(
    task_type=TaskType.CODE_ANALYSIS,
    prompt="Analizza questo codice...",
)
response = await multi_ai.generate(request)
print(response.text)
```

### **Esempio 2: Genera documentazione**

```python
request = AIRequest(
    task_type=TaskType.DOCUMENTATION,
    prompt="Genera documentazione per questa funzione...",
)
response = await multi_ai.generate(request)
```

### **Esempio 3: Code review**

```python
request = AIRequest(
    task_type=TaskType.CODE_REVIEW,
    prompt="Fai code review di questo codice...",
)
response = await multi_ai.generate(request)
```

---

## ✅ VUOI CHE LO INTEGRI?

Posso:

1. ✅ Integrare nel `unified_test_force_orchestrator.py`
2. ✅ Creare script `analyze_code.py`
3. ✅ Creare script `open_in_ide.py`
4. ✅ Mostrare altri esempi

**Dimmi cosa vuoi e lo faccio!**
