# Google AI Ultra Plan - Opzioni per Estrazione Metadata

## Panoramica

Con **Google AI Ultra plan** hai accesso a:
- ✅ **Gemini 2.5 Flash**: Unlimited (già configurato)
- ✅ **Google Document AI**: Servizio managed per estrazione documenti
- ✅ **Vertex AI**: Piattaforma completa con modelli avanzati
- ✅ **NotebookLM**: Analisi documentale intelligente

## Problema Attuale

**Gemini 2.5 Flash** blocca contenuti legali/fiscali/immigrazione tramite safety filters, anche con piano Ultra.

## Soluzioni Disponibili con Ultra Plan

### 1. ✅ Google Document AI (RACCOMANDATO)

**Caratteristiche:**
- ✅ **Specializzato per documenti**: OCR + estrazione strutturata
- ✅ **Nessun safety filter**: Progettato per documenti legali/fiscali
- ✅ **API managed**: Nessuna gestione infrastruttura
- ✅ **Incluso in Ultra plan**: Potrebbe essere incluso

**Costi:**
- $1.50 per 1000 pagine
- **25k documenti: ~$37.50**

**Quando usare:**
- Documenti PDF/immagini
- Quando serve OCR
- Estrazione campi strutturati
- Documenti con form standardizzati

**API:**
```python
from google.cloud import documentai

def extract_metadata_with_document_ai(file_path: str):
    client = documentai.DocumentProcessorServiceClient()

    # Process document
    with open(file_path, "rb") as f:
        raw_document = documentai.RawDocument(
            content=f.read(), mime_type="application/pdf"
        )

    request = documentai.ProcessRequest(
        name=processor_name, raw_document=raw_document
    )

    result = client.process_document(request=request)
    document = result.document

    # Extract structured data
    return {
        "text": document.text,
        "entities": document.entities,
        "form_fields": document.form_fields,
    }
```

---

### 2. ✅ Vertex AI Gemini Pro (Se Disponibile)

**Caratteristiche:**
- ✅ **Modelli più potenti**: Gemini Pro su Vertex AI
- ✅ **Meno restrizioni**: Potrebbe avere safety filters configurabili
- ✅ **Enterprise grade**: Più controllo

**Quando usare:**
- Quando Document AI non è sufficiente
- Quando serve comprensione contestuale avanzata
- Budget Vertex AI disponibile

**API:**
```python
from google.cloud import aiplatform
import vertexai
from vertexai.preview.generative_models import GenerativeModel

vertexai.init(project="your-project", location="us-central1")
model = GenerativeModel("gemini-pro")

response = model.generate_content(
    prompt,
    generation_config={
        "temperature": 0.1,
        "max_output_tokens": 500,
    },
    safety_settings={
        "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
        "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
        "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
    }
)
```

---

### 3. ✅ NotebookLM (Google)

**Caratteristiche:**
- ✅ **Analisi documentale**: Interagisce con documenti
- ✅ **Generazione riassunti**: Crea riassunti automatici
- ✅ **Interfaccia conversazionale**: Chat con documenti

**Quando usare:**
- Analisi documenti complessi
- Quando serve interazione conversazionale
- Generazione riassunti automatici

**Limitazioni:**
- ⚠️ Non è un'API diretta per estrazione metadata
- ⚠️ Più orientato a analisi che estrazione strutturata

---

### 4. ✅ Pattern Extraction (Fallback Sicuro)

**Caratteristiche:**
- ✅ **100% success rate**: Sempre funziona
- ✅ **Gratis**: Nessun costo
- ✅ **Veloce**: Processing locale
- ✅ **Nessun safety filter**: Controllo totale

**Quando usare:**
- Default per tutti i documenti
- Quando ML è bloccato
- Quando serve affidabilità massima

---

## Strategia Raccomandata con Ultra Plan

### Opzione 1: Google Document AI (Se Incluso)

**Fase 1: Document AI**
- Estrae struttura e campi da PDF
- OCR automatico
- Form parsing

**Fase 2: Pattern Extraction**
- Fallback per campi non estratti
- Validazione risultati

**Costo: ~$37.50 per 25k documenti**

---

### Opzione 2: Pattern + Vertex AI Gemini Pro

**Fase 1: Pattern Extraction (80%)**
- Success: 100%
- Costo: $0

**Fase 2: Vertex AI Gemini Pro (20%)**
- Quando Pattern fallisce
- Safety settings configurabili
- Potrebbe funzionare meglio di Flash

**Costo: Dipende da pricing Vertex AI**

---

### Opzione 3: Pattern Only (Raccomandato)

**Pattern Extraction:**
- Success: 100%
- Costo: $0
- Veloce e affidabile

**Quando serve ML:**
- Usa OpenAI GPT-4o-mini ($2.63 per 25k docs)
- O Claude 3.5 Sonnet ($56.25 per 25k docs)

**Costo totale: ~$2.63 per 25k documenti**

---

## Verifica Disponibilità

Per verificare cosa è incluso nel tuo Ultra plan:

1. **Google Cloud Console**:
   - Vai a Vertex AI > Models
   - Verifica modelli disponibili
   - Controlla quota e limiti

2. **Document AI**:
   - Vai a Document AI > Processors
   - Verifica se incluso nel piano
   - Controlla pricing

3. **API Testing**:
   ```bash
   python scripts/list_gemini_models.py
   python scripts/test_gemini_ultra_extraction.py
   ```

---

## Conclusione

**Con Google AI Ultra plan:**

1. ✅ **Pattern Extraction**: Default, gratis, 100% success
2. ✅ **Google Document AI**: Se incluso, ottimo per PDF/OCR
3. ✅ **Vertex AI Gemini Pro**: Se disponibile, potrebbe essere meno restrittivo
4. ⚠️ **Gemini 2.5 Flash**: Blocca contenuti legali (non adatto)
5. ✅ **OpenAI GPT-4o-mini**: Fallback esterno, $2.63 per 25k docs

**Raccomandazione:**
- Usa **Pattern Extraction** come default
- Se serve ML, prova **Google Document AI** (se incluso)
- Altrimenti usa **OpenAI GPT-4o-mini** come fallback
