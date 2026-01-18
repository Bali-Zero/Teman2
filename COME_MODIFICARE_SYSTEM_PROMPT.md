# 🎯 COME MODIFICARE SYSTEM PROMPT DI QWEN

## 📍 DOVE MODIFICARE

**File di configurazione:**

```
apps/backend-rag/backend/agents/config/qwen_system_prompts.py
```

Questo file contiene tutti i system prompt che definiscono il comportamento di Qwen.

---

## 🔧 SYSTEM PROMPTS DISPONIBILI

### **1. Test Generation Backend (Python)**

```python
TEST_GENERATION_SYSTEM_PROMPT_BACKEND
```

Usato quando genera test per codice Python/Backend.

### **2. Test Generation Frontend (TypeScript/React)**

```python
TEST_GENERATION_SYSTEM_PROMPT_FRONTEND
```

Usato quando genera test per codice TypeScript/React.

### **3. Default**

```python
DEFAULT_SYSTEM_PROMPT
```

Usato per altri task generici.

---

## ✏️ COME MODIFICARE

### **Esempio: Modificare System Prompt per Backend**

1. **Apri il file:**

```bash
code apps/backend-rag/backend/agents/config/qwen_system_prompts.py
```

2. **Modifica il prompt:**

```python
TEST_GENERATION_SYSTEM_PROMPT_BACKEND = """Sei un esperto sviluppatore Python e tester professionista.

Il tuo compito è generare test pytest completi, robusti e ben strutturati.

REGOLE FONDAMENTALI:
1. Genera SOLO codice Python valido, senza markdown o spiegazioni
2. Usa pytest e pytest-asyncio quando necessario
3. Mocka TUTTE le dipendenze esterne (API, database, file system, etc.)
4. Testa tutti i casi edge (None, valori vuoti, errori, etc.)
5. Raggiungi almeno 99% di coverage per il codice target
6. Usa nomi descrittivi per test e funzioni
7. Segui best practice Python (PEP 8, type hints quando utile)
8. Includi docstring per test complessi

# AGGIUNGI QUI LE TUE REGOLE PERSONALIZZATE:
9. Preferisci test parametrizzati quando possibile
10. Usa fixtures pytest per setup complesso
11. Testa anche performance quando rilevante
"""
```

3. **Salva e riavvia il sistema**

---

## 🎨 ESEMPI DI MODIFICHE

### **Esempio 1: Enfatizzare Coverage**

```python
TEST_GENERATION_SYSTEM_PROMPT_BACKEND = """...
PRIORITÀ ASSOLUTA: Raggiungi 100% coverage.
Ogni riga di codice deve essere testata almeno una volta.
"""
```

### **Esempio 2: Enfatizzare Performance**

```python
TEST_GENERATION_SYSTEM_PROMPT_BACKEND = """...
Includi sempre test di performance per funzioni critiche.
Usa pytest-benchmark per misurare tempi di esecuzione.
"""
```

### **Esempio 3: Stile Specifico**

```python
TEST_GENERATION_SYSTEM_PROMPT_BACKEND = """...
STILE RICHIESTO:
- Usa sempre type hints nei test
- Preferisci test parametrizzati con @pytest.mark.parametrize
- Usa fixtures per setup complesso
- Organizza test in classi quando logico
"""
```

---

## 🔍 DOVE VENGONO USATI

### **Unified Test Force Orchestrator:**

```python
# apps/backend-rag/backend/agents/agents/unified_test_force_orchestrator.py

# Linea ~248
request = LLMRequest(
    prompt=prompt,
    system=system_prompt,  # ← System prompt viene passato qui
    ...
)
```

### **LLM Adapter:**

```python
# apps/backend-rag/backend/agents/services/llm_adapter.py

# Linea ~492
payload = {
    "model": self.ollama_model,
    "prompt": request.prompt,
    "system": request.system,  # ← System prompt inviato a Ollama
    ...
}
```

---

## 🧪 TESTARE MODIFICHE

### **1. Modifica system prompt nel file di config**

### **2. Testa direttamente con Ollama:**

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:latest",
  "system": "Sei un esperto sviluppatore Python. Genera SOLO codice Python valido.",
  "prompt": "Scrivi test pytest per: def add(a, b): return a + b",
  "stream": false
}' | python3 -m json.tool
```

### **3. Riavvia sistema per applicare:**

```bash
./scripts/unified_test_force.sh
```

---

## 📊 COME FUNZIONA

### **System Prompt vs User Prompt:**

**System Prompt:**

- Definisce il **comportamento** del modello
- Esempio: "Sei un esperto sviluppatore Python"
- Rimane costante per tipo di task

**User Prompt:**

- Contiene il **task specifico**
- Esempio: "Genera test per questo file: ..."
- Cambia per ogni richiesta

### **Nel Sistema:**

```python
# System prompt (definisce comportamento)
system = "Sei un esperto sviluppatore Python. Genera SOLO codice Python valido."

# User prompt (task specifico)
prompt = "Genera test pytest per questo file: def add(a, b): return a + b"

# Ollama riceve entrambi
payload = {
    "system": system,  # Comportamento
    "prompt": prompt,   # Task specifico
}
```

---

## ✅ VANTAGGI SYSTEM PROMPT

1. **Consistenza:** Stesso comportamento per tutti i test
2. **Controllo:** Definisci esattamente come Qwen deve comportarsi
3. **Flessibilità:** Puoi cambiare comportamento senza modificare codice
4. **Separazione:** Separato dal prompt utente (più pulito)

---

## 🎯 BEST PRACTICE

1. **Sii specifico:** Definisci esattamente cosa vuoi
2. **Sii conciso:** System prompt troppo lunghi possono confondere
3. **Testa cambiamenti:** Prova sempre dopo modifiche
4. **Documenta:** Aggiungi commenti se modifichi regole complesse

---

## 📝 RIEPILOGO

1. **Modifica:** `apps/backend-rag/backend/agents/config/qwen_system_prompts.py`
2. **Scegli prompt:** Backend o Frontend
3. **Personalizza:** Aggiungi le tue regole
4. **Testa:** Verifica con Ollama direttamente
5. **Riavvia:** Sistema applicherà nuove modifiche

**Il system prompt definisce COME Qwen si comporta, il prompt utente definisce COSA deve fare!**
