# Piano Integrazione News Room Dashboard - VERSIONE CORRETTA

**Purpose:** Piano corretto per integrare articoli Intel Scraper nella dashboard News Room  
**Date:** 2026-01-24  
**Status:** ✅ PIANO CORRETTO - PRONTO PER IMPLEMENTAZIONE

---

## ⚠️ CORREZIONE CRITICA

**Gli articoli dell'Intel Scraper sono ARTICOLI DI BLOG/NEWS, NON conoscenza legale!**

**❌ NON devono andare in:**

- `visa_oracle` (conoscenza legale su visti)
- `kbli_unified` (conoscenza legale su KBLI)
- `tax_genius` (conoscenza legale su tasse)
- `legal_unified` (conoscenza legale generale)
- Qualsiasi collection della knowledge base legale

**✅ Devono essere pubblicati SOLO su:**

- GitHub → Vercel → `https://balizero.com/{category}/{slug}`
- Come articoli di blog pubblici

**❌ NON devono essere salvati in Qdrant knowledge base!**

---

## 📊 FLUSSO CORRETTO

### 1. Intel Scraper → Backend Submission

**Endpoint:** `POST /api/intel/scraper/submit`

**Payload:**

```python
{
    "title": article.headline,
    "content": self.format_as_markdown(article),
    "preview_html": preview_html_content,  # NUOVO
    "preview_url": preview_url,  # NUOVO
    "source_url": article.source_url,
    "source_name": article.source,
    "category": article.category,
    "relevance_score": article.relevance_score,
    # ❌ cover_image: NON incluso (verrà aggiunto manualmente)
}
```

### 2. Backend → Staging Storage

**Location:** `data/staging/news/{item_id}.json`

**Dati salvati:**

```json
{
    "item_id": "news_20260124_123456_a1b2c3d4",
    "title": "Article Title",
    "content": "Markdown content...",
    "preview_html": "<html>...</html>",
    "preview_url": "https://bali-intel-scraper.fly.dev/preview/{id}",
    "category": "immigration",
    "status": "pending",
    ...
}
```

### 3. Frontend → News Room Dashboard

**Endpoint:** `GET /api/intel/staging/pending?type=news`

**Mostra articoli pending per:**

- Visualizzazione preview HTML
- Editing (titolo, contenuto, categoria)
- Upload cover image manuale
- Approvazione

### 4. Utente → Approva Articolo

**Endpoint:** `POST /api/intel/staging/publish/{type}/{item_id}`

**❌ FLUSSO ATTUALE (SBAGLIATO):**

```python
# Step 1: Ingest to Qdrant (knowledge base) ❌ SBAGLIATO!
ingestion_success = await ingest_intel_to_qdrant(item_id, type)
# Questo salva in "visa_oracle" o "bali_intel_bali_news" ❌

# Step 2: Register in anti-duplicate system ✅ OK
# Step 3: Update staging file ✅ OK
# ❌ MANCA: Pubblicazione su GitHub/Vercel
```

**✅ FLUSSO CORRETTO (DA IMPLEMENTARE):**

```python
# Step 1: ❌ RIMUOVERE ingest to Qdrant (NON serve per articoli blog)
# Gli articoli NON vanno nella knowledge base!

# Step 2: Register in anti-duplicate system ✅ OK
# (per evitare duplicati, ma NON salva in Qdrant)

# Step 3: Convert staging item → EnrichedArticle ✅ NUOVO
enriched_article = convert_staging_to_enriched_article(data)

# Step 4: Publish to GitHub/Vercel → balizero.com ✅ NUOVO
publish_result = await publish_article(PublishRequest(
    article=enriched_article,
    cover_image_base64=cover_image_base64,
    cover_image_filename=cover_image_filename
))

# Step 5: Update staging file con URL reale ✅
data["published_url"] = publish_result.article_url
data["published_at"] = datetime.utcnow().isoformat()
data["status"] = "published"
```

---

## 🔧 MODIFICHE NECESSARIE

### Modifica 1: Rimuovere Ingest to Qdrant

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Endpoint:** `publish_staging_item()`

**Rimuovere:**

```python
# ❌ RIMUOVERE QUESTO:
# Step 1: Ingest to Qdrant (knowledge base)
from backend.app.routers.telegram import ingest_intel_to_qdrant
ingestion_success = await ingest_intel_to_qdrant(item_id, type)
```

**Motivo:** Gli articoli di blog NON devono essere nella knowledge base Qdrant. Sono articoli pubblici su balizero.com, non conoscenza legale.

### Modifica 2: Aggiungere Pubblicazione GitHub/Vercel

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Endpoint:** `publish_staging_item()`

**Aggiungere dopo Step 2 (anti-duplicate):**

```python
# Step 3: Convert staging item → EnrichedArticle
enriched_article = convert_staging_to_enriched_article(data)

# Step 4: Publish to GitHub/Vercel → balizero.com
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

# Pubblica su GitHub/Vercel
publish_request = PublishRequest(
    article=enriched_article,
    cover_image_base64=cover_image_base64,
    cover_image_filename=cover_image_filename,
    slug=None,  # Auto-generato
    position="normal"
)

publish_result = await publish_article(publish_request)

if publish_result.success:
    # Aggiorna staging data con URL reale
    data["published_url"] = publish_result.article_url
    data["github_commit_sha"] = publish_result.commit_sha
    data["published_at"] = datetime.utcnow().isoformat()
    data["status"] = "published"
else:
    # Gestisci errore pubblicazione
    logger.error(f"Failed to publish to GitHub/Vercel: {publish_result.error}")
    raise HTTPException(status_code=500, detail="Failed to publish article")
```

---

## 📋 PIANO IMPLEMENTAZIONE CORRETTO (9 STEP)

### STEP 1: Includere Preview HTML nel Payload

**File:** `apps/bali-intel-scraper/scripts/article_deep_enricher.py`

**Modifica:** Aggiungere `preview_html` e `preview_url` al payload

### STEP 2: Backend Salva Preview HTML

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Modifica:** Salvare preview HTML in `data/staging/{type}/previews/{item_id}.html`

### STEP 3: Backend - Endpoint Editing Articolo

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Nuovo endpoint:** `PUT /api/intel/staging/{type}/{item_id}`

### STEP 4: Backend - Endpoint Upload Cover Image

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Nuovo endpoint:** `POST /api/intel/staging/{type}/{item_id}/cover`

### STEP 5: Backend - Funzione Conversione Staging → EnrichedArticle

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Nuova funzione:** `convert_staging_to_enriched_article(staging_data: dict) -> EnrichedArticle`

### STEP 6: Backend - Modificare Pubblicazione (CRITICO)

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Modifiche a `publish_staging_item()`:**

1. **❌ RIMUOVERE:** Ingest to Qdrant (NON serve per articoli blog)
2. **✅ MANTENERE:** Register in anti-duplicate system (per evitare duplicati)
3. **✅ AGGIUNGERE:** Convert staging → EnrichedArticle
4. **✅ AGGIUNGERE:** Publish to GitHub/Vercel → balizero.com
5. **✅ AGGIUNGERE:** Update staging file con URL reale

### STEP 7: Frontend - API Client Aggiornato

**File:** `apps/mouth/src/lib/api/intelligence.api.ts`

**Nuove funzioni:** `editItem()`, `uploadCoverImage()`

### STEP 8: Frontend - Componenti Editor e Uploader

**File:**

- `apps/mouth/src/app/(workspace)/intelligence/news-room/components/ArticleEditor.tsx`
- `apps/mouth/src/app/(workspace)/intelligence/news-room/components/CoverImageUploader.tsx`

### STEP 9: Integrazione nella Dashboard

**File:** `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`

**Modifiche:** Integrare editor e uploader

---

## 🎯 FLUSSO FINALE CORRETTO

```
1. Intel Scraper → invia articolo (con preview_html) SENZA cover_image
2. Backend → salva in staging (data/staging/news/{item_id}.json)
3. Frontend → mostra nella News Room
4. Utente → visualizza preview HTML, modifica, aggiunge cover image
5. Utente → approva articolo
6. Backend → pubblica automaticamente:
   ✅ Registra in anti-duplicate system (per evitare duplicati)
   ✅ Converti staging → EnrichedArticle
   ✅ Pubblica su GitHub/Vercel → balizero.com
   ❌ NON salva in Qdrant knowledge base!
7. Articolo appare su https://balizero.com/{category}/{slug}
```

---

## ⚠️ IMPORTANTE

**Gli articoli dell'Intel Scraper sono ARTICOLI DI BLOG/NEWS pubblici.**

**NON sono conoscenza legale e NON devono essere nella knowledge base Qdrant.**

**Devono essere pubblicati SOLO su GitHub/Vercel → balizero.com come articoli di blog.**

---

**Status:** ✅ PIANO CORRETTO - PRONTO PER IMPLEMENTAZIONE  
**Next:** Attendere approvazione utente prima di iniziare implementazione
