# Vertex AI Setup - Google Cloud Service Account

## Configurazione completata ✅

Il backend è stato configurato per usare **Vertex AI** con il service account Google Cloud fornito.

### Credenziali configurate:
- **Project ID**: `gen-lang-client-0498009027`
- **Service Account**: `vertex-express@gen-lang-client-0498009027.iam.gserviceaccount.com`
- **Credito disponibile**: ~5 milioni IDR (scade il 6 febbraio 2026)

### Come funziona:

1. **Secret su Fly.io**: `GOOGLE_CREDENTIALS_JSON` contiene il JSON completo del service account
2. **Supporto alias**: Il codice supporta anche `GEMINI_SA_TOKEN` come alias per `GOOGLE_CREDENTIALS_JSON`
3. **Inizializzazione automatica**: All'avvio, il backend:
   - Legge `GOOGLE_CREDENTIALS_JSON` o `GEMINI_SA_TOKEN` dall'ambiente
   - Scrive le credenziali in un file temporaneo (`/tmp/google_credentials.json`)
   - Imposta `GOOGLE_APPLICATION_CREDENTIALS` per Application Default Credentials (ADC)
   - Inizializza il client GenAI con `vertexai=True` e il `project_id`

### Modelli configurati (2025-12-28):
- **gemini-3-flash** (primary) - Veloce e cost-effective
- **gemini-2.0-flash** (fallback) - Stabile e affidabile

### Strategia di Fallback:
```
gemini-3-flash → gemini-2.0-flash
```
**Nota**: OpenRouter è stato rimosso come fallback. Ora usiamo solo modelli Gemini.

### Vantaggi di Vertex AI:
- ✅ Usa i crediti Google Cloud invece di API key con limiti
- ✅ Nessun costo aggiuntivo fino a esaurimento crediti
- ✅ Maggiore affidabilità e quota più alta
- ✅ Supporto per modelli avanzati

### Verifica funzionamento:

Il backend logga automaticamente:
- `✅ Service Account credentials configured: <email> (project: <project_id>)`
- `✅ GenAI client initialized with Vertex AI (project: <project_id>)`

### File modificati:
- `apps/backend-rag/backend/app/core/config.py`: Aggiunto campo `google_credentials_json`
- `apps/backend-rag/backend/llm/genai_client.py`: Supporto per `GEMINI_SA_TOKEN` alias

### Prossimi passi:
1. ✅ Secret configurato su Fly.io
2. ✅ Codice aggiornato per supportare Vertex AI
3. ✅ Backend riavviato con nuove credenziali
4. ✅ Log confermano uso di Vertex AI

---

## Fix Persona (2025-12-23)

### Problema identificato:
Alcune risposte iniziavano con intro filosofici invece di risposte dirette.

### Root Cause:
Conflitto tra istruzioni nel prompt:
- **Persona** diceva: "Start with 'The ancestors would say...'"
- **Tools block** diceva: "DO NOT start with philosophical statements"

### Fix applicato:
Modificato `zantara_system_prompt.md` - sezione OPENER:

```diff
- 2.  **THE OPENER (The Hook)**
-     *   Start with the *Setiabudi Brain* or *Toraja Soul*.
-     *   "I've calculated the risk..." or "The ancestors would say..."

+ 2.  **THE OPENER (CRITICAL: Direct Answer First)**
+     *   **ALWAYS start with the DIRECT ANSWER**
+     *   NO philosophical hooks
+     *   For business: Start with facts, numbers, requirements
+     *   THEN weave in Jaksel personality through word choice
```

---

**Data configurazione**: 2025-12-22
**Ultimo update**: 2025-12-23 (v912)
**Status**: ✅ Configurato e attivo




