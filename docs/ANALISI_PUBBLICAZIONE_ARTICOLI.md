# Analisi Pubblicazione Articoli - Dove Vengono Pubblicati?

**Purpose:** Capire dove vengono pubblicati gli articoli dopo l'approvazione  
**Date:** 2026-01-24  
**Status:** 🔍 ANALISI IN CORSO

---

## 🎯 DOMANDA CHIAVE

**Utente approva articolo → Articolo viene pubblicato automaticamente → Ma DOVE?**

---

## 📊 FLUSSO ATTUALE PUBBLICAZIONE

### Endpoint Pubblicazione Intel

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Endpoint:** `POST /api/intel/staging/publish/{type}/{item_id}`

**Cosa fa attualmente:**

1. ✅ Ingest to Qdrant (knowledge base)
2. ✅ Register in anti-duplicate system
3. ✅ Update staging file with publish timestamp
4. ✅ Generate `published_url = f"https://balizero.com/{category}/{item_id}"`

**Problema identificato:**

- ❌ `published_url` è solo un URL generato, non significa che l'articolo sia effettivamente pubblicato
- ❌ Non viene chiamato `/api/articles/publish` che pubblica su GitHub → Vercel → balizero.com
- ❌ Articolo viene solo salvato in Qdrant (knowledge base), non pubblicato come articolo pubblico

---

## 🔍 SISTEMA PUBBLICAZIONE ESISTENTE

### Article Composer API

**File:** `apps/backend-rag/backend/app/routers/article_composer.py`

**Endpoint:** `POST /api/articles/publish`

**Cosa fa:**

1. ✅ Riceve `EnrichedArticle` con tutti i campi
2. ✅ Genera MDX format
3. ✅ Committa su GitHub (`Balizero1987/Teman2`)
4. ✅ Upload cover image su GitHub
5. ✅ Trigger Vercel deploy automatico
6. ✅ Articolo appare su `https://balizero.com/{category}/{slug}`

**Struttura dati richiesta:**

```python
class EnrichedArticle(BaseModel):
    title: str
    headline: str
    tldr: TLDRSection
    facts: str
    bali_zero_take: BaliZeroTake
    next_steps: NextSteps
    category: str
    priority: str
    relevance_score: int
    ai_summary: str
    ai_tags: list[str]
    suggested_components: list[str]
    cover_image: str | None = None
    source: str
    source_url: str | None
    enriched_at: str
```

---

## ❌ PROBLEMA IDENTIFICATO

### Flusso Attuale (INCOMPLETO)

```
1. Utente approva articolo nella News Room
   → Chiama: POST /api/intel/staging/publish/{type}/{id}

2. Backend pubblica articolo
   → Salva in Qdrant (knowledge base) ✅
   → Registra in anti-duplicate system ✅
   → Genera published_url ✅
   → ❌ NON pubblica su GitHub/Vercel
   → ❌ Articolo NON appare su balizero.com

3. Risultato
   → Articolo è solo nella knowledge base (Qdrant)
   → Articolo NON è pubblicato come articolo pubblico
   → URL generato non funziona
```

### Flusso Corretto (DA IMPLEMENTARE)

```
1. Utente approva articolo nella News Room
   → Chiama: POST /api/intel/staging/publish/{type}/{id}

2. Backend pubblica articolo
   → Salva in Qdrant (knowledge base) ✅
   → Registra in anti-duplicate system ✅
   → ❌ MANCA: Converti staging item → EnrichedArticle
   → ❌ MANCA: Chiama POST /api/articles/publish
   → ❌ MANCA: Pubblica su GitHub → Vercel → balizero.com

3. Risultato
   → Articolo nella knowledge base ✅
   → Articolo pubblicato su balizero.com ✅
   → URL funzionante ✅
```

---

## 🔧 SOLUZIONE PROPOSTA

### Modificare Endpoint Pubblicazione

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Endpoint:** `POST /api/intel/staging/publish/{type}/{item_id}`

**Modifiche necessarie:**

1. **Dopo ingest to Qdrant**, aggiungere:

   ```python
   # Step 4: Publish to GitHub/Vercel (balizero.com)
   from backend.app.routers.article_composer import publish_article

   # Convert staging item to EnrichedArticle format
   enriched_article = convert_staging_to_enriched_article(data)

   # Publish to GitHub/Vercel
   publish_result = await publish_article(enriched_article)

   # Update staging data with actual published URL
   data["published_url"] = publish_result.published_url
   data["published_at"] = datetime.utcnow().isoformat()
   ```

2. **Creare funzione di conversione:**
   ```python
   def convert_staging_to_enriched_article(staging_data: dict) -> EnrichedArticle:
       """Convert staging item to EnrichedArticle format"""
       # Parse content to extract sections
       # Generate tldr, bali_zero_take, etc.
       # Return EnrichedArticle
   ```

---

## 📋 CHECKLIST DA VERIFICARE

- [ ] Verificare se `publish_staging_item` chiama già `/api/articles/publish`
- [ ] Verificare struttura dati staging vs EnrichedArticle
- [ ] Verificare se serve conversione dati
- [ ] Verificare se cover_image è disponibile quando si pubblica
- [ ] Verificare se preview_html può essere usato per generare MDX

---

## 🎯 PROSSIMI PASSI

1. **Verificare codice attuale** di `publish_staging_item`
2. **Verificare** se esiste già integrazione con `/api/articles/publish`
3. **Creare funzione** di conversione staging → EnrichedArticle
4. **Integrare** pubblicazione GitHub/Vercel nel flusso
5. **Testare** pubblicazione end-to-end

---

**Status:** 🔍 ANALISI IN CORSO  
**Next:** Verificare codice attuale e identificare cosa manca
