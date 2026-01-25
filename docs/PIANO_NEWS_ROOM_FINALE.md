# Piano Integrazione News Room Dashboard - VERSIONE FINALE

**Purpose:** Piano completo per integrare articoli Intel Scraper nella dashboard News Room  
**Date:** 2026-01-24  
**Status:** ✅ PIANO FINALE - PRONTO PER IMPLEMENTAZIONE

---

## 🎯 OBIETTIVO FINALE

Dashboard News Room (`https://zantara.balizero.com/intelligence/news-room`) dove:

- ✅ Visualizzare articoli completi dall'Intel Scraper (già arricchiti e impaginati)
- ✅ Approvare/rifiutare articoli
- ✅ **Editare articoli** (titolo, contenuto, categoria)
- ✅ **Aggiungere cover image manualmente** quando articolo è già nella News Room
- ✅ **Approvare articolo → pubblicazione automatica su balizero.com**

---

## 📊 FLUSSO COMPLETO CORRETTO

### Flusso End-to-End

```
1. Intel Scraper crea articolo completo
   → Salvato in: data/pending_articles/{id}.json
   → Preview HTML: data/previews/{id}.html (con componenti interattivi)
   → ❌ Cover Image: NON viene inviato automaticamente

2. send_to_api() viene chiamato
   → Endpoint: POST /api/intel/scraper/submit
   → ✅ Invia: title, content (markdown), preview_html, preview_url
   → ❌ NON invia: cover_image (verrà aggiunta manualmente)

3. Backend salva in staging
   → Location: data/staging/{type}/{item_id}.json
   → ✅ Salva: preview_html, preview_url
   → ❌ cover_image: mancante (verrà aggiunta manualmente)

4. Frontend mostra articoli nella News Room
   → ✅ Articoli completi con preview HTML
   → ⚠️ Cover image mancante (mostra warning)
   → ✅ Pulsante "Upload Cover Image" disponibile
   → ✅ Pulsante "Edit" disponibile
   → ✅ Pulsante "Approve" disponibile

5. Utente visualizza e modifica articolo
   → ✅ Visualizza preview HTML completo (con componenti interattivi)
   → ✅ Modifica titolo, contenuto, categoria se necessario
   → ✅ Aggiunge cover image manualmente tramite upload

6. Utente approva articolo
   → ✅ Chiama: POST /api/intel/staging/publish/{type}/{id}
   → ✅ Backend pubblica automaticamente:
      a) Salva in Qdrant (knowledge base) ✅
      b) Registra in anti-duplicate system ✅
      c) ❌ MANCA: Pubblica su GitHub/Vercel → balizero.com

7. ❌ PROBLEMA: Articolo NON viene pubblicato su balizero.com
   → URL generato: https://balizero.com/{category}/{item_id}
   → Ma articolo NON esiste effettivamente su balizero.com
   → Serve chiamare POST /api/articles/publish per pubblicare su GitHub/Vercel
```

---

## ❌ PROBLEMA CRITICO IDENTIFICATO

### Pubblicazione Attuale (INCOMPLETA)

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Endpoint:** `POST /api/intel/staging/publish/{type}/{item_id}`

**Cosa fa attualmente:**

1. ✅ Ingest to Qdrant (knowledge base)
2. ✅ Register in anti-duplicate system
3. ✅ Generate `published_url = f"https://balizero.com/{category}/{item_id}"`
4. ❌ **MANCA:** Pubblicazione su GitHub/Vercel → balizero.com

**Risultato:**

- Articolo è solo nella knowledge base (Qdrant)
- Articolo NON è pubblicato come articolo pubblico su balizero.com
- URL generato non funziona

### Soluzione Necessaria

**Modificare `publish_staging_item` per:**

1. Convertire staging item → `EnrichedArticle` format
2. Chiamare `POST /api/articles/publish` per pubblicare su GitHub/Vercel
3. Aggiornare `published_url` con URL reale da GitHub/Vercel

---

## 📋 PIANO IMPLEMENTAZIONE FINALE (9 STEP)

### STEP 1: Includere Preview HTML nel Payload

**File:** `apps/bali-intel-scraper/scripts/article_deep_enricher.py`

**Modifica:** Aggiungere `preview_html` e `preview_url` al payload in `send_to_api()`

**Cosa fare:**

1. Leggere preview HTML se disponibile (`data/previews/{id}.html`)
2. Includere nel payload come stringa
3. Includere preview_url (URL online: `https://bali-intel-scraper.fly.dev/preview/{id}`)

### STEP 2: Backend Salva Preview HTML

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Modifica:** Salvare preview HTML file se presente

**Cosa fare:**

1. Se preview_html presente → salvare file
2. Aggiornare staging_data con path preview HTML
3. Salvare preview_url nel staging_data

### STEP 3: Backend - Endpoint Editing Articolo

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Nuovo endpoint:** `PUT /api/intel/staging/{type}/{item_id}`

**Cosa fare:**

1. Creare `EditStagingItemRequest` model
2. Implementare endpoint editing
3. Validazione dati
4. Salvataggio modifiche

### STEP 4: Backend - Endpoint Upload Cover Image

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Nuovo endpoint:** `POST /api/intel/staging/{type}/{item_id}/cover`

**Cosa fare:**

1. Creare `UploadCoverImageRequest` model
2. Implementare endpoint upload
3. Decodificare base64
4. Salvare file cover image
5. Aggiornare staging_data con path cover image

### STEP 5: Backend - Funzione Conversione Staging → EnrichedArticle

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Nuova funzione:** `convert_staging_to_enriched_article(staging_data: dict) -> EnrichedArticle`

**Cosa fare:**

1. Parsare `content` (markdown) per estrarre sezioni
2. Generare `tldr` section
3. Generare `bali_zero_take` section
4. Generare `next_steps` section
5. Estrarre `ai_summary`, `ai_tags`, `suggested_components`
6. Costruire `EnrichedArticle` object

**Struttura dati staging:**

```python
{
    "title": "...",
    "content": "...",  # Markdown con sezioni
    "category": "...",
    "relevance_score": 50,
    "cover_image": "...",  # Path o URL
    "preview_html": "...",  # HTML completo
    "preview_url": "...",  # URL preview online
    ...
}
```

**Struttura dati EnrichedArticle richiesta:**

```python
{
    "title": "...",
    "headline": "...",
    "tldr": {
        "should_worry": "...",
        "what": "...",
        "who": "...",
        "when": "...",
        "risk_level": "..."
    },
    "facts": "...",
    "bali_zero_take": {
        "hidden_insight": "...",
        "our_analysis": "...",
        "our_advice": "..."
    },
    "next_steps": {
        "expat": [...],
        "investor": [...]
    },
    "category": "...",
    "priority": "...",
    "relevance_score": 50,
    "ai_summary": "...",
    "ai_tags": [...],
    "suggested_components": [...],
    "cover_image": "...",
    "source": "...",
    "source_url": "...",
    "enriched_at": "..."
}
```

### STEP 6: Backend - Modificare Pubblicazione per Includere GitHub/Vercel

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Modifica:** `publish_staging_item()` per chiamare `/api/articles/publish`

**Cosa fare:**

1. Dopo ingest to Qdrant, convertire staging → EnrichedArticle
2. Chiamare `POST /api/articles/publish` con EnrichedArticle
3. Aggiornare `published_url` con URL reale da GitHub/Vercel
4. Gestire errori se pubblicazione GitHub fallisce

**Codice da aggiungere:**

```python
# Step 4: Publish to GitHub/Vercel (balizero.com)
try:
    from backend.app.routers.article_composer import publish_article
    from backend.app.routers.article_composer import EnrichedArticle, PublishRequest

    # Convert staging item to EnrichedArticle
    enriched_article = convert_staging_to_enriched_article(data)

    # Create publish request
    publish_request = PublishRequest(
        article=enriched_article,
        publish_to_github=True
    )

    # Publish to GitHub/Vercel
    publish_result = await publish_article(publish_request)

    # Update staging data with actual published URL
    data["published_url"] = publish_result.published_url
    data["github_commit_sha"] = publish_result.commit_sha

    logger.info(
        "✅ Article published to GitHub/Vercel",
        extra={
            "type": type,
            "item_id": item_id,
            "published_url": publish_result.published_url
        }
    )
except Exception as e:
    logger.error(
        f"⚠️ Failed to publish to GitHub/Vercel: {e}",
        exc_info=True,
        extra={"type": type, "item_id": item_id}
    )
    # Non bloccare la pubblicazione se GitHub fallisce
    # Articolo è già in Qdrant
```

### STEP 7: Frontend - API Client Aggiornato

**File:** `apps/mouth/src/lib/api/intelligence.api.ts`

**Nuove funzioni:**

- `editItem(type, id, edits)`
- `uploadCoverImage(type, id, imageBase64, filename)`

### STEP 8: Frontend - Componenti Editor e Uploader

**File:**

- `apps/mouth/src/app/(workspace)/intelligence/news-room/components/ArticleEditor.tsx`
- `apps/mouth/src/app/(workspace)/intelligence/news-room/components/CoverImageUploader.tsx`

**Funzionalità:**

- Editor: Form editing titolo, contenuto, categoria
- Uploader: Drag & drop, preview, upload base64

### STEP 9: Integrazione nella Dashboard

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Modifiche:**

1. Aggiungere pulsante "Edit" su ogni card
2. Aggiungere pulsante "Upload Cover" se cover_image mancante
3. Integrare ArticleEditor (dialog/modal)
4. Integrare CoverImageUploader (dialog/modal)
5. Aggiornare card dopo editing/upload
6. ✅ Pulsante "Approve" già esiste → pubblica automaticamente

---

## 🎯 PRIORITÀ IMPLEMENTAZIONE

### 🔴 Priorità ALTA (Blocca funzionalità)

1. **STEP 1-2:** Includere preview_html nel payload + Backend salva preview HTML
2. **STEP 5-6:** Funzione conversione + Pubblicazione GitHub/Vercel
3. **STEP 4:** Backend endpoint upload cover image (MANUALE)
4. **STEP 8-9:** Upload cover image nella dashboard (MANUALE)

### 🟡 Priorità MEDIA (Migliora UX)

5. **STEP 3:** Backend endpoint editing articolo
6. **STEP 7-8:** Frontend componenti editor
7. **STEP 9:** Integrazione editing nella dashboard

---

## ⚠️ CRITICAL CONSIDERATIONS

### 1. Pubblicazione Automatica

**Workflow:**

1. Utente approva articolo nella News Room
2. Backend pubblica automaticamente:
   - Salva in Qdrant (knowledge base) ✅
   - Registra in anti-duplicate system ✅
   - **NUOVO:** Pubblica su GitHub/Vercel → balizero.com ✅
3. Articolo appare su `https://balizero.com/{category}/{slug}`

**Gestione Errori:**

- Se pubblicazione GitHub fallisce, articolo è già in Qdrant
- Log errore ma non bloccare pubblicazione
- Utente può riprovare pubblicazione manualmente se necessario

### 2. Conversione Dati

**Sfida:** Convertire staging item (markdown semplice) → EnrichedArticle (struttura complessa)

**Soluzione:**

- Parsare markdown per estrarre sezioni
- Usare regex o parser markdown
- Generare sezioni mancanti con valori di default
- Migliorare conversione iterativamente

### 3. Cover Image Upload Strategy

**Workflow:**

1. Articolo arriva nella News Room SENZA cover image
2. Utente visualizza preview HTML completo
3. Utente decide cover image appropriata
4. Utente upload cover image manualmente
5. Utente approva → articolo completo viene pubblicato

---

## 📋 CHECKLIST IMPLEMENTAZIONE

### Backend Changes

- [ ] Modificare `ScraperSubmission` model per includere `preview_html`, `preview_url`
- [ ] Modificare `submit_from_scraper()` per salvare preview HTML
- [ ] Creare endpoint `PUT /api/intel/staging/{type}/{id}` per editing
- [ ] Creare endpoint `POST /api/intel/staging/{type}/{id}/cover` per upload
- [ ] Creare funzione `convert_staging_to_enriched_article()`
- [ ] Modificare `publish_staging_item()` per chiamare `/api/articles/publish`
- [ ] Gestire errori pubblicazione GitHub

### Intel Scraper Changes

- [ ] Modificare `send_to_api()` per includere `preview_html`
- [ ] Modificare `send_to_api()` per includere `preview_url`
- [ ] ❌ NON includere `cover_image` (verrà aggiunto manualmente)

### Frontend Changes

- [ ] Aggiornare `intelligence.api.ts` con nuove funzioni
- [ ] Creare componente `ArticleEditor.tsx`
- [ ] Creare componente `CoverImageUploader.tsx`
- [ ] Modificare `news-room/page.tsx` per integrare editor e uploader
- [ ] Aggiungere pulsanti "Edit" e "Upload Cover" nelle card

### Testing

- [ ] Test invio articolo completo con preview HTML
- [ ] Test salvataggio preview HTML nel backend
- [ ] Test editing articolo
- [ ] Test upload cover image manuale
- [ ] Test conversione staging → EnrichedArticle
- [ ] Test pubblicazione GitHub/Vercel
- [ ] Test end-to-end completo: Approvazione → Pubblicazione su balizero.com

---

## 🚀 ORDINE DI IMPLEMENTAZIONE RACCOMANDATO

1. **STEP 1-2:** Modificare Intel Scraper per inviare preview_html + Backend salva preview HTML
2. **STEP 5-6:** Funzione conversione + Pubblicazione GitHub/Vercel (CRITICO)
3. **STEP 3-4:** Backend endpoint editing e upload cover image
4. **STEP 7:** Frontend API client aggiornato
5. **STEP 8:** Frontend componenti editor e uploader
6. **STEP 9:** Integrazione nella dashboard

**⚠️ IMPORTANTE:**

- STEP 5-6 sono CRITICI per pubblicazione automatica
- Ogni step deve essere testato prima di procedere al successivo!

---

**Status:** ✅ PIANO FINALE - PRONTO PER IMPLEMENTAZIONE  
**Next:** Attendere approvazione utente prima di iniziare implementazione
