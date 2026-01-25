# Analisi RAG: Separazione News vs Conoscenza Legale

**Purpose:** Analizzare come separare articoli di attualità/news dalla conoscenza legale nel RAG  
**Date:** 2026-01-24  
**Status:** 🔍 ANALISI IN CORSO

---

## 🎯 OBIETTIVO

**Problema:** Come inserire articoli di attualità/news in Qdrant senza danneggiare la source of truth della conoscenza legale?

**Requisiti:**

1. ✅ Articoli news vanno in Qdrant (collection dedicata)
2. ✅ RAG deve distinguere tra "attualità" e "leggi/conoscenza legale"
3. ✅ Source of truth legale NON deve essere compromessa
4. ✅ RAG deve sapere quando usare news vs conoscenza legale

---

## 📊 STATO ATTUALE

### Collection Esistenti

**File:** `apps/backend-rag/backend/app/core/constants.py`

**INTEL_COLLECTIONS:**

```python
COLLECTIONS = {
    "visa": "visa_oracle",
    "news": "bali_intel_bali_news",  # ✅ Esiste già!
    "immigration": "bali_intel_immigration",
    "bkpm_tax": "bali_intel_bkpm_tax",
    "realestate": "bali_intel_realestate",
    "events": "bali_intel_events",
    "social": "bali_intel_social",
    "competitors": "bali_intel_competitors",
    "bali_news": "bali_intel_bali_news",
    "roundup": "bali_intel_roundup",
}
```

**Collection per News:** `"bali_intel_bali_news"` ✅ ESISTE GIÀ!

### Ingest Attuale

**File:** `apps/backend-rag/backend/app/routers/telegram.py`

**Funzione:** `ingest_intel_to_qdrant()`

**Collection usata:**

```python
collection_name = "visa_oracle" if intel_type == "visa" else "bali_intel_bali_news"
```

**Metadata attuale:**

```python
metadata = {
    "title": title,
    "content": content,
    "source_url": source_url,
    "detection_type": detection_type,
    "intel_type": intel_type,  # "visa" o "news"
    "ingested_at": dt.utcnow().isoformat(),
    "ingested_via": "telegram_voting",
    "item_id": item_id,
}
```

**❌ PROBLEMA:** Metadata NON distingue tra "attualità" e "conoscenza legale"!

---

## 🔍 ANALISI RAG ATTUALE

### Query Router

**File:** `apps/backend-rag/backend/services/routing/query_router.py`

**Come funziona:**

- Analizza query per determinare collection da usare
- Usa keyword matching e domain detection
- Non distingue esplicitamente tra "attualità" e "conoscenza legale"

### Collection Priority

**File:** `apps/backend-rag/backend/services/routing/priority_override.py`

**Collections prioritarie:**

- `visa_oracle`
- `kbli_eye`
- `tax_genius`
- `legal_architect`

**❌ PROBLEMA:** `bali_intel_bali_news` NON è nelle collections prioritarie!

---

## 🎯 BEST PRACTICES 2026

### 1. Metadata Schema per Distinguere Tipo Contenuto

**Best Practice:** Usare metadata espliciti per distinguere tipo di contenuto

**Schema proposto:**

```python
metadata = {
    # Identificazione documento
    "document_id": item_id,
    "title": title,
    "content": content,
    "source_url": source_url,

    # Tipo contenuto (CRITICO)
    "content_type": "news" | "legal_knowledge" | "regulation" | "guidance",
    "knowledge_type": "current_events" | "legal_framework" | "procedural",
    "is_authoritative": bool,  # True per leggi, False per news
    "source_reliability": "high" | "medium" | "low",

    # Categoria
    "category": category,
    "intel_type": intel_type,

    # Timestamp
    "published_at": published_at,
    "ingested_at": ingested_at,

    # Context
    "detection_type": detection_type,
    "ingested_via": "telegram_voting" | "manual" | "scraper",
}
```

### 2. Collection Separation Strategy

**Best Practice:** Separare collections per tipo di contenuto

**Collections legali (source of truth):**

- `visa_oracle` → Conoscenza legale su visti
- `kbli_unified` → Conoscenza legale su KBLI
- `tax_genius` → Conoscenza legale su tasse
- `legal_unified` → Conoscenza legale generale

**Collections news/attualità:**

- `bali_intel_bali_news` → Articoli di attualità/news
- `bali_intel_immigration` → News su immigrazione
- `bali_intel_bkpm_tax` → News su BKPM/tasse
- etc.

### 3. RAG Routing Strategy

**Best Practice:** RAG deve decidere quale collection usare basandosi su:

1. Tipo di query (richiede conoscenza legale o attualità?)
2. Context della conversazione
3. Metadata dei documenti

**Strategia proposta:**

```python
# Query analysis
if query_requires_legal_knowledge(query):
    # Usa collections legali (source of truth)
    collections = ["visa_oracle", "kbli_unified", "tax_genius", "legal_unified"]
    priority = "legal_knowledge"
elif query_requires_current_events(query):
    # Usa collections news/attualità
    collections = ["bali_intel_bali_news", "bali_intel_immigration"]
    priority = "current_events"
else:
    # Hybrid: prima legale, poi news come contesto
    collections = ["visa_oracle", "kbli_unified", "bali_intel_bali_news"]
    priority = "hybrid"
```

### 4. Source of Truth Protection

**Best Practice:** Proteggere source of truth con:

1. Metadata `is_authoritative: true` per documenti legali
2. Priority boost per collections legali
3. Explicit filtering per escludere news quando serve conoscenza legale
4. Warning quando si usa news invece di conoscenza legale

**Implementazione:**

```python
# Quando serve conoscenza legale
filter = {
    "must": [
        {"key": "is_authoritative", "match": {"value": True}},
        {"key": "content_type", "match": {"value": "legal_knowledge"}}
    ]
}

# Quando serve attualità
filter = {
    "must": [
        {"key": "content_type", "match": {"value": "news"}},
        {"key": "knowledge_type", "match": {"value": "current_events"}}
    ]
}
```

---

## 🔧 SOLUZIONE PROPOSTA

### Step 1: Modificare Metadata per News

**File:** `apps/backend-rag/backend/app/routers/telegram.py`

**Funzione:** `ingest_intel_to_qdrant()`

**Modifiche metadata:**

```python
metadata = {
    # Identificazione
    "title": title,
    "content": content,
    "source_url": source_url,
    "item_id": item_id,

    # Tipo contenuto (NUOVO)
    "content_type": "news",  # Esplicito: è news, non conoscenza legale
    "knowledge_type": "current_events",  # Esplicito: attualità
    "is_authoritative": False,  # Esplicito: NON è source of truth legale
    "source_reliability": "medium",  # News hanno reliability media

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

### Step 2: Modificare Query Router per Distinguere

**File:** `apps/backend-rag/backend/services/routing/query_router.py`

**Aggiungere logica:**

```python
def determine_content_type_needed(query: str, context: dict) -> str:
    """
    Determina se la query richiede conoscenza legale o attualità.

    Returns:
        "legal_knowledge" | "current_events" | "hybrid"
    """
    # Keywords per conoscenza legale
    legal_keywords = [
        "law", "regulation", "requirement", "procedure", "how to",
        "what is", "definition", "legal", "permit", "visa type"
    ]

    # Keywords per attualità
    news_keywords = [
        "latest", "recent", "update", "news", "happened", "announced",
        "changed", "new policy", "recently"
    ]

    query_lower = query.lower()

    legal_score = sum(1 for kw in legal_keywords if kw in query_lower)
    news_score = sum(1 for kw in news_keywords if kw in query_lower)

    if legal_score > news_score:
        return "legal_knowledge"
    elif news_score > legal_score:
        return "current_events"
    else:
        return "hybrid"
```

### Step 3: Modificare Search per Usare Filter

**File:** `apps/backend-rag/backend/core/qdrant_db.py`

**Aggiungere filter per tipo contenuto:**

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
        return {
            "must": [
                {"key": "is_authoritative", "match": {"value": True}},
                {"key": "content_type", "match": {"value": "legal_knowledge"}}
            ]
        }
    elif content_type == "current_events":
        return {
            "must": [
                {"key": "content_type", "match": {"value": "news"}},
                {"key": "knowledge_type", "match": {"value": "current_events"}}
            ]
        }
    else:  # hybrid
        return {}  # Nessun filter, cerca ovunque
```

### Step 4: Aggiungere Warning nel RAG

**File:** `apps/backend-rag/backend/services/rag/agentic/orchestrator.py`

**Aggiungere warning quando si usa news invece di conoscenza legale:**

```python
def format_rag_response(results: list, content_type: str) -> str:
    """
    Formatta risposta RAG con warning se necessario.
    """
    response = format_results(results)

    # Se query richiede conoscenza legale ma risultati sono news
    if content_type == "legal_knowledge":
        news_results = [r for r in results if r.get("content_type") == "news"]
        if news_results:
            warning = "\n\n⚠️ **ATTENZIONE:** I risultati includono articoli di attualità. Per informazioni legali ufficiali, consulta le fonti autoritative."
            response += warning

    return response
```

---

## 📋 CHECKLIST IMPLEMENTAZIONE

### Backend Changes

- [ ] Modificare `ingest_intel_to_qdrant()` per aggiungere metadata `content_type`, `knowledge_type`, `is_authoritative`
- [ ] Modificare `publish_staging_item()` per usare collection `bali_intel_bali_news` per news
- [ ] Modificare query router per distinguere tra "legal_knowledge" e "current_events"
- [ ] Aggiungere filter per tipo contenuto nelle ricerche Qdrant
- [ ] Aggiungere warning quando si usa news invece di conoscenza legale

### Testing

- [ ] Test ingest news con metadata corretti
- [ ] Test query routing per distinguere tipo contenuto
- [ ] Test filter per escludere news quando serve conoscenza legale
- [ ] Test warning quando si usa news invece di conoscenza legale

---

**Status:** 🔍 ANALISI IN CORSO  
**Next:** Verificare implementazione attuale e proporre modifiche dettagliate
