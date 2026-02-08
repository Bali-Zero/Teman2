# Flusso Completo News Room Dashboard - Analisi Dettagliata

**Purpose:** Analisi completa del flusso attuale e piano per integrazione articoli Intel Scraper  
**Date:** 2026-01-24  
**Status:** 🔍 ANALISI COMPLETA

---

## 📊 FLUSSO ATTUALE (Come Funziona Oggi)

### 1. Intel Scraper → Backend

**File:** `apps/bali-intel-scraper/scripts/article_deep_enricher.py`

**Metodo:** `send_to_api()`

**Endpoint:** `POST /api/intel/scraper/submit`

**Payload inviato:**

```python
{
    "title": article.headline,
    "content": self.format_as_markdown(article),  # Markdown formattato
    "source_url": article.source_url,
    "source_name": article.source,
    "category": article.category,
    "relevance_score": article.relevance_score,
    "published_at": article.published_at,
    "extraction_method": "claude_max",
    "tier": "T1",
    "components": article.components,
    # ❌ cover_image NON viene inviato!
}
```

**Problema identificato:**

- ❌ `cover_image` NON viene incluso nel payload
- ❌ `preview_html` NON viene incluso
- ❌ Solo markdown text viene inviato

### 2. Backend → Staging Storage

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Endpoint:** `POST /api/intel/scraper/submit`

**Processo:**

1. Classifica tipo (`visa` o `news`) usando `classification_service`
2. Genera `item_id` univoco
3. Controlla duplicati
4. Salva in `data/staging/{type}/{item_id}.json`

**Dati salvati:**

```json
{
  "item_id": "...",
  "title": "...",
  "content": "...", // Markdown text
  "source_url": "...",
  "source_name": "...",
  "category": "...",
  "relevance_score": 50,
  "status": "pending",
  "detection_type": "scraper_auto",
  "detected_at": "2026-01-24T...",
  "cover_image": "..." // Solo se presente nel payload
  // ❌ preview_html NON viene salvato
}
```

### 3. Backend → Frontend API

**Endpoint:** `GET /api/intel/staging/pending?type=news`

**Risposta:**

```json
{
  "items": [
    {
      "id": "...",
      "type": "news",
      "title": "...",
      "content": "...", // Markdown text
      "cover_image": "...", // URL/path se presente
      "detected_at": "...",
      "source": "...",
      "detection_type": "NEW",
      "status": "pending"
    }
  ],
  "count": 12
}
```

### 4. Frontend → Dashboard

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Funzionalità esistenti:**

- ✅ Lista articoli pending
- ✅ Filtri e ricerca
- ✅ Preview articolo (dialog)
- ✅ Pulsante "Publish"
- ✅ Bulk publish
- ✅ Mostra cover image se presente
- ⚠️ Mostra warning se cover image mancante

**Cosa manca:**

- ❌ Editing articolo (titolo, contenuto, categoria)
- ❌ Upload cover image se mancante
- ❌ Preview HTML completo (usa solo markdown text)
- ❌ Link a preview online (`https://bali-intel-scraper.fly.dev/preview/{id}`)

---

## 🔍 PROBLEMA PRINCIPALE IDENTIFICATO

### Gli Articoli Completi NON Arrivano alla Dashboard

**Causa:**

1. Intel Scraper salva articoli in `data/pending_articles/` localmente
2. `send_to_api()` viene chiamato ma:
   - ❌ `cover_image` NON viene incluso nel payload
   - ❌ `preview_html` NON viene incluso
   - ❌ Solo markdown text viene inviato
3. Gli articoli vengono salvati in staging ma senza cover image e preview HTML

**Risultato:**

- Dashboard mostra articoli ma senza cover image
- Preview HTML non è accessibile
- Editing e upload cover image non funzionano

---

## 📋 PIANO IMPLEMENTAZIONE STRUTTURATO

### FASE 1: Backend - Completare Payload Submission

**Obiettivo:** Inviare cover image e preview HTML al backend

**File da modificare:**

- `apps/bali-intel-scraper/scripts/article_deep_enricher.py` → `send_to_api()`

**Modifiche:**

1. Includere `cover_image` nel payload (come base64 o URL)
2. Includere `preview_html` nel payload (come stringa HTML)
3. Includere `preview_url` nel payload (URL preview online)
4. Includere `enriched_content` completo (non solo markdown)

**Schema payload aggiornato:**

```python
{
    "title": article.headline,
    "content": self.format_as_markdown(article),
    "enriched_content": article.enriched_content,  # NUOVO
    "cover_image": cover_image_base64_or_url,  # NUOVO
    "preview_html": preview_html_content,  # NUOVO
    "preview_url": preview_online_url,  # NUOVO
    "source_url": article.source_url,
    "source_name": article.source,
    "category": article.category,
    "relevance_score": article.relevance_score,
    "published_at": article.published_at,
    "extraction_method": "claude_max",
    "tier": "T1",
    "components": article.components,
}
```

### FASE 2: Backend - Storage Cover Image e Preview HTML

**Obiettivo:** Salvare cover images e preview HTML nel backend

**File da modificare:**

- `apps/backend-rag/backend/app/routers/intel.py` → `submit_from_scraper()`
- `apps/backend-rag/backend/services/intel/intel_staging_service.py`

**Modifiche:**

1. Salvare cover image in storage permanente (se base64)
2. Salvare preview HTML in storage permanente
3. Aggiornare staging data con path cover image e preview HTML
4. Gestire URL cover image se già disponibile online

**Storage structure:**

```
data/staging/news/{item_id}.json
data/staging/news/images/{item_id}.png  # Cover image
data/staging/news/previews/{item_id}.html  # Preview HTML
```

### FASE 3: Backend - Endpoint Editing e Upload Cover Image

**Obiettivo:** Permettere editing articoli e upload cover image

**Nuovi endpoint da creare:**

- `PUT /api/intel/staging/{type}/{item_id}` - Modifica articolo
- `POST /api/intel/staging/{type}/{item_id}/cover` - Upload cover image
- `GET /api/intel/staging/{type}/{item_id}/preview-html` - Get preview HTML

**File da creare/modificare:**

- `apps/backend-rag/backend/app/routers/intel.py`

**Schema request editing:**

```python
class EditStagingItemRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    # Altri campi modificabili
```

**Schema request upload cover:**

```python
class UploadCoverImageRequest(BaseModel):
    cover_image_base64: str  # Base64 encoded image
    filename: str | None = None
```

### FASE 4: Frontend - Componenti Editing e Upload

**Obiettivo:** Aggiungere funzionalità editing e upload cover image

**Componenti da creare:**

- `apps/mouth/src/app/(workspace)/intelligence/news-room/components/ArticleEditor.tsx`
- `apps/mouth/src/app/(workspace)/intelligence/news-room/components/CoverImageUploader.tsx`

**Modifiche a componenti esistenti:**

- `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`
  - Aggiungere pulsante "Edit" su ogni card
  - Aggiungere pulsante "Upload Cover" se cover image mancante
  - Integrare editor e uploader

**API client da aggiornare:**

- `apps/mouth/src/lib/api/intelligence.api.ts`
  - Aggiungere `editItem()`
  - Aggiungere `uploadCoverImage()`
  - Aggiungere `getPreviewHtml()`

### FASE 5: Frontend - Preview HTML Completo

**Obiettivo:** Mostrare preview HTML completo invece di solo markdown

**Modifiche:**

- Usare `preview_url` se disponibile (iframe o link esterno)
- Oppure renderizzare `preview_html` se disponibile
- Fallback a markdown text se preview HTML non disponibile

---

## 🎯 PRIORITÀ IMPLEMENTAZIONE

### Priorità ALTA (Blocca funzionalità)

1. **FASE 1:** Includere cover_image nel payload submission
2. **FASE 2:** Salvare cover image nel backend storage
3. **FASE 4:** Upload cover image nella dashboard

### Priorità MEDIA (Migliora UX)

4. **FASE 3:** Endpoint editing articoli
5. **FASE 4:** Componente editor articoli
6. **FASE 5:** Preview HTML completo

### Priorità BASSA (Nice to have)

7. Preview HTML storage nel backend
8. Link a preview online nella dashboard

---

## ⚠️ CRITICAL ISSUES DA RISOLVERE

### Issue 1: Cover Image Non Arriva al Backend

**Problema:** `send_to_api()` non include `cover_image` nel payload

**Soluzione:** Modificare `send_to_api()` per:

1. Leggere cover image file se disponibile
2. Convertire in base64 o ottenere URL
3. Includere nel payload

### Issue 2: Cover Image Storage

**Problema:** Backend riceve cover_image ma non lo salva correttamente

**Soluzione:**

1. Se base64 → salvare file in storage
2. Se URL → salvare URL nel JSON
3. Aggiornare staging data con path corretto

### Issue 3: Preview HTML Non Disponibile

**Problema:** Preview HTML è solo locale, non accessibile dal backend

**Soluzione:**

1. Includere preview HTML nel payload (come stringa)
2. Salvare preview HTML nel backend storage
3. Oppure usare URL preview online (`https://bali-intel-scraper.fly.dev/preview/{id}`)

---

## 📋 CHECKLIST PRE-IMPLEMENTAZIONE

Prima di iniziare, verificare:

- [x] ✅ Frontend page esiste (`news-room/page.tsx`)
- [x] ✅ Backend router esiste (`intel.py`)
- [x] ✅ Endpoint `/api/intel/scraper/submit` esiste
- [x] ✅ Endpoint `/api/intel/staging/pending` esiste
- [x] ✅ API client frontend esiste (`intelligence.api.ts`)
- [ ] ⏳ Testare endpoint `/api/intel/staging/pending?type=news`
- [ ] ⏳ Verificare struttura dati staging
- [ ] ⏳ Verificare storage cover images
- [ ] ⏳ Verificare se preview HTML è accessibile

---

## 🚀 PROSSIMI PASSI IMMEDIATI

1. **Testare endpoint esistente:**

   ```bash
   curl "https://nuzantara-rag.fly.dev/api/intel/staging/pending?type=news" \
     -H "X-API-Key: 69ff6340462fd10b"
   ```

2. **Verificare se articoli sono già in staging:**
   - Controllare `data/staging/news/` nel backend
   - Verificare struttura dati

3. **Testare invio articolo completo:**
   - Modificare `send_to_api()` per includere cover_image
   - Testare invio articolo completo
   - Verificare che appaia nella dashboard

4. **Creare piano dettagliato step-by-step:**
   - Con file specifici da modificare
   - Con codice esempio per ogni modifica
   - Con test per ogni step

---

**Status:** 🔍 ANALISI COMPLETA - PRONTO PER PIANIFICAZIONE DETTAGLIATA  
**Next:** Creare piano implementazione step-by-step con codice specifico
