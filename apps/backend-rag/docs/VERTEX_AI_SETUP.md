# Vertex AI Setup - Google Cloud Service Account

## Configurazione Completata ✅

Il backend è stato configurato per usare **Vertex AI come PRIMARY** con il service account Google Cloud.

**Data ultima configurazione:** 2026-01-19
**Status:** ✅ Attivo e funzionante
**Deployment version:** 1668

---

## 🎯 Credenziali Configurate

| Proprietà               | Valore                                                  |
| ----------------------- | ------------------------------------------------------- |
| **Project ID**          | `nuzantara`                                             |
| **Service Account**     | `nuzantara-drive-bot@nuzantara.iam.gserviceaccount.com` |
| **Credito disponibile** | 16.663.501 Rp (~$1,000 USD)                             |
| **Validità credito**    | Copre modelli Gemini 2.0+ su Vertex AI                  |
| **Durata stimata**      | ~7 mesi con Gemini 3 Flash Preview                      |

---

## 🔄 Strategia di Autenticazione LLM

**Ordine di priorità:**

```
1. PRIMARY: Vertex AI (Service Account)
   └─ Secret: GOOGLE_SERVICE_ACCOUNT_JSON
   └─ Project: nuzantara
   └─ Location: global
   └─ Quota: 2,000 RPM
   └─ ✅ USA CREDITO 16.66M IDR

2. FALLBACK: API Key (AI Studio)
   └─ Secret: GOOGLE_API_KEY
   └─ Solo se Vertex AI fallisce
   └─ Quota: 1,500 RPM

3. FALLBACK FINALE: OpenRouter
   └─ Ultima risorsa
```

**Codice di inizializzazione** (`genai_client.py:206-232`):

```python
# Try Service Account first (Vertex AI mode) - PREFERRED for production
if _sa_configured and _sa_project_id:
    self._client = genai.Client(
        vertexai=True,
        project=_sa_project_id,  # "nuzantara"
        location="global",
    )
    logger.info("✅ GenAI client initialized with Vertex AI")
    return  # ← ESCE QUI, non va al fallback!

# Fallback to API Key (solo se Vertex AI fallisce)
if self.api_key:
    self._client = genai.Client(api_key=self.api_key)
    logger.info("✅ GenAI client initialized with API Key (AI Studio)")
```

---

## 🤖 Modelli Configurati (2026-01-19)

**Primary Model:** `gemini-3-flash-preview`

- Fast & cost-effective
- $0.50/1M input tokens
- $3.00/1M output tokens

**Fallback Model:** `gemini-2.0-flash`

- Stable & reliable
- $0.075/1M input tokens (6.6x cheaper)
- $0.30/1M output tokens (10x cheaper)

**Strategia fallback modelli:**

```
gemini-3-flash-preview → gemini-2.0-flash → OpenRouter
```

---

## 🔧 Configurazione Tecnica

### Secrets Fly.io

```bash
# Vertex AI (PRIMARY)
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
GOOGLE_PROJECT_ID=nuzantara
GOOGLE_LOCATION=global

# API Key (FALLBACK)
GOOGLE_API_KEY=AIzaSy...
GOOGLEAISTUDIO_API_KEY=AIzaSy... (alias)
```

### Inizializzazione Automatica

All'avvio del backend (`genai_client.py:64-135`):

1. Legge `GOOGLE_SERVICE_ACCOUNT_JSON` da environment
2. Valida il JSON (parse + verifica private_key)
3. Scrive credenziali in `/tmp/google_credentials.json`
4. Imposta `GOOGLE_APPLICATION_CREDENTIALS` (ADC)
5. Inizializza `genai.Client(vertexai=True)`

### File Modificati

| File                          | Modifiche                                  | Commit   |
| ----------------------------- | ------------------------------------------ | -------- |
| `backend/llm/genai_client.py` | Supporto per `GOOGLE_SERVICE_ACCOUNT_JSON` | 9c2adf1a |
| `backend/app/core/config.py`  | Validator per alias secret names           | 9c2adf1a |
| `apps/backend-rag/Dockerfile` | Fix host :: → 0.0.0.0 (IPv4)               | a97bd0c8 |

---

## 🐛 Fix Applicati

### Fix 1: Dockerfile Host Binding (2026-01-19)

**Problema:** Backend non raggiungibile (502 error)

**Root Cause:**

```dockerfile
# PRIMA (SBAGLIATO)
CMD ["uvicorn", "backend.app.main_cloud:app", "--host", "::", ...]
# :: = solo IPv6, Fly.io proxy usa IPv4 ❌
```

**Fix:**

```dockerfile
# DOPO (CORRETTO)
CMD ["uvicorn", "backend.app.main_cloud:app", "--host", "0.0.0.0", ...]
# 0.0.0.0 = tutti gli indirizzi IPv4 ✅
```

**Commit:** `a97bd0c8`

### Fix 2: Service Account Support (2026-01-18)

**Aggiunto supporto per alias secret names:**

- `GOOGLE_SERVICE_ACCOUNT_JSON` (Fly.io standard)
- `GOOGLE_CREDENTIALS_JSON` (legacy)
- `GEMINI_SA_TOKEN` (alias legacy)

**Commit:** `9c2adf1a`

---

## ✅ Verifica Funzionamento

### 1. Health Check

```bash
curl https://nuzantara-rag.fly.dev/health
# {"status":"healthy","database":{"status":"connected"},...}
```

### 2. Logs Backend

```bash
fly logs -a nuzantara-rag | grep "GenAI"
# ✅ GenAI client initialized with Vertex AI (project: nuzantara)
```

### 3. Status Machines

```bash
fly status -a nuzantara-rag
# 2/2 machines running, 1 total check passing
```

---

## 💰 Calcolo Costi e Durata Credito

### Con Gemini 3 Flash Preview (attuale)

**Assunzioni:**

- 150K input tokens/giorno
- 30K output tokens/giorno

**Costo mensile:**

```
Input:  150K × 30 giorni = 4.5M tokens × $0.50  = $67.50
Output: 30K  × 30 giorni = 0.9M tokens × $3.00  = $67.50
TOTALE: $135/mese
```

**Durata credito:**

```
$1,000 ÷ $135/mese = 7.4 mesi (~7 mesi)
```

### Se si usasse Gemini 2.0 Flash (10x più economico)

**Costo mensile:**

```
Input:  4.5M tokens × $0.075 = $6.75
Output: 0.9M tokens × $0.30  = $6.75
TOTALE: $13.50/mese (10x cheaper!)
```

**Durata credito:**

```
$1,000 ÷ $13.50/mese = 74 mesi (~6 anni!)
```

---

## 📋 Checklist Deployment

- [x] Service Account JSON caricato su Fly.io
- [x] `GOOGLE_PROJECT_ID` configurato
- [x] Codice supporta Vertex AI come primary
- [x] Dockerfile fixato (host 0.0.0.0)
- [x] Backend deployato (version 1668)
- [x] Health check passing
- [x] Logs confermano uso Vertex AI
- [x] Credito 16.66M IDR verificato
- [x] Gemini 3 Flash Preview attivo

---

## 🔗 Link Utili

- **Google Cloud Console:** https://console.cloud.google.com/billing/01FF0E-59E80E-F3689B
- **Vertex AI Docs:** https://cloud.google.com/vertex-ai/docs
- **Fly.io Dashboard:** https://fly.io/apps/nuzantara-rag
- **Health Endpoint:** https://nuzantara-rag.fly.dev/health

---

**Ultimo aggiornamento:** 2026-01-19
**Versione backend:** 1668
**Status:** ✅ Operativo e testato
