# Soluzione RAG: News come Contesto Umano per Conoscenza Legale

**Purpose:** Soluzione finale per integrare news come contesto umano nella conoscenza legale  
**Date:** 2026-01-24  
**Status:** ✅ SOLUZIONE FINALE

---

## 🎯 FILOSOFIA

**Le news NON si nascondono, anzi arricchiscono la conoscenza legale!**

**Approccio:**

- ✅ News vengono mostrate insieme alla conoscenza legale quando rilevanti
- ✅ Rendono il RAG più umano: legale + contesto attualità
- ✅ MA devono essere chiaramente marcate come "news dai media" e NON "conferma legale"
- ✅ Il RAG deve sempre specificare la distinzione nella risposta

**Esempio:**

```
"Per ottenere un KITAS investitore servono:
- Requisiti legali: [conoscenza legale da visa_oracle]
- Contesto attuale: [news recenti da bali_intel_bali_news]
  ⚠️ Nota: Le news sono informazioni dai media, non conferma legale ufficiale"
```

---

## 📊 COLLECTION E METADATA

### Collection per News

**Collection:** `"bali_intel_bali_news"` ✅ ESISTE GIÀ!

**Usata per:** Articoli di attualità/news dall'Intel Scraper

### Metadata Schema

**Per articoli news:**

```python
metadata = {
    # Identificazione
    "title": title,
    "content": content,
    "source_url": source_url,
    "item_id": item_id,

    # Tipo contenuto (CRITICO per RAG)
    "content_type": "news",  # Esplicito: è news, non conoscenza legale
    "knowledge_type": "current_events",  # Esplicito: attualità
    "is_authoritative": False,  # Esplicito: NON è source of truth legale
    "source_reliability": "medium",  # News hanno reliability media
    "source_category": "media",  # NUOVO: categoria fonte (media, official, etc.)

    # Categoria
    "category": category,
    "intel_type": intel_type,  # "news"

    # Timestamp
    "published_at": published_at,
    "ingested_at": ingested_at,

    # Context
    "detection_type": detection_type,
    "ingested_via": "telegram_voting",
}
```

**Per conoscenza legale:**

```python
metadata = {
    # ... altri campi ...

    "content_type": "legal_knowledge",  # Esplicito: conoscenza legale
    "knowledge_type": "legal_framework",  # Esplicito: framework legale
    "is_authoritative": True,  # Esplicito: È source of truth legale
    "source_reliability": "high",  # Conoscenza legale ha reliability alta
    "source_category": "official",  # Fonte ufficiale
}
```

---

## 🔧 MODIFICHE NECESSARIE

### STEP 1: Modificare Ingest per Aggiungere Metadata Espliciti

**File:** `apps/backend-rag/backend/app/routers/telegram.py`

**Funzione:** `ingest_intel_to_qdrant()`

**Modifiche:**

```python
# Determinare tipo contenuto
if intel_type == "news":
    content_type = "news"
    knowledge_type = "current_events"
    is_authoritative = False
    source_reliability = "medium"
    source_category = "media"
elif intel_type == "visa":
    # Visa può essere sia legale che news
    # Analizza categoria per determinare
    category_lower = category.lower()
    if any(kw in category_lower for kw in ["regulation", "law", "requirement", "procedure"]):
        content_type = "legal_knowledge"
        knowledge_type = "legal_framework"
        is_authoritative = True
        source_reliability = "high"
        source_category = "official"
    else:
        content_type = "news"
        knowledge_type = "current_events"
        is_authoritative = False
        source_reliability = "medium"
        source_category = "media"

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
    "is_authoritative": is_authoritative,  # False per news, True per legale
    "source_reliability": source_reliability,  # "medium" per news, "high" per legale
    "source_category": source_category,  # "media" per news, "official" per legale

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

# Aggiungi metadata aggiuntivi da staging file
for key in ["detected_at", "relevance_score", "category"]:
    if key in data:
        metadata[key] = data[key]
```

### STEP 2: Modificare RAG per Mostrare News con Disclaimers

**File:** `apps/backend-rag/backend/services/rag/agentic/orchestrator.py`

**Modifiche alla formattazione risposta:**

```python
def format_rag_response_with_context(
    results: list,
    query: str,
    include_news: bool = True  # NUOVO: includere news come contesto
) -> str:
    """
    Formatta risposta RAG con news come contesto umano.

    Strategia:
    - Mostra conoscenza legale (source of truth)
    - Aggiunge news rilevanti come contesto
    - Specifica chiaramente che news sono "dai media" e NON "conferma legale"
    """
    # Separa risultati legali e news
    legal_results = [
        r for r in results
        if r.get("metadata", {}).get("is_authoritative") == True
    ]
    news_results = [
        r for r in results
        if r.get("metadata", {}).get("content_type") == "news"
    ]

    # Formatta conoscenza legale
    legal_section = format_legal_knowledge(legal_results)

    # Formatta news come contesto (se rilevanti e include_news=True)
    news_section = ""
    if include_news and news_results:
        news_section = format_news_context(news_results)

    # Combina risposta
    response = legal_section

    if news_section:
        response += "\n\n---\n\n"
        response += "📰 **Contesto Attuale (News dai Media):**\n\n"
        response += news_section
        response += "\n\n⚠️ **IMPORTANTE:** Le informazioni sopra sono news dai media e rappresentano attualità, non conferma legale ufficiale. Per informazioni legali ufficiali e aggiornate, consulta sempre le fonti autoritative."

    return response

def format_legal_knowledge(results: list) -> str:
    """Formatta conoscenza legale (source of truth)."""
    if not results:
        return "Informazioni legali non disponibili."

    formatted = []
    for result in results:
        title = result.get("metadata", {}).get("title", "Untitled")
        content = result.get("content", "")
        source = result.get("metadata", {}).get("source_category", "official")

        formatted.append(f"**{title}**\n{content}\n*Fonte: {source}*")

    return "\n\n".join(formatted)

def format_news_context(results: list) -> str:
    """Formatta news come contesto umano."""
    if not results:
        return ""

    formatted = []
    for result in results:
        title = result.get("metadata", {}).get("title", "Untitled")
        content = result.get("content", "")[:500]  # Limita lunghezza
        source_url = result.get("metadata", {}).get("source_url", "")
        published_at = result.get("metadata", {}).get("published_at", "")

        formatted.append(
            f"• **{title}** ({published_at[:10] if published_at else 'Data sconosciuta'})\n"
            f"  {content}...\n"
            f"  *Fonte media: {source_url}*"
        )

    return "\n\n".join(formatted)
```

### STEP 3: Modificare Query Processing per Includere News

**File:** `apps/backend-rag/backend/services/rag/agentic/orchestrator.py`

**Modifiche al process_query:**

```python
async def process_query_core(
    self,
    query: str,
    user_id: str | None = None,
    conversation_history: list[dict] | None = None,
    start_time: float | None = None,
    session_id: str | None = None,
    tool_execution_counter: dict = None,
) -> CoreResult:
    """
    Process query con news come contesto umano.
    """
    # ... existing code ...

    # Step 1: Cerca conoscenza legale (source of truth)
    legal_filter = {
        "must": [
            {"key": "is_authoritative", "match": {"value": True}},
            {"key": "content_type", "match": {"value": "legal_knowledge"}}
        ]
    }

    legal_results = await self.retriever.search(
        query=query,
        collections=["visa_oracle", "kbli_unified", "tax_genius", "legal_unified"],
        filter=legal_filter,
        limit=5
    )

    # Step 2: Cerca news rilevanti come contesto (se query è rilevante)
    news_relevant = is_news_relevant_for_query(query, legal_results)

    news_results = []
    if news_relevant:
        news_filter = {
            "must": [
                {"key": "content_type", "match": {"value": "news"}},
                {"key": "knowledge_type", "match": {"value": "current_events"}}
            ]
        }

        news_results = await self.retriever.search(
            query=query,
            collections=["bali_intel_bali_news"],
            filter=news_filter,
            limit=3  # Massimo 3 news come contesto
        )

    # Step 3: Formatta risposta con legale + news
    answer = format_rag_response_with_context(
        results=legal_results + news_results,
        query=query,
        include_news=True
    )

    # ... rest of existing code ...

    return CoreResult(
        answer=answer,
        sources=legal_results + news_results,
        metadata={
            "legal_sources_count": len(legal_results),
            "news_sources_count": len(news_results),
            "has_news_context": len(news_results) > 0
        }
    )

def is_news_relevant_for_query(query: str, legal_results: list) -> bool:
    """
    Determina se le news sono rilevanti per la query.

    News sono rilevanti se:
    - Query riguarda argomenti che possono avere aggiornamenti recenti
    - Legal results esistono (altrimenti non ha senso aggiungere contesto)
    """
    if not legal_results:
        return False  # Se non c'è conoscenza legale, non aggiungere news

    # Keywords che indicano che news potrebbero essere rilevanti
    news_relevant_keywords = [
        "visa", "kitas", "kitap", "immigration", "permit",
        "business", "company", "tax", "property", "investment"
    ]

    query_lower = query.lower()
    return any(kw in query_lower for kw in news_relevant_keywords)
```

### STEP 4: Modificare Prompt Builder per Includere Istruzioni News

**File:** `apps/backend-rag/backend/services/rag/agentic/prompt_builder.py`

**Aggiungere istruzioni al system prompt:**

```python
def build_system_prompt_with_news_context(self, ...) -> str:
    """
    Build system prompt con istruzioni per gestire news come contesto.
    """
    base_prompt = self.build_system_prompt(...)

    news_instructions = """

## 📰 GESTIONE NEWS E CONTESTO ATTUALITÀ

Quando includi informazioni da articoli di news/attualità:

1. **Distingui sempre tra conoscenza legale e news:**
   - Conoscenza legale = Source of truth ufficiale (is_authoritative: true)
   - News = Informazioni dai media (is_authoritative: false, source_category: "media")

2. **Usa news come contesto umano:**
   - Mostra prima la conoscenza legale (source of truth)
   - Aggiungi news rilevanti come contesto attuale
   - Specifica sempre che le news sono "dai media" e NON "conferma legale"

3. **Formato risposta:**
```

[Conoscenza Legale - Source of Truth]

---

📰 Contesto Attuale (News dai Media):
[News rilevanti]

⚠️ IMPORTANTE: Le informazioni sopra sono news dai media e rappresentano attualità,
non conferma legale ufficiale. Per informazioni legali ufficiali e aggiornate,
consulta sempre le fonti autoritative.

```

4. **Rendi umano:**
- Combina conoscenza legale + opinioni pubbliche/attualità
- Mostra come le news influenzano il contesto legale
- Spiega differenze tra legge e attualità quando rilevante
"""

 return base_prompt + news_instructions
```

---

## 📋 PIANO IMPLEMENTAZIONE COMPLETO

### Backend Changes

1. **Modificare `ingest_intel_to_qdrant()`:**
   - Aggiungere metadata `content_type="news"`, `knowledge_type="current_events"`, `is_authoritative=False`, `source_category="media"`
   - Per news: sempre questi valori
   - Per visa legale: `content_type="legal_knowledge"`, `is_authoritative=True`, `source_category="official"`

2. **Modificare `publish_staging_item()`:**
   - Mantenere ingest to Qdrant per news (collection `bali_intel_bali_news`)
   - Aggiungere pubblicazione GitHub/Vercel
   - Aggiornare metadata con tipo contenuto

3. **Modificare RAG Orchestrator:**
   - Cercare sia conoscenza legale che news rilevanti
   - Formattare risposta con legale + news come contesto
   - Aggiungere disclaimer chiaro che news sono "dai media" e NON "conferma legale"

4. **Modificare Prompt Builder:**
   - Aggiungere istruzioni per gestire news come contesto umano
   - Istruire LLM a distinguere tra legale e news
   - Istruire LLM a rendere umano combinando legale + attualità

### Testing

- [ ] Test ingest news con metadata corretti
- [ ] Test RAG mostra news insieme a conoscenza legale
- [ ] Test disclaimer chiaro che news sono "dai media"
- [ ] Test risposta umana: legale + contesto attualità

---

## 🎯 RISULTATO FINALE

**Articoli news:**

- ✅ Salvati in Qdrant (collection `bali_intel_bali_news`)
- ✅ Metadata: `content_type="news"`, `is_authoritative=False`, `source_category="media"`
- ✅ Pubblicati su GitHub/Vercel → balizero.com
- ✅ RAG li mostra insieme alla conoscenza legale quando rilevanti
- ✅ Chiaramente marcati come "news dai media" e NON "conferma legale"
- ✅ Rendono il RAG più umano: legale + contesto attualità

**Conoscenza legale:**

- ✅ Rimane in collections dedicate (`visa_oracle`, `kbli_unified`, etc.)
- ✅ Metadata: `content_type="legal_knowledge"`, `is_authoritative=True`, `source_category="official"`
- ✅ Source of truth protetta
- ✅ Mostrata prima nella risposta, poi news come contesto

**Risposta RAG:**

- ✅ Mostra conoscenza legale (source of truth)
- ✅ Aggiunge news rilevanti come contesto umano
- ✅ Specifica chiaramente distinzione: "news dai media" vs "conferma legale"
- ✅ Rende umano: legale + opinioni pubbliche/attualità

---

**Status:** ✅ SOLUZIONE FINALE - PRONTO PER IMPLEMENTAZIONE  
**Next:** Attendere approvazione utente prima di iniziare implementazione
