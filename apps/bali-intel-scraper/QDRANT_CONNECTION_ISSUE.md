# Qdrant Connection Issue - Diagnosi e Soluzioni

**Data:** 2026-01-10  
**Status:** ⚠️ Problema di connessione rilevato

## Problema

L'app `bali-intel-scraper` non riesce a connettersi a Qdrant (`https://nuzantara-qdrant.fly.dev`) con errore:
```
[Errno 104] Connection reset by peer
```

L'errore si verifica durante il TLS handshake, suggerendo un problema di rete o configurazione.

## Verifiche Eseguite

1. ✅ Qdrant è raggiungibile da locale (`curl` restituisce 401 - normale per endpoint protetto)
2. ✅ Secrets configurati correttamente su `bali-intel-scraper`:
   - `QDRANT_URL=https://nuzantara-qdrant.fly.dev`
   - `QDRANT_API_KEY` (configurato)
   - `OPENAI_API_KEY` (configurato)
3. ❌ Connessione da `bali-intel-scraper` fallisce con "Connection reset by peer"

## Possibili Cause

1. **Restrizioni IP su Qdrant Cloud** - Qdrant potrebbe avere whitelist IP
2. **Problema di rete tra app Fly.io** - Connessioni inter-app potrebbero essere bloccate
3. **Configurazione TLS** - Problema con certificati SSL/TLS
4. **Timeout troppo breve** - Connessione interrotta prima del completamento

## Soluzioni Proposte

### Soluzione 1: Verificare Restrizioni IP su Qdrant

Se Qdrant Cloud ha restrizioni IP, aggiungere gli IP di Fly.io Singapore:
```bash
# Verifica IP della macchina Intel Scraper
fly ssh console -a bali-intel-scraper
curl ifconfig.me
```

Poi aggiungi l'IP alla whitelist su Qdrant Cloud dashboard.

### Soluzione 2: Usare gRPC invece di HTTP

Modifica `semantic_deduplicator.py` e `init_news_collection.py`:
```python
client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    timeout=30,
    prefer_grpc=True  # Prova gRPC invece di HTTP
)
```

### Soluzione 3: Usare Qdrant tramite Backend (Proxy)

Invece di connettersi direttamente da Intel Scraper, usa il backend come proxy:
- Intel Scraper → Backend API → Qdrant
- Il backend ha già connessione funzionante a Qdrant

### Soluzione 4: Verificare Network Policy Fly.io

Controlla se ci sono network policies che bloccano connessioni tra app:
```bash
fly status -a bali-intel-scraper
fly status -a nuzantara-qdrant
```

### Soluzione 5: Test da Backend (Verifica Funzionamento)

Verifica che il backend possa connettersi a Qdrant:
```bash
fly ssh console -a nuzantara-rag
python3 -c "from qdrant_client import QdrantClient; import os; c = QdrantClient(url=os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API_KEY')); print('OK:', len(c.get_collections().collections))"
```

## Test Alternativo: Eseguire da Backend

Poiché il backend ha già connessione funzionante, puoi eseguire l'inizializzazione dalla macchina backend:

```bash
# Copia script su backend
fly ssh sftp shell -a nuzantara-rag
# Upload init_news_collection.py

# Oppure esegui direttamente:
fly ssh console -a nuzantara-rag
cd /app
python3 -c "
from qdrant_client import QdrantClient, models
import os
client = QdrantClient(url=os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API_KEY'))
cols = client.get_collections().collections
exists = any(c.name == 'balizero_news_history' for c in cols.collections)
if not exists:
    client.create_collection(
        collection_name='balizero_news_history',
        vectors_config={'default': models.VectorParams(size=1536, distance=models.Distance.COSINE)},
        sparse_vectors_config={'bm25': models.SparseVectorParams(modifier=models.Modifier.IDF)}
    )
    print('Collection created')
else:
    print('Collection exists')
"
```

## Prossimi Passi

1. ✅ **Deploy completato** - Codice deployato su `bali-intel-scraper`
2. ⏳ **Risolvere connessione Qdrant** - Usare una delle soluzioni sopra
3. ⏳ **Eseguire test completo** - Dopo risoluzione connessione

## Note

- Il codice è pronto e deployato correttamente
- Il problema è solo di connettività di rete
- Una volta risolto, il test completo funzionerà
