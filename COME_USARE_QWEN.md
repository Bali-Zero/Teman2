# 🤖 COME USARE QWEN - Guida Completa

## 🎯 COS'È QWEN?

**Qwen** è un modello LLM (Large Language Model) sviluppato da Alibaba Cloud, disponibile localmente tramite **Ollama**.

**Ollama** è un sistema che permette di eseguire modelli LLM localmente sul tuo Mac, senza bisogno di connessione internet o API esterne.

---

## 📚 DOCUMENTAZIONE

### **Ollama Official:**
- **Sito web:** https://ollama.ai
- **GitHub:** https://github.com/ollama/ollama
- **Documentazione:** https://github.com/ollama/ollama/blob/main/docs/README.md

### **Qwen Models:**
- **Hugging Face:** https://huggingface.co/Qwen
- **Ollama Library:** https://ollama.com/library/qwen2.5

---

## 🖥️ COMANDI BASE OLLAMA

### **1. Vedere modelli installati:**
```bash
ollama list
```

### **2. Scaricare un modello:**
```bash
ollama pull qwen2.5:latest
ollama pull qwen2.5:3b      # Versione più piccola
ollama pull qwen2.5:7b      # Versione media
```

### **3. Eseguire prompt direttamente:**
```bash
ollama run qwen2.5:latest "Scrivi una funzione Python per calcolare il fattoriale"
```

### **4. Chat interattiva:**
```bash
ollama run qwen2.5:latest
# Poi scrivi i tuoi prompt direttamente
```

---

## 🌐 API HTTP (Come Usa il Sistema)

### **1. Test semplice:**
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:latest",
  "prompt": "Scrivi una funzione Python per calcolare il fattoriale",
  "stream": false
}'
```

### **2. Con parametri avanzati:**
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:latest",
  "prompt": "Scrivi test pytest per questa funzione Python: def add(a, b): return a + b",
  "stream": false,
  "num_predict": 500,
  "temperature": 0.2
}'
```

### **3. Stream (risposta in tempo reale):**
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:latest",
  "prompt": "Spiega come funziona Python",
  "stream": true
}'
```

---

## 🐍 USO DA PYTHON

### **Esempio semplice:**
```python
import httpx
import json

response = httpx.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5:latest",
        "prompt": "Scrivi una funzione Python per calcolare il fattoriale",
        "stream": False,
    },
    timeout=600.0
)

data = response.json()
print(data["response"])
```

### **Esempio con parametri:**
```python
import httpx

response = httpx.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5:latest",
        "prompt": "Genera test pytest per questa funzione...",
        "num_predict": 2000,      # Max tokens
        "temperature": 0.2,        # Creatività (0.0-1.0)
        "stream": False,
    },
    timeout=600.0
)
```

---

## 🎨 PARAMETRI IMPORTANTI

### **num_predict (max_tokens):**
- **Cosa fa:** Limita lunghezza risposta
- **Range:** 1-200000
- **Default:** 128
- **Uso:** `2000` per test lunghi

### **temperature:**
- **Cosa fa:** Controlla creatività/randomness
- **Range:** 0.0-1.0
- **0.0:** Deterministico, ripetibile
- **0.7:** Creativo ma controllato
- **1.0:** Molto creativo
- **Uso:** `0.2` per codice/test (preciso)

### **top_p:**
- **Cosa fa:** Nucleus sampling
- **Range:** 0.0-1.0
- **Default:** 0.9
- **Uso:** `0.9` per varietà controllata

### **repeat_penalty:**
- **Cosa fa:** Penalizza ripetizioni
- **Range:** 0.0-2.0
- **Default:** 1.1
- **Uso:** `1.1` per evitare loop

---

## 🔧 COME IL SISTEMA USA QWEN

Il sistema Unified Test Force usa Qwen così:

```python
# backend/agents/services/llm_adapter.py

request = LLMRequest(
    prompt="Genera test pytest per questo file...",
    max_tokens=2000,        # Limite tokens
    temperature=0.2,        # Preciso, non creativo
    provider=LLMProvider.OLLAMA
)

response = await llm_adapter.generate(request)
```

**URL chiamato:**
```
POST http://localhost:11434/api/generate
```

**Payload:**
```json
{
  "model": "qwen2.5:latest",
  "prompt": "...",
  "num_predict": 2000,
  "temperature": 0.2,
  "stream": false
}
```

---

## 🧪 TEST PROMPT DIRETTAMENTE

### **1. Via Terminale:**
```bash
ollama run qwen2.5:latest "Scrivi test pytest per questa funzione Python: def multiply(a, b): return a * b"
```

### **2. Via HTTP:**
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:latest",
  "prompt": "Scrivi test pytest per questa funzione Python: def multiply(a, b): return a * b",
  "stream": false
}' | python3 -m json.tool
```

### **3. Via Python Script:**
```python
# test_qwen.py
import httpx
import json

prompt = """
Genera test pytest completi per questa funzione Python:

def calculate_total(items):
    return sum(item['price'] * item['quantity'] for item in items)

Requisiti:
- Test tutti i casi edge
- Usa pytest fixtures
- Mock dipendenze esterne
"""

response = httpx.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5:latest",
        "prompt": prompt,
        "num_predict": 2000,
        "temperature": 0.2,
        "stream": False,
    },
    timeout=600.0
)

data = response.json()
print(data["response"])
```

Esegui:
```bash
python3 test_qwen.py
```

---

## 📊 MODELLI QWEN DISPONIBILI

### **Dimensioni:**
- **qwen2.5:3b** - 3B parametri (più veloce, meno preciso)
- **qwen2.5:7b** - 7B parametri (bilanciato) ⭐
- **qwen2.5:latest** - 7B Q4_K_M (default)

### **Scaricare versione diversa:**
```bash
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b
```

### **Usare modello diverso:**
```bash
# Nel sistema, modifica:
export OLLAMA_MODEL="qwen2.5:3b"  # Più veloce
```

---

## 🎯 ESEMPI PROMPT PER TEST GENERATION

### **Esempio 1: Test Unitario Semplice**
```
Genera test pytest per questa funzione Python:

def add(a, b):
    return a + b

Requisiti:
- Test casi normali
- Test casi edge (None, stringhe, etc)
- Test errori
```

### **Esempio 2: Test con Mock**
```
Genera test pytest per questa funzione che usa requests:

def fetch_data(url):
    response = requests.get(url)
    return response.json()

Requisiti:
- Mock requests.get
- Test successo
- Test errore
- Test timeout
```

### **Esempio 3: Test Async**
```
Genera test pytest per questa funzione async:

async def fetch_user(user_id):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"/users/{user_id}")
        return response.json()

Requisiti:
- Usa pytest-asyncio
- Mock httpx.AsyncClient
- Test tutti i casi
```

---

## 🔍 DEBUGGING

### **Verificare Ollama funziona:**
```bash
curl http://localhost:11434/api/tags
```

### **Verificare modello disponibile:**
```bash
ollama list
```

### **Test generazione semplice:**
```bash
ollama run qwen2.5:latest "Ciao, funzioni?"
```

### **Vedere log Ollama:**
```bash
# Ollama log su macOS
tail -f ~/Library/Logs/ollama/ollama.log
```

---

## ✅ RIEPILOGO

1. **Ollama** = Sistema per eseguire LLM localmente
2. **Qwen** = Modello LLM disponibile via Ollama
3. **API:** `http://localhost:11434/api/generate`
4. **Comando diretto:** `ollama run qwen2.5:latest "prompt"`
5. **Il sistema** usa Qwen automaticamente per generare test

---

## 🚀 PROSSIMI PASSI

1. Prova prompt direttamente: `ollama run qwen2.5:latest "test prompt"`
2. Modifica prompt nel sistema se necessario
3. Testa diversi parametri (temperature, max_tokens)
4. Monitora performance e qualità risposte
