# Soluzione RAG: Separazione News vs Conoscenza Legale

**Purpose:** Soluzione completa per separare articoli news dalla conoscenza legale nel RAG  
**Date:** 2026-01-24  
**Status:** ✅ SOLUZIONE COMPLETA

---

## 🎯 PROBLEMA

**Come inserire articoli di attualità/news in Qdrant senza danneggiare la source of truth della conoscenza legale?**

**Requisiti:**

1. ✅ Articoli news vanno in Qdrant (collection `bali_intel_bali_news`)
2. ✅ RAG deve distinguere tra "attualità" e "leggi/conoscenza legale"
3. ✅ Source of truth legale NON deve essere compromessa
4. ✅ RAG deve sapere quando usare news vs conoscenza legale

---

## 📊 STATO ATTUALE

### Collection Esistente

**Collection per News:** `"bali_intel_bali_news"` ✅ ESISTE GIÀ!

**Definita in:** `apps/backend-rag/backend/app/core/constants.py`

```python
INTEL_COLLECTIONS = {
    "news": "bali_intel_bali_news",
    ...
}
```

### Ingest Attuale

**File:** `apps/backend-rag/backend/app/routers/telegram.py`

**Funzione:** `ingest_intel_to_qdrant()`

**Collection usata:**

```python
collection_name = "visa_oracle" if intel_type == "visa" else "bali_intel_bali_news"
```

**Metadata attuale (INCOMPLETO):**

```python
metadata = {
    "title": title,
    "content": content,
    "source_url": source_url,
    "intel_type": intel_type,  # "visa" o "news"
    "ingested_at": dt.utcnow().isoformat(),
    # ❌ MANCA: content_type, knowledge_type, is_authoritative
}
```

---

## 🎯 BEST PRACTICES 2026

### 1. Metadata Schema Esplicito

**Best Practice:** Usare metadata espliciti per distinguere tipo di contenuto

**Schema proposto:**

```python
metadata = {
    # Identificazione documento
    "document_id": item_id,
    "title": title,
    "content": content,
    "source_url": source_url,

    # Tipo contenuto (CRITICO per RAG)
    "content_type": "news" | "legal_knowledge" | "regulation" | "guidance",
    "knowledge_type": "current_events" | "legal_framework" | "procedural",
    "is_authoritative": bool,  # True per leggi/ufficiali, False per news
    "source_reliability": "high" | "medium" | "low",

    # Categoria
    "category": category,
    "intel_type": intel_type,

    # Timestamp
    "published_at": published_at,
    "ingested_at": ingested_at,
}
```

### 2. Collection Separation

**Collections legali (source of truth):**

- `visa_oracle` → Conoscenza legale su visti (is_authoritative: true)
- `kbli_unified` → Conoscenza legale su KBLI (is_authoritative: true)
- `tax_genius` → Conoscenza legale su tasse (is_authoritative: true)
- `legal_unified` → Conoscenza legale generale (is_authoritative: true)

**Collections news/attualità:**

- `bali_intel_bali_news` → Articoli di attualità/news (is_authoritative: false)
- `bali_intel_immigration` → News su immigrazione (is_authoritative: false)
- etc.

### 3. RAG Routing Intelligente

**Best Practice:** RAG deve decidere quale collection usare basandosi su:

1. Tipo di query (richiede conoscenza legale o attualità?)
2. Context della conversazione
3. Metadata dei documenti

**Strategia:**

- Query su "leggi", "requisiti", "procedure" → Collections legali
- Query su "ultime notizie", "aggiornamenti", "cambiamenti recenti" → Collections news
- Query generiche → Hybrid (prima legale, poi news come contesto)

### 4. Source of Truth Protection

**Best Practice:** Proteggere source of truth con:

1. Metadata `is_authoritative: true` per documenti legali
2. Priority boost per collections legali nel routing
3. Explicit filtering per escludere news quando serve conoscenza legale
4. Warning quando si usa news invece di conoscenza legale

---

## 🔧 SOLUZIONE IMPLEMENTAZIONE

### STEP 1: Modificare Ingest per Aggiungere Metadata

**File:** `apps/backend-rag/backend/app/routers/telegram.py`

**Funzione:** `ingest_intel_to_qdrant()`

**Modifiche:**

```python
# Determinare tipo contenuto
if intel_type == "visa":
    # Visa può essere sia legale che news
    # Se category contiene "regulation", "law", "requirement" → legale
    # Altrimenti → news
    if any(kw in category.lower() for kw in ["regulation", "law", "requirement", "procedure"]):
        content_type = "legal_knowledge"
        knowledge_type = "legal_framework"
        is_authoritative = True
    else:
        content_type = "news"
        knowledge_type = "current_events"
        is_authoritative = False
else:  # news
    content_type = "news"
    knowledge_type = "current_events"
    is_authoritative = False

# Metadata completo
metadata = {
    # Identificazione
    "title": title,
    "content": content,
    "source_url": source_url,
    "item_id": item_id,

    # Tipo contenuto (NUOVO - CRITICO)
    "content_type": content_type,  # "news" o "legal_knowledge"
    "knowledge_type": knowledge_type,  # "current_events" o "legal_framework"
    "is_authoritative": is_authoritative,  # True per legale, False per news
    "source_reliability": "high" if is_authoritative else "medium",

    # Categoria
    "category": category,
    "intel_type": intel_type,

    # Timestamp
    "published_at": published_at or dt.utcnow().isoformat(),
    "ingested_at": dt.utcnow().isoformat(),

    # Context
    "detection_type": detection_type,
    "ingested_via": "telegram_voting",
}
```

### STEP 2: Modificare Publish per Usare Collection News

**File:** `apps/backend-rag/backend/app/routers/intel.py`

**Funzione:** `publish_staging_item()`

**Modifiche:**

```python
# Per articoli news, usare collection dedicata
if type == "news":
    # Ingest to Qdrant (collection news dedicata)
    ingestion_success = await ingest_intel_to_qdrant(item_id, type)
    # Questo salverà in "bali_intel_bali_news" con metadata corretti

    # Poi pubblica su GitHub/Vercel
    enriched_article = convert_staging_to_enriched_article(data)
    publish_result = await publish_article(PublishRequest(...))

    # Aggiorna staging
    data["published_url"] = publish_result.article_url
    data["published_at"] = datetime.utcnow().isoformat()
    data["status"] = "published"
```

### STEP 3: Modificare Query Router per Distinguere Tipo Contenuto

**File:** `apps/backend-rag/backend/services/routing/query_router.py`

**Aggiungere funzione:**

```python
def determine_content_type_needed(query: str, context: dict = None) -> str:
    """
    Determina se la query richiede conoscenza legale o attualità.

    Returns:
        "legal_knowledge" | "current_events" | "hybrid"
    """
    # Keywords per conoscenza legale
    legal_keywords = [
        "law", "regulation", "requirement", "procedure", "how to",
        "what is", "definition", "legal", "permit", "visa type",
        "kitas", "kitap", "requirement", "document", "application"
    ]

    # Keywords per attualità
    news_keywords = [
        "latest", "recent", "update", "news", "happened", "announced",
        "changed", "new policy", "recently", "today", "this week",
        "breaking", "update", "change"
    ]

    query_lower = query.lower()

    legal_score = sum(1 for kw in legal_keywords if kw in query_lower)
    news_score = sum(1 for kw in news_keywords if kw in query_lower)

    if legal_score > news_score and legal_score > 0:
        return "legal_knowledge"
    elif news_score > legal_score and news_score > 0:
        return "current_events"
    else:
        return "hybrid"
```

**Modificare routing:**

```python
def route_query(query: str, context: dict = None) -> str:
    """
    Route query to appropriate collection.
    """
    content_type = determine_content_type_needed(query, context)

    if content_type == "legal_knowledge":
        # Usa collections legali (source of truth)
        return route_to_legal_collection(query)
    elif content_type == "current_events":
        # Usa collections news
        return "bali_intel_bali_news"
    else:  # hybrid
        # Usa entrambe, ma priorità a legale
        return route_hybrid(query)
```

### STEP 4: Modificare Search per Usare Filter

**File:** `apps/backend-rag/backend/core/qdrant_db.py`

**Aggiungere funzione:**

```python
def build_content_type_filter(content_type: str) -> dict:
    """
    Build Qdrant filter per tipo contenuto.

    Args:
        content_type: "legal_knowledge" | "current_events" | "hybrid"

    Returns:
        Qdrant filter dict
    """
    if content_type == "legal_knowledge":
        # Solo conoscenza legale autoritativa
        return {
            "must": [
                {"key": "is_authoritative", "match": {"value": True}},
                {"key": "content_type", "match": {"value": "legal_knowledge"}}
            ]
        }
    elif content_type == "current_events":
        # Solo news/attualità
        return {
            "must": [
                {"key": "content_type", "match": {"value": "news"}},
                {"key": "knowledge_type", "match": {"value": "current_events"}}
            ]
        }
    else:  # hybrid
        return {}  # Nessun filter, cerca ovunque ma priorità a legale
```

**Modificare search:**

```python
async def search(
    self,
    query: str,
    limit: int = 10,
    content_type: str = "hybrid",  # NUOVO parametro
    **kwargs
):
    """
    Search with content type filtering.
    """
    # Build filter
    filter_dict = build_content_type_filter(content_type)

    # Search with filter
    results = await self.client.query(
        query_vector=embedding,
        limit=limit,
        filter=filter_dict if filter_dict else None,
        **kwargs
    )

    return results
```

### STEP 5: Aggiungere Warning nel RAG Response

**File:** `apps/backend-rag/backend/services/rag/agentic/orchestrator.py`

**Modificare response formatting:**

```python
def format_rag_response(
    results: list,
    content_type: str,
    query: str
) -> str:
    """
    Formatta risposta RAG con warning se necessario.
    """
    response = format_results(results)

    # Se query richiede conoscenza legale ma risultati includono news
    if content_type == "legal_knowledge":
        news_results = [r for r in results if r.get("metadata", {}).get("content_type") == "news"]
        if news_results:
            warning = (
                "\n\n⚠️ **ATTENZIONE:** I risultati includono articoli di attualità. "
                "Per informazioni legali ufficiali e aggiornate, consulta le fonti autoritative. "
                "Gli articoli di attualità possono contenere informazioni temporanee che potrebbero cambiare."
            )
            response += warning

    # Se query richiede attualità ma risultati includono solo legale
    elif content_type == "current_events":
        legal_results = [r for r in results if r.get("metadata", {}).get("is_authoritative") == True]
        if legal_results and len(news_results) == 0:
            info = (
                "\n\nℹ️ **NOTA:** I risultati mostrano conoscenza legale di base. "
                "Per le ultime notizie e aggiornamenti recenti, consulta gli articoli di attualità."
            )
            response += info

    return response
```

---

## 📋 PIANO IMPLEMENTAZIONE COMPLETO

### Backend Changes

1. **Modificare `ingest_intel_to_qdrant()`:**
   - Aggiungere metadata `content_type`, `knowledge_type`, `is_authoritative`
   - Per news: `content_type="news"`, `knowledge_type="current_events"`, `is_authoritative=False`
   - Per visa legale: `content_type="legal_knowledge"`, `knowledge_type="legal_framework"`, `is_authoritative=True`

2. **Modificare `publish_staging_item()`:**
   - Mantenere ingest to Qdrant per news (collection `bali_intel_bali_news`)
   - Aggiungere pubblicazione GitHub/Vercel
   - Aggiornare metadata con tipo contenuto

3. **Modificare Query Router:**
   - Aggiungere `determine_content_type_needed()`
   - Modificare routing per distinguere tipo contenuto
   - Priorità a collections legali quando serve conoscenza legale

4. **Modificare Qdrant Search:**
   - Aggiungere `build_content_type_filter()`
   - Modificare search per usare filter quando necessario
   - Priorità a risultati legali quando serve conoscenza legale

5. **Modificare RAG Orchestrator:**
   - Aggiungere warning quando si usa news invece di conoscenza legale
   - Formattare risposta con informazioni sul tipo contenuto

### Testing

- [ ] Test ingest news con metadata corretti (`content_type="news"`, `is_authoritative=False`)
- [ ] Test ingest visa legale con metadata corretti (`content_type="legal_knowledge"`, `is_authoritative=True`)
- [ ] Test query routing per distinguere tipo contenuto
- [ ] Test filter per escludere news quando serve conoscenza legale
- [ ] Test warning quando si usa news invece di conoscenza legale
- [ ] Test source of truth protection (solo legale quando richiesto)

---

## 🎯 RISULTATO FINALE

**Articoli news:**

- ✅ Salvati in Qdrant (collection `bali_intel_bali_news`)
- ✅ Metadata: `content_type="news"`, `knowledge_type="current_events"`, `is_authoritative=False`
- ✅ Pubblicati su GitHub/Vercel → balizero.com
- ✅ RAG li usa solo quando serve attualità
- ✅ NON danneggiano source of truth legale

**Conoscenza legale:**

- ✅ Rimane in collections dedicate (`visa_oracle`, `kbli_unified`, etc.)
- ✅ Metadata: `content_type="legal_knowledge"`, `is_authoritative=True`
- ✅ RAG le usa quando serve conoscenza legale
- ✅ Source of truth protetta

---

**Status:** ✅ SOLUZIONE COMPLETA - PRONTO PER IMPLEMENTAZIONE  
**Next:** Attendere approvazione utente prima di iniziare implementazione
