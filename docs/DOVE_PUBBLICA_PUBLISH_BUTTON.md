# Dove Pubblica il Button "Publish" nella News Room

**Data:** 2026-01-24  
**Status:** ⚠️ PUBBLICAZIONE INCOMPLETA - MANCA GITHUB/VERCEL

---

## 🎯 DOMANDA

**Quando si clicca "Publish" nella News Room, dove viene pubblicato l'articolo?**

---

## 📊 STATO ATTUALE (INCOMPLETO)

### Cosa Fa Attualmente

**File:** `apps/backend-rag/backend/app/routers/intel.py`  
**Endpoint:** `POST /api/intel/staging/publish/{type}/{item_id}`

**Flusso attuale:**

1. ✅ **Ingest to Qdrant** (knowledge base)
   - Collection: `bali_intel_bali_news` (per news) o `visa_oracle` (per visa)
   - Articolo salvato nel vector database per RAG

2. ✅ **Register in Anti-Duplicate System**
   - Registrato in `ClaudeValidator` per evitare duplicati

3. ❌ **Genera URL Fittizio** (NON FUNZIONA)

   ```python
   published_url = f"https://balizero.com/{category}/{item_id}"
   ```

   - URL generato: `https://balizero.com/immigration/25e46a72449c`
   - **PROBLEMA:** Articolo NON esiste su balizero.com!
   - URL non funziona perché articolo non è stato pubblicato su GitHub/Vercel

4. ❌ **MANCA:** Pubblicazione su GitHub/Vercel → balizero.com

---

## ✅ DOVE DOVREBBE ESSERE PUBBLICATO

### Posizione Finale

**URL Pubblico:** `https://balizero.com/{category_folder}/{slug}`

**Esempi:**

- `https://balizero.com/immigration/indonesia-s-golden-visa-who-actually-qualifies`
- `https://balizero.com/property/bali-villa-developer-claims-32-rental-surge`
- `https://balizero.com/business/new-investment-opportunities-in-bali`

### Come Funziona la Pubblicazione Reale

**File:** `apps/backend-rag/backend/app/routers/article_composer.py`  
**Endpoint:** `POST /api/articles/publish`

**Flusso completo:**

1. **Riceve `EnrichedArticle`** (struttura complessa con sezioni)
2. **Genera slug** da headline: `generate_slug(headline)`
   - Esempio: `"Indonesia's Golden Visa: Who Actually Qualifies"` → `"indonesia-s-golden-visa-who-actually-qualifies"`
3. **Genera MDX content** con frontmatter e componenti React
4. **Salva su GitHub:**
   - MDX file: `apps/mouth/src/content/articles/{category_folder}/{slug}.mdx`
   - Cover image: `apps/mouth/public/static/news/{image_filename}` (se presente)
   - Repository: `Balizero1987/Teman2`
   - Branch: `main`
5. **Vercel Auto-Deploy:**
   - Vercel rileva commit su GitHub
   - Auto-deploy in ~1 minuto
   - Articolo disponibile su `https://balizero.com/{category_folder}/{slug}`

---

## ❌ PROBLEMA CRITICO

### Gap tra Staging e Pubblicazione

**Problema:**

- `publish_staging_item()` in `intel.py` NON chiama `publish_article()` da `article_composer.py`
- Articolo viene salvato solo in Qdrant (knowledge base)
- Articolo NON viene pubblicato come articolo pubblico su balizero.com

**Risultato:**

- ✅ Articolo disponibile per RAG (knowledge base)
- ❌ Articolo NON disponibile come articolo pubblico su balizero.com
- ❌ URL generato non funziona

---

## ✅ SOLUZIONE NECESSARIA

### Modificare `publish_staging_item()` per Includere Pubblicazione GitHub/Vercel

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Cosa aggiungere:**

```python
@router.post("/api/intel/staging/publish/{type}/{item_id}")
async def publish_staging_item(type: str, item_id: str):
    """
    Publish approved item:
    1. Ingest to Qdrant (knowledge base) ✅
    2. Register in anti-duplicate system ✅
    3. Publish to GitHub/Vercel → balizero.com ✅ NUOVO
    """
    # ... existing code ...

    # Step 1: Ingest to Qdrant ✅ (già implementato)
    ingestion_success = await ingest_intel_to_qdrant(item_id, type)

    # Step 2: Register in anti-duplicate system ✅ (già implementato)
    # ... existing code ...

    # Step 3: Publish to GitHub/Vercel → balizero.com ✅ NUOVO
    try:
        from backend.app.routers.article_composer import (
            publish_article,
            PublishRequest,
            EnrichedArticle,
        )

        # Convert staging item to EnrichedArticle
        enriched_article = convert_staging_to_enriched_article(data)

        # Prepare cover image if available
        cover_image_base64 = None
        cover_image_filename = None
        if data.get("cover_image"):
            # Read cover image file and convert to base64
            cover_path = staging_service.get_staging_dir(type) / data["cover_image"]
            if cover_path.exists():
                cover_image_base64 = base64.b64encode(cover_path.read_bytes()).decode("utf-8")
                cover_image_filename = cover_path.name

        # Create publish request
        publish_request = PublishRequest(
            article=enriched_article,
            cover_image_base64=cover_image_base64,
            cover_image_filename=cover_image_filename,
            position="normal",
        )

        # Publish to GitHub/Vercel
        publish_result = await publish_article(publish_request)

        if publish_result.success:
            # Update staging data with actual published URL
            data["published_url"] = publish_result.article_url
            data["github_commit_sha"] = publish_result.commit_sha
            data["mdx_path"] = publish_result.mdx_path

            logger.info(
                "✅ Article published to GitHub/Vercel",
                extra={
                    "type": type,
                    "item_id": item_id,
                    "published_url": publish_result.article_url,
                    "commit_sha": publish_result.commit_sha,
                },
            )
        else:
            logger.error(
                f"⚠️ Failed to publish to GitHub/Vercel: {publish_result.error}",
                extra={"type": type, "item_id": item_id},
            )
            # Non bloccare pubblicazione se GitHub fallisce
            # Articolo è già in Qdrant

    except Exception as e:
        logger.error(
            f"⚠️ Failed to publish to GitHub/Vercel: {e}",
            exc_info=True,
            extra={"type": type, "item_id": item_id},
        )
        # Non bloccare pubblicazione se GitHub fallisce
        # Articolo è già in Qdrant

    # ... rest of existing code ...
```

---

## 📋 FUNZIONE CONVERSIONE NECESSARIA

### `convert_staging_to_enriched_article()`

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Scopo:** Convertire staging item (markdown semplice) → EnrichedArticle (struttura complessa)

**Input (staging item):**

```python
{
    "title": "Indonesia's Golden Visa: Who Actually Qualifies",
    "content": "## Summary\n...\n## Facts\n...\n## Bali Zero Take\n...",
    "category": "immigration",
    "cover_image": "covers/25e46a72449c.jpg",
    "source_url": "https://...",
    "source_name": "Bali Intel Scraper",
    ...
}
```

**Output (EnrichedArticle):**

```python
EnrichedArticle(
    title="Indonesia's Golden Visa: Who Actually Qualifies",
    headline="Indonesia's Golden Visa: Who Actually Qualifies",
    tldr={
        "should_worry": "...",
        "what": "...",
        "who": "...",
        "when": "...",
        "risk_level": "..."
    },
    facts="...",
    bali_zero_take={
        "hidden_insight": "...",
        "our_analysis": "...",
        "our_advice": "..."
    },
    next_steps={
        "expat": [...],
        "investor": [...]
    },
    category="immigration",
    priority="high",
    relevance_score=85,
    ai_summary="...",
    ai_tags=["visa", "immigration", "golden-visa"],
    suggested_components=["InfoCard", "Checklist"],
    cover_image="/static/news/25e46a72449c.jpg",
    source="Bali Intel Scraper",
    source_url="https://...",
    enriched_at="2026-01-24T10:00:00Z"
)
```

**Implementazione:**

- Parsare markdown `content` per estrarre sezioni (`## Summary`, `## Facts`, etc.)
- Generare sezioni mancanti con valori di default
- Estrarre metadata da staging item

---

## 🎯 RISULTATO FINALE (Quando Implementato)

### Flusso Completo

1. **Utente clicca "Publish" nella News Room**
2. **Backend esegue:**
   - ✅ Ingest to Qdrant (knowledge base)
   - ✅ Register in anti-duplicate system
   - ✅ Convert staging → EnrichedArticle
   - ✅ Publish to GitHub (`Balizero1987/Teman2`)
   - ✅ Vercel auto-deploy (~1 minuto)
3. **Articolo disponibile su:**
   - ✅ Knowledge base (Qdrant) per RAG
   - ✅ Articolo pubblico su `https://balizero.com/{category}/{slug}`

### URL Finale

**Formato:** `https://balizero.com/{category_folder}/{slug}`

**Esempio:**

- Staging item ID: `25e46a72449c`
- Title: `"Indonesia's Golden Visa: Who Actually Qualifies"`
- Category: `immigration`
- **URL finale:** `https://balizero.com/immigration/indonesia-s-golden-visa-who-actually-qualifies`

---

## 📋 CHECKLIST IMPLEMENTAZIONE

### Backend Changes

- [ ] Creare funzione `convert_staging_to_enriched_article()`
- [ ] Modificare `publish_staging_item()` per chiamare `publish_article()`
- [ ] Gestire cover image (leggere file e convertire a base64)
- [ ] Gestire errori se pubblicazione GitHub fallisce
- [ ] Aggiornare `published_url` con URL reale da GitHub/Vercel

### Testing

- [ ] Test conversione staging → EnrichedArticle
- [ ] Test pubblicazione GitHub/Vercel
- [ ] Test URL finale funzionante su balizero.com
- [ ] Test gestione errori se GitHub fallisce

---

## ⚠️ IMPORTANTE

**Gestione Errori:**

- Se pubblicazione GitHub fallisce, articolo è già in Qdrant
- Log errore ma non bloccare pubblicazione
- Utente può riprovare pubblicazione manualmente se necessario

**Priorità:**

- 🔴 **ALTA:** Implementare pubblicazione GitHub/Vercel
- 🟡 **MEDIA:** Migliorare conversione staging → EnrichedArticle

---

**Status:** ⚠️ MANCA PUBBLICAZIONE GITHUB/VERCEL  
**Next:** Implementare `convert_staging_to_enriched_article()` e integrare `publish_article()` in `publish_staging_item()`
