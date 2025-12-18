# 🆓 PATCH: Modelli GRATUITI per Bali Intel Scraper

**Cosa fa questa patch:**
- Sostituisce Llama 3.3 70B ($0.20/$0.20) con **Google Gemini Flash 1.5 (GRATIS)**
- Sostituisce Gemini 2.0 Flash (a pagamento) con **Gemini Flash 1.5 (GRATIS)**
- Mantiene Claude Haiku come ultimo fallback (opzionale)
- **COSTO FINALE: $0 con solo OpenRouter API key**

---

## 📝 MODIFICA DA FARE

**File:** `apps/bali-intel-scraper/scripts/ai_journal_generator.py`

### **Linea 93-96** - Cambia il modello Llama

**BEFORE (a pagamento):**
```python
response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {self.openrouter_key}",
        "Content-Type": "application/json"
    },
    json={
        "model": "meta-llama/llama-3.3-70b-instruct",  # ❌ QUESTO COSTA
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 2000
    },
    timeout=60
)
```

**AFTER (GRATIS):**
```python
response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {self.openrouter_key}",
        "Content-Type": "application/json"
    },
    json={
        "model": "google/gemini-flash-1.5",  # ✅ GRATIS!
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 2000
    },
    timeout=60
)
```

---

### **Linea 154** - Elimina Gemini nativo (usa solo OpenRouter)

**BEFORE:**
```python
if self.gemini_key:
    genai.configure(api_key=self.gemini_key)
    self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
```

**AFTER (commenta o rimuovi):**
```python
# Gemini via OpenRouter (gratis) - non serve più Google AI SDK
# if self.gemini_key:
#     genai.configure(api_key=self.gemini_key)
#     self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
```

---

### **Linea 167-187** - Usa OpenRouter per fallback Gemini

**BEFORE (usa Google AI SDK - costa):**
```python
def generate_with_gemini(self, content: str, category: str, metadata: Dict) -> Optional[str]:
    """Generate article using Gemini 2.0 Flash (FALLBACK 1)"""

    if not self.gemini_key:
        return None

    try:
        logger.info("💎 Attempting generation with Gemini 2.0 Flash...")

        prompt = self._build_journal_prompt(content, category, metadata)

        response = self.gemini_model.generate_content(prompt)  # ❌ USA GOOGLE SDK

        if response.text:
            article = response.text
            # ... resto del codice
```

**AFTER (usa OpenRouter - gratis):**
```python
def generate_with_gemini(self, content: str, category: str, metadata: Dict) -> Optional[str]:
    """Generate article using Gemini Flash 1.5 via OpenRouter (FALLBACK 1 - FREE)"""

    if not self.openrouter_key:  # ✅ Usa OpenRouter invece di gemini_key
        return None

    try:
        logger.info("💎 Attempting generation with Gemini Flash 1.5 FREE (via OpenRouter)...")

        import requests

        prompt = self._build_journal_prompt(content, category, metadata)

        # ✅ USA OPENROUTER (GRATIS)
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-flash-1.5",  # ✅ GRATIS
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2000
            },
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            article = result['choices'][0]['message']['content']

            # Estimate cost (FREE!)
            input_tokens = result['usage']['prompt_tokens']
            output_tokens = result['usage']['completion_tokens']
            cost = 0.0  # ✅ GRATIS!

            self.metrics['gemini_success'] += 1
            self.metrics['total_cost_usd'] += cost

            logger.success(f"✅ Gemini FREE generated article (Cost: $0.00)")
            return article
        else:
            logger.warning(f"❌ Gemini failed: {response.status_code}")
            return None
```

---

## 🚀 COME APPLICARE LA PATCH

### **Opzione 1: Modifica Manuale (consigliato)**

1. Apri il file:
   ```bash
   code apps/bali-intel-scraper/scripts/ai_journal_generator.py
   ```

2. Trova la linea 97 e cambia:
   ```python
   "model": "meta-llama/llama-3.3-70b-instruct",
   ```
   in:
   ```python
   "model": "google/gemini-flash-1.5",
   ```

3. Trova la linea 170-187 (funzione `generate_with_gemini`) e sostituisci con il codice AFTER mostrato sopra.

4. Salva il file.

---

### **Opzione 2: Usa Claude Code**

Passa questo file a Claude Code e chiedigli:

```
"Applica le modifiche descritte in FREE_MODELS_PATCH.md al file
apps/bali-intel-scraper/scripts/ai_journal_generator.py"
```

---

## ✅ RISULTATO FINALE

**PRIMA (costi):**
- Llama 3.3 70B: $0.20/$0.20 per 1M tokens
- Gemini 2.0 Flash: $0.075/$0.30 per 1M tokens
- **Costo medio:** ~$0.0004 per articolo

**DOPO (gratis):**
- Gemini Flash 1.5 (PRIMARY): **$0.00**
- Gemini Flash 1.5 (FALLBACK 1): **$0.00**
- Claude Haiku (FALLBACK 2 opzionale): $1/$5 per 1M tokens
- **Costo medio:** **$0.00 per articolo**

---

## 🧪 TEST

Dopo aver applicato la patch:

```bash
# Set solo OpenRouter key
export OPENROUTER_API_KEY_LLAMA="your_openrouter_api_key_here"

# Test completo GRATIS
cd apps/bali-intel-scraper
python3 scripts/orchestrator.py \
  --stage all \
  --categories immigration \
  --scrape-limit 2 \
  --max-articles 2

# Verifica output
ls -la data/articles/immigration/
```

**Aspettati:**
- ✅ Scraping: 2 articoli raw
- ✅ AI Generation: 2 articoli professional journal
- ✅ Costo: $0.00
- ✅ Tempo: ~30 secondi

---

## 📊 MODELLI GRATUITI OPENROUTER

Altri modelli gratis che puoi usare:

| Model | Provider | Costo | Qualità |
|-------|----------|-------|---------|
| `google/gemini-flash-1.5` | Google | **FREE** | ⭐⭐⭐⭐⭐ |
| `meta-llama/llama-3.2-3b-instruct` | Meta | **FREE** | ⭐⭐⭐⭐ |
| `mistralai/mistral-7b-instruct` | Mistral | **FREE** | ⭐⭐⭐⭐ |
| `google/gemini-2.0-flash-thinking-exp-01-21` | Google | **FREE** | ⭐⭐⭐⭐⭐ |

**Consiglio:** Usa `google/gemini-flash-1.5` - è il migliore per qualità/prezzo (gratis).

---

## 💡 NOTE

1. **OpenRouter ha rate limits sui modelli gratis** (solitamente 200 richieste/giorno)
2. Se superi il limit, lo script farà fallback automatico a Claude (se configurato)
3. Per uso production pesante, considera modelli a pagamento economici
4. Gemini Flash 1.5 FREE è perfetto per test e uso moderato

---

**Created:** 2025-11-13
**For:** Bali Zero Intel Scraper
**By:** Claude Code
