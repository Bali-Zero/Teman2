# Piano Integrazione News Room Dashboard - VERSIONE DETTAGLIATA

**Purpose:** Piano completo e dettagliato per integrare articoli Intel Scraper nella dashboard News Room  
**Date:** 2026-01-24  
**Status:** ✅ PIANO DETTAGLIATO - PRONTO PER IMPLEMENTAZIONE

---

## 🎯 OBIETTIVO FINALE

Dashboard News Room (`https://kita.balizero.com/intelligence/news-room`) dove:

- ✅ Visualizzare articoli completi dall'Intel Scraper (già arricchiti e impaginati)
- ✅ Approvare/rifiutare articoli
- ✅ **Editare articoli** (titolo, contenuto, categoria)
- ✅ **Aggiungere cover image manualmente** quando articolo è già nella News Room
- ✅ **Approvare articolo → pubblicazione automatica su balizero.com**

---

## 📊 FLUSSO COMPLETO DETTAGLIATO

### 1. Intel Scraper → Backend Submission

**File:** `apps/bali-intel-scraper/scripts/article_deep_enricher.py`

**Metodo:** `send_to_api()`

**Endpoint:** `POST https://nuzantara-rag.fly.dev/api/intel/scraper/submit`

**Headers:**

```
Content-Type: application/json
X-API-Key: {API_KEY}
```

**Payload attuale:**

```python
{
    "title": article.headline,
    "content": self.format_as_markdown(article),  # Markdown text
    "source_url": article.source_url,
    "source_name": article.source,
    "category": article.category,  # "immigration", "business", "property", etc.
    "relevance_score": article.relevance_score,  # 0-100
    "published_at": article.published_at,
    "extraction_method": "claude_max",
    "tier": "T1",
    "components": article.components,
    # ❌ cover_image: NON incluso
    # ❌ preview_html: NON incluso
    # ❌ preview_url: NON incluso
}
```

**Payload da modificare (STEP 1):**

```python
{
    "title": article.headline,
    "content": self.format_as_markdown(article),
    "source_url": article.source_url,
    "source_name": article.source,
    "category": article.category,
    "relevance_score": article.relevance_score,
    "published_at": article.published_at,
    "extraction_method": "claude_max",
    "tier": "T1",
    "components": article.components,
    "preview_html": preview_html_content,  # NUOVO: HTML completo
    "preview_url": f"https://bali-intel-scraper.fly.dev/preview/{article.article_id}",  # NUOVO
    # ❌ cover_image: NON incluso (verrà aggiunto manualmente)
}
```

---

### 2. Backend → Staging Storage

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Endpoint:** `POST /api/intel/scraper/submit`

**Handler:** `submit_from_scraper()`

**Processo dettagliato:**

1. **Classificazione tipo:**

   ```python
   intel_type = classification_service.classify_intel_type(
       submission.category, submission.title, submission.content
   )
   # Risultato: "visa" o "news"
   ```

2. **Generazione item_id:**

   ```python
   item_id = staging_service.generate_item_id(
       intel_type, submission.title, submission.source_url
   )
   # Formato: "{intel_type}_{timestamp}_{hash}"
   # Esempio: "news_20260124_123456_a1b2c3d4"
   ```

3. **Controllo duplicati:**

   ```python
   duplicate = staging_service.check_duplicate(intel_type, submission.source_url)
   ```

4. **Preparazione staging_data:**

   ```python
   staging_data = {
       "item_id": item_id,
       "title": submission.title,
       "content": submission.content,  # Markdown text
       "source_url": submission.source_url,
       "source_name": submission.source_name,
       "category": submission.category,
       "relevance_score": submission.relevance_score,
       "published_at": submission.published_at or "unknown",
       "extraction_method": submission.extraction_method,
       "tier": submission.tier,
       "intel_type": intel_type,  # "visa" o "news"
       "status": "pending",
       "detection_type": "scraper_auto",
       "detected_at": datetime.utcnow().isoformat(),
       # ❌ cover_image: NON incluso
       # ❌ preview_html: NON incluso
   }
   ```

5. **Salvataggio staging:**
   ```python
   staging_file = staging_service.save_staging_item(intel_type, item_id, staging_data)
   # Path: data/staging/{intel_type}/{item_id}.json
   # Esempio: data/staging/news/news_20260124_123456_a1b2c3d4.json
   ```

**Modifiche necessarie (STEP 2):**

```python
# Salvare preview_html se presente
if submission.preview_html:
    preview_dir = staging_service.get_staging_dir(intel_type) / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_filename = f"{item_id}.html"
    preview_path = preview_dir / preview_filename
    preview_path.write_text(submission.preview_html, encoding="utf-8")
    staging_data["preview_html_path"] = f"/staging/{intel_type}/previews/{preview_filename}"
    staging_data["preview_url"] = submission.preview_url
```

**Storage structure:**

```
data/staging/
├── visa/
│   ├── {item_id}.json
│   ├── previews/
│   │   └── {item_id}.html
│   └── images/
│       └── {item_id}.png  # Cover image (se uploadata)
└── news/
    ├── {item_id}.json
    ├── previews/
    │   └── {item_id}.html
    └── images/
        └── {item_id}.png  # Cover image (se uploadata)
```

---

### 3. Frontend → Lista Articoli Pending

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**API Call:**

```typescript
const res = await intelligenceApi.getPendingItems("news");
```

**Endpoint Backend:** `GET /api/intel/staging/pending?type=news`

**Handler:** `list_pending_items()`

**Risposta:**

```json
{
  "items": [
    {
      "id": "news_20260124_123456_a1b2c3d4",
      "type": "news",
      "title": "Article Title",
      "content": "Markdown content...",
      "cover_image": null, // o path se presente
      "preview_url": "https://bali-intel-scraper.fly.dev/preview/{id}",
      "detected_at": "2026-01-24T12:34:56",
      "source": "https://source-url.com",
      "source_name": "Source Name",
      "detection_type": "NEW",
      "status": "pending",
      "category": "immigration",
      "relevance_score": 75
    }
  ],
  "count": 12
}
```

---

### 4. Utente → Visualizza Preview HTML

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Funzione:** `handlePreview(item)`

**API Call:**

```typescript
const fullItem = await intelligenceApi.getPreview(item.type, item.id);
```

**Endpoint Backend:** `GET /api/intel/staging/preview/{type}/{item_id}`

**Handler:** `preview_staging_item()`

**Risposta:**

```json
{
  "id": "news_20260124_123456_a1b2c3d4",
  "type": "news",
  "title": "Article Title",
  "content": "Markdown content...",
  "preview_html": "<html>...</html>", // HTML completo con componenti interattivi
  "preview_url": "https://bali-intel-scraper.fly.dev/preview/{id}",
  "cover_image": null,
  "detected_at": "2026-01-24T12:34:56",
  "source": "https://source-url.com",
  "source_name": "Source Name",
  "detection_type": "NEW",
  "status": "pending",
  "category": "immigration",
  "relevance_score": 75
}
```

**Visualizzazione:**

- Dialog con preview HTML completo
- Componenti interattivi funzionanti
- Link a preview online se disponibile

---

### 5. Utente → Modifica Articolo

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Funzione:** `handleEdit(item)`

**API Call:**

```typescript
await intelligenceApi.editItem(item.type, item.id, {
  title: "New Title",
  content: "New Content",
  category: "business",
});
```

**Endpoint Backend:** `PUT /api/intel/staging/{type}/{item_id}` (STEP 3 - DA CREARE)

**Request Body:**

```json
{
  "title": "New Title", // Opzionale
  "content": "New Content", // Opzionale
  "category": "business" // Opzionale
}
```

**Handler:** `edit_staging_item()` (STEP 3 - DA CREARE)

**Processo:**

1. Carica staging item esistente
2. Applica modifiche (solo campi presenti)
3. Salva staging item aggiornato
4. Ritorna item aggiornato

---

### 6. Utente → Upload Cover Image

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Funzione:** `handleUploadCover(item, imageFile)`

**API Call:**

```typescript
const imageBase64 = await convertFileToBase64(imageFile);
await intelligenceApi.uploadCoverImage(
  item.type,
  item.id,
  imageBase64,
  imageFile.name,
);
```

**Endpoint Backend:** `POST /api/intel/staging/{type}/{item_id}/cover` (STEP 4 - DA CREARE)

**Request Body:**

```json
{
  "cover_image_base64": "data:image/png;base64,iVBORw0KG...",
  "filename": "cover.png" // Opzionale
}
```

**Handler:** `upload_cover_image()` (STEP 4 - DA CREARE)

**Processo:**

1. Decodifica base64 → bytes
2. Salva file: `data/staging/{type}/images/{item_id}.png`
3. Aggiorna staging_data:
   ```python
   staging_data["cover_image"] = f"/staging/{type}/images/{item_id}.png"
   ```
4. Salva staging item aggiornato
5. Ritorna path cover image

---

### 7. Utente → Approva Articolo

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Funzione:** `handlePublish(item)`

**API Call:**

```typescript
const response = await intelligenceApi.publishItem(item.type, item.id);
```

**Endpoint Backend:** `POST /api/intel/staging/publish/{type}/{item_id}`

**Handler:** `publish_staging_item()`

**Processo attuale:**

1. **Carica staging item:**

   ```python
   data = staging_service.load_staging_item(type, item_id)
   # Path: data/staging/{type}/{item_id}.json
   ```

2. **Ingest to Qdrant (knowledge base):**

   ```python
   ingestion_success = await ingest_intel_to_qdrant(item_id, type)
   ```

   **Collection Qdrant (PRECISA):**
   - Se `type == "visa"` → Collection: `"visa_oracle"`
   - Se `type == "news"` → Collection: `"bali_intel_bali_news"`

   **Definita in:**
   - `apps/backend-rag/backend/app/core/constants.py` (linea 117-128):
     ```python
     INTEL_COLLECTIONS = {
         "visa": "visa_oracle",
         "news": "bali_intel_bali_news",
         ...
     }
     ```
   - `apps/backend-rag/backend/app/routers/telegram.py` (linea 419):
     ```python
     collection_name = "visa_oracle" if intel_type == "visa" else "bali_intel_bali_news"
     ```

   **Processo ingest:**
   - Legge staging file: `data/staging/{type}/{item_id}.json`
   - Crea embedding del contenuto
   - Salva in Qdrant con metadata:
     ```python
     {
         "item_id": item_id,
         "title": title,
         "category": category,
         "source_url": source_url,
         "intel_type": intel_type,
         "tier": tier,
         "published_date": datetime.utcnow().isoformat(),
         ...
     }
     ```
   - Sposta file a: `data/staging/{type}/archived/approved/{item_id}.json`

3. **Registra in anti-duplicate system:**

   ```python
   published_url = f"https://balizero.com/{category}/{item_id}"
   ClaudeValidator.add_published_article(
       title=title,
       url=published_url,
       category=category,
       published_at=datetime.utcnow().isoformat(),
   )
   ```

4. **Aggiorna staging file:**
   ```python
   data["published_at"] = datetime.utcnow().isoformat()
   data["published_url"] = f"https://balizero.com/{category}/{item_id}"  # ❌ URL fittizio
   data["status"] = "published"
   ```

**❌ PROBLEMA:** URL generato non funziona perché articolo NON è pubblicato su GitHub/Vercel

---

### 8. Backend → Pubblicazione GitHub/Vercel (STEP 5-6 - DA IMPLEMENTARE)

**Modifiche necessarie a `publish_staging_item()`:**

**STEP 5: Creare funzione conversione**

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Funzione:** `convert_staging_to_enriched_article(staging_data: dict) -> EnrichedArticle`

**Input (staging_data):**

```python
{
    "item_id": "news_20260124_123456_a1b2c3d4",
    "title": "Article Title",
    "content": "# Article Title\n\n## Summary\n...\n\n## Facts\n...\n\n## Bali Zero Take\n...",
    "category": "immigration",
    "relevance_score": 75,
    "cover_image": "/staging/news/images/news_20260124_123456_a1b2c3d4.png",  # Se presente
    "source_url": "https://source-url.com",
    "source_name": "Source Name",
    "preview_html": "<html>...</html>",
    "preview_url": "https://bali-intel-scraper.fly.dev/preview/{id}",
    ...
}
```

**Output (EnrichedArticle):**

```python
EnrichedArticle(
    title="Article Title",
    headline="Article Title",
    tldr=TLDRSection(
        should_worry="No",
        what="What happened",
        who="Expats and investors",
        when="Now",
        risk_level="low"
    ),
    facts="Facts section content...",
    bali_zero_take=BaliZeroTake(
        hidden_insight="What they don't tell you...",
        our_analysis="Strategic context...",
        our_advice="Clear actionable recommendation..."
    ),
    next_steps=NextSteps(
        expat=["Action 1", "Action 2"],
        investor=["Action 1", "Action 2"]
    ),
    category="immigration",
    priority="medium",
    relevance_score=75,
    ai_summary="Executive summary...",
    ai_tags=["tag1", "tag2", "tag3"],
    suggested_components=["timeline", "checklist"],
    cover_image="/staging/news/images/news_20260124_123456_a1b2c3d4.png",  # Se presente
    source="Source Name",
    source_url="https://source-url.com",
    enriched_at="2026-01-24T12:34:56"
)
```

**Processo conversione:**

1. Parsare `content` (markdown) per estrarre sezioni:
   - `## Summary` → `tldr.what`
   - `## Facts` → `facts`
   - `## Bali Zero Take` → `bali_zero_take`
   - `## Next Steps` → `next_steps`
2. Generare `tldr` section (se mancante)
3. Generare `ai_summary` (se mancante)
4. Generare `ai_tags` (se mancanti)
5. Generare `suggested_components` (se mancanti)

**STEP 6: Modificare pubblicazione**

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Modifiche a `publish_staging_item()`:**

```python
# Dopo Step 2 (Register in anti-duplicate system), aggiungere:

# Step 3: Convert staging item to EnrichedArticle
try:
    enriched_article = convert_staging_to_enriched_article(data)

    # Step 4: Publish to GitHub/Vercel (balizero.com)
    from backend.app.routers.article_composer import publish_article, PublishRequest

    # Leggi cover image se presente
    cover_image_base64 = None
    cover_image_filename = None
    if data.get("cover_image"):
        cover_image_path = Path(data["cover_image"])
        if cover_image_path.exists():
            cover_image_bytes = cover_image_path.read_bytes()
            cover_image_base64 = base64.b64encode(cover_image_bytes).decode("utf-8")
            cover_image_filename = cover_image_path.name

    # Crea publish request
    publish_request = PublishRequest(
        article=enriched_article,
        cover_image_base64=cover_image_base64,
        cover_image_filename=cover_image_filename,
        slug=None,  # Auto-generato
        position="normal"
    )

    # Pubblica su GitHub/Vercel
    publish_result = await publish_article(publish_request)

    if publish_result.success:
        # Aggiorna staging data con URL reale
        data["published_url"] = publish_result.published_url
        data["github_commit_sha"] = publish_result.commit_sha
        data["published_at"] = datetime.utcnow().isoformat()
        data["status"] = "published"

        logger.info(
            "✅ Article published to GitHub/Vercel",
            extra={
                "type": type,
                "item_id": item_id,
                "published_url": publish_result.published_url,
                "commit_sha": publish_result.commit_sha
            }
        )
    else:
        logger.error(
            "⚠️ Failed to publish to GitHub/Vercel",
            extra={
                "type": type,
                "item_id": item_id,
                "error": publish_result.error
            }
        )
        # Non bloccare pubblicazione se GitHub fallisce
        # Articolo è già in Qdrant

except Exception as e:
    logger.error(
        f"⚠️ Failed to publish to GitHub/Vercel: {e}",
        exc_info=True,
        extra={"type": type, "item_id": item_id}
    )
    # Non bloccare pubblicazione se GitHub fallisce
    # Articolo è già in Qdrant

# Step 5: Update staging file (già fatto sopra se GitHub success)
```

**Endpoint GitHub Publisher:**

**File:** `apps/backend-rag/backend/app/routers/article_composer.py`

**Endpoint:** `POST /api/articles/publish`

**Handler:** `publish_article(request: PublishRequest)`

**Processo:**

1. Genera slug: `generate_slug(article.headline)`
2. Genera MDX content: `generate_mdx_content(article, slug, cover_image_path)`
3. Committa su GitHub:
   - Repository: `Balizero1987/Teman2` (da config)
   - Path MDX: `apps/mouth/src/content/articles/{category}/{slug}.mdx`
   - Path cover image: `apps/mouth/public/images/articles/{category}/{slug}.png` (se presente)
4. Trigger Vercel deploy automatico
5. Ritorna:
   ```python
   PublishResponse(
       success=True,
       published_url=f"https://balizero.com/{category}/{slug}",
       commit_sha="abc123...",
       ...
   )
   ```

**Collection Qdrant finale (PRECISE):**

- **Visa articles:** Collection `"visa_oracle"`
- **News articles:** Collection `"bali_intel_bali_news"`
- **Definite in:** `apps/backend-rag/backend/app/core/constants.py` (INTEL_COLLECTIONS)

**GitHub Repository (PRECISO):**

- **Owner:** `Balizero1987` (default, da config)
- **Repo:** `Teman2` (default, da config)
- **Definito in:** `apps/backend-rag/backend/app/core/config.py` (linea 492-499)

**Path GitHub (PRECISI):**

- **MDX file:** `apps/mouth/src/content/articles/{category_folder}/{slug}.mdx`
- **Cover image:** `apps/mouth/public/static/news/{image_filename}`
- **Category mapping:**
  - `immigration` → `immigration`
  - `business` → `business`
  - `tax` → `tax-legal`
  - `property` → `property`
  - `lifestyle` → `lifestyle`
  - `tech` → `tech`
  - `legal` → `tax-legal`

**URL finale pubblicazione (PRECISO):**

- **Formato:** `https://balizero.com/{category_folder}/{slug}`
- **Esempio:** `https://balizero.com/immigration/indonesia-golden-visa-2025`
- **Slug generato da:** `generate_slug(article.headline)` (lowercase, hyphen-separated, no special chars)

---

## 📋 CHECKLIST IMPLEMENTAZIONE DETTAGLIATA

### Backend Changes

- [ ] **STEP 1:** Modificare `ScraperSubmission` model per includere `preview_html: str | None`, `preview_url: str | None`
- [ ] **STEP 2:** Modificare `submit_from_scraper()` per salvare preview HTML in `data/staging/{type}/previews/{item_id}.html`
- [ ] **STEP 3:** Creare endpoint `PUT /api/intel/staging/{type}/{item_id}` con `EditStagingItemRequest` model
- [ ] **STEP 4:** Creare endpoint `POST /api/intel/staging/{type}/{item_id}/cover` con `UploadCoverImageRequest` model
- [ ] **STEP 5:** Creare funzione `convert_staging_to_enriched_article(staging_data: dict) -> EnrichedArticle`
- [ ] **STEP 6:** Modificare `publish_staging_item()` per chiamare `publish_article()` dopo ingest to Qdrant
- [ ] **STEP 6:** Gestire errori pubblicazione GitHub (non bloccare se fallisce)

### Intel Scraper Changes

- [ ] **STEP 1:** Modificare `send_to_api()` per leggere `data/previews/{article_id}.html`
- [ ] **STEP 1:** Modificare `send_to_api()` per includere `preview_html` nel payload
- [ ] **STEP 1:** Modificare `send_to_api()` per includere `preview_url` nel payload
- [ ] **STEP 1:** ❌ NON includere `cover_image` (verrà aggiunto manualmente)

### Frontend Changes

- [ ] **STEP 7:** Aggiornare `intelligence.api.ts` con `editItem()` e `uploadCoverImage()`
- [ ] **STEP 8:** Creare componente `ArticleEditor.tsx`
- [ ] **STEP 8:** Creare componente `CoverImageUploader.tsx`
- [ ] **STEP 9:** Modificare `news-room/page.tsx` per integrare editor e uploader
- [ ] **STEP 9:** Aggiungere pulsanti "Edit" e "Upload Cover" nelle card

### Testing

- [ ] Test invio articolo completo con preview_html
- [ ] Test salvataggio preview HTML nel backend
- [ ] Test editing articolo
- [ ] Test upload cover image manuale
- [ ] Test conversione staging → EnrichedArticle
- [ ] Test pubblicazione Qdrant (collection corretta)
- [ ] Test pubblicazione GitHub/Vercel
- [ ] Test end-to-end completo: Approvazione → Pubblicazione su balizero.com

---

## 🎯 COLLECTION QDRANT PRECISE

**Per articoli Intel Scraper:**

- **Type "visa":** Collection `"visa_oracle"`
- **Type "news":** Collection `"bali_intel_bali_news"`

**Definite in:**

- `apps/backend-rag/backend/app/routers/telegram.py` (linea ~419)
- `apps/backend-rag/backend/app/core/constants.py` (INTEL_COLLECTIONS)

---

**Status:** ✅ PIANO DETTAGLIATO - PRONTO PER IMPLEMENTAZIONE  
**Next:** Attendere approvazione utente prima di iniziare implementazione
