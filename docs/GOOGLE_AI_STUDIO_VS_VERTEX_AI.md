# 🔍 GOOGLE AI STUDIO vs VERTEX AI - Differenze e Costi

**Data:** 2026-01-11  
**Obiettivo:** Chiarire differenze tra Google AI Studio e Vertex AI, e quale stiamo usando

---

## 📊 DIFFERENZE CHIAVE

### Google AI Studio

**Cos'è:**
- Ambiente di sviluppo web-based per prototipare con Gemini
- Usa **API Key** per autenticazione
- Accesso diretto ai modelli Gemini
- **Gratis** con limiti generosi

**Autenticazione:**
- `GOOGLE_API_KEY` (stringa)
- Oppure ADC con `gemini /auth` (configura credenziali locali)

**Pricing:**
- **Free Tier:** Gratis fino a 1,500 RPD e 15 RPM
- **Paid:** Stesso pricing di Vertex AI dopo free tier

**Limiti Free Tier:**
- 15 richieste/minuto (RPM)
- 1,500 richieste/giorno (RPD)

**Quando usare:**
- ✅ Sviluppo locale
- ✅ Prototipi
- ✅ Test
- ✅ Build incrementali con limiti free tier

---

### Vertex AI

**Cos'è:**
- Piattaforma enterprise Google Cloud per AI/ML
- Usa **Service Account** per autenticazione
- Integrazione con Google Cloud Platform
- Usa crediti Google Cloud

**Autenticazione:**
- `GOOGLE_CREDENTIALS_JSON` (service account JSON)
- Oppure ADC con `gcloud auth application-default login`

**Pricing:**
- Usa crediti Google Cloud
- Stesso pricing di Google AI Studio dopo free tier
- Nessun limite free tier (usa crediti)

**Limiti:**
- Dipendono dai crediti disponibili
- Quote più alte per produzione

**Quando usare:**
- ✅ Produzione
- ✅ Deploy su cloud
- ✅ Quando hai crediti Google Cloud
- ✅ Quando serve quota alta

---

## 💰 COSTI COMPARATI

### Google AI Studio (API Key)

**Free Tier:**
- ✅ **$0.00** fino a 1,500 RPD e 15 RPM
- ✅ Nessun costo aggiuntivo

**Dopo Free Tier:**
- Stesso pricing di Vertex AI
- Gemini 2.0 Flash: $0.075/1M input, $0.30/1M output

**Limiti:**
- ⚠️ 1,500 richieste/giorno (free tier)
- ⚠️ 15 richieste/minuto (free tier)

---

### Vertex AI (Service Account)

**Costi:**
- Usa crediti Google Cloud
- Stesso pricing di Google AI Studio
- Gemini 2.0 Flash: $0.075/1M input, $0.30/1M output

**Limiti:**
- ✅ Nessun limite free tier
- ✅ Quote più alte
- ✅ Dipende dai crediti disponibili

**Crediti disponibili:**
- ~$320 USD (~5M IDR)
- Scadenza: 6 febbraio 2026

---

## 🔧 COSA STIAMO USANDO ORA

### Nel Backend (Produzione)

**File:** `apps/backend-rag/backend/llm/genai_client.py`

**Strategia:**
1. **Prima:** Prova Vertex AI con Service Account (`GOOGLE_CREDENTIALS_JSON`)
2. **Fallback:** Google AI Studio con API Key (`GOOGLE_API_KEY`)

**Risultato:**
- ✅ Backend usa Vertex AI (preferito)
- ✅ Fallback a Google AI Studio se Vertex AI non disponibile

---

### Nello Script KG Extraction (Locale)

**File:** `apps/backend-rag/scripts/kg_incremental_extraction.py`

**Attualmente:**
- ❌ Usa solo Vertex AI (`vertexai=True`)
- ❌ Non supporta Google AI Studio con ADC

**Problema:**
- L'utente ha fatto `gemini /auth` che configura ADC per **Google AI Studio**
- Lo script cerca solo Vertex AI con service account
- **Non funziona** con ADC di Google AI Studio

---

## ✅ SOLUZIONE: Supportare Entrambi

### Modifiche Necessarie

**File:** `apps/backend-rag/scripts/kg_incremental_extraction.py`

**Strategia:**
1. **Prima:** Prova Vertex AI con Service Account (`GOOGLE_CREDENTIALS_JSON`)
2. **Seconda:** Prova Google AI Studio con ADC (`gemini /auth`)
3. **Terza:** Prova Google AI Studio con API Key (`GOOGLE_API_KEY`)

**Codice:**
```python
# Opzione 1: Vertex AI con Service Account
if creds_json:
    client = genai.Client(vertexai=True, project=project_id, location=location)

# Opzione 2: Google AI Studio con ADC (gemini /auth)
elif not os.environ.get("GOOGLE_API_KEY"):
    try:
        # ADC automatico (da gemini CLI /auth)
        client = genai.Client()  # ADC automatico
    except Exception:
        pass

# Opzione 3: Google AI Studio con API Key
if not client and os.environ.get("GOOGLE_API_KEY"):
    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
```

---

## 💡 RACCOMANDAZIONE

### Per Knowledge Graph Extraction Locale

**Opzione 1: Google AI Studio con ADC (CONSIGLIATO)**
- ✅ Già configurato (`gemini /auth`)
- ✅ Gratis fino a 1,500 RPD
- ✅ Nessun costo aggiuntivo
- ✅ Perfetto per build incrementali

**Opzione 2: Vertex AI con Service Account**
- ✅ Nessun limite free tier
- ✅ Usa crediti Google Cloud
- ✅ Perfetto per full build veloce

**Opzione 3: Google AI Studio con API Key**
- ✅ Fallback se ADC non funziona
- ✅ Stesso pricing di Vertex AI dopo free tier

---

## 📊 COSTI PER KNOWLEDGE GRAPH

### Google AI Studio (Free Tier)

**Incremental (100 chunk/giorno):**
- ✅ **$0.00** (entro limite 1,500 RPD)

**Full Build (58k chunk):**
- ⚠️ Supera limite free tier (1,500 RPD)
- Costo: Stesso di Vertex AI ($5.66 per full build)

### Vertex AI (Con Crediti)

**Incremental (100 chunk/giorno):**
- ✅ **$0.00** (usa crediti, nessun limite)

**Full Build (58k chunk):**
- ✅ **$5.66** (usa crediti)
- ✅ Nessun limite giornaliero

---

## 🎯 CONCLUSIONE

### Cosa Stiamo Usando

**Backend (Produzione):**
- ✅ Vertex AI con Service Account (preferito)
- ✅ Fallback a Google AI Studio con API Key

**Script Locale (KG Extraction):**
- ❌ Attualmente solo Vertex AI
- ✅ **DA AGGIORNARE:** Supportare Google AI Studio con ADC

### Costi Attuali

**Google AI Studio (con `gemini /auth`):**
- ✅ **$0.00** per incremental (entro 1,500 RPD)
- ⚠️ Full build supera limite free tier

**Vertex AI (con crediti):**
- ✅ **$0.00** per incremental (usa crediti)
- ✅ **$5.66** per full build (usa crediti)

### Prossimo Step

**Aggiornare script per supportare Google AI Studio con ADC:**
- ✅ Rilevare ADC automatico (`gemini /auth`)
- ✅ Fallback a Vertex AI se ADC non disponibile
- ✅ Fallback a API Key se necessario

---

**Documentazione creata:** 2026-01-11
