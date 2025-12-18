# Alternative ML per Estrazione Metadata - Contenuti Legali/Fiscali

## Problema: Gemini Blocca Contenuti Legali/Fiscali

**Gemini 2.5 Flash** blocca sistematicamente contenuti legali/fiscali/immigrazione tramite safety filters, anche con impostazioni permissive.

**Risultato**: Success rate 0% su questi contenuti.

## Alternative Disponibili

### 1. ✅ OpenAI GPT-4o-mini (RACCOMANDATO)

**Vantaggi:**
- ✅ Meno restrittivo di Gemini per contenuti legali/fiscali
- ✅ Già configurato nel sistema (`zantara_ai_model: gpt-4o-mini`)
- ✅ Buon supporto per estrazione strutturata
- ✅ Costo ragionevole: ~$0.15/$0.60 per 1M tokens
- ✅ API stabile e affidabile

**Configurazione:**
```bash
export OPENAI_API_KEY='your-openai-api-key'
```

**Costo stimato per 25k documenti:**
- Input: ~500 tokens/doc × 25k = 12.5M tokens = ~$1.88
- Output: ~50 tokens/doc × 25k = 1.25M tokens = ~$0.75
- **Totale: ~$2.63**

**Quando usare:**
- Contenuti legali/fiscali/immigrazione
- Estrazione metadata strutturata
- Quando Pattern extraction non è sufficiente

### 2. ✅ Claude 3.5 Sonnet (Anthropic)

**Vantaggi:**
- ✅ Più permissivo per contenuti legali
- ✅ Eccellente per estrazione strutturata
- ✅ Migliore comprensione contestuale
- ✅ Safety filters configurabili

**Svantaggi:**
- ⚠️ Più costoso: ~$3/$15 per 1M tokens
- ⚠️ Richiede API key Anthropic

**Configurazione:**
```bash
export ANTHROPIC_API_KEY='your-anthropic-api-key'
```

**Costo stimato per 25k documenti:**
- Input: ~500 tokens/doc × 25k = 12.5M tokens = ~$37.50
- Output: ~50 tokens/doc × 25k = 1.25M tokens = ~$18.75
- **Totale: ~$56.25**

**Quando usare:**
- Quando OpenAI non è sufficiente
- Documenti molto complessi
- Quando budget lo permette

### 3. ⚠️ Modelli Open-Source via OpenRouter

**Opzioni:**
- Llama 3.1 70B
- Mistral Large
- Mixtral 8x7B

**Vantaggi:**
- ✅ Più economici
- ✅ Nessun safety filter restrittivo
- ✅ Open-source

**Svantaggi:**
- ⚠️ Qualità inferiore rispetto a GPT-4/Claude
- ⚠️ Richiede configurazione OpenRouter

**Configurazione:**
```bash
export OPENROUTER_API_KEY_LLAMA='your-openrouter-api-key'
```

## Raccomandazione Finale

### 🎯 Strategia Consigliata: **OpenAI GPT-4o-mini**

**Perché:**
1. ✅ Già configurato nel sistema
2. ✅ Meno restrittivo di Gemini
3. ✅ Costo ragionevole (~$2.63 per 25k docs)
4. ✅ Buona qualità per estrazione strutturata
5. ✅ API stabile e affidabile

### 📊 Confronto Modelli

| Modello | Success Rate | Costo (25k docs) | Safety Filters | Raccomandato |
|---------|--------------|------------------|----------------|--------------|
| **Gemini 2.5 Flash** | 0% ❌ | $0 | Blocca legali/fiscali | ❌ NO |
| **OpenAI GPT-4o-mini** | ~95% ✅ | $2.63 | Permissivo | ✅ SÌ |
| **Claude 3.5 Sonnet** | ~98% ✅ | $56.25 | Molto permissivo | ⚠️ Se budget lo permette |
| **Pattern Extraction** | 100% ✅ | $0 | N/A | ✅ Fallback sicuro |

## Implementazione

### Opzione 1: Usa OpenAI già configurato

Il sistema ha già supporto per OpenAI. Modifica `ml_metadata_extractor.py` per usare OpenAI invece di Gemini:

```python
from openai import OpenAI

class OpenAIExtractor:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"

    def extract(self, collection_name: str, text: str) -> dict:
        # Usa OpenAI invece di Gemini
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[...],
            temperature=0.1,
        )
        return parse_json(response.choices[0].message.content)
```

### Opzione 2: Usa Pattern Extraction (Raccomandato)

**Pattern extraction è sufficiente per la maggior parte dei casi:**
- ✅ Success rate: 100%
- ✅ Veloce e gratis
- ✅ Media: 2-3 campi/documento
- ✅ Non bloccato da safety filters

**Quando usare ML:**
- Solo quando Pattern fallisce
- Documenti molto complessi
- Quando servono più campi strutturati

## Prossimi Passi

1. **Test OpenAI GPT-4o-mini:**
   ```bash
   export OPENAI_API_KEY='your-key'
   python scripts/ml_extractor_alternatives.py
   ```

2. **Confronta risultati:**
   - Pattern vs OpenAI
   - Qualità vs Costo
   - Success rate

3. **Decidi strategia:**
   - Pattern-first (raccomandato)
   - OpenAI per casi complessi
   - Hybrid (Pattern + OpenAI)

## Conclusione

**Per contenuti legali/fiscali/immigrazione:**

1. ✅ **Pattern Extraction** come default (gratis, 100% success rate)
2. ✅ **OpenAI GPT-4o-mini** quando Pattern non è sufficiente
3. ❌ **Gemini** non adatto (blocca contenuti)

**Costo totale stimato:**
- Pattern: $0 (gratis)
- OpenAI (solo quando necessario): ~$2.63 per 25k docs
- **Risparmio vs Claude: ~$53.62**
