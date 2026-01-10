# Qdrant Collections - Guida Completa

**Ultimo aggiornamento:** 2026-01-10

Questa guida documenta tutte le collezioni Qdrant del sistema Zantara/Nuzantara, come aggiungerle, e come fare troubleshooting.

---

## Panoramica Collezioni (Aggiornato 2026-01-10)

| Collezione | Documenti | Stato | Scopo |
|------------|-----------|-------|-------|
| `legal_unified_hybrid` | **47,959** | ✅ Attiva | Leggi indonesiane (PP, UU, Permen) - **PRIMARY** |
| `training_conversations_hybrid` | 3,525 | ✅ Attiva | Conversazioni training (hybrid format) |
| `training_conversations` | 2,898 | ✅ Attiva | Conversazioni training (standard) |
| `kbli_unified` | **2,818** | ✅ Attiva | Codici KBLI, classificazione business |
| `tax_genius_hybrid` | 332 | ✅ Attiva | PPh 21, PPN/VAT, tasse (hybrid format) |
| `tax_genius` | 332 | ✅ Attiva | PPh 21, PPN/VAT, tasse (standard) |
| `visa_oracle` | **82** | ✅ Attiva | Immigration, KITAS, KITAP, permessi |
| `bali_zero_pricing` | 70 | ✅ Attiva | Listino prezzi servizi Bali Zero |
| `balizero_news_history` | 6 | ✅ Attiva | Storia news Bali Zero |
| `collective_memories` | 0 | 📭 Vuota | Memoria collettiva team (da popolare) |

**⚠️ NOTA:** `bali_zero_team` non esiste più. Il sistema usa `TeamKnowledgeTool` che legge da PostgreSQL.

**Totale documenti:** **58,022** (verificato 2026-01-10)

---

## Configurazione Tecnica

```yaml
Vector Config:
  provider: OpenAI
  model: text-embedding-3-small
  dimensions: 1536
  distance: Cosine

Qdrant Cloud:
  url: https://nuzantara-qdrant.fly.dev
  api_key: QDRANT_API_KEY (env var)
```

---

## Query Router

Il file `backend/services/routing/query_router.py` determina quale collezione usare per ogni query.

### Keyword Routing (linee 550-600)

```python
# Tax queries → tax_genius
elif primary_domain == "tax":
    collection = "tax_genius"

# Visa queries → visa_oracle
elif primary_domain == "visa":
    collection = "visa_oracle"

# Legal queries → legal_unified_hybrid
# FIXED 2026-01-10: legal_unified doesn't exist, using legal_unified_hybrid
elif primary_domain == "legal":
    collection = "legal_unified_hybrid"
```

### Fallback Chains

Se una collezione non trova risultati, il sistema usa fallback chains definite in `fallback_manager.py`:

```python
FALLBACK_CHAINS = {
    "tax_genius": ["legal_unified_hybrid"],  # tax → legal
    "visa_oracle": ["legal_unified_hybrid"],  # visa → legal
    "kbli_unified": ["legal_unified_hybrid"], # kbli → legal
}
```

---

## Come Aggiungere una Nuova Collezione

### 1. Preparare i Documenti

Crea i documenti in formato Markdown in `training-data/`:

```
training-data/
├── tax/
│   ├── tax_016_pph21_individual_indonesian.md
│   └── tax_019_ppn_vat_full_cycle.md
├── visa/
│   └── visa_xxx_topic.md
└── nuova_categoria/
    └── documento.md
```

### 2. Creare Script di Ingestion

Usa `scripts/ingest_tax_genius.py` come template:

```python
"""
Nuova Collezione Ingestion Script
"""
import asyncio
from pathlib import Path
from core.chunker import TextChunker
from core.embeddings import create_embeddings_generator
from core.qdrant_db import QdrantClient

DOCUMENTS = [
    {
        "path": "training-data/categoria/documento.md",
        "title": "Titolo Documento",
        "category": "categoria",
        "tier": "A",
    },
]

async def ingest():
    chunker = TextChunker()
    embedder = create_embeddings_generator()
    qdrant = QdrantClient(collection_name="nuova_collezione")

    # Crea collezione se non esiste
    stats = await qdrant.get_collection_stats()
    if "error" in stats:
        await qdrant.create_collection(vector_size=1536, distance="Cosine")

    # Process documents...
    for doc in DOCUMENTS:
        content = Path(doc["path"]).read_text()
        chunks = chunker.semantic_chunk(content)
        embeddings = embedder.generate_embeddings([c["text"] for c in chunks])
        await qdrant.upsert_documents(chunks, embeddings, metadatas)

    await qdrant.close()

if __name__ == "__main__":
    asyncio.run(ingest())
```

### 3. Eseguire Ingestion

```bash
# Dry run (verifica senza inserire)
python -m scripts.ingest_nuova_collezione --dry-run

# Esegui (inserisce in Qdrant Cloud)
python -m scripts.ingest_nuova_collezione
```

### 4. Aggiornare Query Router

In `backend/services/routing/query_router.py`, aggiungi il routing:

```python
elif primary_domain == "nuova_categoria":
    collection = "nuova_collezione"
```

### 5. Aggiornare Collection Manager

In `backend/services/ingestion/collection_manager.py`:

```python
self.collection_definitions = {
    # ... existing ...
    "nuova_collezione": {"priority": "high", "doc_count": XXX},
}
```

### 6. Testare

```bash
# Test ricerca diretta
python3 -c "
import asyncio
from core.embeddings import create_embeddings_generator
from core.qdrant_db import QdrantClient

async def test():
    embedder = create_embeddings_generator()
    qdrant = QdrantClient(collection_name='nuova_collezione')
    embedding = embedder.generate_single_embedding('query test')
    results = await qdrant.search(query_embedding=embedding, limit=3)
    print(results)
    await qdrant.close()

asyncio.run(test())
"
```

---

## Troubleshooting

### Query restituisce "Mi dispiace, non ho trovato informazioni..."

**Cause possibili:**

1. **Collezione non esiste in Qdrant**
   - Verifica: `curl -H "api-key: $QDRANT_API_KEY" https://nuzantara-qdrant.fly.dev/collections`
   - Fix: Esegui script di ingestion

2. **Query Router non instrada correttamente**
   - Verifica: Controlla logs per vedere quale collezione viene usata
   - Fix: Aggiungi keywords in `query_router.py`

3. **Collezione vuota**
   - Verifica: `/collections/{name}` per vedere `points_count`
   - Fix: Re-ingest documenti

### Verificare Collezioni

```bash
# Lista collezioni
python3 -c "
import asyncio, httpx
from backend.app.core.config import settings

async def list():
    url = settings.qdrant_url + '/collections'
    headers = {'api-key': settings.qdrant_api_key}
    async with httpx.AsyncClient() as c:
        r = await c.get(url, headers=headers)
        for col in r.json()['result']['collections']:
            print(col['name'])

asyncio.run(list())
"
```

### Verificare Conteggio Documenti

```bash
# Stats collezione specifica
python3 -c "
import asyncio, httpx
from backend.app.core.config import settings

async def stats(name):
    url = f'{settings.qdrant_url}/collections/{name}'
    headers = {'api-key': settings.qdrant_api_key}
    async with httpx.AsyncClient() as c:
        r = await c.get(url, headers=headers)
        data = r.json()['result']
        print(f'{name}: {data.get(\"points_count\", 0)} docs')

asyncio.run(stats('tax_genius'))
"
```

---

## Storico Modifiche

| Data | Collezione | Azione | Note |
|------|------------|--------|------|
| 2025-12-31 | `tax_genius` | Creata | 332 chunks da 3 documenti (PPh 21, PPN/VAT) |
| 2025-12-XX | `legal_unified` | Aggiornata | Consolidamento leggi |
| 2025-12-XX | `visa_oracle` | Aggiornata | Nuove regole 2025 |

---

## File Correlati

- `backend/services/routing/query_router.py` - Routing queries → collezioni
- `backend/services/routing/fallback_manager.py` - Fallback chains
- `backend/services/ingestion/collection_manager.py` - Definizioni collezioni
- `backend/core/qdrant_db.py` - Client Qdrant
- `scripts/ingest_tax_genius.py` - Template ingestion script
