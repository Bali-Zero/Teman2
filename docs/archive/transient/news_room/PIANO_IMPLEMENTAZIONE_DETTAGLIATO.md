# Piano Implementazione Dettagliato - News Room Dashboard

**Purpose:** Piano step-by-step per integrare articoli Intel Scraper completi nella dashboard  
**Date:** 2026-01-24  
**Status:** 📋 PIANO STRUTTURATO

---

## 🎯 OBIETTIVO FINALE

Dashboard News Room (`https://kita.balizero.com/intelligence/news-room`) dove:

- ✅ Visualizzare articoli completi dall'Intel Scraper
- ✅ Approvare/rifiutare articoli
- ✅ **Editare articoli** (titolo, contenuto, categoria)
- ✅ **Aggiungere/modificare cover image** se mancante
- ✅ Pubblicare articoli approvati

---

## 📊 ANALISI FLUSSO ATTUALE

### Flusso Attuale (Parzialmente Funzionante)

```
1. Intel Scraper crea articolo completo
   → Salvato in: data/pending_articles/{id}.json
   → Preview HTML: data/previews/{id}.html
   → Cover Image: data/images/cover_*.png

2. send_to_api() viene chiamato
   → Endpoint: POST /api/intel/scraper/submit
   → ❌ PROBLEMA: cover_image NON incluso nel payload
   → ❌ PROBLEMA: preview_html NON incluso nel payload
   → ✅ Solo markdown text viene inviato

3. Backend salva in staging
   → Location: data/staging/{type}/{item_id}.json
   → ❌ cover_image mancante o non salvato correttamente
   → ❌ preview_html non salvato

4. Frontend chiama API
   → GET /api/intel/staging/pending?type=news
   → ✅ Articoli vengono mostrati
   → ❌ Cover image mancante (mostra warning)
   → ❌ Preview HTML non disponibile

5. Dashboard mostra articoli
   → ✅ Lista articoli funziona
   → ✅ Preview markdown funziona
   → ❌ Cover image mancante
   → ❌ Editing non disponibile
   → ❌ Upload cover image non disponibile
```

---

## 🔍 PROBLEMI IDENTIFICATI

### Problema 1: Cover Image Non Arriva al Backend

**Causa:** `send_to_api()` in `article_deep_enricher.py` non include `cover_image` nel payload

**File:** `apps/bali-intel-scraper/scripts/article_deep_enricher.py` (linea ~832)

**Codice attuale:**

```python
payload = {
    "title": article.headline,
    "content": self.format_as_markdown(article),
    # ❌ cover_image mancante
    # ❌ preview_html mancante
    ...
}
```

### Problema 2: Cover Image Non Salvato Correttamente

**Causa:** Backend riceve `cover_image` ma potrebbe essere solo URL/path, non file

**File:** `apps/backend-rag/backend/app/routers/intel.py` (linea ~185)

**Codice attuale:**

```python
if submission.cover_image:
    staging_data["cover_image"] = submission.cover_image
    # ❌ Non salva file fisicamente se è base64
    # ❌ Non verifica se URL è accessibile
```

### Problema 3: Editing e Upload Non Disponibili

**Causa:** Endpoint e componenti frontend non esistono

**Manca:**

- ❌ Endpoint `PUT /api/intel/staging/{type}/{item_id}` per editing
- ❌ Endpoint `POST /api/intel/staging/{type}/{item_id}/cover` per upload
- ❌ Componente `ArticleEditor.tsx`
- ❌ Componente `CoverImageUploader.tsx`

---

## 📋 PIANO IMPLEMENTAZIONE STEP-BY-STEP

### STEP 1: Modificare `send_to_api()` per Includere Cover Image

**File:** `apps/bali-intel-scraper/scripts/article_deep_enricher.py`

**Modifiche:**

1. Leggere cover image file se disponibile
2. Convertire in base64 se file locale
3. Oppure usare URL se già disponibile online
4. Includere nel payload

**Codice da aggiungere:**

```python
# In send_to_api() method
cover_image_data = None
if article.cover_image:
    # Prova a leggere file locale
    image_path = Path(article.cover_image)
    if image_path.exists():
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            cover_image_data = base64.b64encode(image_bytes).decode("utf-8")
    else:
        # Usa URL se disponibile
        cover_image_data = article.cover_image

payload = {
    ...
    "cover_image": cover_image_data,  # NUOVO
    "cover_image_filename": image_path.name if image_path.exists() else None,  # NUOVO
}
```

### STEP 2: Includere Preview HTML nel Payload

**File:** `apps/bali-intel-scraper/scripts/article_deep_enricher.py`

**Modifiche:**

1. Leggere preview HTML se disponibile
2. Includere nel payload come stringa
3. Includere preview_url (URL online)

**Codice da aggiungere:**

```python
# In send_to_api() method
preview_html_content = None
preview_url = None

# Cerca preview HTML locale
preview_path = Path("data/previews") / f"{article.article_id}.html"
if preview_path.exists():
    preview_html_content = preview_path.read_text(encoding="utf-8")
    preview_url = f"https://bali-intel-scraper.fly.dev/preview/{article.article_id}"

payload = {
    ...
    "preview_html": preview_html_content,  # NUOVO
    "preview_url": preview_url,  # NUOVO
}
```

### STEP 3: Backend - Salvare Cover Image in Storage

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Modifiche:**

1. Se cover_image è base64 → salvare file
2. Se cover_image è URL → salvare URL
3. Aggiornare staging_data con path corretto

**Codice da aggiungere:**

```python
# In submit_from_scraper()
cover_image_path = None
if submission.cover_image:
    if submission.cover_image.startswith("data:image") or len(submission.cover_image) > 1000:
        # È base64 → salva file
        import base64
        image_data = base64.b64decode(submission.cover_image)
        image_dir = staging_service.get_staging_dir(intel_type) / "images"
        image_dir.mkdir(parents=True, exist_ok=True)
        image_filename = f"{item_id}.png"
        image_path = image_dir / image_filename
        image_path.write_bytes(image_data)
        cover_image_path = f"/staging/{intel_type}/images/{image_filename}"
    else:
        # È URL → salva URL
        cover_image_path = submission.cover_image

    staging_data["cover_image"] = cover_image_path
```

### STEP 4: Backend - Salvare Preview HTML

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Modifiche:**

1. Se preview_html presente → salvare file
2. Aggiornare staging_data con path preview HTML

**Codice da aggiungere:**

```python
# In submit_from_scraper()
preview_html_path = None
if submission.preview_html:
    preview_dir = staging_service.get_staging_dir(intel_type) / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_filename = f"{item_id}.html"
    preview_path = preview_dir / preview_filename
    preview_path.write_text(submission.preview_html, encoding="utf-8")
    preview_html_path = f"/staging/{intel_type}/previews/{preview_filename}"
    staging_data["preview_html_path"] = preview_html_path
    staging_data["preview_url"] = submission.preview_url
```

### STEP 5: Backend - Endpoint Editing Articolo

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Nuovo endpoint:**

```python
@router.put("/api/intel/staging/{type}/{item_id}")
async def edit_staging_item(
    type: str,
    item_id: str,
    request: EditStagingItemRequest,
):
    """Edit staging item (title, content, category)"""
    # Carica item esistente
    # Applica modifiche
    # Salva aggiornato
    # Ritorna item aggiornato
```

### STEP 6: Backend - Endpoint Upload Cover Image

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Nuovo endpoint:**

```python
@router.post("/api/intel/staging/{type}/{item_id}/cover")
async def upload_cover_image(
    type: str,
    item_id: str,
    request: UploadCoverImageRequest,
):
    """Upload cover image for staging item"""
    # Decodifica base64
    # Salva file
    # Aggiorna staging_data
    # Ritorna path cover image
```

### STEP 7: Frontend - API Client Aggiornato

**File:** `apps/mouth/src/lib/api/intelligence.api.ts`

**Nuove funzioni:**

```typescript
editItem: async (type, id, edits) => {
  // PUT /api/intel/staging/{type}/{id}
};

uploadCoverImage: async (type, id, imageBase64, filename) => {
  // POST /api/intel/staging/{type}/{id}/cover
};

getPreviewHtml: async (type, id) => {
  // GET /api/intel/staging/{type}/{id}/preview-html
};
```

### STEP 8: Frontend - Componente Editor

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/components/ArticleEditor.tsx`

**Funzionalità:**

- Form editing titolo, contenuto, categoria
- Validazione input
- Salvataggio modifiche
- Chiusura editor

### STEP 9: Frontend - Componente Upload Cover Image

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/components/CoverImageUploader.tsx`

**Funzionalità:**

- Drag & drop o file picker
- Preview immagine selezionata
- Upload base64
- Aggiornamento card dopo upload

### STEP 10: Frontend - Integrazione nella Dashboard

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Modifiche:**

1. Aggiungere pulsante "Edit" su ogni card
2. Aggiungere pulsante "Upload Cover" se cover_image mancante
3. Integrare ArticleEditor (dialog/modal)
4. Integrare CoverImageUploader (dialog/modal)
5. Aggiornare card dopo editing/upload

---

## ⚠️ CRITICAL CONSIDERATIONS

### 1. Cover Image Storage Strategy

**Opzioni:**

- **A)** Salvare come file nel backend storage
- **B)** Usare URL esterno (CDN, S3, etc.)
- **C)** Ibrido: file locale + URL fallback

**Raccomandazione:** Opzione C (ibrido)

- Salvare file locale per backup
- Usare URL preview online se disponibile
- Permettere upload manuale se mancante

### 2. Preview HTML Strategy

**Opzioni:**

- **A)** Salvare HTML nel backend storage
- **B)** Usare URL preview online (`https://bali-intel-scraper.fly.dev/preview/{id}`)
- **C)** Generare HTML dal markdown nel frontend

**Raccomandazione:** Opzione B (URL online)

- Già disponibile e funzionante
- Non richiede storage aggiuntivo
- Accessibile da qualsiasi dispositivo

### 3. Editing Strategy

**Opzioni:**

- **A)** Editing completo (titolo, contenuto, categoria)
- **B)** Editing limitato (solo titolo e categoria)
- **C)** Solo aggiunta cover image

**Raccomandazione:** Opzione A (editing completo)

- Massima flessibilità
- Permette correzioni errori
- Migliora qualità articoli

---

## 📋 CHECKLIST IMPLEMENTAZIONE

### Backend Changes

- [ ] Modificare `ScraperSubmission` model per includere `cover_image`, `preview_html`, `preview_url`
- [ ] Modificare `submit_from_scraper()` per salvare cover image file
- [ ] Modificare `submit_from_scraper()` per salvare preview HTML
- [ ] Creare endpoint `PUT /api/intel/staging/{type}/{item_id}` per editing
- [ ] Creare endpoint `POST /api/intel/staging/{type}/{item_id}/cover` per upload
- [ ] Creare endpoint `GET /api/intel/staging/{type}/{item_id}/preview-html` per preview HTML
- [ ] Aggiornare `IntelStagingService` per gestire cover images e preview HTML

### Intel Scraper Changes

- [ ] Modificare `send_to_api()` per includere `cover_image` (base64 o URL)
- [ ] Modificare `send_to_api()` per includere `preview_html`
- [ ] Modificare `send_to_api()` per includere `preview_url`
- [ ] Testare invio articolo completo

### Frontend Changes

- [ ] Aggiornare `intelligence.api.ts` con nuove funzioni
- [ ] Creare componente `ArticleEditor.tsx`
- [ ] Creare componente `CoverImageUploader.tsx`
- [ ] Modificare `news-room/page.tsx` per integrare editor e uploader
- [ ] Aggiungere pulsanti "Edit" e "Upload Cover" nelle card
- [ ] Gestire stati loading e errori

### Testing

- [ ] Test invio articolo completo con cover image
- [ ] Test salvataggio cover image nel backend
- [ ] Test editing articolo
- [ ] Test upload cover image
- [ ] Test preview HTML nella dashboard
- [ ] Test end-to-end completo

---

## 🚀 ORDINE DI IMPLEMENTAZIONE RACCOMANDATO

1. **STEP 1-2:** Modificare Intel Scraper per inviare cover_image e preview_html
2. **STEP 3-4:** Backend salva cover image e preview HTML
3. **STEP 5-6:** Backend endpoint editing e upload cover image
4. **STEP 7:** Frontend API client aggiornato
5. **STEP 8-9:** Frontend componenti editor e uploader
6. **STEP 10:** Integrazione nella dashboard

**Ogni step deve essere testato prima di procedere al successivo!**

---

**Status:** 📋 PIANO COMPLETO - PRONTO PER IMPLEMENTAZIONE  
**Next:** Attendere approvazione utente prima di iniziare implementazione
