# Piano Integrazione News Room Dashboard - AGGIORNATO

**Purpose:** Piano per integrare articoli Intel Scraper nella dashboard News Room  
**Date:** 2026-01-24  
**Status:** ✅ PIANO AGGIORNATO - PRONTO PER IMPLEMENTAZIONE

---

## 🎯 OBIETTIVO FINALE

Dashboard News Room (`https://kita.balizero.com/intelligence/news-room`) dove:

- ✅ Visualizzare articoli completi dall'Intel Scraper (già arricchiti e impaginati)
- ✅ Approvare/rifiutare articoli
- ✅ **Editare articoli** (titolo, contenuto, categoria)
- ✅ **Aggiungere cover image manualmente** quando articolo è già nella News Room
- ✅ Pubblicare articoli approvati

---

## 📊 FLUSSO AGGIORNATO

### Flusso Corretto (Come Dovrebbe Funzionare)

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

5. Utente aggiunge cover image manualmente
   → ✅ Upload cover image tramite dashboard
   → ✅ Cover image salvata nel backend
   → ✅ Card aggiornata con cover image

6. Utente pubblica articolo
   → ✅ Articolo completo con cover image
   → ✅ Pubblicazione funziona
```

---

## ✅ COSA C'È GIÀ (Funziona)

### Frontend

- ✅ Pagina News Room esiste: `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`
- ✅ Lista articoli pending funziona
- ✅ Filtri e ricerca funzionano
- ✅ Preview articolo (dialog) funziona
- ✅ Pulsante "Publish" funziona
- ✅ Bulk publish funziona
- ✅ Mostra warning se cover image mancante

### Backend

- ✅ Endpoint `POST /api/intel/scraper/submit` esiste
- ✅ Endpoint `GET /api/intel/staging/pending?type=news` esiste
- ✅ Endpoint `POST /api/intel/staging/publish/{type}/{id}` esiste
- ✅ Staging service funziona

---

## ❌ COSA MANCA (Problemi Identificati)

### Problema 1: Preview HTML Non Disponibile

**Causa:** Preview HTML è solo locale, non viene inviato al backend

**Risultato:** Dashboard mostra solo markdown text, non preview HTML completo con componenti interattivi

### Problema 2: Editing Non Disponibile

**Causa:** Endpoint e componenti frontend non esistono

**Manca:**

- ❌ Endpoint `PUT /api/intel/staging/{type}/{id}` per editing
- ❌ Componente `ArticleEditor.tsx`
- ❌ Funzionalità editing nella dashboard

### Problema 3: Upload Cover Image Non Disponibile

**Causa:** Endpoint e componenti frontend non esistono

**Manca:**

- ❌ Endpoint `POST /api/intel/staging/{type}/{id}/cover` per upload
- ❌ Componente `CoverImageUploader.tsx`
- ❌ Funzionalità upload nella dashboard

---

## 📋 PIANO IMPLEMENTAZIONE AGGIORNATO (8 STEP)

### STEP 1: Includere Preview HTML nel Payload

**File:** `apps/bali-intel-scraper/scripts/article_deep_enricher.py`

**Modifica:** Aggiungere `preview_html` e `preview_url` al payload in `send_to_api()`

**Cosa fare:**

1. Leggere preview HTML se disponibile (`data/previews/{id}.html`)
2. Includere nel payload come stringa
3. Includere preview_url (URL online: `https://bali-intel-scraper.fly.dev/preview/{id}`)

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
    # ❌ cover_image NON incluso (verrà aggiunto manualmente)
}
```

### STEP 2: Backend Salva Preview HTML

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Modifica:** Salvare preview HTML file se presente

**Cosa fare:**

1. Se preview_html presente → salvare file
2. Aggiornare staging_data con path preview HTML
3. Salvare preview_url nel staging_data

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

### STEP 3: Backend - Endpoint Editing Articolo

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Nuovo endpoint:** `PUT /api/intel/staging/{type}/{item_id}`

**Cosa fare:**

1. Creare `EditStagingItemRequest` model
2. Implementare endpoint editing
3. Validazione dati
4. Salvataggio modifiche

**Schema request:**

```python
class EditStagingItemRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    # Altri campi modificabili
```

### STEP 4: Backend - Endpoint Upload Cover Image

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Nuovo endpoint:** `POST /api/intel/staging/{type}/{item_id}/cover`

**Cosa fare:**

1. Creare `UploadCoverImageRequest` model
2. Implementare endpoint upload
3. Decodificare base64
4. Salvare file cover image
5. Aggiornare staging_data con path cover image

**Schema request:**

```python
class UploadCoverImageRequest(BaseModel):
    cover_image_base64: str  # Base64 encoded image
    filename: str | None = None
```

**Codice endpoint:**

```python
@router.post("/api/intel/staging/{type}/{item_id}/cover")
async def upload_cover_image(
    type: str,
    item_id: str,
    request: UploadCoverImageRequest,
):
    """Upload cover image for staging item"""
    # Carica item esistente
    data = staging_service.load_staging_item(type, item_id)
    if not data:
        raise HTTPException(status_code=404, detail="Item not found")

    # Decodifica base64
    import base64
    image_data = base64.b64decode(request.cover_image_base64)

    # Salva file
    image_dir = staging_service.get_staging_dir(type) / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_filename = f"{item_id}.png"
    image_path = image_dir / image_filename
    image_path.write_bytes(image_data)

    # Aggiorna staging_data
    cover_image_path = f"/staging/{type}/images/{image_filename}"
    data["cover_image"] = cover_image_path
    staging_service.save_staging_item(type, item_id, data)

    return {
        "success": True,
        "cover_image": cover_image_path,
        "message": "Cover image uploaded successfully"
    }
```

### STEP 5: Frontend - API Client Aggiornato

**File:** `apps/mouth/src/lib/api/intelligence.api.ts`

**Nuove funzioni:**

```typescript
editItem: async (
  type: "visa" | "news",
  id: string,
  edits: {
    title?: string;
    content?: string;
    category?: string;
  },
): Promise<ApproveResponse> => {
  const endpoint = `/api/intel/staging/${type}/${id}`;
  return await api.request<ApproveResponse>(endpoint, {
    method: "PUT",
    body: JSON.stringify(edits),
  });
};

uploadCoverImage: async (
  type: "visa" | "news",
  id: string,
  imageBase64: string,
  filename?: string,
): Promise<{ success: boolean; cover_image: string }> => {
  const endpoint = `/api/intel/staging/${type}/${id}/cover`;
  return await api.request<{ success: boolean; cover_image: string }>(
    endpoint,
    {
      method: "POST",
      body: JSON.stringify({
        cover_image_base64: imageBase64,
        filename,
      }),
    },
  );
};
```

### STEP 6: Frontend - Componente Editor

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/components/ArticleEditor.tsx`

**Funzionalità:**

- Form editing titolo, contenuto, categoria
- Validazione input
- Salvataggio modifiche
- Chiusura editor

### STEP 7: Frontend - Componente Upload Cover Image

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/components/CoverImageUploader.tsx`

**Funzionalità:**

- Drag & drop o file picker
- Preview immagine selezionata
- Converti in base64
- Upload base64
- Aggiornamento card dopo upload

### STEP 8: Integrazione nella Dashboard

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Modifiche:**

1. Aggiungere pulsante "Edit" su ogni card
2. Aggiungere pulsante "Upload Cover" se cover_image mancante
3. Integrare ArticleEditor (dialog/modal)
4. Integrare CoverImageUploader (dialog/modal)
5. Aggiornare card dopo editing/upload

---

## 🎯 PRIORITÀ IMPLEMENTAZIONE

### 🔴 Priorità ALTA (Blocca funzionalità)

1. **STEP 1:** Includere preview_html nel payload submission
2. **STEP 2:** Backend salva preview HTML
3. **STEP 4:** Backend endpoint upload cover image
4. **STEP 7-8:** Upload cover image nella dashboard

### 🟡 Priorità MEDIA (Migliora UX)

5. **STEP 3:** Backend endpoint editing articolo
6. **STEP 5-6:** Frontend componenti editor
7. **STEP 8:** Integrazione editing nella dashboard

---

## ⚠️ CRITICAL CONSIDERATIONS

### 1. Preview HTML Strategy

**Raccomandazione:** Usare URL preview online (`https://bali-intel-scraper.fly.dev/preview/{id}`)

- Già disponibile e funzionante
- Include componenti interattivi
- Non richiede storage aggiuntivo
- Accessibile da qualsiasi dispositivo

**Backup:** Salvare anche HTML locale nel backend per fallback

### 2. Cover Image Upload Strategy

**Workflow:**

1. Articolo arriva nella News Room SENZA cover image
2. Utente visualizza preview HTML completo
3. Utente decide cover image appropriata
4. Utente upload cover image manualmente
5. Articolo completo viene pubblicato

**Formato:** Base64 upload → salvataggio file PNG nel backend

### 3. Editing Strategy

**Raccomandazione:** Editing completo (titolo, contenuto, categoria)

- Massima flessibilità
- Permette correzioni errori
- Migliora qualità articoli

---

## 📋 CHECKLIST IMPLEMENTAZIONE

### Backend Changes

- [ ] Modificare `ScraperSubmission` model per includere `preview_html`, `preview_url`
- [ ] Modificare `submit_from_scraper()` per salvare preview HTML
- [ ] Creare endpoint `PUT /api/intel/staging/{type}/{id}` per editing
- [ ] Creare endpoint `POST /api/intel/staging/{type}/{id}/cover` per upload
- [ ] Aggiornare `IntelStagingService` per gestire preview HTML e cover images

### Intel Scraper Changes

- [ ] Modificare `send_to_api()` per includere `preview_html`
- [ ] Modificare `send_to_api()` per includere `preview_url`
- [ ] ❌ NON includere `cover_image` (verrà aggiunto manualmente)
- [ ] Testare invio articolo completo

### Frontend Changes

- [ ] Aggiornare `intelligence.api.ts` con nuove funzioni
- [ ] Creare componente `ArticleEditor.tsx`
- [ ] Creare componente `CoverImageUploader.tsx`
- [ ] Modificare `news-room/page.tsx` per integrare editor e uploader
- [ ] Aggiungere pulsanti "Edit" e "Upload Cover" nelle card
- [ ] Gestire stati loading e errori

### Testing

- [ ] Test invio articolo completo con preview HTML
- [ ] Test salvataggio preview HTML nel backend
- [ ] Test editing articolo
- [ ] Test upload cover image manuale
- [ ] Test preview HTML nella dashboard
- [ ] Test end-to-end completo

---

## 🚀 ORDINE DI IMPLEMENTAZIONE RACCOMANDATO

1. **STEP 1-2:** Modificare Intel Scraper per inviare preview_html + Backend salva preview HTML
2. **STEP 3-4:** Backend endpoint editing e upload cover image
3. **STEP 5:** Frontend API client aggiornato
4. **STEP 6-7:** Frontend componenti editor e uploader
5. **STEP 8:** Integrazione nella dashboard

**⚠️ IMPORTANTE:** Ogni step deve essere testato prima di procedere al successivo!

---

## 📚 DOCUMENTAZIONE

**Documenti aggiornati:**

- `docs/PIANO_NEWS_ROOM_AGGIORNATO.md` - Questo documento (piano aggiornato)

**Documenti da aggiornare:**

- `docs/RIEPILOGO_PIANO_NEWS_ROOM.md` - Riepilogo (da aggiornare)
- `docs/PIANO_IMPLEMENTAZIONE_DETTAGLIATO.md` - Piano dettagliato (da aggiornare)

---

**Status:** ✅ PIANO AGGIORNATO - PRONTO PER IMPLEMENTAZIONE  
**Next:** Attendere approvazione utente prima di iniziare implementazione
